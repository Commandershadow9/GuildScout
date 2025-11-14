"""Scorer for calculating user scores based on activity and membership duration."""

import logging
from typing import Dict, List
from datetime import datetime
from dataclasses import dataclass
import discord


logger = logging.getLogger("guildscout.scorer")


@dataclass
class UserScore:
    """Data class representing a user's score."""

    user_id: int
    username: str
    discriminator: str
    days_in_server: int
    message_count: int
    days_score: float
    activity_score: float
    final_score: float
    join_date: datetime

    @property
    def display_name(self) -> str:
        """Get display name for the user."""
        if self.discriminator == "0":
            # New username system (no discriminator)
            return self.username
        return f"{self.username}#{self.discriminator}"


class Scorer:
    """Calculates scores for users based on membership and activity."""

    def __init__(
        self,
        weight_days: float = 0.4,
        weight_messages: float = 0.6,
        min_messages: int = 10
    ):
        """
        Initialize the scorer.

        Args:
            weight_days: Weight for days in server (0-1)
            weight_messages: Weight for message count (0-1)
            min_messages: Minimum messages required to be scored
        """
        self.weight_days = weight_days
        self.weight_messages = weight_messages
        self.min_messages = min_messages

        # Validate weights
        total_weight = weight_days + weight_messages
        if not 0.99 <= total_weight <= 1.01:  # Allow small floating point errors
            logger.warning(
                f"Weights don't sum to 1.0: {total_weight}. "
                f"Normalizing weights."
            )
            self.weight_days = weight_days / total_weight
            self.weight_messages = weight_messages / total_weight

    def calculate_scores(
        self,
        members: List[discord.Member],
        message_counts: Dict[int, int]
    ) -> List[UserScore]:
        """
        Calculate scores for all members.

        Args:
            members: List of Discord members
            message_counts: Dictionary mapping user ID to message count

        Returns:
            List of UserScore objects
        """
        logger.info(f"Calculating scores for {len(members)} members...")

        scores = []
        now = datetime.utcnow()

        # First pass: collect all valid users and find max values
        valid_users = []
        max_days = 0
        max_messages = 0

        for member in members:
            message_count = message_counts.get(member.id, 0)

            # Skip users below minimum message threshold
            if message_count < self.min_messages:
                logger.debug(
                    f"Skipping {member.name}: "
                    f"only {message_count} messages (min: {self.min_messages})"
                )
                continue

            # Calculate days in server
            if member.joined_at is None:
                logger.warning(f"No join date for {member.name}, skipping")
                continue

            days_in_server = (now - member.joined_at).days

            valid_users.append({
                "member": member,
                "days": days_in_server,
                "messages": message_count
            })

            # Track max values for normalization
            max_days = max(max_days, days_in_server)
            max_messages = max(max_messages, message_count)

        logger.info(
            f"Valid users after filtering: {len(valid_users)} "
            f"(filtered out: {len(members) - len(valid_users)})"
        )

        # Prevent division by zero
        if max_days == 0:
            max_days = 1
        if max_messages == 0:
            max_messages = 1

        # Second pass: calculate normalized scores
        for user_data in valid_users:
            member = user_data["member"]
            days = user_data["days"]
            messages = user_data["messages"]

            # Normalize to 0-100 scale
            days_score = (days / max_days) * 100
            activity_score = (messages / max_messages) * 100

            # Calculate weighted final score
            final_score = (
                (days_score * self.weight_days) +
                (activity_score * self.weight_messages)
            )

            score = UserScore(
                user_id=member.id,
                username=member.name,
                discriminator=member.discriminator,
                days_in_server=days,
                message_count=messages,
                days_score=round(days_score, 2),
                activity_score=round(activity_score, 2),
                final_score=round(final_score, 2),
                join_date=member.joined_at
            )

            scores.append(score)

        logger.info(f"Calculated scores for {len(scores)} users")
        return scores

    def get_scoring_info(self) -> Dict:
        """
        Get information about scoring configuration.

        Returns:
            Dictionary with scoring configuration
        """
        return {
            "weight_days": self.weight_days,
            "weight_messages": self.weight_messages,
            "min_messages": self.min_messages,
            "formula": (
                f"Score = (Days_Score × {self.weight_days}) + "
                f"(Activity_Score × {self.weight_messages})"
            )
        }
