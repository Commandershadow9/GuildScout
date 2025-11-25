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
        self._update_interval = max(60, update_interval_seconds)  # Min 1 minute
        self._idle_gap = max(30, idle_gap_seconds)  # Min 30 seconds
        self._dashboard_state: Dict[int, Dict[str, Any]] = {}
        self._dashboard_locks: Dict[int, asyncio.Lock] = {}

    def _get_ranking_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Get the ranking channel for a guild."""
        channel_id = self.config.ranking_channel_id
        if not channel_id:
            return None

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            logger.warning(f"Ranking channel {channel_id} not found or not a text channel")
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
        """Update the dashboard embed with current info."""
        channel = self._get_ranking_channel(guild)
        if not channel:
            logger.warning(f"No ranking channel configured for guild {guild.name}")
            return

        # Build embed
        embed = discord.Embed(
            title="📋 GuildScout Dashboard",
            description="",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )

        # Commands Section
        commands_text = (
            "**📖 Available Commands:**\n"
            "• `/analyze` - Rank users by role\n"
            "• `/guild-status` - View guild members  \n"
            "• `/my-score` - Check your ranking\n"
            "• `/verify-message-counts` - Verify data accuracy"
        )
        embed.add_field(name="Commands", value=commands_text, inline=False)

        # Live Activity Section
        try:
            stats = await self.message_store.get_stats(guild.id)
            db_total = stats.get("total_messages", 0)
        except Exception as e:
            logger.warning(f"Could not load stats: {e}")
            db_total = 0

        activity_text = (
            f"**📊 Database Total:** {db_total:,} messages\n"
            f"**🔄 Tracked Since Restart:** {state['total_tracked']} messages\n"
            f"**🕐 Last Update:** <t:{int(discord.utils.utcnow().timestamp())}:R>"
        )
        embed.add_field(name="Live Activity", value=activity_text, inline=False)

        # Recent Messages Section
        if state["entries"]:
            entries_text = []
            for entry in list(state["entries"])[:3]:  # Show only last 3
                timestamp_relative = f"<t:{int(entry['timestamp'].timestamp())}:R>"
                link = f"[Jump]({entry['jump_url']})" if entry['jump_url'] else "—"
                entries_text.append(
                    f"• {timestamp_relative} {entry['user_mention']} in {entry['channel_mention']} {link}"
                )
            recent_text = "\n".join(entries_text)
        else:
            recent_text = "*No messages tracked yet.*"

        embed.add_field(name="Recent Messages", value=recent_text, inline=False)
        embed.set_footer(text="Updates automatically • Live tracking active")

        try:
            if state["dashboard_message"]:
                # Update existing message
                await state["dashboard_message"].edit(embed=embed)
            else:
                # Create new message
                state["dashboard_message"] = await channel.send(embed=embed)
                logger.info(f"✅ Created dashboard in #{channel.name} for {guild.name}")

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

            # Create initial dashboard
            await self._update_dashboard(guild, state)
