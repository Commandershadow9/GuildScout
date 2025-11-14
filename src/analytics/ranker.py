"""Ranker for sorting and organizing user scores."""

import logging
from typing import List, Optional
from .scorer import UserScore


logger = logging.getLogger("guildscout.ranker")


class Ranker:
    """Ranks users based on their scores."""

    @staticmethod
    def rank_users(
        scores: List[UserScore],
        top_n: Optional[int] = None
    ) -> List[tuple[int, UserScore]]:
        """
        Rank users by their final score.

        Args:
            scores: List of UserScore objects
            top_n: Optional limit to top N users

        Returns:
            List of tuples (rank, UserScore), sorted by score descending
        """
        logger.info(f"Ranking {len(scores)} users...")

        # Sort by final score (descending)
        sorted_scores = sorted(
            scores,
            key=lambda x: x.final_score,
            reverse=True
        )

        # Limit to top N if specified
        if top_n is not None and top_n > 0:
            sorted_scores = sorted_scores[:top_n]
            logger.info(f"Limited to top {top_n} users")

        # Add ranks (1-indexed)
        ranked_users = [
            (rank, score)
            for rank, score in enumerate(sorted_scores, start=1)
        ]

        return ranked_users

    @staticmethod
    def get_user_rank(
        user_id: int,
        ranked_users: List[tuple[int, UserScore]]
    ) -> Optional[int]:
        """
        Get the rank of a specific user.

        Args:
            user_id: Discord user ID
            ranked_users: List of ranked users

        Returns:
            User's rank (1-indexed) or None if not found
        """
        for rank, score in ranked_users:
            if score.user_id == user_id:
                return rank
        return None

    @staticmethod
    def get_statistics(scores: List[UserScore]) -> dict:
        """
        Calculate statistics about the scores.

        Args:
            scores: List of UserScore objects

        Returns:
            Dictionary with statistics
        """
        if not scores:
            return {
                "total_users": 0,
                "avg_score": 0,
                "avg_days": 0,
                "avg_messages": 0,
                "max_score": 0,
                "min_score": 0,
                "max_days": 0,
                "max_messages": 0
            }

        final_scores = [s.final_score for s in scores]
        days = [s.days_in_server for s in scores]
        messages = [s.message_count for s in scores]

        return {
            "total_users": len(scores),
            "avg_score": round(sum(final_scores) / len(final_scores), 2),
            "avg_days": round(sum(days) / len(days), 2),
            "avg_messages": round(sum(messages) / len(messages), 2),
            "max_score": max(final_scores),
            "min_score": min(final_scores),
            "max_days": max(days),
            "max_messages": max(messages)
        }
