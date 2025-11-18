"""Historical message import for populating the message store."""

import logging
import discord
from typing import List, Optional, Callable
from collections import defaultdict

from src.database.message_store import MessageStore


logger = logging.getLogger("guildscout.historical_import")


class HistoricalImporter:
    """Imports historical messages into the message store."""

    def __init__(
        self,
        guild: discord.Guild,
        message_store: MessageStore,
        excluded_channel_names: Optional[List[str]] = None
    ):
        """
        Initialize the historical importer.

        Args:
            guild: Discord guild to import from
            message_store: MessageStore instance
            excluded_channel_names: List of channel name patterns to exclude
        """
        self.guild = guild
        self.message_store = message_store
        self.excluded_channel_names = excluded_channel_names or []

    def _should_exclude_channel(self, channel: discord.TextChannel) -> bool:
        """
        Check if a channel should be excluded from import.

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

    async def import_guild_history(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> dict:
        """
        Import all historical messages for a guild.

        Args:
            progress_callback: Optional callback function(channel_name, current, total)

        Returns:
            Dictionary with import statistics
        """
        # Check if import already completed
        if await self.message_store.is_import_completed(self.guild.id):
            logger.warning(f"Import already completed for guild {self.guild.id}")
            return {
                "success": False,
                "error": "Import already completed. Use reset_guild() to re-import."
            }

        logger.info(f"Starting historical import for guild: {self.guild.name}")

        # Get all text channels
        channels = [
            channel for channel in self.guild.text_channels
            if not self._should_exclude_channel(channel)
        ]

        total_channels = len(channels)
        total_messages = 0
        channels_processed = 0
        channels_failed = 0

        # Dictionary to batch message counts: (guild_id, user_id, channel_id) -> count
        message_counts = defaultdict(int)

        for idx, channel in enumerate(channels, 1):
            try:
                # Check permissions
                if not channel.permissions_for(self.guild.me).read_message_history:
                    logger.warning(f"No permission to read history in #{channel.name}")
                    channels_failed += 1
                    continue

                logger.info(f"Processing channel #{channel.name} ({idx}/{total_channels})")

                if progress_callback:
                    await progress_callback(channel.name, idx, total_channels)

                channel_message_count = 0

                # Iterate through all messages in the channel
                async for message in channel.history(limit=None, oldest_first=False):
                    # Skip bot messages
                    if message.author.bot:
                        continue

                    # Count the message
                    key = (self.guild.id, message.author.id, channel.id)
                    message_counts[key] += 1
                    channel_message_count += 1
                    total_messages += 1

                    # Batch insert every 1000 messages to improve performance
                    if total_messages % 1000 == 0:
                        await self._flush_counts(message_counts)
                        message_counts.clear()
                        logger.debug(f"Processed {total_messages} messages...")

                logger.info(
                    f"Completed #{channel.name}: {channel_message_count} messages"
                )
                channels_processed += 1

            except discord.Forbidden:
                logger.error(f"Forbidden: Cannot access #{channel.name}")
                channels_failed += 1
            except Exception as e:
                logger.error(f"Error processing #{channel.name}: {e}", exc_info=True)
                channels_failed += 1

        # Flush remaining counts
        if message_counts:
            await self._flush_counts(message_counts)

        # Mark import as completed
        await self.message_store.mark_import_completed(
            guild_id=self.guild.id,
            total_messages=total_messages
        )

        result = {
            "success": True,
            "total_messages": total_messages,
            "channels_processed": channels_processed,
            "channels_failed": channels_failed,
            "total_channels": total_channels
        }

        logger.info(f"Import completed: {result}")
        return result

    async def _flush_counts(self, message_counts: dict):
        """
        Flush batched message counts to database.

        Args:
            message_counts: Dictionary of (guild_id, user_id, channel_id) -> count
        """
        for (guild_id, user_id, channel_id), count in message_counts.items():
            await self.message_store.increment_message(
                guild_id=guild_id,
                user_id=user_id,
                channel_id=channel_id,
                count=count
            )
