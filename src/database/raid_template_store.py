"""SQLite storage for raid slot templates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import aiosqlite


DEFAULT_TEMPLATE_SPECS = [
    {"name": "Standard", "tanks": 2, "healers": 2, "dps": 6, "bench": 0, "is_default": True},
    {"name": "Small", "tanks": 1, "healers": 1, "dps": 3, "bench": 0, "is_default": False},
    {"name": "Large", "tanks": 3, "healers": 3, "dps": 9, "bench": 2, "is_default": False},
]


@dataclass(frozen=True)
class RaidTemplate:
    template_id: int
    guild_id: int
    name: str
    tanks: int
    healers: int
    dps: int
    bench: int
    is_default: bool

    def to_counts(self) -> Dict[str, int]:
        return {
            "tank": self.tanks,
            "healer": self.healers,
            "dps": self.dps,
            "bench": self.bench,
        }


class RaidTemplateStore:
    def __init__(self, db_path: str = "data/web_ui.db"):
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
                CREATE TABLE IF NOT EXISTS raid_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    tanks INTEGER NOT NULL,
                    healers INTEGER NOT NULL,
                    dps INTEGER NOT NULL,
                    bench INTEGER NOT NULL,
                    is_default INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_raid_templates_guild ON raid_templates(guild_id)"
            )
            await db.commit()
        self._initialized = True

    def _row_to_template(self, row) -> RaidTemplate:
        return RaidTemplate(
            template_id=row[0],
            guild_id=row[1],
            name=row[2],
            tanks=row[3],
            healers=row[4],
            dps=row[5],
            bench=row[6],
            is_default=bool(row[7]),
        )

    async def list_templates(self, guild_id: int) -> List[RaidTemplate]:
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id, guild_id, name, tanks, healers, dps, bench, is_default "
                "FROM raid_templates WHERE guild_id = ? ORDER BY is_default DESC, name ASC",
                (guild_id,),
            )
            rows = await cursor.fetchall()
        return [self._row_to_template(row) for row in rows]

    async def ensure_default_templates(self, guild_id: int) -> None:
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM raid_templates WHERE guild_id = ?",
                (guild_id,),
            )
            count = (await cursor.fetchone())[0]
            if count:
                return
            for spec in DEFAULT_TEMPLATE_SPECS:
                await db.execute(
                    """
                    INSERT INTO raid_templates (guild_id, name, tanks, healers, dps, bench, is_default)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        guild_id,
                        spec["name"],
                        spec["tanks"],
                        spec["healers"],
                        spec["dps"],
                        spec["bench"],
                        int(spec["is_default"]),
                    ),
                )
            await db.commit()

    async def create_template(
        self,
        guild_id: int,
        name: str,
        tanks: int,
        healers: int,
        dps: int,
        bench: int,
        is_default: bool = False,
    ) -> int:
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            if is_default:
                await db.execute(
                    "UPDATE raid_templates SET is_default = 0 WHERE guild_id = ?",
                    (guild_id,),
                )
            cursor = await db.execute(
                """
                INSERT INTO raid_templates (guild_id, name, tanks, healers, dps, bench, is_default)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (guild_id, name, tanks, healers, dps, bench, int(is_default)),
            )
            await db.commit()
            return cursor.lastrowid

    async def update_template(
        self,
        template_id: int,
        name: str,
        tanks: int,
        healers: int,
        dps: int,
        bench: int,
        is_default: bool,
    ) -> None:
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            if is_default:
                await db.execute(
                    "UPDATE raid_templates SET is_default = 0 WHERE id != ? AND guild_id = (SELECT guild_id FROM raid_templates WHERE id = ?)",
                    (template_id, template_id),
                )
            await db.execute(
                """
                UPDATE raid_templates
                SET name = ?, tanks = ?, healers = ?, dps = ?, bench = ?, is_default = ?
                WHERE id = ?
                """,
                (name, tanks, healers, dps, bench, int(is_default), template_id),
            )
            await db.commit()

    async def delete_template(self, template_id: int) -> None:
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM raid_templates WHERE id = ?", (template_id,))
            await db.commit()

    async def set_default_template(self, template_id: int) -> None:
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE raid_templates SET is_default = 0 WHERE id != ? AND guild_id = (SELECT guild_id FROM raid_templates WHERE id = ?)",
                (template_id, template_id),
            )
            await db.execute(
                "UPDATE raid_templates SET is_default = 1 WHERE id = ?",
                (template_id,),
            )
            await db.commit()


__all__ = ["RaidTemplateStore", "RaidTemplate", "DEFAULT_TEMPLATE_SPECS"]
