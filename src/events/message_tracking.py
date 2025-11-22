"""Event handler for real-time message tracking."""

import asyncio
import logging
from collections import deque
from datetime import timedelta
from typing import Any, Dict, List, Optional

import discord
from discord.ext import commands

from src.database.message_store import MessageStore
from src.utils.log_helper import DiscordLogger


logger = logging.getLogger("guildscout.message_tracking")


class MessageTracker(commands.Cog):
    """Tracks messages in real-time for accurate statistics."""

    def __init__(
        self,
        bot: commands.Bot,
        message_store: MessageStore,
        excluded_channel_names: Optional[List[str]] = None,
        discord_logger: Optional[DiscordLogger] = None,
        live_log_interval_seconds: Optional[int] = None,
        live_log_idle_gap_seconds: Optional[int] = None
    ):
        """
        Initialize the message tracker.

        Args:
            bot: Discord bot instance
            message_store: MessageStore instance
            excluded_channel_names: List of channel name patterns to exclude
        """
        self.bot = bot
        self.message_store = message_store
        self.excluded_channel_names = excluded_channel_names or []
        self.discord_logger = discord_logger
        self._live_log_state: Dict[int, Dict[str, Any]] = {}
        self._live_log_locks: Dict[int, asyncio.Lock] = {}
        interval = live_log_interval_seconds or 3600
        idle_gap = live_log_idle_gap_seconds or 180
        self._live_log_update_interval = max(5, interval)
        self._live_log_interval_label = self._format_interval(self._live_log_update_interval)
        self._live_log_idle_gap = max(10, idle_gap)

    @staticmethod
    def _format_interval(seconds: int) -> str:
        """Return a human readable version of the update interval."""
        if seconds >= 86400:
            days = seconds / 86400
            return f"{days:.1f} Tage" if days % 1 else f"{int(days)} Tage"
        if seconds >= 3600:
            hours = seconds / 3600
            return f"{hours:.1f} Stunden" if hours % 1 else f"{int(hours)} Stunden"
        if seconds >= 60:
            minutes = seconds / 60
            return f"{minutes:.1f} Minuten" if minutes % 1 else f"{int(minutes)} Minuten"
        return f"{seconds} Sekunden"

    def _should_exclude_channel(self, channel: discord.abc.GuildChannel) -> bool:
        """
        Check if a channel should be excluded from tracking.

        Args:
            channel: Channel to check

        Returns:
            True if channel should be excluded
        """
        names_to_check = [channel.name.lower()]
        parent = getattr(channel, "parent", None)
        if parent:
            names_to_check.append(parent.name.lower())

        # Exclude by name patterns
        for pattern in self.excluded_channel_names:
            pattern_lower = pattern.lower()
            if any(pattern_lower in name for name in names_to_check):
                return True

        # Exclude NSFW channels
        if hasattr(channel, 'nsfw') and channel.nsfw:
            return True
        if parent and getattr(parent, "nsfw", False):
            return True

        return False

    def _get_live_log_state(self, guild_id: int) -> Dict[str, Any]:
        """Return or initialize the live-tracking state for a guild."""
        state = self._live_log_state.get(guild_id)
        if not state:
            state = {
                "entries": deque(maxlen=10),
                "total": 0,
                "log_message": None,
                "last_update": discord.utils.utcnow(),
                "last_message_time": None
            }
            self._live_log_state[guild_id] = state
        return state

    async def _update_live_log_message(
        self,
        guild: discord.Guild,
        state: Dict[str, Any]
    ):
        """Send or update the rolling live-tracking embed."""
        if not self.discord_logger:
            return

        entries_text = []
        for entry in state["entries"]:
            timestamp = entry["timestamp"].strftime("%H:%M:%S UTC")
            link = (
                f"[Nachricht öffnen]({entry['jump_url']})"
                if entry["jump_url"]
                else f"ID: {entry['message_id']}"
            )
            entries_text.append(
                f"• `{timestamp}` {entry['user_mention']} in "
                f"{entry['channel_label']} – {link}"
            )

        entries_block = "\n".join(entries_text) if entries_text else "Noch keine Einträge."
        db_total_text = ""
        try:
            stats = await self.message_store.get_stats(guild.id)
            db_total = stats.get("total_messages", 0)
            db_total_text = f"**Datenbank gesamt:** {db_total:,} Nachrichten\n"
        except Exception as stats_exc:
            logger.warning("Could not load message store stats for live log: %s", stats_exc)

        description = (
            "Neue Nachrichten werden live gezählt und sofort im Message Store gespeichert.\n"
            f"**Update-Intervall:** alle {self._live_log_interval_label}\n"
            f"{db_total_text}"
            f"**Seit letztem Neustart erfasst:** {state['total']} Nachrichten\n\n"
            "**Letzte Einträge:**\n"
            f"{entries_block}"
        )

        log_message = await self.discord_logger.send(
            guild,
            "🟢 Live-Tracking aktiv",
            description,
            status=f"{state['total']} Nachrichten",
            color=discord.Color.green(),
            message=state["log_message"]
        )
        if log_message:
            state["log_message"] = log_message
            state["last_update"] = discord.utils.utcnow()

    async def _ensure_live_log_placeholder(self, guild: discord.Guild):
        """Ensure there is at least one visible live-tracking message per guild."""
        if not self.discord_logger:
            return

        lock = self._live_log_locks.setdefault(guild.id, asyncio.Lock())
        async with lock:
            state = self._get_live_log_state(guild.id)
            if state["log_message"]:
                return
            await self._update_live_log_message(guild, state)
            # Allow immediate refresh on the next real message
            state["last_update"] = (
                discord.utils.utcnow() - timedelta(seconds=self._live_log_update_interval)
            )
            self._live_log_initialized[guild.id] = True

    async def _log_live_tracking_to_discord(
        self,
        message: discord.Message,
        channel: discord.abc.Messageable
    ):
        """
        Mirror live tracking activity into the configured Discord log channel.
        """
        if not self.discord_logger:
            return

        guild = message.guild
        if not guild:
            return

        lock = self._live_log_locks.setdefault(guild.id, asyncio.Lock())
        async with lock:
            state = self._get_live_log_state(guild.id)

            now = discord.utils.utcnow()

            state["entries"].appendleft(
                {
                    "timestamp": now,
                    "user_mention": message.author.mention,
                    "channel_label": getattr(channel, "mention", f"#{getattr(channel, 'name', 'unbekannt')}"),
                    "jump_url": getattr(message, "jump_url", ""),
                    "message_id": message.id
                }
            )
            previous_message_time = state.get("last_message_time")
            state["last_message_time"] = now
            state["total"] += 1

            idle_break = (
                previous_message_time is None
                or (now - previous_message_time).total_seconds() >= self._live_log_idle_gap
            )
            should_post = (
                state["log_message"] is None
                or idle_break
                or (now - state["last_update"]).total_seconds() >= self._live_log_update_interval
            )
            if not should_post:
                return

            await self._update_live_log_message(guild, state)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Track a message when it's sent.

        Args:
            message: Message object
        """
        # Ignore bot messages
        if message.author.bot:
            return

        # Only track guild messages
        if not message.guild:
            return

        # Check if channel should be excluded (includes threads)
        channel = message.channel
        if isinstance(channel, (discord.TextChannel, discord.Thread)):
            if self._should_exclude_channel(channel):
                logger.debug(f"Excluded channel: {channel.name}")
                return

        # Check if import is currently running
        try:
            import_running = await self.message_store.is_import_running(message.guild.id)

            if import_running:
                # Import is running - only track messages created AFTER import started
                import_start_time = await self.message_store.get_import_start_time(
                    message.guild.id
                )

                if import_start_time:
                    # Make sure both timestamps are timezone-aware for comparison
                    message_time = message.created_at
                    if message_time.tzinfo is None:
                        from datetime import timezone
                        message_time = message_time.replace(tzinfo=timezone.utc)

                    if message_time < import_start_time:
                        # Message was created BEFORE import started
                        # Skip tracking - historical import will handle it
                        logger.debug(
                            f"Skipping message from {message.author.name} "
                            f"(created before import started)"
                        )
                        return
                    else:
                        # Message was created AFTER import started
                        # Track it - historical import won't see it
                        logger.debug(
                            f"Tracking new message from {message.author.name} "
                            f"during active import"
                        )

            # Track the message
            await self.message_store.upsert_member(message.author)
            await self.message_store.increment_message(
                guild_id=message.guild.id,
                user_id=message.author.id,
                channel_id=channel.id,
                count=1,
                message_date=message.created_at
            )
            logger.debug(
                f"Tracked message from {message.author.name} in {channel.name}"
            )
            logger.info(
                "🟢 Live-Tracking | Guild: %s (%d) | Channel: #%s (%d) | User: %s (%d) | Message ID: %d",
                message.guild.name,
                message.guild.id,
                getattr(channel, 'name', '???'),
                channel.id,
                message.author.display_name or message.author.name,
                message.author.id,
                message.id
            )
            await self._log_live_tracking_to_discord(message, channel)
        except Exception as e:
            logger.error(f"Failed to track message: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Reduce counts when a message is deleted."""
        try:
            # Only adjust if we have enough context
            if not message.guild or not message.author or message.author.bot:
                return

            channel = message.channel
            if isinstance(channel, (discord.TextChannel, discord.Thread)):
                if self._should_exclude_channel(channel):
                    return

            await self.message_store.adjust_message_count(
                guild_id=message.guild.id,
                user_id=message.author.id,
                channel_id=channel.id,
                delta=-1
            )
            logger.debug(
                "Adjusted count for deleted message from %s in %s",
                getattr(message.author, "name", "unknown"),
                getattr(channel, "name", "unknown")
            )
        except Exception as exc:
            logger.error("Failed to handle message deletion: %s", exc, exc_info=True)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: List[discord.Message]):
        """Handle bulk deletions efficiently."""
        try:
            aggregate = {}
            for msg in messages:
                if not msg.guild or not getattr(msg, "author", None) or msg.author.bot:
                    continue
                channel = msg.channel
                if isinstance(channel, (discord.TextChannel, discord.Thread)):
                    if self._should_exclude_channel(channel):
                        continue
                key = (msg.guild.id, msg.author.id, channel.id)
                aggregate[key] = aggregate.get(key, 0) + 1

            for (guild_id, user_id, channel_id), count in aggregate.items():
                await self.message_store.adjust_message_count(
                    guild_id=guild_id,
                    user_id=user_id,
                    channel_id=channel_id,
                    delta=-count
                )
            if aggregate:
                logger.debug("Adjusted counts for %d deleted messages (bulk)", sum(aggregate.values()))
        except Exception as exc:
            logger.error("Failed to handle bulk message deletion: %s", exc, exc_info=True)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Purge counts when a channel is deleted."""
        try:
            removed = await self.message_store.delete_channel_counts(
                channel.guild.id,
                channel.id
            )
            if removed:
                logger.info(
                    "Removed %d rows for deleted channel #%s (%d)",
                    removed,
                    getattr(channel, "name", "unknown"),
                    channel.id
                )
        except Exception as exc:
            logger.error("Failed to purge deleted channel %s: %s", getattr(channel, "name", "unknown"), exc, exc_info=True)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread):
        """Purge counts when a thread is deleted."""
        try:
            removed = await self.message_store.delete_channel_counts(
                thread.guild.id,
                thread.id
            )
            if removed:
                logger.info(
                    "Removed %d rows for deleted thread #%s (%d)",
                    removed,
                    getattr(thread, "name", "unknown"),
                    thread.id
                )
        except Exception as exc:
            logger.error("Failed to purge deleted thread %s: %s", getattr(thread, "name", "unknown"), exc, exc_info=True)

    @commands.Cog.listener()
    async def on_ready(self):
        """Ensure the live-tracking status is visible when the bot connects."""
        for guild in self.bot.guilds:
            try:
                await self._ensure_live_log_placeholder(guild)
            except Exception as exc:
                logger.warning("Failed to initialize live-tracking log for %s: %s", guild.name, exc)


async def setup(bot: commands.Bot, config, message_store: MessageStore):
    """
    Setup the message tracking event handler.

    Args:
        bot: Discord bot instance
        config: Configuration object
        message_store: MessageStore instance
    """
    excluded_channel_names = getattr(
        config,
        'excluded_channel_names',
        ['nsfw', 'bot-spam']
    )
    discord_logger = DiscordLogger(bot, config)
    live_tracking_interval = getattr(
        config,
        'live_tracking_interval_seconds',
        3600
    )
    live_tracking_idle_gap = getattr(
        config,
        'live_tracking_idle_gap_seconds',
        180
    )

    # Add the cog to the bot
    await bot.add_cog(
        MessageTracker(
            bot,
            message_store,
            excluded_channel_names=excluded_channel_names,
            discord_logger=discord_logger,
            live_log_interval_seconds=live_tracking_interval,
            live_log_idle_gap_seconds=live_tracking_idle_gap
        )
    )
    logger.info("Message tracking cog loaded")
