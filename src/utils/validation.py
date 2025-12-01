"""Validation tools for message tracking accuracy."""

import logging
import discord
from typing import Dict, List, Optional, Callable, Awaitable
from discord.ext import commands

from src.database.message_store import MessageStore
from src.analytics.activity_tracker import ActivityTracker


logger = logging.getLogger("guildscout.validation")


ProgressCallback = Optional[
    Callable[
        [int, int, discord.Member, int, int],
        Awaitable[None]
    ]
]

ChannelProgressCallback = Optional[
    Callable[
        [
            discord.Member,
            int,
            int,
            discord.TextChannel,
            int,
            int,
            int
        ],
        Awaitable[None]
    ]
]


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
        tolerance_percent: float = 2.0,
        progress_callback: ProgressCallback = None,
        channel_progress_callback: ChannelProgressCallback = None,
        heal_mismatches: bool = False
    ) -> Dict:
        """
        Validate message counts for a sample of users.

        Compares MessageStore counts with fresh Discord API counts.

        Args:
            sample_users: List of users to validate
            tolerance_percent: Acceptable difference percentage (default: 2%)
            progress_callback: Optional coroutine to report progress
            heal_mismatches: Whether to automatically fix DB counts using API data (default: False)

        Returns:
            Dictionary with validation results
        """
        logger.info(f"Starting OPTIMIZED validation for {len(sample_users)} users (Healing: {heal_mismatches})...")

        results = {
            "total_users": len(sample_users),
            "matches": 0,
            "mismatches": 0,
            "healed": 0,
            "max_difference": 0,
            "avg_difference": 0,
            "discrepancies": [],
            "user_results": []
        }

        total_diff = 0

        # Get all excluded channels (both by ID and Name patterns) from tracker
        excluded_channel_ids = self.activity_tracker.get_excluded_channel_ids()

        # OPTIMIZATION: Use channel-first counting for all users at once (10x faster!)
        logger.info("🚀 Using optimized channel-first algorithm for validation...")
        api_counts, cache_stats = await self.activity_tracker.count_messages_for_users(
            sample_users,
            days_lookback=None,
            use_cache=False,  # Force fresh count
            parallel_channels=3  # Conservative parallelism to avoid rate limits
        )
        logger.info(f"✅ Optimized counting complete! Now comparing results...")

        # Phase 1: Compare all users
        users_needing_healing = []

        for idx, user in enumerate(sample_users, start=1):
            # Get count from MessageStore
            store_count = await self.message_store.get_user_total(
                self.guild.id,
                user.id,
                excluded_channels=excluded_channel_ids
            )

            # Get API count from optimized batch result
            api_count = api_counts.get(user.id, 0)

            # Calculate difference
            diff = abs(store_count - api_count)
            diff_percent = (diff / max(api_count, 1)) * 100

            total_diff += diff

            # Check if within tolerance
            match = diff_percent <= tolerance_percent

            if match:
                results["matches"] += 1
            else:
                results["mismatches"] += 1

                # Track users that need healing
                if heal_mismatches:
                    users_needing_healing.append((user, store_count, api_count, diff))

                results["discrepancies"].append({
                    "user": user.name,
                    "user_id": user.id,
                    "store_count": store_count,
                    "api_count": api_count,
                    "difference": diff,
                    "difference_percent": diff_percent,
                    "healed": False  # Will be updated in phase 2
                })

            results["user_results"].append({
                "user": user.name,
                "user_id": user.id,
                "store_count": store_count,
                "api_count": api_count,
                "difference": diff,
                "difference_percent": diff_percent,
                "match": match,
                "healed": False  # Will be updated in phase 2
            })

            # Update max difference
            if diff > results["max_difference"]:
                results["max_difference"] = diff

            logger.debug(
                f"User {user.name}: Store={store_count}, API={api_count}, "
                f"Diff={diff} ({diff_percent:.1f}%)"
            )

            if progress_callback:
                try:
                    await progress_callback(
                        idx,
                        len(sample_users),
                        user,
                        store_count,
                        api_count
                    )
                except Exception as exc:
                    logger.debug("Progress callback failed: %s", exc)

        # Phase 2: Heal mismatched users (only the ones that need it)
        if heal_mismatches and users_needing_healing:
            logger.info(f"🩹 Healing {len(users_needing_healing)} users with mismatches...")

            for user, store_count, api_count, diff in users_needing_healing:
                try:
                    # Get detailed breakdown for this user only
                    logger.info(f"🔍 Fetching breakdown for {user.name}...")
                    _, channel_breakdown = await self.activity_tracker.count_user_messages(
                        user,
                        use_cache=False,
                        return_breakdown=True
                    )

                    # Update database with correct counts
                    logger.info(f"🩹 Healing user {user.name} (Diff: {diff}, Store: {store_count}, API: {api_count})")
                    await self.message_store.update_user_counts(
                        self.guild.id,
                        user.id,
                        channel_breakdown
                    )

                    results["healed"] += 1

                    # Update results to mark as healed
                    for disc in results["discrepancies"]:
                        if disc["user_id"] == user.id:
                            disc["healed"] = True

                    for user_result in results["user_results"]:
                        if user_result["user_id"] == user.id:
                            user_result["healed"] = True

                except Exception as e:
                    logger.error(f"Failed to heal user {user.name}: {e}")

        # Calculate average difference
        results["avg_difference"] = (
            total_diff / len(sample_users) if sample_users else 0
        )

        # Determine overall result (passed if match OR healed)
        # If we healed the mismatches, the "state" is now effectively valid, 
        # but we still report the initial state as "failed/healed".
        
        accuracy = (results["matches"] / len(sample_users) * 100) if sample_users else 0
        results["accuracy_percent"] = accuracy
        
        # Pass if high accuracy OR if we healed everything
        results["passed"] = (accuracy >= 95.0)

        logger.info("=" * 60)
        logger.info("📊 VALIDATION RESULTS")
        logger.info("=" * 60)
        logger.info(f"Users validated: {len(sample_users)}")
        logger.info(f"Matches: {results['matches']}")
        logger.info(f"Mismatches: {results['mismatches']}")
        if heal_mismatches:
            logger.info(f"Healed: {results['healed']}")
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
