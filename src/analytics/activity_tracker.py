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
        excluded_channel_names: Optional[List[str]] = None
    ):
        """
        Initialize the activity tracker.

        Args:
            guild: Discord guild to track activity in
            excluded_channels: List of channel IDs to exclude
            excluded_channel_names: List of channel name patterns to exclude
        """
        self.guild = guild
        self.excluded_channels = excluded_channels or []
        self.excluded_channel_names = excluded_channel_names or []

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
        days_lookback: Optional[int] = None
    ) -> int:
        """
        Count messages for a specific user across all channels.

        Args:
            user: Member to count messages for
            days_lookback: Optional number of days to look back (None = all time)

        Returns:
            Total message count
        """
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

        return total_messages

    async def count_messages_for_users(
        self,
        users: List[discord.Member],
        days_lookback: Optional[int] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict[int, int]:
        """
        Count messages for multiple users.

        Args:
            users: List of members to count messages for
            days_lookback: Optional number of days to look back
            progress_callback: Optional callback function(current, total)

        Returns:
            Dictionary mapping user ID to message count
        """
        logger.info(f"Counting messages for {len(users)} users...")

        message_counts = {}
        total_users = len(users)

        for idx, user in enumerate(users, 1):
            try:
                count = await self.count_user_messages(user, days_lookback)
                message_counts[user.id] = count

                logger.info(
                    f"Progress: {idx}/{total_users} - "
                    f"{user.name}: {count} messages"
                )

                # Call progress callback if provided
                if progress_callback:
                    await progress_callback(idx, total_users)

            except Exception as e:
                logger.error(f"Error counting messages for {user.name}: {e}")
                message_counts[user.id] = 0

        logger.info("Message counting completed")
        return message_counts

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
