"""SQLite caching system for message counts."""

import aiosqlite
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
import json


logger = logging.getLogger("guildscout.cache")


class MessageCache:
    """SQLite-based cache for user message counts."""

    def __init__(self, db_path: str = "data/cache.db", ttl: Optional[int] = None):
        """
        Initialize the message cache.

        Args:
            db_path: Path to SQLite database file
            ttl: Cache time-to-live in seconds (None = never expires)
        """
        self.db_path = Path(db_path)
        self.ttl = ttl

        # Create data directory if it doesn't exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._initialized = False

    async def initialize(self):
        """Initialize the database schema."""
        if self._initialized:
            return

        async with aiosqlite.connect(self.db_path) as db:
            # Create message counts table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS message_counts (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    message_count INTEGER NOT NULL,
                    last_updated TEXT NOT NULL,
                    days_lookback INTEGER,
                    excluded_channels TEXT,
                    PRIMARY KEY (guild_id, user_id, days_lookback, excluded_channels)
                )
            """)

            # Create index for faster lookups
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_guild_user
                ON message_counts(guild_id, user_id)
            """)

            # Create metadata table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cache_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            await db.commit()

        self._initialized = True
        logger.info(f"Cache initialized at {self.db_path}")

    def _make_cache_key(
        self,
        guild_id: int,
        user_id: int,
        days_lookback: Optional[int],
        excluded_channels: list
    ) -> tuple:
        """
        Create a cache key from parameters.

        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            days_lookback: Days to look back
            excluded_channels: List of excluded channel IDs

        Returns:
            Tuple cache key
        """
        # Sort excluded channels for consistent hashing
        excluded_str = json.dumps(sorted(excluded_channels))
        return (guild_id, user_id, days_lookback, excluded_str)

    async def get(
        self,
        guild_id: int,
        user_id: int,
        days_lookback: Optional[int] = None,
        excluded_channels: Optional[list] = None
    ) -> Optional[int]:
        """
        Get cached message count for a user.

        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            days_lookback: Days to look back
            excluded_channels: List of excluded channel IDs

        Returns:
            Cached message count or None if not found/expired
        """
        await self.initialize()

        if excluded_channels is None:
            excluded_channels = []

        excluded_str = json.dumps(sorted(excluded_channels))

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT message_count, last_updated
                FROM message_counts
                WHERE guild_id = ?
                AND user_id = ?
                AND days_lookback IS ?
                AND excluded_channels = ?
                """,
                (guild_id, user_id, days_lookback, excluded_str)
            )

            row = await cursor.fetchone()

            if row is None:
                logger.debug(f"Cache miss for user {user_id}")
                return None

            message_count, last_updated_str = row
            last_updated = datetime.fromisoformat(last_updated_str)

            # Check if cache is expired (only if TTL is set)
            # If TTL is None or 0, cache never expires
            if self.ttl is not None and self.ttl > 0:
                if datetime.now(timezone.utc) - last_updated > timedelta(seconds=self.ttl):
                    logger.debug(f"Cache expired for user {user_id}")
                    return None

            logger.debug(f"Cache hit for user {user_id}: {message_count} messages")
            return message_count

    async def set(
        self,
        guild_id: int,
        user_id: int,
        message_count: int,
        days_lookback: Optional[int] = None,
        excluded_channels: Optional[list] = None
    ):
        """
        Cache a user's message count.

        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            message_count: Message count to cache
            days_lookback: Days to look back
            excluded_channels: List of excluded channel IDs
        """
        await self.initialize()

        if excluded_channels is None:
            excluded_channels = []

        excluded_str = json.dumps(sorted(excluded_channels))
        now = datetime.now(timezone.utc).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO message_counts
                (guild_id, user_id, message_count, last_updated, days_lookback, excluded_channels)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (guild_id, user_id, message_count, now, days_lookback, excluded_str)
            )
            await db.commit()

        logger.debug(f"Cached {message_count} messages for user {user_id}")

    async def clear_user(self, guild_id: int, user_id: int):
        """
        Clear cache for a specific user.

        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM message_counts WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            )
            await db.commit()

        logger.info(f"Cleared cache for user {user_id}")

    async def clear_guild(self, guild_id: int):
        """
        Clear all cache for a guild.

        Args:
            guild_id: Discord guild ID
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM message_counts WHERE guild_id = ?",
                (guild_id,)
            )
            await db.commit()
            deleted = cursor.rowcount

        logger.info(f"Cleared cache for guild {guild_id} ({deleted} entries)")
        return deleted

    async def clear_all(self):
        """Clear entire cache."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM message_counts")
            await db.commit()
            deleted = cursor.rowcount

        logger.info(f"Cleared entire cache ({deleted} entries)")
        return deleted

    async def get_stats(self) -> Dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            # Total entries
            cursor = await db.execute("SELECT COUNT(*) FROM message_counts")
            total_entries = (await cursor.fetchone())[0]

            # Expired entries (only if TTL is set)
            if self.ttl is not None and self.ttl > 0:
                cutoff = (datetime.now(timezone.utc) - timedelta(seconds=self.ttl)).isoformat()
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM message_counts WHERE last_updated < ?",
                    (cutoff,)
                )
                expired_entries = (await cursor.fetchone())[0]
            else:
                expired_entries = 0  # No expiration when TTL is None

            # Valid entries
            valid_entries = total_entries - expired_entries

            # Database size
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

        return {
            "total_entries": total_entries,
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "db_size_bytes": db_size,
            "db_size_mb": round(db_size / 1024 / 1024, 2),
            "ttl_seconds": self.ttl
        }

    async def cleanup_expired(self):
        """Remove expired entries from cache."""
        await self.initialize()

        # If TTL is None, nothing expires
        if self.ttl is None or self.ttl <= 0:
            logger.info("Cache TTL is disabled - no entries to clean up")
            return 0

        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=self.ttl)).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM message_counts WHERE last_updated < ?",
                (cutoff,)
            )
            await db.commit()
            deleted = cursor.rowcount

        logger.info(f"Cleaned up {deleted} expired cache entries")
        return deleted
