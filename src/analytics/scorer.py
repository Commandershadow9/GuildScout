"""Scorer for calculating user scores based on activity and membership duration."""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
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
    voice_seconds: int
    days_score: float
    message_score: float
    voice_score: float
    final_score: float
    join_date: datetime

    @property
    def display_name(self) -> str:
        """Get display name for the user."""
        if self.discriminator == "0":
            # New username system (no discriminator)
            return self.username
        return f"{self.username}#{self.discriminator}"
    
    @property
    def activity_score(self) -> float:
        """Legacy property for compatibility (returns combined message + voice score)."""
        # This is approximate since we now have separate weights
        return max(self.message_score, self.voice_score)


class Scorer:
    """Calculates scores for users based on membership and activity."""

    def __init__(
        self,
        weight_days: float = 0.4,
        weight_messages: float = 0.4,
        weight_voice: float = 0.2,
        min_messages: int = 10
    ):
        """
        Initialize the scorer.

        Args:
            weight_days: Weight for days in server (0-1)
            weight_messages: Weight for message count (0-1)
            weight_voice: Weight for voice activity (0-1)
            min_messages: Minimum messages required to be scored
        """
        self.weight_days = weight_days
        self.weight_messages = weight_messages
        self.weight_voice = weight_voice
        self.min_messages = min_messages

        # Validate weights
        total_weight = weight_days + weight_messages + weight_voice
        if not 0.99 <= total_weight <= 1.01:  # Allow small floating point errors
            logger.warning(
                f"Weights don't sum to 1.0: {total_weight}. "
                f"Normalizing weights."
            )
            self.weight_days = weight_days / total_weight
            self.weight_messages = weight_messages / total_weight
            self.weight_voice = weight_voice / total_weight

    def calculate_scores(
        self,
        members: List[discord.Member],
        message_counts: Dict[int, int],
        voice_counts: Optional[Dict[int, int]] = None
    ) -> List[UserScore]:
        """
        Calculate scores for all members.

        Args:
            members: List of Discord members
            message_counts: Dictionary mapping user ID to message count
            voice_counts: Dictionary mapping user ID to voice seconds

        Returns:
            List of UserScore objects
        """
        logger.info(f"Calculating scores for {len(members)} members...")
        
        if voice_counts is None:
            voice_counts = {}

        scores = []
        now = datetime.now(timezone.utc)

        # First pass: collect all valid users and find max values
        valid_users = []
        max_days = 0
        max_messages = 0
        max_voice = 0

        for member in members:
            message_count = message_counts.get(member.id, 0)
            voice_seconds = voice_counts.get(member.id, 0)
            
            # Calculate days in server
            if member.joined_at is None:
                logger.warning(f"No join date for {member.name}, skipping")
                continue

            days_in_server = (now - member.joined_at).days

            valid_users.append({
                "member": member,
                "days": days_in_server,
                "messages": message_count,
                "voice_seconds": voice_seconds
            })

            # Track max values for normalization
            max_days = max(max_days, days_in_server)
            max_messages = max(max_messages, message_count)
            max_voice = max(max_voice, voice_seconds)

        logger.info(
            f"Valid users after filtering: {len(valid_users)} "
            f"(filtered out: {len(members) - len(valid_users)})"
        )

        # Prevent division by zero
        if max_days == 0: max_days = 1
        if max_messages == 0: max_messages = 1
        if max_voice == 0: max_voice = 1

        # Second pass: calculate normalized scores
        for user_data in valid_users:
            member = user_data["member"]
            days = user_data["days"]
            messages = user_data["messages"]
            voice_seconds = user_data["voice_seconds"]

            # Normalize to 0-100 scale
            days_score = (days / max_days) * 100
            message_score = (messages / max_messages) * 100
            voice_score = (voice_seconds / max_voice) * 100

            # Calculate weighted final score
            final_score = (
                (days_score * self.weight_days) +
                (message_score * self.weight_messages) +
                (voice_score * self.weight_voice)
            )

            score = UserScore(
                user_id=member.id,
                username=member.name,
                discriminator=member.discriminator,
                days_in_server=days,
                message_count=messages,
                voice_seconds=voice_seconds,
                days_score=round(days_score, 2),
                message_score=round(message_score, 2),
                voice_score=round(voice_score, 2),
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
            "weight_voice": self.weight_voice,
            "min_messages": self.min_messages,
            "formula": (
                f"Score = (Days × {self.weight_days}) + "
                f"(Msg × {self.weight_messages}) + "
                f"(Voice × {self.weight_voice})"
            )
        }
