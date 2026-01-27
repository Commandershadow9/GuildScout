"""Activity API for fetching recent events in GuildScout Dashboard."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

logger = logging.getLogger("guildscout.web_api.activity")


class ActivityService:
    """Service for fetching activity events from various sources."""

    def __init__(
        self,
        messages_db_path: str = "data/messages.db",
        raids_db_path: str = "data/raids.db",
    ):
        """Initialize the activity service.

        Args:
            messages_db_path: Path to messages.db
            raids_db_path: Path to raids.db
        """
        self.messages_db_path = Path(messages_db_path)
        self.raids_db_path = Path(raids_db_path)

    async def get_recent_activity(
        self,
        guild_id: int,
        limit: int = 20,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """Get recent activity events for a guild.

        Args:
            guild_id: Discord guild ID
            limit: Maximum events to return
            hours: Look back period in hours

        Returns:
            List of activity events
        """
        activities: List[Dict[str, Any]] = []

        # Get raid activities
        raid_activities = await self._get_raid_activities(guild_id, hours)
        activities.extend(raid_activities)

        # Sort by timestamp (newest first) and limit
        activities.sort(key=lambda x: x["timestamp"], reverse=True)
        return activities[:limit]

    async def _get_raid_activities(
        self,
        guild_id: int,
        hours: int,
    ) -> List[Dict[str, Any]]:
        """Get recent raid-related activities.

        Args:
            guild_id: Discord guild ID
            hours: Look back period

        Returns:
            List of raid activities
        """
        activities = []

        if not self.raids_db_path.exists():
            return activities

        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

        try:
            async with aiosqlite.connect(self.raids_db_path) as db:
                db.row_factory = aiosqlite.Row

                # Get recently created/updated raids
                cursor = await db.execute(
                    """
                    SELECT id, title, game, mode, status, scheduled_for, created_at, updated_at
                    FROM raids
                    WHERE guild_id = ? AND (created_at >= ? OR updated_at >= ?)
                    ORDER BY COALESCE(updated_at, created_at) DESC
                    LIMIT 20
                    """,
                    (guild_id, cutoff, cutoff)
                )
                raids = await cursor.fetchall()

                for raid in raids:
                    # Determine activity type
                    created_at = raid["created_at"]
                    updated_at = raid["updated_at"]

                    if updated_at and updated_at >= cutoff:
                        if raid["status"] == "closed":
                            activity_type = "raid_closed"
                            description = f"Raid '{raid['title']}' was closed"
                            icon = "check-circle"
                        elif raid["status"] == "locked":
                            activity_type = "raid_locked"
                            description = f"Raid '{raid['title']}' was locked"
                            icon = "lock"
                        else:
                            activity_type = "raid_updated"
                            description = f"Raid '{raid['title']}' was updated"
                            icon = "edit"
                        timestamp = updated_at
                    else:
                        activity_type = "raid_created"
                        description = f"New raid '{raid['title']}' created"
                        icon = "plus-circle"
                        timestamp = created_at

                    activities.append({
                        "id": f"raid_{raid['id']}_{activity_type}",
                        "type": activity_type,
                        "icon": icon,
                        "description": description,
                        "timestamp": timestamp,
                        "metadata": {
                            "raid_id": raid["id"],
                            "title": raid["title"],
                            "game": raid["game"],
                            "mode": raid["mode"],
                            "status": raid["status"],
                            "scheduled_for": raid["scheduled_for"],
                        }
                    })

                # Get recent signups
                cursor = await db.execute(
                    """
                    SELECT s.raid_id, s.user_id, s.role, s.signed_up_at, s.display_name,
                           r.title as raid_title
                    FROM signups s
                    JOIN raids r ON s.raid_id = r.id
                    WHERE r.guild_id = ? AND s.signed_up_at >= ?
                    ORDER BY s.signed_up_at DESC
                    LIMIT 30
                    """,
                    (guild_id, cutoff)
                )
                signups = await cursor.fetchall()

                for signup in signups:
                    role_emoji = {
                        "tank": "🛡️",
                        "healer": "💚",
                        "dps": "⚔️",
                        "bench": "🪑",
                    }.get(signup["role"], "👤")

                    activities.append({
                        "id": f"signup_{signup['raid_id']}_{signup['user_id']}",
                        "type": "raid_signup",
                        "icon": "user-plus",
                        "description": f"{signup['display_name']} signed up as {role_emoji} {signup['role']}",
                        "timestamp": signup["signed_up_at"],
                        "user_name": signup["display_name"],
                        "metadata": {
                            "raid_id": signup["raid_id"],
                            "raid_title": signup["raid_title"],
                            "role": signup["role"],
                        }
                    })

        except Exception as e:
            logger.error(f"Error fetching raid activities: {e}")

        return activities

    async def get_activity_summary(
        self,
        guild_id: int,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Get activity summary statistics.

        Args:
            guild_id: Discord guild ID
            days: Period to summarize

        Returns:
            Summary statistics
        """
        summary = {
            "raids_created": 0,
            "raids_closed": 0,
            "total_signups": 0,
            "unique_participants": 0,
        }

        if not self.raids_db_path.exists():
            return summary

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        try:
            async with aiosqlite.connect(self.raids_db_path) as db:
                # Count raids created
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM raids WHERE guild_id = ? AND created_at >= ?",
                    (guild_id, cutoff)
                )
                summary["raids_created"] = (await cursor.fetchone())[0]

                # Count raids closed
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM raids WHERE guild_id = ? AND status = 'closed' AND updated_at >= ?",
                    (guild_id, cutoff)
                )
                summary["raids_closed"] = (await cursor.fetchone())[0]

                # Count signups
                cursor = await db.execute(
                    """
                    SELECT COUNT(*) FROM signups s
                    JOIN raids r ON s.raid_id = r.id
                    WHERE r.guild_id = ? AND s.signed_up_at >= ?
                    """,
                    (guild_id, cutoff)
                )
                summary["total_signups"] = (await cursor.fetchone())[0]

                # Count unique participants
                cursor = await db.execute(
                    """
                    SELECT COUNT(DISTINCT s.user_id) FROM signups s
                    JOIN raids r ON s.raid_id = r.id
                    WHERE r.guild_id = ? AND s.signed_up_at >= ?
                    """,
                    (guild_id, cutoff)
                )
                summary["unique_participants"] = (await cursor.fetchone())[0]

        except Exception as e:
            logger.error(f"Error fetching activity summary: {e}")

        return summary


# Singleton instance
_activity_service: Optional[ActivityService] = None


def get_activity_service(
    messages_db_path: str = "data/messages.db",
    raids_db_path: str = "data/raids.db",
) -> ActivityService:
    """Get or create the activity service singleton.

    Args:
        messages_db_path: Path to messages database
        raids_db_path: Path to raids database

    Returns:
        ActivityService instance
    """
    global _activity_service
    if _activity_service is None:
        _activity_service = ActivityService(messages_db_path, raids_db_path)
    return _activity_service
