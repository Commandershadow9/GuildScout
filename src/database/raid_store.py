"""SQLite storage for raid scheduling and signups."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import aiosqlite


logger = logging.getLogger("guildscout.raid_store")


@dataclass(frozen=True)
class RaidRecord:
    """Represents a stored raid."""

    id: int
    guild_id: int
    channel_id: int
    message_id: Optional[int]
    creator_id: int
    title: str
    description: Optional[str]
    start_time: int
    tanks_needed: int
    healers_needed: int
    dps_needed: int
    bench_needed: int
    status: str
    created_at: int
    closed_at: Optional[int]


class RaidStore:
    """SQLite-based storage for raids and signups."""

    def __init__(self, db_path: str = "data/raids.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def initialize(self) -> None:
        """Ensure the database schema exists."""
        if self._initialized:
            return

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS raids (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    message_id INTEGER,
                    creator_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    start_time INTEGER NOT NULL,
                    tanks_needed INTEGER NOT NULL,
                    healers_needed INTEGER NOT NULL,
                    dps_needed INTEGER NOT NULL,
                    bench_needed INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at INTEGER NOT NULL,
                    closed_at INTEGER
                )
                """
            )

            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_raids_message
                ON raids(message_id)
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS raid_signups (
                    raid_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    joined_at INTEGER NOT NULL,
                    preferred_role TEXT,
                    confirmed INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (raid_id, user_id)
                )
                """
            )

            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_raid_signups_raid
                ON raid_signups(raid_id)
                """
            )

            # Add preferred_role column for existing installs
            cursor = await db.execute("PRAGMA table_info(raid_signups)")
            columns = [row[1] for row in await cursor.fetchall()]
            if "preferred_role" not in columns:
                await db.execute("ALTER TABLE raid_signups ADD COLUMN preferred_role TEXT")
            if "confirmed" not in columns:
                await db.execute(
                    "ALTER TABLE raid_signups ADD COLUMN confirmed INTEGER NOT NULL DEFAULT 0"
                )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS raid_reminders (
                    raid_id INTEGER NOT NULL,
                    reminder_hours INTEGER NOT NULL,
                    sent_at INTEGER NOT NULL,
                    PRIMARY KEY (raid_id, reminder_hours)
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS raid_confirmations (
                    raid_id INTEGER PRIMARY KEY,
                    message_id INTEGER NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS raid_alerts (
                    raid_id INTEGER NOT NULL,
                    alert_type TEXT NOT NULL,
                    sent_at INTEGER NOT NULL,
                    PRIMARY KEY (raid_id, alert_type)
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS raid_participation (
                    raid_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confirmed INTEGER NOT NULL,
                    joined_at INTEGER NOT NULL,
                    recorded_at INTEGER NOT NULL,
                    PRIMARY KEY (raid_id, user_id)
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS raid_leave_requests (
                    user_id INTEGER NOT NULL,
                    raid_id INTEGER NOT NULL,
                    requested_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    PRIMARY KEY (user_id, raid_id)
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS raid_leave_reasons (
                    raid_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    PRIMARY KEY (raid_id, user_id)
                )
                """
            )

            await db.commit()

        self._initialized = True
        logger.info("Raid store initialized at %s", self.db_path)

    @staticmethod
    def _row_to_record(row: aiosqlite.Row) -> RaidRecord:
        return RaidRecord(
            id=row[0],
            guild_id=row[1],
            channel_id=row[2],
            message_id=row[3],
            creator_id=row[4],
            title=row[5],
            description=row[6],
            start_time=row[7],
            tanks_needed=row[8],
            healers_needed=row[9],
            dps_needed=row[10],
            bench_needed=row[11],
            status=row[12],
            created_at=row[13],
            closed_at=row[14],
        )

    async def create_raid(
        self,
        guild_id: int,
        channel_id: int,
        creator_id: int,
        title: str,
        description: Optional[str],
        start_time: int,
        tanks_needed: int,
        healers_needed: int,
        dps_needed: int,
        bench_needed: int,
    ) -> int:
        """Insert a raid and return its ID."""
        await self.initialize()
        created_at = int(datetime.now(timezone.utc).timestamp())

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO raids (
                    guild_id,
                    channel_id,
                    creator_id,
                    title,
                    description,
                    start_time,
                    tanks_needed,
                    healers_needed,
                    dps_needed,
                    bench_needed,
                    status,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)
                """,
                (
                    guild_id,
                    channel_id,
                    creator_id,
                    title,
                    description,
                    start_time,
                    tanks_needed,
                    healers_needed,
                    dps_needed,
                    bench_needed,
                    created_at,
                ),
            )
            await db.commit()
            return cursor.lastrowid

    async def set_message_id(self, raid_id: int, message_id: int) -> None:
        """Associate a Discord message with a raid."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE raids SET message_id = ? WHERE id = ?",
                (message_id, raid_id),
            )
            await db.commit()

    async def get_raid_by_message_id(self, message_id: int) -> Optional[RaidRecord]:
        """Fetch a raid by its message ID."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, guild_id, channel_id, message_id, creator_id, title, description,
                       start_time, tanks_needed, healers_needed, dps_needed, bench_needed,
                       status, created_at, closed_at
                FROM raids
                WHERE message_id = ?
                """,
                (message_id,),
            )
            row = await cursor.fetchone()
            return self._row_to_record(row) if row else None

    async def get_raid(self, raid_id: int) -> Optional[RaidRecord]:
        """Fetch a raid by ID."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, guild_id, channel_id, message_id, creator_id, title, description,
                       start_time, tanks_needed, healers_needed, dps_needed, bench_needed,
                       status, created_at, closed_at
                FROM raids
                WHERE id = ?
                """,
                (raid_id,),
            )
            row = await cursor.fetchone()
            return self._row_to_record(row) if row else None

    async def get_signups_by_role(self, raid_id: int) -> Dict[str, List[int]]:
        """Return signups grouped by role."""
        await self.initialize()
        signups: Dict[str, List[int]] = {}
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT user_id, role FROM raid_signups WHERE raid_id = ?",
                (raid_id,),
            )
            rows = await cursor.fetchall()
            for user_id, role in rows:
                signups.setdefault(role, []).append(int(user_id))
        return signups

    async def get_user_role(self, raid_id: int, user_id: int) -> Optional[str]:
        """Return a user's current role for a raid."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT role FROM raid_signups WHERE raid_id = ? AND user_id = ?",
                (raid_id, user_id),
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def upsert_signup(self, raid_id: int, user_id: int, role: str) -> None:
        """Insert or update a signup."""
        await self.initialize()
        joined_at = int(datetime.now(timezone.utc).timestamp())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO raid_signups (raid_id, user_id, role, joined_at, preferred_role)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(raid_id, user_id)
                DO UPDATE SET role = excluded.role,
                              joined_at = excluded.joined_at,
                              preferred_role = excluded.preferred_role,
                              confirmed = 0
                """,
                (raid_id, user_id, role, joined_at, None),
            )
            await db.commit()

    async def upsert_signup_with_preference(
        self,
        raid_id: int,
        user_id: int,
        role: str,
        preferred_role: Optional[str],
    ) -> None:
        """Insert or update a signup with optional preferred role."""
        await self.initialize()
        joined_at = int(datetime.now(timezone.utc).timestamp())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO raid_signups (raid_id, user_id, role, joined_at, preferred_role)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(raid_id, user_id)
                DO UPDATE SET role = excluded.role,
                              joined_at = excluded.joined_at,
                              preferred_role = excluded.preferred_role,
                              confirmed = 0
                """,
                (raid_id, user_id, role, joined_at, preferred_role),
            )
            await db.commit()

    async def remove_signup(self, raid_id: int, user_id: int) -> None:
        """Remove a signup entry."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM raid_signups WHERE raid_id = ? AND user_id = ?",
                (raid_id, user_id),
            )
            await db.commit()

    async def close_raid(self, raid_id: int, closed_at: Optional[int] = None) -> None:
        """Mark a raid as closed."""
        await self.initialize()
        timestamp = closed_at or int(datetime.now(timezone.utc).timestamp())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE raids SET status = 'closed', closed_at = ? WHERE id = ?",
                (timestamp, raid_id),
            )
            await db.commit()

    async def update_status(self, raid_id: int, status: str) -> None:
        """Update raid status."""
        await self.initialize()
        closed_at = None
        if status in ("closed", "cancelled"):
            closed_at = int(datetime.now(timezone.utc).timestamp())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE raids SET status = ?, closed_at = ? WHERE id = ?",
                (status, closed_at, raid_id),
            )
            await db.commit()

    async def update_raid_details(
        self,
        raid_id: int,
        title: str,
        description: Optional[str],
        start_time: int,
    ) -> None:
        """Update title/description/start time for a raid."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE raids
                SET title = ?, description = ?, start_time = ?
                WHERE id = ?
                """,
                (title, description, start_time, raid_id),
            )
            await db.execute("DELETE FROM raid_reminders WHERE raid_id = ?", (raid_id,))
            await db.commit()

    async def update_raid_slots(
        self,
        raid_id: int,
        tanks_needed: int,
        healers_needed: int,
        dps_needed: int,
        bench_needed: int,
    ) -> None:
        """Update role slot counts for a raid."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE raids
                SET tanks_needed = ?, healers_needed = ?, dps_needed = ?, bench_needed = ?
                WHERE id = ?
                """,
                (tanks_needed, healers_needed, dps_needed, bench_needed, raid_id),
            )
            await db.commit()

    async def list_raids_to_close(self, now_ts: int) -> List[RaidRecord]:
        """Return open/locked raids with start_time <= now_ts."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, guild_id, channel_id, message_id, creator_id, title, description,
                       start_time, tanks_needed, healers_needed, dps_needed, bench_needed,
                       status, created_at, closed_at
                FROM raids
                WHERE status IN ('open', 'locked') AND start_time <= ?
                """,
                (now_ts,),
            )
            rows = await cursor.fetchall()
            return [self._row_to_record(row) for row in rows]

    async def list_active_raids(self, now_ts: int) -> List[RaidRecord]:
        """Return open/locked raids that have not started yet."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, guild_id, channel_id, message_id, creator_id, title, description,
                       start_time, tanks_needed, healers_needed, dps_needed, bench_needed,
                       status, created_at, closed_at
                FROM raids
                WHERE status IN ('open', 'locked') AND start_time > ?
                ORDER BY start_time ASC
                """,
                (now_ts,),
            )
            rows = await cursor.fetchall()
            return [self._row_to_record(row) for row in rows]

    async def list_raids_past_grace(
        self,
        now_ts: int,
        grace_seconds: int,
    ) -> List[RaidRecord]:
        """Return open/locked raids that passed start_time + grace."""
        await self.initialize()
        cutoff = now_ts - grace_seconds
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, guild_id, channel_id, message_id, creator_id, title, description,
                       start_time, tanks_needed, healers_needed, dps_needed, bench_needed,
                       status, created_at, closed_at
                FROM raids
                WHERE status IN ('open', 'locked') AND start_time <= ?
                """,
                (cutoff,),
            )
            rows = await cursor.fetchall()
            return [self._row_to_record(row) for row in rows]

    async def list_upcoming_raids(self, now_ts: int, limit: int = 10) -> List[RaidRecord]:
        """Return upcoming raids for listing."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, guild_id, channel_id, message_id, creator_id, title, description,
                       start_time, tanks_needed, healers_needed, dps_needed, bench_needed,
                       status, created_at, closed_at
                FROM raids
                WHERE status IN ('open', 'locked') AND start_time > ?
                ORDER BY start_time ASC
                LIMIT ?
                """,
                (now_ts, limit),
            )
            rows = await cursor.fetchall()
            return [self._row_to_record(row) for row in rows]

    async def list_recent_raids(
        self,
        limit: int = 5,
        statuses: Optional[tuple[str, ...]] = None,
    ) -> List[RaidRecord]:
        """Return recently closed raids."""
        await self.initialize()
        status_values = statuses or ("closed", "auto-closed")
        placeholders = ",".join("?" for _ in status_values)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                f"""
                SELECT id, guild_id, channel_id, message_id, creator_id, title, description,
                       start_time, tanks_needed, healers_needed, dps_needed, bench_needed,
                       status, created_at, closed_at
                FROM raids
                WHERE status IN ({placeholders})
                ORDER BY closed_at DESC, start_time DESC
                LIMIT ?
                """,
                (*status_values, limit),
            )
            rows = await cursor.fetchall()
            return [self._row_to_record(row) for row in rows]

    async def list_signups(self, raid_id: int) -> List[Dict[str, Optional[str]]]:
        """Return signups with role details."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT user_id, role, preferred_role, joined_at, confirmed
                FROM raid_signups
                WHERE raid_id = ?
                ORDER BY joined_at ASC
                """,
                (raid_id,),
            )
            rows = await cursor.fetchall()
            return [
                {
                    "user_id": int(row[0]),
                    "role": row[1],
                    "preferred_role": row[2],
                    "joined_at": int(row[3]),
                    "confirmed": int(row[4] or 0),
                }
                for row in rows
            ]

    async def reset_confirmations(self, raid_id: int) -> None:
        """Reset confirmations for a raid."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE raid_signups SET confirmed = 0 WHERE raid_id = ?",
                (raid_id,),
            )
            await db.commit()

    async def set_signup_confirmed(
        self,
        raid_id: int,
        user_id: int,
        confirmed: bool,
    ) -> None:
        """Set confirmation state for a signup."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE raid_signups SET confirmed = ? WHERE raid_id = ? AND user_id = ?",
                (1 if confirmed else 0, raid_id, user_id),
            )
            await db.commit()

    async def mark_no_shows(self, raid_id: int) -> List[int]:
        """Mark unconfirmed signups as no-shows and return their IDs."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT user_id
                FROM raid_signups
                WHERE raid_id = ? AND confirmed = 0
                """,
                (raid_id,),
            )
            rows = await cursor.fetchall()
            user_ids = [int(row[0]) for row in rows]
            if user_ids:
                await db.execute(
                    "UPDATE raid_signups SET confirmed = 2 WHERE raid_id = ? AND confirmed = 0",
                    (raid_id,),
                )
            await db.commit()
            return user_ids

    async def archive_participation(self, raid_id: int, status: str) -> None:
        """Archive signups into participation history."""
        await self.initialize()
        recorded_at = int(datetime.now(timezone.utc).timestamp())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO raid_participation (
                    raid_id, user_id, role, status, confirmed, joined_at, recorded_at
                )
                SELECT raid_id, user_id, role, ?, confirmed, joined_at, ?
                FROM raid_signups
                WHERE raid_id = ?
                """,
                (status, recorded_at, raid_id),
            )
            await db.commit()

    async def get_user_participation_summary(
        self,
        user_id: int,
        include_cancelled: bool = False,
    ) -> Dict[str, int]:
        """Return participation counts by role for a user."""
        await self.initialize()
        statuses = ("closed", "auto-closed")
        if include_cancelled:
            statuses = ("closed", "auto-closed", "cancelled")
        placeholders = ",".join("?" for _ in statuses)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                f"""
                SELECT role, COUNT(*)
                FROM raid_participation
                WHERE user_id = ? AND status IN ({placeholders})
                GROUP BY role
                """,
                (user_id, *statuses),
            )
            rows = await cursor.fetchall()
            summary = {row[0]: int(row[1]) for row in rows}
            summary["total"] = sum(summary.values())
            return summary

    async def get_participation_leaderboard(
        self,
        limit: int = 10,
        include_cancelled: bool = False,
    ) -> List[Dict[str, int]]:
        """Return top participants with per-role counts."""
        await self.initialize()
        statuses = ("closed", "auto-closed")
        if include_cancelled:
            statuses = ("closed", "auto-closed", "cancelled")
        placeholders = ",".join("?" for _ in statuses)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                f"""
                SELECT user_id, role, COUNT(*)
                FROM raid_participation
                WHERE status IN ({placeholders})
                GROUP BY user_id, role
                """,
                (*statuses,),
            )
            rows = await cursor.fetchall()

        totals: Dict[int, Dict[str, int]] = {}
        for row in rows:
            user_id = int(row[0])
            role = str(row[1])
            count = int(row[2])
            entry = totals.setdefault(user_id, {"total": 0})
            entry[role] = entry.get(role, 0) + count
            entry["total"] += count

        leaderboard = [
            {"user_id": user_id, **counts} for user_id, counts in totals.items()
        ]
        leaderboard.sort(key=lambda item: item.get("total", 0), reverse=True)
        return leaderboard[: max(0, int(limit))]

    async def add_leave_request(
        self,
        user_id: int,
        raid_id: int,
        expires_at: int,
    ) -> None:
        """Store a leave-reason request."""
        await self.initialize()
        requested_at = int(datetime.now(timezone.utc).timestamp())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO raid_leave_requests (
                    user_id, raid_id, requested_at, expires_at
                ) VALUES (?, ?, ?, ?)
                """,
                (user_id, raid_id, requested_at, expires_at),
            )
            await db.commit()

    async def get_latest_leave_request(self, user_id: int) -> Optional[Dict[str, int]]:
        """Return the latest leave request for a user."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT raid_id, requested_at, expires_at
                FROM raid_leave_requests
                WHERE user_id = ?
                ORDER BY requested_at DESC
                LIMIT 1
                """,
                (user_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "raid_id": int(row[0]),
                "requested_at": int(row[1]),
                "expires_at": int(row[2]),
            }

    async def clear_leave_request(self, user_id: int, raid_id: int) -> None:
        """Remove a leave request."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM raid_leave_requests WHERE user_id = ? AND raid_id = ?",
                (user_id, raid_id),
            )
            await db.commit()

    async def add_leave_reason(self, raid_id: int, user_id: int, reason: str) -> None:
        """Store a leave reason."""
        await self.initialize()
        created_at = int(datetime.now(timezone.utc).timestamp())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO raid_leave_reasons (
                    raid_id, user_id, reason, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (raid_id, user_id, reason, created_at),
            )
            await db.commit()

    async def list_leave_reasons(self, raid_id: int) -> List[Dict[str, str]]:
        """Return leave reasons for a raid."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT user_id, reason
                FROM raid_leave_reasons
                WHERE raid_id = ?
                ORDER BY created_at ASC
                """,
                (raid_id,),
            )
            rows = await cursor.fetchall()
            return [
                {"user_id": int(row[0]), "reason": row[1]}
                for row in rows
            ]

    async def get_confirmed_user_ids(self, raid_id: int) -> List[int]:
        """Return confirmed signup user IDs."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT user_id
                FROM raid_signups
                WHERE raid_id = ? AND confirmed = 1
                """,
                (raid_id,),
            )
            rows = await cursor.fetchall()
            return [int(row[0]) for row in rows]

    async def get_unconfirmed_user_ids(self, raid_id: int) -> List[int]:
        """Return unconfirmed signup user IDs."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT user_id
                FROM raid_signups
                WHERE raid_id = ? AND confirmed = 0
                """,
                (raid_id,),
            )
            rows = await cursor.fetchall()
            return [int(row[0]) for row in rows]

    async def get_no_show_user_ids(self, raid_id: int) -> List[int]:
        """Return no-show user IDs."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT user_id
                FROM raid_signups
                WHERE raid_id = ? AND confirmed = 2
                """,
                (raid_id,),
            )
            rows = await cursor.fetchall()
            return [int(row[0]) for row in rows]

    async def set_confirmation_message(self, raid_id: int, message_id: int) -> None:
        """Store confirmation message for a raid."""
        await self.initialize()
        created_at = int(datetime.now(timezone.utc).timestamp())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO raid_confirmations (raid_id, message_id, created_at)
                VALUES (?, ?, ?)
                """,
                (raid_id, message_id, created_at),
            )
            await db.commit()

    async def get_confirmation_message_id(self, raid_id: int) -> Optional[int]:
        """Return confirmation message ID for a raid."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT message_id FROM raid_confirmations WHERE raid_id = ?",
                (raid_id,),
            )
            row = await cursor.fetchone()
            return int(row[0]) if row else None

    async def clear_confirmation_message(self, raid_id: int) -> None:
        """Remove stored confirmation message for a raid."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM raid_confirmations WHERE raid_id = ?",
                (raid_id,),
            )
            await db.commit()

    async def get_confirmation_raid_id(self, message_id: int) -> Optional[int]:
        """Return raid ID for a confirmation message."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT raid_id FROM raid_confirmations WHERE message_id = ?",
                (message_id,),
            )
            row = await cursor.fetchone()
            return int(row[0]) if row else None

    async def mark_alert_sent(self, raid_id: int, alert_type: str) -> None:
        """Mark a raid alert as sent."""
        await self.initialize()
        sent_at = int(datetime.now(timezone.utc).timestamp())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO raid_alerts (raid_id, alert_type, sent_at)
                VALUES (?, ?, ?)
                """,
                (raid_id, alert_type, sent_at),
            )
            await db.commit()

    async def get_alert_sent_at(self, raid_id: int, alert_type: str) -> Optional[int]:
        """Return timestamp of last alert."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT sent_at FROM raid_alerts WHERE raid_id = ? AND alert_type = ?",
                (raid_id, alert_type),
            )
            row = await cursor.fetchone()
            return int(row[0]) if row else None

    async def get_bench_queue(
        self,
        raid_id: int,
        preferred_role: Optional[str] = None,
    ) -> List[int]:
        """Return bench users ordered by join time."""
        await self.initialize()
        query = (
            "SELECT user_id FROM raid_signups WHERE raid_id = ? AND role = 'bench' "
        )
        params = [raid_id]
        if preferred_role:
            query += "AND preferred_role = ? "
            params.append(preferred_role)
        else:
            query += "AND preferred_role IS NULL "
        query += "ORDER BY joined_at ASC"

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(query, tuple(params))
            rows = await cursor.fetchall()
            return [int(row[0]) for row in rows]

    async def count_user_active_signups(self, guild_id: int, user_id: int) -> int:
        """Count active raids for a user."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT COUNT(*)
                FROM raid_signups s
                JOIN raids r ON s.raid_id = r.id
                WHERE s.user_id = ?
                  AND r.guild_id = ?
                  AND r.status IN ('open', 'locked')
                """,
                (user_id, guild_id),
            )
            row = await cursor.fetchone()
            return int(row[0]) if row else 0

    async def get_sent_reminders(self, raid_ids: List[int]) -> Dict[int, List[int]]:
        """Return sent reminders for raids."""
        await self.initialize()
        if not raid_ids:
            return {}
        placeholders = ",".join("?" for _ in raid_ids)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                f"""
                SELECT raid_id, reminder_hours
                FROM raid_reminders
                WHERE raid_id IN ({placeholders})
                """,
                tuple(raid_ids),
            )
            rows = await cursor.fetchall()
            result: Dict[int, List[int]] = {}
            for raid_id, hours in rows:
                result.setdefault(int(raid_id), []).append(int(hours))
            return result

    async def mark_reminder_sent(self, raid_id: int, reminder_hours: int) -> None:
        """Mark a reminder as sent."""
        await self.initialize()
        sent_at = int(datetime.now(timezone.utc).timestamp())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO raid_reminders (raid_id, reminder_hours, sent_at)
                VALUES (?, ?, ?)
                """,
                (raid_id, reminder_hours, sent_at),
            )
            await db.commit()
