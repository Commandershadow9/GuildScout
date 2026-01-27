"""Analytics API endpoints for GuildScout Dashboard."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

logger = logging.getLogger("guildscout.web_api.analytics")


@dataclass
class MemberScore:
    """Score data for a guild member (Web API version without discord.py dependency)."""

    user_id: int
    display_name: str
    days_in_server: int
    message_count: int
    voice_seconds: int
    days_score: float
    message_score: float
    voice_score: float
    final_score: float
    joined_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "user_id": str(self.user_id),
            "display_name": self.display_name,
            "days_in_server": self.days_in_server,
            "message_count": self.message_count,
            "voice_seconds": self.voice_seconds,
            "voice_minutes": self.voice_seconds // 60,
            "days_score": self.days_score,
            "message_score": self.message_score,
            "voice_score": self.voice_score,
            "final_score": self.final_score,
            "joined_at": self.joined_at,
        }


class AnalyticsService:
    """Service for computing analytics data from the message database."""

    def __init__(self, db_path: str = "data/messages.db"):
        """Initialize the analytics service.

        Args:
            db_path: Path to the messages.db SQLite database
        """
        self.db_path = Path(db_path)

        # Default scoring weights (should match bot config)
        self.weight_days = 0.10
        self.weight_messages = 0.55
        self.weight_voice = 0.35

    def set_weights(self, days: float, messages: float, voice: float) -> None:
        """Set scoring weights.

        Args:
            days: Weight for days in server (0-1)
            messages: Weight for message count (0-1)
            voice: Weight for voice activity (0-1)
        """
        total = days + messages + voice
        if total > 0:
            self.weight_days = days / total
            self.weight_messages = messages / total
            self.weight_voice = voice / total

    async def get_member_rankings(
        self,
        guild_id: int,
        limit: int = 50,
        offset: int = 0,
        days_lookback: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get ranked member list with scores.

        Args:
            guild_id: Discord guild ID
            limit: Maximum number of members to return
            offset: Offset for pagination
            days_lookback: Optional filter for voice activity days

        Returns:
            Dictionary with rankings and metadata
        """
        if not self.db_path.exists():
            return {"rankings": [], "total": 0, "error": "Database not found"}

        async with aiosqlite.connect(self.db_path) as db:
            # Get all members with their data
            members_data = await self._fetch_members_with_activity(
                db, guild_id, days_lookback
            )

            if not members_data:
                return {"rankings": [], "total": 0}

            # Calculate scores
            scores = self._calculate_scores(members_data)

            # Sort by final score (descending)
            scores.sort(key=lambda x: x.final_score, reverse=True)

            # Add ranks
            total = len(scores)
            paginated = scores[offset:offset + limit]

            rankings = []
            for idx, score in enumerate(paginated, start=offset + 1):
                data = score.to_dict()
                data["rank"] = idx
                rankings.append(data)

            return {
                "rankings": rankings,
                "total": total,
                "page": (offset // limit) + 1 if limit > 0 else 1,
                "per_page": limit,
                "weights": {
                    "days": self.weight_days,
                    "messages": self.weight_messages,
                    "voice": self.weight_voice,
                }
            }

    async def get_member_score(
        self,
        guild_id: int,
        user_id: int,
        days_lookback: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get score for a specific member.

        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            days_lookback: Optional filter for voice activity days

        Returns:
            Member score data or None if not found
        """
        if not self.db_path.exists():
            return None

        async with aiosqlite.connect(self.db_path) as db:
            # Get all members to calculate relative scores
            members_data = await self._fetch_members_with_activity(
                db, guild_id, days_lookback
            )

            if not members_data:
                return None

            # Calculate all scores for proper normalization
            scores = self._calculate_scores(members_data)
            scores.sort(key=lambda x: x.final_score, reverse=True)

            # Find the user
            for rank, score in enumerate(scores, start=1):
                if score.user_id == user_id:
                    data = score.to_dict()
                    data["rank"] = rank
                    data["total_members"] = len(scores)
                    data["percentile"] = round(
                        (1 - (rank - 1) / len(scores)) * 100, 1
                    ) if len(scores) > 1 else 100
                    return data

            return None

    async def get_activity_overview(
        self,
        guild_id: int,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get activity overview for a guild.

        Args:
            guild_id: Discord guild ID
            days: Number of days for daily history

        Returns:
            Activity overview data
        """
        if not self.db_path.exists():
            return {"error": "Database not found"}

        async with aiosqlite.connect(self.db_path) as db:
            # Daily activity
            daily = await self._get_daily_stats(db, guild_id, days)

            # Hourly activity (all-time)
            hourly = await self._get_hourly_stats(db, guild_id)

            # General stats
            stats = await self._get_guild_stats(db, guild_id)

            return {
                "daily_activity": daily,
                "hourly_activity": hourly,
                "stats": stats,
            }

    async def _fetch_members_with_activity(
        self,
        db: aiosqlite.Connection,
        guild_id: int,
        days_lookback: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch all members with their message and voice activity.

        Args:
            db: Database connection
            guild_id: Discord guild ID
            days_lookback: Optional voice activity filter

        Returns:
            List of member data dictionaries
        """
        now = datetime.now(timezone.utc)

        # Get members from guild_members table
        cursor = await db.execute(
            """
            SELECT user_id, display_name, joined_at
            FROM guild_members
            WHERE guild_id = ? AND is_bot = 0
            """,
            (guild_id,)
        )
        members = await cursor.fetchall()

        if not members:
            # Fallback: Get users from message_counts
            cursor = await db.execute(
                """
                SELECT DISTINCT user_id
                FROM message_counts
                WHERE guild_id = ?
                """,
                (guild_id,)
            )
            user_rows = await cursor.fetchall()
            members = [(row[0], f"User {row[0]}", None) for row in user_rows]

        # Get message counts
        cursor = await db.execute(
            """
            SELECT user_id, SUM(message_count) as total
            FROM message_counts
            WHERE guild_id = ?
            GROUP BY user_id
            """,
            (guild_id,)
        )
        message_rows = await cursor.fetchall()
        message_counts = {row[0]: row[1] for row in message_rows}

        # Get voice totals
        voice_query = """
            SELECT user_id, SUM(total_seconds) as total
            FROM voice_daily_stats
            WHERE guild_id = ?
        """
        params = [guild_id]

        if days_lookback:
            cutoff = now.strftime("%Y-%m-%d")
            voice_query += " AND date >= date(?, '-' || ? || ' days')"
            params.extend([cutoff, days_lookback])

        voice_query += " GROUP BY user_id"

        cursor = await db.execute(voice_query, params)
        voice_rows = await cursor.fetchall()
        voice_counts = {row[0]: row[1] for row in voice_rows}

        # Combine data
        result = []
        for user_id, display_name, joined_at in members:
            # Calculate days in server
            days_in_server = 0
            if joined_at:
                try:
                    join_dt = datetime.fromisoformat(joined_at.replace('Z', '+00:00'))
                    days_in_server = (now - join_dt).days
                except (ValueError, TypeError):
                    days_in_server = 30  # Default fallback
            else:
                days_in_server = 30  # Default for unknown join date

            result.append({
                "user_id": user_id,
                "display_name": display_name or f"User {user_id}",
                "days_in_server": max(1, days_in_server),
                "message_count": message_counts.get(user_id, 0),
                "voice_seconds": voice_counts.get(user_id, 0),
                "joined_at": joined_at,
            })

        return result

    def _calculate_scores(
        self,
        members_data: List[Dict[str, Any]]
    ) -> List[MemberScore]:
        """Calculate normalized scores for all members.

        Args:
            members_data: List of member data dictionaries

        Returns:
            List of MemberScore objects
        """
        if not members_data:
            return []

        # Find max values for normalization
        max_days = max(m["days_in_server"] for m in members_data) or 1
        max_messages = max(m["message_count"] for m in members_data) or 1
        max_voice = max(m["voice_seconds"] for m in members_data) or 1

        scores = []
        for member in members_data:
            # Normalize to 0-100 scale
            days_score = (member["days_in_server"] / max_days) * 100
            message_score = (member["message_count"] / max_messages) * 100
            voice_score = (member["voice_seconds"] / max_voice) * 100

            # Calculate weighted final score
            final_score = (
                (days_score * self.weight_days) +
                (message_score * self.weight_messages) +
                (voice_score * self.weight_voice)
            )

            scores.append(MemberScore(
                user_id=member["user_id"],
                display_name=member["display_name"],
                days_in_server=member["days_in_server"],
                message_count=member["message_count"],
                voice_seconds=member["voice_seconds"],
                days_score=round(days_score, 2),
                message_score=round(message_score, 2),
                voice_score=round(voice_score, 2),
                final_score=round(final_score, 2),
                joined_at=member.get("joined_at"),
            ))

        return scores

    async def _get_daily_stats(
        self,
        db: aiosqlite.Connection,
        guild_id: int,
        days: int
    ) -> List[Dict[str, Any]]:
        """Get daily message statistics.

        Args:
            db: Database connection
            guild_id: Discord guild ID
            days: Number of days to fetch

        Returns:
            List of daily stat entries
        """
        cursor = await db.execute(
            """
            SELECT date, message_count
            FROM daily_stats
            WHERE guild_id = ?
            ORDER BY date DESC
            LIMIT ?
            """,
            (guild_id, days)
        )
        rows = await cursor.fetchall()

        # Return in chronological order
        return [
            {"date": row[0], "messages": row[1]}
            for row in reversed(rows)
        ]

    async def _get_hourly_stats(
        self,
        db: aiosqlite.Connection,
        guild_id: int
    ) -> List[Dict[str, Any]]:
        """Get hourly activity distribution.

        Args:
            db: Database connection
            guild_id: Discord guild ID

        Returns:
            List of hourly stat entries (0-23)
        """
        cursor = await db.execute(
            """
            SELECT hour, message_count
            FROM hourly_stats
            WHERE guild_id = ?
            ORDER BY hour
            """,
            (guild_id,)
        )
        rows = await cursor.fetchall()

        # Fill in missing hours with 0
        hourly_map = {row[0]: row[1] for row in rows}
        return [
            {"hour": h, "messages": hourly_map.get(h, 0)}
            for h in range(24)
        ]

    async def _get_guild_stats(
        self,
        db: aiosqlite.Connection,
        guild_id: int
    ) -> Dict[str, Any]:
        """Get general guild statistics.

        Args:
            db: Database connection
            guild_id: Discord guild ID

        Returns:
            Dictionary with guild stats
        """
        # Total messages
        cursor = await db.execute(
            "SELECT COALESCE(SUM(message_count), 0) FROM message_counts WHERE guild_id = ?",
            (guild_id,)
        )
        total_messages = (await cursor.fetchone())[0]

        # Total users with messages
        cursor = await db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM message_counts WHERE guild_id = ?",
            (guild_id,)
        )
        active_users = (await cursor.fetchone())[0]

        # Total tracked members
        cursor = await db.execute(
            "SELECT COUNT(*) FROM guild_members WHERE guild_id = ? AND is_bot = 0",
            (guild_id,)
        )
        total_members = (await cursor.fetchone())[0]

        # Total voice time
        cursor = await db.execute(
            "SELECT COALESCE(SUM(total_seconds), 0) FROM voice_daily_stats WHERE guild_id = ?",
            (guild_id,)
        )
        total_voice_seconds = (await cursor.fetchone())[0]

        # Total channels tracked
        cursor = await db.execute(
            "SELECT COUNT(DISTINCT channel_id) FROM message_counts WHERE guild_id = ?",
            (guild_id,)
        )
        total_channels = (await cursor.fetchone())[0]

        return {
            "total_messages": total_messages,
            "active_users": active_users,
            "total_members": total_members or active_users,
            "total_voice_hours": round(total_voice_seconds / 3600, 1),
            "total_channels": total_channels,
        }


# Singleton instance
_analytics_service: Optional[AnalyticsService] = None


def get_analytics_service(db_path: str = "data/messages.db") -> AnalyticsService:
    """Get or create the analytics service singleton.

    Args:
        db_path: Path to the messages database

    Returns:
        AnalyticsService instance
    """
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService(db_path)
    return _analytics_service
