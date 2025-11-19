"""Historical message import for populating the message store."""

import logging
import discord
import asyncio
import aiosqlite
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

    def _should_exclude_channel(self, channel: discord.abc.GuildChannel) -> bool:
        """
        Check if a channel should be excluded from import.

        Args:
            channel: Channel to check

        Returns:
            True if channel should be excluded
        """
        names_to_check = [channel.name.lower()]
        parent = getattr(channel, "parent", None)
        if parent:
            names_to_check.append(parent.name.lower())

        # Exclude by name patterns (channel or parent)
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

    async def _gather_text_sources(self) -> List[discord.abc.GuildChannel]:
        """Collect text channels and their threads for import."""
        sources: List[discord.abc.GuildChannel] = []
        seen_ids = set()

        for channel in self.guild.text_channels:
            if self._should_exclude_channel(channel):
                continue

            if channel.id not in seen_ids:
                sources.append(channel)
                seen_ids.add(channel.id)

            # Active threads
            for thread in getattr(channel, "threads", []):
                if thread.id in seen_ids or self._should_exclude_channel(thread):
                    continue
                sources.append(thread)
                seen_ids.add(thread.id)

            # Archived public threads
            try:
                async for thread in channel.archived_threads(limit=None):
                    if thread.id in seen_ids or self._should_exclude_channel(thread):
                        continue
                    sources.append(thread)
                    seen_ids.add(thread.id)
            except discord.Forbidden:
                logger.debug("Forbidden reading archived threads in #%s", channel.name)
            except Exception as exc:
                logger.warning(
                    "Failed to fetch archived threads in #%s: %s",
                    channel.name,
                    exc
                )

            # Archived private threads (requires permissions)
            try:
                async for thread in channel.archived_threads(limit=None, private=True):
                    if thread.id in seen_ids or self._should_exclude_channel(thread):
                        continue
                    sources.append(thread)
                    seen_ids.add(thread.id)
            except discord.Forbidden:
                logger.debug("No access to private archived threads in #%s", channel.name)
            except Exception as exc:
                logger.warning(
                    "Failed to fetch private archived threads in #%s: %s",
                    channel.name,
                    exc
                )

        return sources

    async def _process_channel(
        self,
        channel: discord.abc.GuildChannel
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

        # Mark import as started (before we begin processing)
        await self.message_store.mark_import_started(self.guild.id)
        logger.info(f"Starting historical import for guild: {self.guild.name}")
        await self.message_store.sync_guild_members(self.guild)

        # Use try-finally to ensure cleanup on crash
        total_messages = 0
        channels_processed = 0
        channels_failed = 0
        failed_channels = []
        all_message_counts = defaultdict(int)

        try:
            # Get all text channels
            channels = await self._gather_text_sources()

            total_channels = len(channels)

            for idx, channel in enumerate(channels, 1):
                try:
                    channel_label = (
                        f"{getattr(channel.parent, 'name', '')} › {channel.name}"
                        if isinstance(channel, discord.Thread) and channel.parent
                        else channel.name
                    )

                    # Check permissions
                    permissions = channel.permissions_for(self.guild.me)
                    if not permissions.read_message_history:
                        logger.warning(
                            f"⚠️ No permission to read history in #{channel_label}"
                        )
                        channels_failed += 1
                        failed_channels.append({
                            "name": channel_label,
                            "reason": "No read permission"
                        })
                        continue

                    logger.info(
                        f"📊 Processing channel #{channel_label} ({idx}/{total_channels})"
                    )

                    if progress_callback:
                        await progress_callback(channel_label, idx, total_channels)

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
                    logger.error(f"🔒 Forbidden: Cannot access #{channel_label}")
                    channels_failed += 1
                    failed_channels.append({
                        "name": channel_label,
                        "reason": "Access forbidden"
                    })

                except Exception as e:
                    logger.error(
                        f"❌ CRITICAL: Error processing #{channel_label}: {e}",
                        exc_info=True
                    )
                    channels_failed += 1
                    failed_channels.append({
                        "name": channel_label,
                        "reason": f"Error: {str(e)}"
                    })
                    # IMPORTANT: Continue with other channels even if one fails

            # Flush remaining counts
            if all_message_counts:
                logger.info("💾 Saving final batch...")
                await self._flush_counts(all_message_counts)

            # Refresh member snapshot at the end to capture any late join/leave events
            await self.message_store.sync_guild_members(self.guild)

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

        except Exception as e:
            # Catastrophic failure - something went terribly wrong
            logger.error(
                f"❌ CATASTROPHIC: Import failed with exception: {e}",
                exc_info=True
            )

            # Clean up import state to allow retry
            try:
                # Clear the import_started flag so import can be retried
                await self.message_store.mark_import_completed(
                    guild_id=self.guild.id,
                    total_messages=0  # Mark as 0 to indicate failure
                )
                # But immediately clear it again to allow retry
                async with aiosqlite.connect(self.message_store.db_path) as db:
                    await db.execute(
                        "UPDATE import_metadata SET import_completed = 0, import_start_time = NULL, import_end_time = NULL WHERE guild_id = ?",
                        (self.guild.id,)
                    )
                    await db.commit()
                logger.info("Import state cleared - can retry")
            except Exception as cleanup_error:
                logger.error(f"Failed to clean up import state: {cleanup_error}")

            return {
                "success": False,
                "error": str(e),
                "total_messages": total_messages,
                "channels_processed": channels_processed,
                "channels_failed": channels_failed
            }

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
