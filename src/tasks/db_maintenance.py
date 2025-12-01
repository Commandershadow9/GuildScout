"""SQLite database maintenance scheduler."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

import aiosqlite
from discord.ext import commands, tasks

from src.utils import Config

logger = logging.getLogger("guildscout.db_maintenance")


class DatabaseMaintenance(commands.Cog):
    """
    Performs regular SQLite database maintenance.

    Tasks:
    - VACUUM: Defragments database and reclaims unused space
    - ANALYZE: Updates query optimizer statistics for better performance
    """

    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config
        self.db_path = Path("data/messages.db")

        # Start weekly maintenance task (runs every Monday at 04:00 UTC)
        self.maintenance_task.start()
        logger.info("📊 Weekly database maintenance scheduled for Mondays at 04:00 UTC")

        # Start daily size monitoring (runs every 24 hours)
        self.size_monitor_task.start()
        logger.info("📏 Daily database size monitoring enabled")

    def cog_unload(self):
        self.maintenance_task.cancel()
        self.size_monitor_task.cancel()

    def get_db_size_mb(self) -> float:
        """Get current database size in MB."""
        if not self.db_path.exists():
            return 0.0
        return self.db_path.stat().st_size / (1024 * 1024)

    @tasks.loop(hours=168)  # Every 7 days (weekly)
    async def maintenance_task(self):
        """Perform weekly database maintenance."""
        await self.bot.wait_until_ready()

        # Calculate next Monday at 04:00 UTC
        now = datetime.utcnow()
        weekday = now.weekday()  # 0=Monday, 6=Sunday

        # Only run on Mondays between 04:00-05:00
        if weekday == 0 and 4 <= now.hour < 5:
            await self.run_maintenance()

    async def run_maintenance(self):
        """Run VACUUM and ANALYZE on the database."""
        if not self.db_path.exists():
            logger.warning("Database not found, skipping maintenance.")
            return

        try:
            start_time = datetime.utcnow()
            db_size_before = self.db_path.stat().st_size / (1024 * 1024)  # MB

            logger.info(f"🔧 Starting database maintenance (DB size: {db_size_before:.2f} MB)")

            async with aiosqlite.connect(self.db_path) as db:
                # VACUUM: Rebuilds database, reclaims space, defragments
                logger.info("🗜️ Running VACUUM...")
                await db.execute("VACUUM")

                # ANALYZE: Updates statistics for query optimizer
                logger.info("📊 Running ANALYZE...")
                await db.execute("ANALYZE")

                await db.commit()

            # Calculate results
            db_size_after = self.db_path.stat().st_size / (1024 * 1024)  # MB
            space_saved = db_size_before - db_size_after
            duration = (datetime.utcnow() - start_time).total_seconds()

            logger.info(
                f"✅ Database maintenance complete in {duration:.1f}s\n"
                f"   Size before: {db_size_before:.2f} MB\n"
                f"   Size after: {db_size_after:.2f} MB\n"
                f"   Space saved: {space_saved:.2f} MB ({space_saved/db_size_before*100:.1f}%)"
            )

            # Notify status channel
            if hasattr(self.bot, 'status_manager'):
                import discord
                guild = self.bot.get_guild(self.config.guild_id)
                if guild:
                    await self.bot.status_manager.send_temp_status(
                        guild,
                        title="🔧 Datenbank-Wartung abgeschlossen",
                        description=(
                            f"**VACUUM & ANALYZE** erfolgreich durchgeführt\n\n"
                            f"**Vorher:** {db_size_before:.2f} MB\n"
                            f"**Nachher:** {db_size_after:.2f} MB\n"
                            f"**Gespart:** {space_saved:.2f} MB ({space_saved/db_size_before*100:.1f}%)\n"
                            f"**Dauer:** {duration:.1f}s"
                        ),
                        color=discord.Color.blue()
                    )

        except Exception as e:
            logger.error(f"Database maintenance failed: {e}", exc_info=True)

            # Notify error
            if hasattr(self.bot, 'status_manager'):
                import discord
                guild = self.bot.get_guild(self.config.guild_id)
                if guild:
                    await self.bot.status_manager.send_error(
                        guild,
                        "❌ Datenbank-Wartung fehlgeschlagen",
                        f"VACUUM/ANALYZE konnte nicht durchgeführt werden:\n{e}",
                        color=discord.Color.red()
                    )

    @tasks.loop(hours=24)  # Daily
    async def size_monitor_task(self):
        """Monitor database size and warn if getting large."""
        await self.bot.wait_until_ready()

        db_size = self.get_db_size_mb()

        # Warn if > 100 MB
        if db_size > 100:
            logger.warning(f"⚠️ Database size: {db_size:.1f} MB (exceeds 100 MB threshold)")

            if hasattr(self.bot, 'status_manager'):
                import discord
                guild = self.bot.get_guild(self.config.guild_id)
                if guild:
                    await self.bot.status_manager.send_temp_status(
                        guild,
                        title="⚠️ Datenbank wird groß",
                        description=(
                            f"**Aktuelle Größe:** {db_size:.1f} MB\n\n"
                            f"Die Datenbank überschreitet 100 MB.\n"
                            f"Nächstes VACUUM wird automatisch Speicher freigeben."
                        ),
                        color=discord.Color.orange()
                    )
        elif db_size > 50:
            logger.info(f"📊 Database size: {db_size:.1f} MB")
        else:
            logger.debug(f"📊 Database size: {db_size:.1f} MB")


async def setup(bot: commands.Bot, config: Config):
    """Add the database maintenance scheduler to the bot."""
    await bot.add_cog(DatabaseMaintenance(bot, config))
