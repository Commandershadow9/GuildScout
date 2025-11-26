"""Dashboard Manager for Guild Rankings Channel with Commands & Live Activity."""

import asyncio
import logging
from collections import deque
from datetime import timedelta
from typing import Any, Dict, Optional

import discord
from discord.ext import commands

from src.database.message_store import MessageStore
from src.utils.config import Config
from src.utils.verification_stats import VerificationStats
from src.utils.bot_statistics import BotStatistics

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

    async def _update_dashboard(self, guild: discord.Guild, state: Dict[str, Any]):
        """Update the combined dashboard + welcome message embed."""
        channel = self._get_dashboard_channel(guild)
        if not channel:
            logger.warning(f"No dashboard channel configured for guild {guild.name}")
            return

        # Build comprehensive embed combining dashboard + welcome content
        embed = discord.Embed(
            title="📊 GuildScout Dashboard",
            description=(
                "Zentrale Übersicht für alle GuildScout-Funktionen und Auswertungen.\n"
                "Die Bewertung kombiniert **40 %** Tage im Server und **60 %** Nachrichtenaktivität."
            ),
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )

        # ========== AKTUELLE BELEGUNG ==========
        from ..analytics import RoleScanner
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
            belegung_text = "Keine Gildenrolle im Config-File hinterlegt (`guild_role_id`)."

        embed.add_field(name="Aktuelle Belegung", value=belegung_text, inline=False)

        # ========== LIVE ACTIVITY ==========
        try:
            stats = await self.message_store.get_stats(guild.id)
            db_total = stats.get("total_messages", 0)
        except Exception as e:
            logger.warning(f"Could not load stats: {e}")
            db_total = 0

        # Get bot statistics (session + lifetime)
        bot_stats_summary = self.bot_statistics.get_dashboard_summary()

        activity_text = (
            f"**📊 Database Total:** {db_total:,} messages\n"
            f"{bot_stats_summary}\n"
            f"**🕐 Last Update:** <t:{int(discord.utils.utcnow().timestamp())}:R>"
        )

        # Recent Messages Section
        if state["entries"]:
            entries_text = []
            for entry in list(state["entries"])[:3]:  # Show only last 3
                timestamp_relative = f"<t:{int(entry['timestamp'].timestamp())}:R>"
                link = f"[Jump]({entry['jump_url']})" if entry['jump_url'] else "—"
                entries_text.append(
                    f"• {timestamp_relative} {entry['user_mention']} in {entry['channel_mention']} {link}"
                )
            activity_text += "\n\n**Letzte Nachrichten:**\n" + "\n".join(entries_text)

        embed.add_field(name="Live Activity", value=activity_text, inline=False)

        # ========== VERIFIKATIONEN ==========
        verification_summary = self.verification_stats.get_summary(guild.id)
        if verification_summary and verification_summary != "Keine Verifikationen durchgeführt":
            embed.add_field(name="🔍 Datenqualität", value=verification_summary, inline=False)

        # ========== COMMANDS ==========
        commands_text = (
            "**Basis-Commands:**\n"
            "• `/analyze role:@Rolle [days] [top_n]` – Auswertung starten\n"
            "• `/guild-status` – Aktuelle Besetzung & Restplätze\n"
            "• `/my-score [role:@Rolle]` – Eigenen Score prüfen\n\n"
            "**Admin-Werkzeuge:**\n"
            "• `/assign-guild-role ranking_role:@Rolle count:10` – Gildenrolle vergeben\n"
            "• `/set-max-spots value:<Zahl>` – Verfügbare Plätze festlegen\n"
            "• `/cache-stats` & `/cache-clear` – Cache verwalten\n"
            "• `/bot-info` – System- und Laufzeitinfos"
        )
        embed.add_field(name="📖 Commands", value=commands_text, inline=False)

        # ========== DATEN & TRACKING ==========
        daten_text = (
            "• `/import-status` – Import-Status prüfen\n"
            "• `/import-messages [force]` – Historische Nachrichten einlesen\n"
            "• `/message-store-stats` – Datenbankgröße prüfen\n"
            "• `/verify-message-counts [sample_size]` – Stichprobenkontrolle"
        )
        embed.add_field(name="📂 Daten & Tracking", value=daten_text, inline=False)

        embed.set_footer(text="GuildScout – faire und transparente Auswahl • Updates automatically")

        try:
            if state["dashboard_message"]:
                # Update existing message
                await state["dashboard_message"].edit(embed=embed)
            else:
                # Create new message and pin it
                state["dashboard_message"] = await channel.send(embed=embed)
                await self._pin_dashboard(channel, state["dashboard_message"])
                logger.info(f"✅ Created combined dashboard in #{channel.name} for {guild.name}")

            state["last_update"] = discord.utils.utcnow()
        except Exception as e:
            logger.error(f"Failed to update dashboard: {e}", exc_info=True)

    async def ensure_dashboard_exists(self, guild: discord.Guild):
        """Ensure the dashboard message exists for a guild."""
        lock = self._dashboard_locks.setdefault(guild.id, asyncio.Lock())
        async with lock:
            state = self._get_dashboard_state(guild.id)
            if state["dashboard_message"]:
                return  # Already exists

            channel = self._get_dashboard_channel(guild)
            if channel:
                # Clean up old bot messages before creating new dashboard
                await self._cleanup_old_messages(channel)

            # Create initial dashboard
            await self._update_dashboard(guild, state)

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

    async def _cleanup_old_messages(self, channel: discord.TextChannel, max_scan: int = 500):
        """
        Delete old bot messages from the channel to keep it clean.

        Args:
            channel: Channel to clean up
            max_scan: Maximum number of messages to scan (default 500)
        """
        try:
            bot_user_id = self.bot.user.id
            deleted_count = 0
            unpinned_count = 0

            # First, unpin all old pinned messages from the bot
            try:
                pinned_messages = await channel.pins()
                for pinned_msg in pinned_messages:
                    if pinned_msg.author.id == bot_user_id:
                        try:
                            await pinned_msg.unpin()
                            unpinned_count += 1
                            logger.info(f"Unpinned old bot message {pinned_msg.id} in #{channel.name}")
                        except Exception as unpin_err:
                            logger.warning(f"Could not unpin message {pinned_msg.id}: {unpin_err}")
            except Exception as pin_err:
                logger.warning(f"Could not fetch pinned messages: {pin_err}")

            # Fetch messages and delete all old bot messages + system messages
            async for message in channel.history(limit=max_scan):
                # Skip protected messages (e.g., import status)
                if message.id in self._protected_messages:
                    continue

                should_delete = False

                # Delete all bot messages (including previously pinned ones)
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
                    try:
                        await message.delete()
                        deleted_count += 1
                    except discord.NotFound:
                        pass  # Already deleted
                    except Exception as del_err:
                        logger.warning(f"Could not delete message {message.id}: {del_err}")

            if deleted_count > 0 or unpinned_count > 0:
                logger.info(f"🧹 Cleaned up {deleted_count} messages and unpinned {unpinned_count} in #{channel.name}")
        except Exception as e:
            logger.error(f"Failed to cleanup old messages: {e}", exc_info=True)

    async def cleanup_log_channel(self, guild: discord.Guild):
        """Clean up old bot messages in the log channel."""
        log_channel_id = self.config.log_channel_id
        if not log_channel_id:
            return

        channel = guild.get_channel(log_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        # Clean up old messages in log channel (scan more messages - 500)
        await self._cleanup_old_messages(channel, max_scan=500)

    def protect_message(self, message_id: int):
        """Protect a message from cleanup (e.g., import status)."""
        self._protected_messages.add(message_id)
        logger.info(f"Protected message {message_id} from cleanup")

    def unprotect_message(self, message_id: int):
        """Remove message protection."""
        self._protected_messages.discard(message_id)
        logger.info(f"Unprotected message {message_id}")
