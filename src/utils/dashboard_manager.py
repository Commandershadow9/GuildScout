"""Dashboard Manager for Guild Rankings Channel with Commands & Live Activity."""

import asyncio
import logging
from collections import deque
from datetime import timedelta, datetime
from typing import Any, Dict, Optional

import discord
from discord.ext import commands

from src.database.message_store import MessageStore
from src.utils.config import Config
from src.utils.verification_stats import VerificationStats
from src.utils.bot_statistics import BotStatistics
from src.utils.chart_generator import generate_activity_chart
from src.analytics.scorer import Scorer

logger = logging.getLogger("guildscout.dashboard")


class DashboardManager:
    """Manages the combined Commands + Live Activity dashboard in #guild-rankings."""

    def __init__(
        self,
        bot: commands.Bot,
        config: Config,
        message_store: MessageStore,
        update_interval_seconds: int = 300,  # 5 minutes
        idle_gap_seconds: int = 120  # 2 minutes
    ):
        """
        Initialize the dashboard manager.

        Args:
            bot: Discord bot instance
            config: Config instance
            message_store: MessageStore instance
            update_interval_seconds: Max time between updates (default 5 min)
            idle_gap_seconds: Idle time before immediate update (default 2 min)
        """
        self.bot = bot
        self.config = config
        self.message_store = message_store
        self.verification_stats = VerificationStats()
        self.bot_statistics = BotStatistics()
        self._update_interval = max(60, update_interval_seconds)  # Min 1 minute
        self._idle_gap = max(30, idle_gap_seconds)  # Min 30 seconds
        self._dashboard_state: Dict[int, Dict[str, Any]] = {}
        self._dashboard_locks: Dict[int, asyncio.Lock] = {}
        self._protected_messages: set = set()  # Message IDs to skip during cleanup

    def _get_dashboard_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Get the dashboard channel for a guild."""
        channel_id = self.config.dashboard_channel_id
        if not channel_id:
            return None

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            logger.warning(f"Dashboard channel {channel_id} not found or not a text channel")
            return None

        return channel

    def _get_dashboard_state(self, guild_id: int) -> Dict[str, Any]:
        """Return or initialize the dashboard state for a guild."""
        state = self._dashboard_state.get(guild_id)
        if not state:
            state = {
                "entries": deque(maxlen=10),  # Last 10 messages
                "total_tracked": 0,
                "dashboard_message": None,
                "last_update": discord.utils.utcnow(),
                "last_message_time": None
            }
            self._dashboard_state[guild_id] = state
        return state

    async def add_message_event(
        self,
        message: discord.Message,
        channel: discord.abc.Messageable
    ):
        """
        Add a message event to the dashboard.

        Args:
            message: Discord message that was sent
            channel: Channel where message was sent
        """
        guild = message.guild
        if not guild:
            return

        lock = self._dashboard_locks.setdefault(guild.id, asyncio.Lock())
        async with lock:
            state = self._get_dashboard_state(guild.id)
            now = discord.utils.utcnow()

            # Add entry to recent messages
            state["entries"].appendleft({
                "timestamp": now,
                "user_mention": message.author.mention,
                "channel_mention": getattr(channel, "mention", f"#{getattr(channel, 'name', 'unbekannt')}"),
                "jump_url": getattr(message, "jump_url", ""),
                "message_id": message.id
            })

            previous_message_time = state.get("last_message_time")
            state["last_message_time"] = now
            state["total_tracked"] += 1

            # Track message in bot statistics (lifetime + session)
            self.bot_statistics.track_message()

            # Decide if we should update now
            idle_break = (
                previous_message_time is None
                or (now - previous_message_time).total_seconds() >= self._idle_gap
            )
            should_update = (
                state["dashboard_message"] is None  # First message
                or idle_break  # After idle period
                or (now - state["last_update"]).total_seconds() >= self._update_interval  # Max interval
            )

            if should_update:
                await self._update_dashboard(guild, state)

    async def ensure_dashboard_exists(self, guild: discord.Guild):
        """Ensure the dashboard message exists for a guild."""
        lock = self._dashboard_locks.setdefault(guild.id, asyncio.Lock())
        async with lock:
            state = self._get_dashboard_state(guild.id)
            
            # If we already have a message in memory, we are good
            if state["dashboard_message"]:
                return

            channel = self._get_dashboard_channel(guild)
            if not channel:
                return

            # Try to recover message from config
            stored_message_id = self.config.ranking_channel_message_id
            recovered_message = None
            
            if stored_message_id:
                try:
                    recovered_message = await channel.fetch_message(stored_message_id)
                    logger.info(f"Recovered existing dashboard message {stored_message_id}")
                except discord.NotFound:
                    logger.warning(f"Stored dashboard message {stored_message_id} not found, will create new one")
                    self.config.set_ranking_channel_message_id(None)
                except Exception as e:
                    logger.error(f"Error fetching stored message: {e}")

            if recovered_message:
                state["dashboard_message"] = recovered_message
                # Update it immediately to ensure it's fresh
                await self._update_dashboard(guild, state)
            else:
                # Clean up old bot messages before creating new dashboard
                await self._cleanup_old_messages(channel)
                # Create initial dashboard
                await self._update_dashboard(guild, state)

    async def _update_dashboard(self, guild: discord.Guild, state: Dict[str, Any]):
        """Update the combined dashboard + welcome message embed."""
        channel = self._get_dashboard_channel(guild)
        if not channel:
            logger.warning(f"No dashboard channel configured for guild {guild.name}")
            return

        # --- FETCH DATA ---
        # 1. Daily & Hourly Stats (Fetch 60 days for monthly comparison)
        daily_history = await self.message_store.get_daily_history(guild.id, days=60)
        hourly_activity = await self.message_store.get_hourly_activity(guild.id)

        # 2. Trend Calculation
        # A) Daily Trend (Today vs Yesterday)
        now_str = datetime.utcnow().strftime("%Y-%m-%d")
        yesterday_str = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        today_count = daily_history.get(now_str, 0)
        yesterday_count = daily_history.get(yesterday_str, 0)

        daily_trend_emoji = "➖"
        daily_trend_pct = 0.0
        if yesterday_count > 0:
            daily_trend_pct = ((today_count - yesterday_count) / yesterday_count) * 100
            if daily_trend_pct > 5: daily_trend_emoji = "📈"
            elif daily_trend_pct < -5: daily_trend_emoji = "📉"
        
        daily_text = f"{daily_trend_emoji} **{today_count}** heute ({daily_trend_pct:+.0f}%)"

        # Sort dates descending for range calculations
        sorted_dates = sorted(daily_history.keys(), reverse=True)

        # B) Weekly Trend (Last 7 Days vs Previous 7 Days)
        last_7_days_sum = sum([daily_history[d] for d in sorted_dates[:7]])
        prev_7_days_sum = sum([daily_history[d] for d in sorted_dates[7:14]])

        weekly_trend_emoji = "➖"
        weekly_trend_pct = 0.0
        if prev_7_days_sum > 0:
            weekly_trend_pct = ((last_7_days_sum - prev_7_days_sum) / prev_7_days_sum) * 100
            if weekly_trend_pct > 5: weekly_trend_emoji = "⬆️"
            elif weekly_trend_pct < -5: weekly_trend_emoji = "⬇️"
        
        weekly_text = f"{weekly_trend_emoji} **{last_7_days_sum}** / 7 Tage ({weekly_trend_pct:+.0f}%)"

        # C) Monthly Trend (Last 30 Days vs Previous 30 Days)
        last_30_days_sum = sum([daily_history[d] for d in sorted_dates[:30]])
        prev_30_days_sum = sum([daily_history[d] for d in sorted_dates[30:60]])

        monthly_trend_emoji = "➖"
        monthly_trend_pct = 0.0
        if prev_30_days_sum > 0:
            monthly_trend_pct = ((last_30_days_sum - prev_30_days_sum) / prev_30_days_sum) * 100
            if monthly_trend_pct > 5: monthly_trend_emoji = "⬆️"
            elif monthly_trend_pct < -5: monthly_trend_emoji = "⬇️"
        
        monthly_text = f"{monthly_trend_emoji} **{last_30_days_sum}** / 30 Tage ({monthly_trend_pct:+.0f}%)"

        # 3. Prime Time
        prime_time_text = "—"
        if hourly_activity:
            best_hour = max(hourly_activity, key=hourly_activity.get)
            prime_time_text = f"🕒 Prime Time: **{best_hour:02d}:00 UTC**"

        # 4. Chart Generation (Pass only last 14 days for better readability)
        chart_data_14_days = {k: v for k, v in daily_history.items() if k in sorted_dates[:14]}
        chart_file = await self.bot.loop.run_in_executor(
            None, generate_activity_chart, chart_data_14_days, hourly_activity
        )

        # 5. At-Risk Users
        at_risk_text = "Keine Daten."
        if self.config.guild_role_id:
            try:
                from src.analytics.role_scanner import RoleScanner
                scanner = RoleScanner(
                    guild, 
                    exclusion_role_ids=self.config.exclusion_roles,
                    exclusion_user_ids=self.config.exclusion_users
                )
                role_members, _ = await scanner.get_members_by_role_id(self.config.guild_role_id)
                totals = await self.message_store.get_guild_totals(guild.id)
                scorer = Scorer(
                    weight_days=self.config.scoring_weights["days_in_server"],
                    weight_messages=self.config.scoring_weights["message_count"],
                    min_messages=0
                )
                scores = scorer.calculate_scores(role_members, totals)
                
                # FILTER: Ignore users who joined less than 7 days ago
                # New users have low scores by definition (low days_in_server)
                scores = [s for s in scores if s.days_in_server >= 7]

                scores.sort(key=lambda x: x.final_score)
                
                # Show raw bottom 5
                bottom_5 = scores[:5]
                if bottom_5:
                    lines = []
                    for s in bottom_5:
                        lines.append(f"• **{s.display_name}**: {s.final_score:.1f} (Msg: {s.message_count})")
                    at_risk_text = "\n".join(lines)
                else:
                    at_risk_text = "Keine gefährdeten Mitglieder (>7 Tage)."
            except Exception as e:
                logger.warning(f"At-risk calc failed: {e}")
                at_risk_text = "⚠️ Fehler bei Berechnung"

        # --- BUILD EMBED ---
        embed = discord.Embed(
            title="📊 GuildScout Dashboard",
            description=(
                "Zentrale Übersicht für alle GuildScout-Funktionen.\n"
                "Die Bewertung kombiniert **40 %** Tage im Server und **60 %** Nachrichtenaktivität."
            ),
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )

        # 1. Belegung
        from src.analytics.role_scanner import RoleScanner
        role = guild.get_role(self.config.guild_role_id) if self.config.guild_role_id else None
        scanner = RoleScanner(
            guild,
            exclusion_role_ids=self.config.exclusion_roles,
            exclusion_user_ids=self.config.exclusion_users
        )
        member_count = scanner.count_all_excluded_members()
        max_spots = self.config.max_guild_spots
        free_spots = max(max_spots - member_count, 0)

        if role:
            belegung_text = (
                f"Rolle: {role.mention}\n"
                f"Mitglieder: **{member_count}** / {max_spots}\n"
                f"Freie Plätze: **{free_spots}**"
            )
        else:
            belegung_text = "Keine Gildenrolle konfiguriert."
        embed.add_field(name="👥 Aktuelle Belegung", value=belegung_text, inline=True)

        # 2. Aktivitäts-Analyse
        # Get bot stats summary
        try:
            stats = await self.message_store.get_stats(guild.id)
            db_total = stats.get("total_messages", 0)
        except:
            db_total = 0
        
        # Combine Trend, Prime Time and Session Stats
        analysis_text = (
            f"{daily_text}\n"
            f"{weekly_text}\n"
            f"{monthly_text}\n"
            f"{prime_time_text}\n"
            f"Gesamt-DB: **{db_total}**"
        )
        embed.add_field(name="📈 Aktivität", value=analysis_text, inline=True)

        # 3. Wackelkandidaten (Bottom 5)
        embed.add_field(name="⚠️ Wackelkandidaten (Bottom 5)", value=at_risk_text, inline=False)

        # 4. Live Feed (Recent Messages)
        if state["entries"]:
            entries_text = []
            for entry in list(state["entries"])[:3]:
                timestamp_relative = f"<t:{int(entry['timestamp'].timestamp())}:R>"
                link = f"[Link]({entry['jump_url']})" if entry['jump_url'] else "—"
                entries_text.append(
                    f"• {timestamp_relative} {entry['user_mention']} in {entry['channel_mention']} {link}"
                )
            embed.add_field(name="💬 Live Feed", value="\n".join(entries_text), inline=False)

        # 5. Datenqualität
        verification_summary = self.verification_stats.get_summary(guild.id)
        if verification_summary and verification_summary != "Keine Verifikationen durchgeführt":
            embed.add_field(name="🔍 Datenqualität", value=verification_summary, inline=False)

        # 6. Footer/Commands
        commands_text = (
            "**Basis-Commands:**\n"
            "• `/analyze role:@Rolle [days] [top_n]` – Auswertung starten\n"
            "• `/guild-status` – Aktuelle Besetzung & Restplätze\n"
            "• `/my-score [role:@Rolle]` – Eigenen Score prüfen\n\n"
            "**Admin-Werkzeuge:**\n"
            "• `/assign-guild-role ranking_role:@Rolle count:10` – Gildenrolle vergeben\n"
            "• `/set-max-spots value:<Zahl>` – Verfügbare Plätze festlegen\n"
            "• `/cache-stats` & `/cache-clear` – Cache verwalten\n"
            "• `/bot-info` – System- und Laufzeitinfos\n"
            "• `/verify-message-counts` – Stichprobenkontrolle"
        )
        embed.add_field(name="📖 Commands & Tools", value=commands_text, inline=False)

        if chart_file:
            embed.set_image(url="attachment://activity_chart.png")
            logger.debug("Attached activity chart to dashboard")

        embed.set_footer(text=f"GuildScout • Last Update: {datetime.utcnow().strftime('%H:%M')} UTC")

        try:
            # Prepare args
            kwargs = {"embed": embed}
            if chart_file:
                kwargs["file"] = chart_file
                # Note: If we edit, we replace attachments. This is desired.
            
            if state["dashboard_message"]:
                try:
                    await state["dashboard_message"].edit(**kwargs)
                except discord.NotFound:
                    state["dashboard_message"] = None # Trigger re-send
            
            if not state["dashboard_message"]:
                # Create new
                state["dashboard_message"] = await channel.send(**kwargs)
                # Pin & Persist
                try:
                    self.config.set_ranking_channel_message_id(state["dashboard_message"].id)
                    await self._pin_dashboard(channel, state["dashboard_message"])
                except:
                    pass

            state["last_update"] = discord.utils.utcnow()
            logger.info("✅ Dashboard updated with Trends & Charts")

        except Exception as e:
            logger.error(f"Failed to update dashboard: {e}", exc_info=True)

    async def _pin_dashboard(self, channel: discord.TextChannel, message: discord.Message):
        """Pin the dashboard message and unpin all other messages."""
        try:
            # Get all pinned messages
            pinned_messages = await channel.pins()

            # Unpin all messages except the dashboard
            for pinned_msg in pinned_messages:
                if pinned_msg.id != message.id:
                    try:
                        await pinned_msg.unpin()
                        logger.info(f"Unpinned old message {pinned_msg.id} in #{channel.name}")
                    except Exception as unpin_err:
                        logger.warning(f"Could not unpin message {pinned_msg.id}: {unpin_err}")

            # Pin the dashboard
            await message.pin()
            logger.info(f"Pinned dashboard {message.id} in #{channel.name}")
        except discord.Forbidden:
            logger.warning(f"Missing permissions to pin/unpin in #{channel.name}")
        except Exception as pin_err:
            logger.error(f"Failed to manage pins: {pin_err}", exc_info=True)

    async def _cleanup_old_messages(self, channel: discord.TextChannel, max_scan: int = 100):
        """
        Delete old bot messages from the channel to keep it clean.

        Args:
            channel: Channel to clean up
            max_scan: Maximum number of messages to scan (default 100)
        """
        try:
            bot_user_id = self.bot.user.id
            messages_to_delete = []
            unpinned_count = 0

            # First, unpin all old pinned messages from the bot
            try:
                pinned_messages = await channel.pins()
                for pinned_msg in pinned_messages:
                    if pinned_msg.author.id == bot_user_id:
                        # Skip if it's a protected message
                        if pinned_msg.id in self._protected_messages:
                            continue
                            
                        try:
                            await pinned_msg.unpin()
                            unpinned_count += 1
                        except Exception as unpin_err:
                            logger.warning(f"Could not unpin message {pinned_msg.id}: {unpin_err}")
            except Exception as pin_err:
                logger.warning(f"Could not fetch pinned messages: {pin_err}")

            # Fetch messages to delete
            async for message in channel.history(limit=max_scan):
                # Skip protected messages (e.g., import status)
                if message.id in self._protected_messages:
                    continue

                should_delete = False

                # Delete all bot messages
                if message.author.id == bot_user_id:
                    should_delete = True

                # Delete Discord system messages (pin notifications, etc.)
                elif message.type in [
                    discord.MessageType.pins_add,
                    discord.MessageType.channel_name_change,
                    discord.MessageType.channel_icon_change
                ]:
                    should_delete = True

                if should_delete:
                    messages_to_delete.append(message)

            # Delete messages
            if messages_to_delete:
                # Try bulk delete first (only works for messages < 14 days old)
                try:
                    if len(messages_to_delete) > 1:
                        await channel.delete_messages(messages_to_delete)
                        logger.info(f"🧹 Bulk deleted {len(messages_to_delete)} messages in #{channel.name}")
                    else:
                        await messages_to_delete[0].delete()
                        logger.info(f"🧹 Deleted 1 message in #{channel.name}")
                except discord.HTTPException:
                    # Fallback to individual deletion if bulk fails (e.g. messages too old)
                    deleted_count = 0
                    for msg in messages_to_delete:
                        try:
                            await msg.delete()
                            deleted_count += 1
                            await asyncio.sleep(0.5)  # Avoid rate limits
                        except discord.NotFound:
                            pass
                        except Exception as del_err:
                            logger.warning(f"Could not delete message {msg.id}: {del_err}")
                    logger.info(f"🧹 Individually deleted {deleted_count} messages in #{channel.name}")

            # Wait a moment for Discord to sync updates
            if messages_to_delete or unpinned_count > 0:
                await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"Failed to cleanup old messages: {e}", exc_info=True)

    def protect_message(self, message_id: int):
        """Protect a message from cleanup (e.g., import status)."""
        self._protected_messages.add(message_id)
        logger.info(f"Protected message {message_id} from cleanup")

    def unprotect_message(self, message_id: int):
        """Remove message protection."""
        self._protected_messages.discard(message_id)
        logger.info(f"Unprotected message {message_id}")
