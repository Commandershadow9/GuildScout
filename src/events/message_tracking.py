"""Event handler for real-time message tracking."""

import logging
import discord
from discord.ext import commands
from typing import List, Optional

from src.database.message_store import MessageStore


logger = logging.getLogger("guildscout.message_tracking")


class MessageTracker:
    """Tracks messages in real-time for accurate statistics."""

    def __init__(
        self,
        bot: commands.Bot,
        message_store: MessageStore,
        excluded_channel_names: Optional[List[str]] = None
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

    def _should_exclude_channel(self, channel: discord.TextChannel) -> bool:
        """
        Check if a channel should be excluded from tracking.

        Args:
            channel: Channel to check

        Returns:
            True if channel should be excluded
        """
        # Exclude by name patterns
        channel_name_lower = channel.name.lower()
        for pattern in self.excluded_channel_names:
            if pattern.lower() in channel_name_lower:
                return True

        # Exclude NSFW channels
        if hasattr(channel, 'nsfw') and channel.nsfw:
            return True

        return False

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

        # Check if channel should be excluded
        if isinstance(message.channel, discord.TextChannel):
            if self._should_exclude_channel(message.channel):
                logger.debug(f"Excluded channel: {message.channel.name}")
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
            await self.message_store.increment_message(
                guild_id=message.guild.id,
                user_id=message.author.id,
                channel_id=message.channel.id,
                count=1,
                message_date=message.created_at
            )
            logger.debug(
                f"Tracked message from {message.author.name} in {message.channel.name}"
            )
        except Exception as e:
            logger.error(f"Failed to track message: {e}", exc_info=True)


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

    tracker = MessageTracker(bot, message_store, excluded_channel_names)

    # Register the on_message event
    @bot.event
    async def on_message(message: discord.Message):
        await tracker.on_message(message)
        # Important: Process commands after tracking
        await bot.process_commands(message)

    logger.info("Message tracking event handler registered")
