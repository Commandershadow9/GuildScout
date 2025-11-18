"""Persistent message tracking database for accurate message counts."""

import aiosqlite
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List
import discord


logger = logging.getLogger("guildscout.message_store")


class MessageStore:
    """SQLite-based persistent storage for message counts."""

    def __init__(self, db_path: str = "data/messages.db"):
        """
        Initialize the message store.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)

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
                    channel_id INTEGER NOT NULL,
                    message_count INTEGER NOT NULL DEFAULT 0,
                    last_message_date TEXT,
                    PRIMARY KEY (guild_id, user_id, channel_id)
                )
            """)

            # Create index for faster user lookups
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_guild_user
                ON message_counts(guild_id, user_id)
            """)

            # Create index for faster guild lookups
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_guild
                ON message_counts(guild_id)
            """)

            # Create metadata table for tracking import status
            await db.execute("""
                CREATE TABLE IF NOT EXISTS import_metadata (
                    guild_id INTEGER PRIMARY KEY,
                    import_completed INTEGER NOT NULL DEFAULT 0,
                    import_date TEXT,
                    import_start_time TEXT,
                    import_end_time TEXT,
                    total_messages_imported INTEGER DEFAULT 0
                )
            """)

            await db.commit()

        self._initialized = True
        logger.info(f"Message store initialized at {self.db_path}")

    async def increment_message(
        self,
        guild_id: int,
        user_id: int,
        channel_id: int,
        count: int = 1,
        message_date: Optional[datetime] = None
    ):
        """
        Increment message count for a user in a channel.

        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            channel_id: Discord channel ID
            count: Number of messages to add (default: 1)
            message_date: Date of the message (default: now)
        """
        await self.initialize()

        if message_date is None:
            message_date = datetime.now(timezone.utc)

        message_date_str = message_date.isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            # Insert or update the count
            await db.execute(
                """
                INSERT INTO message_counts
                (guild_id, user_id, channel_id, message_count, last_message_date)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id, channel_id)
                DO UPDATE SET
                    message_count = message_count + ?,
                    last_message_date = ?
                """,
                (guild_id, user_id, channel_id, count, message_date_str, count, message_date_str)
            )
            await db.commit()

    async def get_user_total(
        self,
        guild_id: int,
        user_id: int,
        excluded_channels: Optional[List[int]] = None
    ) -> int:
        """
        Get total message count for a user across all channels.

        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            excluded_channels: List of channel IDs to exclude

        Returns:
            Total message count
        """
        await self.initialize()

        if excluded_channels is None:
            excluded_channels = []

        async with aiosqlite.connect(self.db_path) as db:
            if excluded_channels:
                # Build query with excluded channels
                placeholders = ','.join('?' * len(excluded_channels))
                query = f"""
                    SELECT COALESCE(SUM(message_count), 0)
                    FROM message_counts
                    WHERE guild_id = ?
                    AND user_id = ?
                    AND channel_id NOT IN ({placeholders})
                """
                params = [guild_id, user_id] + excluded_channels
            else:
                # No excluded channels
                query = """
                    SELECT COALESCE(SUM(message_count), 0)
                    FROM message_counts
                    WHERE guild_id = ?
                    AND user_id = ?
                """
                params = [guild_id, user_id]

            cursor = await db.execute(query, params)
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_guild_totals(
        self,
        guild_id: int,
        excluded_channels: Optional[List[int]] = None
    ) -> Dict[int, int]:
        """
        Get message counts for all users in a guild.

        Args:
            guild_id: Discord guild ID
            excluded_channels: List of channel IDs to exclude

        Returns:
            Dictionary mapping user_id to message count
        """
        await self.initialize()

        if excluded_channels is None:
            excluded_channels = []

        async with aiosqlite.connect(self.db_path) as db:
            if excluded_channels:
                # Build query with excluded channels
                placeholders = ','.join('?' * len(excluded_channels))
                query = f"""
                    SELECT user_id, SUM(message_count) as total
                    FROM message_counts
                    WHERE guild_id = ?
                    AND channel_id NOT IN ({placeholders})
                    GROUP BY user_id
                """
                params = [guild_id] + excluded_channels
            else:
                # No excluded channels
                query = """
                    SELECT user_id, SUM(message_count) as total
                    FROM message_counts
                    WHERE guild_id = ?
                    GROUP BY user_id
                """
                params = [guild_id]

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

            return {row[0]: row[1] for row in rows}

    async def get_channel_breakdown(
        self,
        guild_id: int,
        user_id: int
    ) -> Dict[int, int]:
        """
        Get message count breakdown by channel for a user.

        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID

        Returns:
            Dictionary mapping channel_id to message count
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT channel_id, message_count
                FROM message_counts
                WHERE guild_id = ?
                AND user_id = ?
                """,
                (guild_id, user_id)
            )
            rows = await cursor.fetchall()

            return {row[0]: row[1] for row in rows}

    async def is_import_completed(self, guild_id: int) -> bool:
        """
        Check if historical data import is completed for a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            True if import is completed
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT import_completed FROM import_metadata WHERE guild_id = ?",
                (guild_id,)
            )
            row = await cursor.fetchone()

            return bool(row[0]) if row else False

    async def mark_import_started(self, guild_id: int):
        """
        Mark that historical data import has started for a guild.

        Args:
            guild_id: Discord guild ID
        """
        await self.initialize()

        import_start = datetime.now(timezone.utc).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO import_metadata
                (guild_id, import_completed, import_start_time)
                VALUES (?, 0, ?)
                """,
                (guild_id, import_start)
            )
            await db.commit()

        logger.info(f"Marked import as started for guild {guild_id}")

    async def mark_import_completed(
        self,
        guild_id: int,
        total_messages: int
    ):
        """
        Mark historical data import as completed for a guild.

        Args:
            guild_id: Discord guild ID
            total_messages: Total number of messages imported
        """
        await self.initialize()

        import_end = datetime.now(timezone.utc).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            # Update existing row to mark as completed
            await db.execute(
                """
                UPDATE import_metadata
                SET import_completed = 1,
                    import_date = ?,
                    import_end_time = ?,
                    total_messages_imported = ?
                WHERE guild_id = ?
                """,
                (import_end, import_end, total_messages, guild_id)
            )
            await db.commit()

        logger.info(f"Marked import as completed for guild {guild_id} ({total_messages} messages)")

    async def is_import_running(self, guild_id: int) -> bool:
        """
        Check if historical data import is currently running for a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            True if import is currently running
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT import_completed, import_start_time
                FROM import_metadata
                WHERE guild_id = ?
                """,
                (guild_id,)
            )
            row = await cursor.fetchone()

            if not row:
                return False

            import_completed, import_start_time = row

            # Import is running if it's started but not completed
            return bool(import_start_time) and not bool(import_completed)

    async def get_import_start_time(self, guild_id: int) -> Optional[datetime]:
        """
        Get the import start time for a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            Import start time as datetime, or None if not started
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT import_start_time FROM import_metadata WHERE guild_id = ?",
                (guild_id,)
            )
            row = await cursor.fetchone()

            if row and row[0]:
                return datetime.fromisoformat(row[0])

            return None

    async def reset_guild(self, guild_id: int):
        """
        Reset all data for a guild (for re-import).

        Args:
            guild_id: Discord guild ID
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM message_counts WHERE guild_id = ?",
                (guild_id,)
            )
            await db.execute(
                "DELETE FROM import_metadata WHERE guild_id = ?",
                (guild_id,)
            )
            await db.commit()

        logger.info(f"Reset all data for guild {guild_id}")

    async def get_stats(self, guild_id: int) -> Dict:
        """
        Get statistics for a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            Dictionary with statistics
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            # Total messages
            cursor = await db.execute(
                "SELECT COALESCE(SUM(message_count), 0) FROM message_counts WHERE guild_id = ?",
                (guild_id,)
            )
            total_messages = (await cursor.fetchone())[0]

            # Total users
            cursor = await db.execute(
                "SELECT COUNT(DISTINCT user_id) FROM message_counts WHERE guild_id = ?",
                (guild_id,)
            )
            total_users = (await cursor.fetchone())[0]

            # Total channels
            cursor = await db.execute(
                "SELECT COUNT(DISTINCT channel_id) FROM message_counts WHERE guild_id = ?",
                (guild_id,)
            )
            total_channels = (await cursor.fetchone())[0]

            # Import status
            cursor = await db.execute(
                "SELECT import_completed, import_date FROM import_metadata WHERE guild_id = ?",
                (guild_id,)
            )
            import_row = await cursor.fetchone()
            import_completed = bool(import_row[0]) if import_row else False
            import_date = import_row[1] if import_row else None

            # Database size
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

        return {
            "total_messages": total_messages,
            "total_users": total_users,
            "total_channels": total_channels,
            "import_completed": import_completed,
            "import_date": import_date,
            "db_size_bytes": db_size,
            "db_size_mb": round(db_size / 1024 / 1024, 2)
        }
