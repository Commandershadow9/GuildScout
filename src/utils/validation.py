"""Validation tools for message tracking accuracy."""

import logging
import discord
from typing import Dict, List, Tuple
from discord.ext import commands

from src.database.message_store import MessageStore
from src.analytics.activity_tracker import ActivityTracker


logger = logging.getLogger("guildscout.validation")


class MessageCountValidator:
    """Validates message count accuracy by comparing different counting methods."""

    def __init__(
        self,
        guild: discord.Guild,
        message_store: MessageStore,
        activity_tracker: ActivityTracker
    ):
        """
        Initialize the validator.

        Args:
            guild: Discord guild
            message_store: MessageStore instance
            activity_tracker: ActivityTracker instance (for Discord API counting)
        """
        self.guild = guild
        self.message_store = message_store
        self.activity_tracker = activity_tracker

    async def validate_sample(
        self,
        sample_users: List[discord.Member],
        tolerance_percent: float = 2.0
    ) -> Dict:
        """
        Validate message counts for a sample of users.

        Compares MessageStore counts with fresh Discord API counts.

        Args:
            sample_users: List of users to validate
            tolerance_percent: Acceptable difference percentage (default: 2%)

        Returns:
            Dictionary with validation results
        """
        logger.info(f"Starting validation for {len(sample_users)} users...")

        results = {
            "total_users": len(sample_users),
            "matches": 0,
            "mismatches": 0,
            "max_difference": 0,
            "avg_difference": 0,
            "discrepancies": []
        }

        total_diff = 0

        for user in sample_users:
            # Get count from MessageStore
            store_count = await self.message_store.get_user_total(
                self.guild.id,
                user.id
            )

            # Get fresh count from Discord API
            api_count = await self.activity_tracker.count_user_messages(
                user,
                use_cache=False  # Force fresh count
            )

            # Calculate difference
            diff = abs(store_count - api_count)
            diff_percent = (diff / max(api_count, 1)) * 100

            total_diff += diff

            # Check if within tolerance
            if diff_percent <= tolerance_percent:
                results["matches"] += 1
            else:
                results["mismatches"] += 1
                results["discrepancies"].append({
                    "user": user.name,
                    "user_id": user.id,
                    "store_count": store_count,
                    "api_count": api_count,
                    "difference": diff,
                    "difference_percent": diff_percent
                })

            # Update max difference
            if diff > results["max_difference"]:
                results["max_difference"] = diff

            logger.debug(
                f"User {user.name}: Store={store_count}, API={api_count}, "
                f"Diff={diff} ({diff_percent:.1f}%)"
            )

        # Calculate average difference
        results["avg_difference"] = (
            total_diff / len(sample_users) if sample_users else 0
        )

        # Determine overall result
        accuracy = (results["matches"] / len(sample_users) * 100) if sample_users else 0
        results["accuracy_percent"] = accuracy
        results["passed"] = accuracy >= 95.0  # 95% of users must match

        logger.info("=" * 60)
        logger.info("📊 VALIDATION RESULTS")
        logger.info("=" * 60)
        logger.info(f"Users validated: {len(sample_users)}")
        logger.info(f"Matches: {results['matches']}")
        logger.info(f"Mismatches: {results['mismatches']}")
        logger.info(f"Accuracy: {accuracy:.1f}%")
        logger.info(f"Max difference: {results['max_difference']}")
        logger.info(f"Avg difference: {results['avg_difference']:.1f}")
        logger.info(f"Overall: {'✅ PASSED' if results['passed'] else '❌ FAILED'}")
        logger.info("=" * 60)

        return results

    async def validate_total_counts(self) -> Dict:
        """
        Validate total message count for the guild.

        Returns:
            Dictionary with validation results
        """
        logger.info("Validating total guild message counts...")

        # Get total from MessageStore
        stats = await self.message_store.get_stats(self.guild.id)
        store_total = stats["total_messages"]

        logger.info(f"MessageStore total: {store_total:,} messages")

        result = {
            "store_total": store_total,
            "total_users": stats["total_users"],
            "total_channels": stats["total_channels"]
        }

        return result

    async def get_channel_summary(self) -> List[Dict]:
        """
        Get a summary of message counts per channel.

        Returns:
            List of channel summaries
        """
        logger.info("Generating channel summary...")

        # This would require a new method in MessageStore
        # For now, return basic info
        summary = []

        for channel in self.guild.text_channels:
            if self.activity_tracker._should_exclude_channel(channel):
                continue

            summary.append({
                "name": channel.name,
                "id": channel.id,
                "excluded": False
            })

        return summary
