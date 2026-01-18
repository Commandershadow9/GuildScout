"""SQLite storage for web UI sessions and guild settings."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import aiosqlite


@dataclass(frozen=True)
class WebSession:
    session_id: str
    user_id: int
    username: str
    access_token: str
    refresh_token: str
    expires_at: int
    created_at: int
    avatar: Optional[str] = None


@dataclass(frozen=True)
class GuildSettings:
    guild_id: int
    name: str
    raid_channel_id: Optional[int]
    guildwar_channel_id: Optional[int]
    info_channel_id: Optional[int]
    log_channel_id: Optional[int]
    participant_role_id: Optional[int]
    creator_roles: list[int]
    timezone: str
    reminder_hours: list[int]
    dm_reminder_minutes: list[int]
    checkin_enabled: bool
    open_slot_ping_enabled: bool
    auto_close_at_start: bool
    auto_close_after_hours: int
    confirmation_minutes: int
    confirmation_reminder_minutes: int
    open_slot_ping_minutes: int


class WebStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS web_sessions (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    avatar TEXT,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    raid_channel_id INTEGER,
                    guildwar_channel_id INTEGER,
                    info_channel_id INTEGER,
                    log_channel_id INTEGER,
                    participant_role_id INTEGER,
                    creator_roles TEXT NOT NULL,
                    timezone TEXT NOT NULL,
                    reminder_hours TEXT NOT NULL,
                    dm_reminder_minutes TEXT NOT NULL,
                    checkin_enabled INTEGER NOT NULL,
                    open_slot_ping_enabled INTEGER NOT NULL,
                    auto_close_at_start INTEGER NOT NULL,
                    auto_close_after_hours INTEGER NOT NULL,
                    confirmation_minutes INTEGER NOT NULL,
                    confirmation_reminder_minutes INTEGER NOT NULL,
                    open_slot_ping_minutes INTEGER NOT NULL
                )
                """
            )
            await db.commit()
        self._initialized = True

    async def create_session(self, session: WebSession) -> None:
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO web_sessions (
                    id, user_id, username, avatar,
                    access_token, refresh_token,
                    expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.user_id,
                    session.username,
                    session.avatar,
                    session.access_token,
                    session.refresh_token,
                    session.expires_at,
                    session.created_at,
                ),
            )
            await db.commit()

    async def get_session(self, session_id: str) -> Optional[WebSession]:
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id, user_id, username, avatar, access_token, refresh_token, "
                "expires_at, created_at FROM web_sessions WHERE id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        return WebSession(
            session_id=row[0],
            user_id=row[1],
            username=row[2],
            avatar=row[3],
            access_token=row[4],
            refresh_token=row[5],
            expires_at=row[6],
            created_at=row[7],
        )

    async def delete_session(self, session_id: str) -> None:
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM web_sessions WHERE id = ?", (session_id,))
            await db.commit()

    async def purge_expired_sessions(self) -> None:
        await self.initialize()
        now_ts = int(time.time())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM web_sessions WHERE expires_at < ?",
                (now_ts,),
            )
            await db.commit()

    async def get_guild_settings(self, guild_id: int) -> Optional[GuildSettings]:
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT guild_id, name, raid_channel_id, guildwar_channel_id, "
                "info_channel_id, log_channel_id, participant_role_id, creator_roles, "
                "timezone, reminder_hours, dm_reminder_minutes, checkin_enabled, "
                "open_slot_ping_enabled, auto_close_at_start, auto_close_after_hours, "
                "confirmation_minutes, confirmation_reminder_minutes, open_slot_ping_minutes "
                "FROM guild_settings WHERE guild_id = ?",
                (guild_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        return GuildSettings(
            guild_id=row[0],
            name=row[1],
            raid_channel_id=row[2],
            guildwar_channel_id=row[3],
            info_channel_id=row[4],
            log_channel_id=row[5],
            participant_role_id=row[6],
            creator_roles=json.loads(row[7]) if row[7] else [],
            timezone=row[8],
            reminder_hours=json.loads(row[9]) if row[9] else [],
            dm_reminder_minutes=json.loads(row[10]) if row[10] else [],
            checkin_enabled=bool(row[11]),
            open_slot_ping_enabled=bool(row[12]),
            auto_close_at_start=bool(row[13]),
            auto_close_after_hours=int(row[14]),
            confirmation_minutes=int(row[15]),
            confirmation_reminder_minutes=int(row[16]),
            open_slot_ping_minutes=int(row[17]),
        )

    async def upsert_guild_settings(self, settings: GuildSettings) -> None:
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO guild_settings (
                    guild_id, name, raid_channel_id, guildwar_channel_id,
                    info_channel_id, log_channel_id, participant_role_id,
                    creator_roles, timezone, reminder_hours, dm_reminder_minutes,
                    checkin_enabled, open_slot_ping_enabled, auto_close_at_start,
                    auto_close_after_hours, confirmation_minutes,
                    confirmation_reminder_minutes, open_slot_ping_minutes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    name=excluded.name,
                    raid_channel_id=excluded.raid_channel_id,
                    guildwar_channel_id=excluded.guildwar_channel_id,
                    info_channel_id=excluded.info_channel_id,
                    log_channel_id=excluded.log_channel_id,
                    participant_role_id=excluded.participant_role_id,
                    creator_roles=excluded.creator_roles,
                    timezone=excluded.timezone,
                    reminder_hours=excluded.reminder_hours,
                    dm_reminder_minutes=excluded.dm_reminder_minutes,
                    checkin_enabled=excluded.checkin_enabled,
                    open_slot_ping_enabled=excluded.open_slot_ping_enabled,
                    auto_close_at_start=excluded.auto_close_at_start,
                    auto_close_after_hours=excluded.auto_close_after_hours,
                    confirmation_minutes=excluded.confirmation_minutes,
                    confirmation_reminder_minutes=excluded.confirmation_reminder_minutes,
                    open_slot_ping_minutes=excluded.open_slot_ping_minutes
                """,
                (
                    settings.guild_id,
                    settings.name,
                    settings.raid_channel_id,
                    settings.guildwar_channel_id,
                    settings.info_channel_id,
                    settings.log_channel_id,
                    settings.participant_role_id,
                    json.dumps(settings.creator_roles),
                    settings.timezone,
                    json.dumps(settings.reminder_hours),
                    json.dumps(settings.dm_reminder_minutes),
                    int(settings.checkin_enabled),
                    int(settings.open_slot_ping_enabled),
                    int(settings.auto_close_at_start),
                    int(settings.auto_close_after_hours),
                    int(settings.confirmation_minutes),
                    int(settings.confirmation_reminder_minutes),
                    int(settings.open_slot_ping_minutes),
                ),
            )
            await db.commit()


__all__ = [
    "WebStore",
    "WebSession",
    "GuildSettings",
]
