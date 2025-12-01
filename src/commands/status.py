"""Bot status command showing all system metrics."""

import discord
from discord import app_commands
from discord.ext import commands
import psutil
import os
from datetime import datetime, timedelta
from pathlib import Path

from src.utils import Config


class StatusCommand(commands.Cog):
    """Provides /status command for system overview."""

    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config
        self.start_time = datetime.utcnow()

    @app_commands.command(name="status", description="Shows bot system status and metrics")
    async def status_command(self, interaction: discord.Interaction):
        """Display comprehensive bot status."""
        await interaction.response.defer()

        # Get various metrics
        uptime = datetime.utcnow() - self.start_time
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / (1024 * 1024)

        # Database size
        db_path = Path("data/messages.db")
        db_size_mb = db_path.stat().st_size / (1024 * 1024) if db_path.exists() else 0

        # Rate limit stats
        from src.utils.rate_limit_monitor import get_monitor
        rate_monitor = get_monitor()
        rate_stats = rate_monitor.get_stats()

        # Dedup stats
        dedup_stats = {"total_seen": 0, "duplicates_blocked": 0}
        if hasattr(self.bot, 'message_tracking_cog'):
            cog = self.bot.message_tracking_cog
            if hasattr(cog, 'get_dedup_stats'):
                dedup_stats = cog.get_dedup_stats()

        # Last verification
        from src.utils.verification_stats import VerificationStats
        ver_stats = VerificationStats()
        last_ver = ver_stats.get_stats(self.config.guild_id)

        if last_ver:
            last_ver_time = last_ver.get('timestamp', 'Unknown')
            last_ver_acc = last_ver.get('accuracy_percent', 0)
            last_ver_status = f"{last_ver_acc:.1f}% accuracy"
        else:
            last_ver_time = "Never"
            last_ver_status = "No data"

        # ShadowOps Queue
        queue_size = 0
        if hasattr(self.bot, 'verification_scheduler_cog'):
            cog = self.bot.verification_scheduler_cog
            if hasattr(cog, 'shadowops_notifier'):
                queue_size = len(cog.shadowops_notifier.retry_queue)

        # Build embed
        embed = discord.Embed(
            title="🤖 GuildScout System Status",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )

        # Bot Status
        embed.add_field(
            name="⚙️ Bot Status",
            value=(
                f"**Uptime:** {self._format_timedelta(uptime)}\n"
                f"**Memory:** {memory_mb:.1f} MB\n"
                f"**Guilds:** {len(self.bot.guilds)}"
            ),
            inline=True
        )

        # Database
        db_status = "✅ OK" if db_size_mb < 100 else "⚠️ Large"
        embed.add_field(
            name="💾 Database",
            value=(
                f"**Size:** {db_size_mb:.1f} MB\n"
                f"**Status:** {db_status}"
            ),
            inline=True
        )

        # Rate Limits
        embed.add_field(
            name="📊 Rate Limits",
            value=(
                f"**Current:** {rate_stats['requests_per_second']} req/s\n"
                f"**Limit Hits:** {rate_stats['total_rate_limit_hits']}\n"
                f"**Status:** {rate_stats['status']}"
            ),
            inline=True
        )

        # Verification
        embed.add_field(
            name="🔍 Last Verification",
            value=(
                f"**Time:** {last_ver_time}\n"
                f"**Result:** {last_ver_status}"
            ),
            inline=True
        )

        # Deduplication
        total_seen = dedup_stats.get('total_seen', 0)
        duplicates = dedup_stats.get('duplicates_blocked', 0)
        dedup_rate = (duplicates / total_seen * 100) if total_seen > 0 else 0

        embed.add_field(
            name="🔄 Message Deduplication",
            value=(
                f"**Seen:** {total_seen:,}\n"
                f"**Blocked:** {duplicates:,}\n"
                f"**Rate:** {dedup_rate:.2f}%"
            ),
            inline=True
        )

        # ShadowOps Integration
        queue_status = "✅ Empty" if queue_size == 0 else f"📥 {queue_size} pending"
        embed.add_field(
            name="📡 ShadowOps Integration",
            value=(
                f"**Queue:** {queue_status}\n"
                f"**Enabled:** {'✅ Yes' if self.config.shadowops_enabled else '❌ No'}"
            ),
            inline=True
        )

        embed.set_footer(text="Use /profile for performance metrics")

        await interaction.followup.send(embed=embed)

    def _format_timedelta(self, td: timedelta) -> str:
        """Format timedelta as human-readable string."""
        days = td.days
        hours, remainder = divmod(td.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")

        return " ".join(parts)


async def setup(bot: commands.Bot, config: Config):
    """Add status command to bot."""
    await bot.add_cog(StatusCommand(bot, config))
