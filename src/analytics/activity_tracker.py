"""Activity tracker for counting user messages."""

import logging
import asyncio
from typing import Dict, List, Optional, Set, Callable, Awaitable
from datetime import datetime, timedelta, timezone
import discord


logger = logging.getLogger("guildscout.activity_tracker")


class ActivityTracker:
    """Tracks user activity (message counts) across channels."""

    def __init__(
        self,
        guild: discord.Guild,
        excluded_channels: Optional[List[int]] = None,
        excluded_channel_names: Optional[List[str]] = None,
        cache=None,
        message_store=None
    ):
        """
        Initialize the activity tracker.

        Args:
            guild: Discord guild to track activity in
            excluded_channels: List of channel IDs to exclude
            excluded_channel_names: List of channel name patterns to exclude
            cache: Optional MessageCache instance for caching
            message_store: Optional MessageStore instance for persistent tracking
        """
        self.guild = guild
        self.excluded_channels = excluded_channels or []
        self.excluded_channel_names = excluded_channel_names or []
        self.cache = cache
        self.message_store = message_store

    def _should_exclude_channel(self, channel: discord.abc.GuildChannel) -> bool:
        """
        Check if a channel should be excluded from counting.

        Args:
            channel: Channel to check

        Returns:
            True if channel should be excluded
        """
        # Exclude by ID
        if channel.id in self.excluded_channels:
            return True

        names_to_check = [channel.name.lower()]
        parent = getattr(channel, "parent", None)
        if parent:
            names_to_check.append(parent.name.lower())

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

    async def count_user_messages(
        self,
        user: discord.Member,
        days_lookback: Optional[int] = None,
        use_cache: bool = True,
        channel_progress_callback: Optional[
            Callable[[discord.TextChannel, int, int, int], Awaitable[None]]
        ] = None
    ) -> int:
        """
        Count messages for a specific user across all channels.

        Args:
            user: Member to count messages for
            days_lookback: Optional number of days to look back (None = all time)
            use_cache: Whether to use cache (default: True)

        Returns:
            Total message count
        """
        # If message store is available and import is completed, use it for instant results
        if self.message_store and days_lookback is None:
            is_imported = await self.message_store.is_import_completed(self.guild.id)
            if is_imported:
                count = await self.message_store.get_user_total(
                    self.guild.id,
                    user.id,
                    self.excluded_channels
                )
                logger.debug(f"Using message store for {user.name}: {count}")
                return count

        # Try to get from cache first
        if use_cache and self.cache:
            cached_count = await self.cache.get(
                self.guild.id,
                user.id,
                days_lookback,
                self.excluded_channels
            )
            if cached_count is not None:
                logger.debug(f"Using cached count for {user.name}: {cached_count}")
                return cached_count

        # Count messages (cache miss or cache disabled)
        total_messages = 0

        # Calculate cutoff date if specified
        after_date = None
        if days_lookback is not None:
            after_date = datetime.now(timezone.utc) - timedelta(days=days_lookback)

        # Build channel list upfront (includes threads)
        channels_to_scan = await self._gather_message_sources(include_archived_threads=True)

        total_channels = len(channels_to_scan)
        processed_channels = 0

        # Iterate through filtered channels
        for channel in channels_to_scan:
            # Retry loop for rate limiting (same as batch method)
            retry_count = 0
            max_wait = 300
            channel_message_count = 0

            while True:
                try:
                    # Count messages from this user in this channel
                    count = 0
                    async for message in channel.history(
                        limit=None,
                        after=after_date,
                        oldest_first=False
                    ):
                        if message.author.id == user.id:
                            count += 1

                    total_messages += count
                    channel_message_count = count

                    if count > 0:
                        logger.debug(
                            f"User {user.name} has {count} messages in #{channel.name}"
                        )

                    # Success - break retry loop
                    break

                except discord.HTTPException as e:
                    # Handle rate limits and transient errors with retries
                    transient_statuses = {500, 502, 503, 504}
                    if e.status == 429 or e.status in transient_statuses:
                        retry_after = (
                            e.retry_after if hasattr(e, "retry_after")
                            else min(2 ** retry_count, max_wait)
                        )
                        retry_count += 1
                        logger.warning(
                            f"⏳ HTTP {e.status} on #{channel.name} for user {user.name}. "
                            f"Waiting {retry_after:.1f}s (attempt #{retry_count})"
                        )
                        await asyncio.sleep(retry_after)
                        continue  # Retry
                    else:
                        logger.error(f"HTTP error in {channel.name}: {e}")
                        break  # Give up on other HTTP errors

                except discord.Forbidden:
                    logger.warning(f"Access denied to channel: {channel.name}")
                    break

                except Exception as e:
                    logger.error(
                        f"Error counting messages in {channel.name}: {e}"
                    )
                    break

            processed_channels += 1
            if channel_progress_callback:
                try:
                    await channel_progress_callback(
                        channel,
                        processed_channels,
                        total_channels,
                        channel_message_count
                    )
                except Exception as callback_error:
                    logger.debug(f"Channel progress callback failed: {callback_error}")

        # Store in cache
        if use_cache and self.cache:
            await self.cache.set(
                self.guild.id,
                user.id,
                total_messages,
                days_lookback,
                self.excluded_channels
            )
            logger.debug(f"Cached count for {user.name}: {total_messages}")

        return total_messages

    async def _count_channel_for_users(
        self,
        channel: discord.abc.GuildChannel,
        user_ids: Set[int],
        days_lookback: Optional[int] = None
    ) -> Dict[int, int]:
        """
        Count messages for multiple users in a single channel (optimized).

        Args:
            channel: Channel to count messages in
            user_ids: Set of user IDs to count for
            days_lookback: Optional number of days to look back

        Returns:
            Dict mapping user_id -> message count in this channel
        """
        counts = {user_id: 0 for user_id in user_ids}

        # Calculate cutoff date if specified
        after_date = None
        if days_lookback is not None:
            after_date = datetime.now(timezone.utc) - timedelta(days=days_lookback)

        retry_count = 0
        max_wait = 300  # Maximum wait time: 5 minutes

        # Infinite retry loop - we MUST get all messages
        while True:
            try:
                # Single pass through channel history
                async for message in channel.history(
                    limit=None,
                    after=after_date,
                    oldest_first=False
                ):
                    if message.author.id in user_ids:
                        counts[message.author.id] += 1

                # Success - break retry loop
                logger.debug(f"✓ Successfully counted channel {channel.name}")
                break

            except discord.HTTPException as e:
                # Handle rate limiting and transient server errors
                transient_statuses = {500, 502, 503, 504}
                if e.status == 429 or e.status in transient_statuses:
                    # Use Discord's suggested wait time, or exponential backoff
                    retry_after = e.retry_after if hasattr(e, 'retry_after') else min(2 ** retry_count, max_wait)
                    retry_count += 1

                    logger.warning(
                        f"⏳ HTTP {e.status} on channel {channel.name}. "
                        f"Waiting {retry_after:.1f}s (attempt #{retry_count}). "
                        f"Will retry to ensure complete data."
                    )
                    await asyncio.sleep(retry_after)
                    # Continue loop - never give up on rate limits/transients
                    continue
                else:
                    logger.error(f"HTTP error in channel {channel.name}: {e}")
                    break
            except discord.Forbidden:
                logger.warning(f"Access denied to channel: {channel.name}")
                break
            except Exception as e:
                logger.error(f"Error counting messages in {channel.name}: {e}")
                break

        return counts

    async def count_messages_for_users(
        self,
        users: List[discord.Member],
        days_lookback: Optional[int] = None,
        progress_callback: Optional[callable] = None,
        use_cache: bool = True,
        parallel_channels: int = 5
    ) -> tuple[Dict[int, int], Dict]:
        """
        Count messages for multiple users (OPTIMIZED: channel-first algorithm).

        Args:
            users: List of members to count messages for
            days_lookback: Optional number of days to look back
            progress_callback: Optional callback function(current, total)
            use_cache: Whether to use cache (default: True)
            parallel_channels: Number of channels to process in parallel (default: 5)

        Returns:
            Tuple of (message_counts dict, cache_stats dict)
        """
        logger.info(f"Counting messages for {len(users)} users (optimized mode)...")

        # If message store is available and import completed, use it for instant results
        if self.message_store and days_lookback is None:
            is_imported = await self.message_store.is_import_completed(self.guild.id)
            if is_imported:
                logger.info("Using message store for instant counts!")
                message_counts = await self.message_store.get_guild_totals(
                    self.guild.id,
                    self.excluded_channels
                )
                # Filter to only requested users and fill in zeros for users without messages
                user_ids = {user.id for user in users}
                message_counts = {
                    user_id: message_counts.get(user_id, 0)
                    for user_id in user_ids
                }

                cache_stats = {
                    "cache_hits": len(users),
                    "cache_misses": 0,
                    "cache_hit_rate": 100.0,
                    "source": "message_store"
                }

                if progress_callback:
                    await progress_callback(len(users), len(users))

                return message_counts, cache_stats

        message_counts = {}
        total_users = len(users)
        cache_hits = 0
        cache_misses = 0

        # Step 1: Check cache for all users first
        users_needing_count = []
        user_ids_needing_count = set()

        for user in users:
            if use_cache and self.cache:
                cached = await self.cache.get(
                    self.guild.id,
                    user.id,
                    days_lookback,
                    self.excluded_channels
                )
                if cached is not None:
                    message_counts[user.id] = cached
                    cache_hits += 1
                    logger.debug(f"💾 Cache hit for {user.name}: {cached}")
                    continue

            # Need to count this user
            users_needing_count.append(user)
            user_ids_needing_count.add(user.id)
            message_counts[user.id] = 0
            cache_misses += 1

        # Step 2: If all cached, return early
        if not users_needing_count:
            logger.info(f"All {total_users} users found in cache!")
            cache_stats = {
                "cache_hits": cache_hits,
                "cache_misses": 0,
                "cache_hit_rate": 100.0
            }
            return message_counts, cache_stats

        logger.info(
            f"Cache: {cache_hits} hits, {cache_misses} misses. "
            f"Counting {cache_misses} users across channels..."
        )

        # Step 3: Channel-first counting for uncached users
        # Get channels (including threads) to process
        channels_to_process = await self._gather_message_sources(include_archived_threads=True)

        total_channels = len(channels_to_process)
        logger.info(f"Processing {total_channels} channels for {cache_misses} users...")

        # Step 4: Process channels in parallel batches
        processed_channels = 0
        total_batches = (total_channels + parallel_channels - 1) // parallel_channels

        for i in range(0, total_channels, parallel_channels):
            batch_num = (i // parallel_channels) + 1
            batch = channels_to_process[i:i + parallel_channels]

            logger.info(f"📊 Batch {batch_num}/{total_batches}: Processing channels {i+1}-{min(i+parallel_channels, total_channels)} ({len(batch)} channels in parallel)...")

            # Process batch in parallel
            tasks = [
                self._count_channel_for_users(channel, user_ids_needing_count, days_lookback)
                for channel in batch
            ]

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Aggregate results from this batch
            for channel, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error processing channel {channel.name}: {result}")
                    continue

                # Add counts from this channel to total
                for user_id, count in result.items():
                    if count > 0:
                        message_counts[user_id] += count
                        logger.debug(f"User {user_id} has {count} messages in #{channel.name}")

                processed_channels += 1

            logger.info(f"✓ Batch {batch_num}/{total_batches} complete! Processed {processed_channels}/{total_channels} channels so far.")

            # Update progress
            if progress_callback:
                # Estimate progress based on channels processed
                estimated_users_done = cache_hits + int((processed_channels / total_channels) * cache_misses)
                await progress_callback(min(estimated_users_done, total_users), total_users)

        # Step 5: Cache the newly counted users
        if use_cache and self.cache:
            for user in users_needing_count:
                count = message_counts[user.id]
                await self.cache.set(
                    self.guild.id,
                    user.id,
                    count,
                    days_lookback,
                    self.excluded_channels
                )
                logger.debug(f"Cached count for {user.name}: {count}")

        # Step 6: Report results
        cache_stats = {
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "cache_hit_rate": round(cache_hits / total_users * 100, 1) if total_users > 0 else 0
        }

        logger.info(
            f"Message counting completed (optimized) - "
            f"Cache hits: {cache_hits}, Misses: {cache_misses} "
            f"({cache_stats['cache_hit_rate']}% hit rate)"
        )

        # Final progress callback
        if progress_callback:
            await progress_callback(total_users, total_users)

        return message_counts, cache_stats

    async def get_channels_info(self) -> List[Dict]:
        """
        Get information about all text channels.

        Returns:
            List of channel info dictionaries
        """
        channels_info = []

        for channel in self.guild.text_channels:
            excluded = self._should_exclude_channel(channel)
            permissions = channel.permissions_for(self.guild.me)

            channels_info.append({
                "id": channel.id,
                "name": channel.name,
                "excluded": excluded,
                "can_read_history": permissions.read_message_history,
            })

        return channels_info

    def _has_history_permission(self, channel: discord.abc.GuildChannel) -> bool:
        perms = channel.permissions_for(self.guild.me)
        return perms.read_message_history

    async def _gather_message_sources(
        self,
        include_archived_threads: bool = False
    ) -> List[discord.abc.GuildChannel]:
        """Collect channels and threads that should be scanned."""
        sources: List[discord.abc.GuildChannel] = []
        seen_ids = set()

        for channel in self.guild.text_channels:
            if self._should_exclude_channel(channel):
                continue

            if not self._has_history_permission(channel):
                logger.warning(f"No permission to read history in channel: {channel.name}")
                continue

            if channel.id not in seen_ids:
                sources.append(channel)
                seen_ids.add(channel.id)

            # Active threads
            for thread in getattr(channel, "threads", []):
                if thread.id in seen_ids:
                    continue
                if self._should_exclude_channel(thread):
                    continue
                if not self._has_history_permission(thread):
                    logger.debug("No permission to read history in thread %s", thread.name)
                    continue
                sources.append(thread)
                seen_ids.add(thread.id)

            if include_archived_threads:
                for private in (False, True):
                    try:
                        async for thread in channel.archived_threads(limit=None, private=private):
                            if thread.id in seen_ids:
                                continue
                            if self._should_exclude_channel(thread):
                                continue
                            if not self._has_history_permission(thread):
                                logger.debug("No permission to read archived thread %s", thread.name)
                                continue
                            sources.append(thread)
                            seen_ids.add(thread.id)
                    except discord.Forbidden:
                        logger.debug(
                            "Forbidden fetching %s archived threads in #%s",
                            "private" if private else "public",
                            channel.name
                        )
                    except Exception as exc:
                        logger.warning(
                            "Failed to fetch %s archived threads in #%s: %s",
                            "private" if private else "public",
                            channel.name,
                            exc
                        )

        return sources
