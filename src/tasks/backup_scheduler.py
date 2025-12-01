"Daily database backup scheduler."

import asyncio
import logging
from datetime import datetime, time
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands, tasks

from src.utils import Config

logger = logging.getLogger("guildscout.backups")


class BackupScheduler(commands.Cog):
    """Schedules daily backups of the SQLite database."""

    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config
        self.backup_dir = Path("backups")
        self.db_path = Path("data/messages.db")
        
        # Create backup directory
        self.backup_dir.mkdir(exist_ok=True)
        
        # Start backup task (runs daily at 05:00 UTC)
        self.backup_task.start()
        logger.info("Daily backup scheduled for 05:00 UTC")

    def cog_unload(self):
        self.backup_task.cancel()

    @tasks.loop(time=time(hour=5, minute=0))  # 05:00 UTC
    async def backup_task(self):
        """Perform daily backup."""
        await self.create_backup()

    async def create_backup(self):
        """Create a backup of the database and rotate old ones."""
        if not self.db_path.exists():
            logger.warning("No database found to backup.")
            return

        try:
            timestamp = datetime.utcnow().strftime("%Y-%m-%d")
            backup_file = self.backup_dir / f"messages_{timestamp}.db"

            # Use SQLite's atomic backup API for hot backup (safer than file copy)
            import aiosqlite
            async with aiosqlite.connect(self.db_path) as source:
                async with aiosqlite.connect(backup_file) as dest:
                    await source.backup(dest)

            logger.info(f"Created backup: {backup_file}")

            # Cleanup old backups (keep last 30 days)
            await self._cleanup_old_backups(days=30)

            # Notify status channel
            if hasattr(self.bot, 'status_manager'):
                guild = self.bot.get_guild(self.config.guild_id)
                if guild:
                    await self.bot.status_manager.send_temp_status(
                        guild,
                        title="💾 Backup erfolgreich",
                        description=f"Datenbank gesichert als: `{backup_file.name}`",
                        color=discord.Color.green()
                    )

        except Exception as e:
            logger.error(f"Backup failed: {e}", exc_info=True)
            # Notify error
            if hasattr(self.bot, 'status_manager'):
                guild = self.bot.get_guild(self.config.guild_id)
                if guild:
                    await self.bot.status_manager.send_error(
                        guild,
                        "❌ Backup Fehler",
                        f"Backup konnte nicht erstellt werden:\n{e}",
                        color=discord.Color.red()
                    )

    async def _cleanup_old_backups(self, days: int):
        """Remove backups older than X days."""
        try:
            now = datetime.utcnow()
            deleted = 0
            
            for file in self.backup_dir.glob("messages_*.db"):
                # Extract date from filename
                try:
                    date_str = file.stem.replace("messages_", "")
                    file_date = datetime.strptime(date_str, "%Y-%m-%d")
                    age_days = (now - file_date).days
                    
                    if age_days > days:
                        file.unlink()
                        deleted += 1
                        logger.info(f"Deleted old backup: {file.name} ({age_days} days old)")
                except ValueError:
                    continue  # Skip files with weird names

            if deleted > 0:
                logger.info(f"Cleanup complete: Removed {deleted} old backups.")

        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")

async def setup(bot: commands.Bot, config: Config):
    """Add the backup scheduler to the bot."""
    await bot.add_cog(BackupScheduler(bot, config))
