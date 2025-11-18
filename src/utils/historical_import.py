"""Historical message import for populating the message store."""

import logging
import discord
import asyncio
from typing import List, Optional, Callable, Dict
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

    async def _process_channel(
        self,
        channel: discord.TextChannel
    ) -> Dict[str, int]:
        """
        Process a single channel with robust rate-limit handling.

        Args:
            channel: Channel to process

        Returns:
            Dictionary with channel statistics
        """
        message_counts = defaultdict(int)
        channel_message_count = 0
        retry_count = 0
        max_wait = 300  # Maximum wait time: 5 minutes

        # Infinite retry loop - we MUST get all messages
        while True:
            try:
                logger.info(f"📖 Reading #{channel.name}...")

                # Iterate through all messages in the channel
                async for message in channel.history(limit=None, oldest_first=False):
                    # Skip bot messages
                    if message.author.bot:
                        continue

                    # Count the message
                    key = (self.guild.id, message.author.id, channel.id)
                    message_counts[key] += 1
                    channel_message_count += 1

                # Success - break retry loop
                logger.info(
                    f"✅ Completed #{channel.name}: {channel_message_count} messages"
                )
                break

            except discord.HTTPException as e:
                # Handle rate limiting - wait as long as needed
                if e.status == 429:
                    # Use Discord's suggested wait time, or exponential backoff
                    retry_after = (
                        e.retry_after if hasattr(e, 'retry_after')
                        else min(2 ** retry_count, max_wait)
                    )
                    retry_count += 1

                    logger.warning(
                        f"⏳ Rate limited on #{channel.name}. "
                        f"Waiting {retry_after:.1f}s (attempt #{retry_count}). "
                        f"Will retry indefinitely to ensure complete data."
                    )
                    await asyncio.sleep(retry_after)
                    # Continue loop - never give up on rate limits
                    continue
                else:
                    logger.error(f"❌ HTTP error in #{channel.name}: {e}")
                    raise  # Re-raise non-rate-limit HTTP errors

            except discord.Forbidden:
                logger.error(f"🔒 Forbidden: Cannot access #{channel.name}")
                raise

            except Exception as e:
                logger.error(
                    f"❌ Unexpected error in #{channel.name}: {e}",
                    exc_info=True
                )
                raise

        return {
            "message_counts": message_counts,
            "channel_message_count": channel_message_count
        }

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
        failed_channels = []

        # Dictionary to batch message counts: (guild_id, user_id, channel_id) -> count
        all_message_counts = defaultdict(int)

        for idx, channel in enumerate(channels, 1):
            try:
                # Check permissions
                if not channel.permissions_for(self.guild.me).read_message_history:
                    logger.warning(
                        f"⚠️ No permission to read history in #{channel.name}"
                    )
                    channels_failed += 1
                    failed_channels.append({
                        "name": channel.name,
                        "reason": "No read permission"
                    })
                    continue

                logger.info(
                    f"📊 Processing channel #{channel.name} ({idx}/{total_channels})"
                )

                if progress_callback:
                    await progress_callback(channel.name, idx, total_channels)

                # Process channel with robust rate-limit handling
                result = await self._process_channel(channel)

                # Add counts from this channel
                for key, count in result["message_counts"].items():
                    all_message_counts[key] += count

                channel_msg_count = result["channel_message_count"]
                total_messages += channel_msg_count
                channels_processed += 1

                # Flush to database every 5000 messages for safety
                if total_messages % 5000 == 0:
                    logger.info(f"💾 Saving progress... ({total_messages} messages)")
                    await self._flush_counts(all_message_counts)
                    all_message_counts.clear()

            except discord.Forbidden:
                logger.error(f"🔒 Forbidden: Cannot access #{channel.name}")
                channels_failed += 1
                failed_channels.append({
                    "name": channel.name,
                    "reason": "Access forbidden"
                })

            except Exception as e:
                logger.error(
                    f"❌ CRITICAL: Error processing #{channel.name}: {e}",
                    exc_info=True
                )
                channels_failed += 1
                failed_channels.append({
                    "name": channel.name,
                    "reason": f"Error: {str(e)}"
                })
                # IMPORTANT: Continue with other channels even if one fails

        # Flush remaining counts
        if all_message_counts:
            logger.info("💾 Saving final batch...")
            await self._flush_counts(all_message_counts)

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
            "total_channels": total_channels,
            "failed_channels": failed_channels
        }

        # Log summary
        logger.info("=" * 60)
        logger.info("📊 IMPORT SUMMARY")
        logger.info("=" * 60)
        logger.info(f"✅ Total messages imported: {total_messages:,}")
        logger.info(f"✅ Channels processed: {channels_processed}/{total_channels}")
        logger.info(f"❌ Channels failed: {channels_failed}")
        if failed_channels:
            logger.warning("Failed channels:")
            for fc in failed_channels:
                logger.warning(f"  - {fc['name']}: {fc['reason']}")
        logger.info("=" * 60)

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
