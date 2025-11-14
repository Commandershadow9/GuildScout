"""Activity tracker for counting user messages."""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import discord


logger = logging.getLogger("guildscout.activity_tracker")


class ActivityTracker:
    """Tracks user activity (message counts) across channels."""

    def __init__(
        self,
        guild: discord.Guild,
        excluded_channels: Optional[List[int]] = None,
        excluded_channel_names: Optional[List[str]] = None,
        cache=None
    ):
        """
        Initialize the activity tracker.

        Args:
            guild: Discord guild to track activity in
            excluded_channels: List of channel IDs to exclude
            excluded_channel_names: List of channel name patterns to exclude
            cache: Optional MessageCache instance for caching
        """
        self.guild = guild
        self.excluded_channels = excluded_channels or []
        self.excluded_channel_names = excluded_channel_names or []
        self.cache = cache

    def _should_exclude_channel(self, channel: discord.TextChannel) -> bool:
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

        # Exclude by name patterns
        channel_name_lower = channel.name.lower()
        for pattern in self.excluded_channel_names:
            if pattern.lower() in channel_name_lower:
                return True

        # Exclude NSFW channels
        if hasattr(channel, 'nsfw') and channel.nsfw:
            return True

        return False

    async def count_user_messages(
        self,
        user: discord.Member,
        days_lookback: Optional[int] = None,
        use_cache: bool = True
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
            after_date = datetime.utcnow() - timedelta(days=days_lookback)

        # Iterate through all text channels
        for channel in self.guild.text_channels:
            # Skip excluded channels
            if self._should_exclude_channel(channel):
                continue

            # Check if bot has permission to read history
            permissions = channel.permissions_for(self.guild.me)
            if not permissions.read_message_history:
                logger.warning(
                    f"No permission to read history in channel: {channel.name}"
                )
                continue

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

                if count > 0:
                    logger.debug(
                        f"User {user.name} has {count} messages in #{channel.name}"
                    )

            except discord.Forbidden:
                logger.warning(f"Access denied to channel: {channel.name}")
            except Exception as e:
                logger.error(
                    f"Error counting messages in {channel.name}: {e}"
                )

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

    async def count_messages_for_users(
        self,
        users: List[discord.Member],
        days_lookback: Optional[int] = None,
        progress_callback: Optional[callable] = None,
        use_cache: bool = True
    ) -> tuple[Dict[int, int], Dict]:
        """
        Count messages for multiple users.

        Args:
            users: List of members to count messages for
            days_lookback: Optional number of days to look back
            progress_callback: Optional callback function(current, total)
            use_cache: Whether to use cache (default: True)

        Returns:
            Tuple of (message_counts dict, cache_stats dict)
        """
        logger.info(f"Counting messages for {len(users)} users...")

        message_counts = {}
        total_users = len(users)
        cache_hits = 0
        cache_misses = 0

        for idx, user in enumerate(users, 1):
            try:
                # Check cache first
                from_cache = False
                if use_cache and self.cache:
                    cached = await self.cache.get(
                        self.guild.id,
                        user.id,
                        days_lookback,
                        self.excluded_channels
                    )
                    if cached is not None:
                        count = cached
                        from_cache = True
                        cache_hits += 1

                if not from_cache:
                    count = await self.count_user_messages(
                        user,
                        days_lookback,
                        use_cache=use_cache
                    )
                    cache_misses += 1

                message_counts[user.id] = count

                cache_indicator = "💾" if from_cache else "🔍"
                logger.info(
                    f"Progress: {idx}/{total_users} {cache_indicator} - "
                    f"{user.name}: {count} messages"
                )

                # Call progress callback if provided
                if progress_callback:
                    await progress_callback(idx, total_users)

            except Exception as e:
                logger.error(f"Error counting messages for {user.name}: {e}")
                message_counts[user.id] = 0

        cache_stats = {
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "cache_hit_rate": round(cache_hits / total_users * 100, 1) if total_users > 0 else 0
        }

        logger.info(
            f"Message counting completed - "
            f"Cache hits: {cache_hits}, Misses: {cache_misses} "
            f"({cache_stats['cache_hit_rate']}% hit rate)"
        )
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
