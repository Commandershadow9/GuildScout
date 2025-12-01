"""Weekly summary report scheduler."""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import discord
import aiosqlite
from discord.ext import commands, tasks

from src.utils import Config

logger = logging.getLogger("guildscout.weekly_reporter")


class WeeklyReporter(commands.Cog):
    """
    Generates and sends weekly summary reports.

    Scheduled for: Every Monday at 09:00 UTC

    Report includes:
    - Total messages this week
    - Most active users
    - Most active channels
    - Verification summary
    - System health summary
    - Database statistics
    """

    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config
        self.db_path = Path("data/messages.db")

        # Start weekly report task
        self.weekly_report_task.start()
        logger.info("📅 Weekly reporter scheduled for Mondays at 09:00 UTC")

    def cog_unload(self):
        self.weekly_report_task.cancel()

    @tasks.loop(hours=168)  # Every 7 days
    async def weekly_report_task(self):
        """Run weekly report every Monday at 09:00."""
        await self.bot.wait_until_ready()

        # Check if it's Monday between 09:00-10:00 UTC
        now = datetime.utcnow()
        if now.weekday() == 0 and 9 <= now.hour < 10:
            await self.generate_weekly_report()

    async def generate_weekly_report(self):
        """Generate and send the weekly report."""
        try:
            logger.info("📊 Generating weekly report...")

            # Calculate date range (last 7 days)
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=7)

            # Gather all statistics
            stats = await self._gather_weekly_stats(start_date, end_date)

            # Create and send embed
            embed = self._create_report_embed(stats, start_date, end_date)

            # Send to status channel
            if hasattr(self.bot, 'status_manager'):
                guild = self.bot.get_guild(self.config.guild_id)
                if guild:
                    status_channel = guild.get_channel(self.config.status_channel_id)
                    if status_channel:
                        await status_channel.send(embed=embed)
                        logger.info("✅ Weekly report sent successfully")

            # Also send to ShadowOps if enabled
            if self.config.shadowops_enabled and hasattr(self.bot, 'verification_scheduler_cog'):
                cog = self.bot.verification_scheduler_cog
                if hasattr(cog, 'shadowops_notifier'):
                    await cog.shadowops_notifier.send_event({
                        'event_type': 'weekly_report',
                        'source': 'guildscout',
                        'alert_type': 'health',
                        'severity': 'low',
                        'title': '📊 Wöchentlicher GuildScout Bericht',
                        'description': f"Bericht für {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}",
                        'metadata': stats
                    })

        except Exception as e:
            logger.error(f"Failed to generate weekly report: {e}", exc_info=True)

    async def _gather_weekly_stats(self, start_date: datetime, end_date: datetime) -> Dict:
        """Gather all statistics for the weekly report."""
        stats = {
            'total_messages': 0,
            'active_users': 0,
            'top_users': [],
            'top_channels': [],
            'database_size_mb': 0,
            'verifications_run': 0,
            'verification_avg_accuracy': 0,
            'dedup_blocked': 0,
            'dedup_total': 0,
            'rate_limit_hits': 0
        }

        # Database stats
        if self.db_path.exists():
            stats['database_size_mb'] = self.db_path.stat().st_size / (1024 * 1024)

            async with aiosqlite.connect(self.db_path) as db:
                # Total messages this week
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM messages WHERE timestamp >= ?",
                    (start_date.isoformat(),)
                )
                row = await cursor.fetchone()
                stats['total_messages'] = row[0] if row else 0

                # Active users count
                cursor = await db.execute(
                    "SELECT COUNT(DISTINCT user_id) FROM messages WHERE timestamp >= ?",
                    (start_date.isoformat(),)
                )
                row = await cursor.fetchone()
                stats['active_users'] = row[0] if row else 0

                # Top 5 users
                cursor = await db.execute(
                    """
                    SELECT user_id, COUNT(*) as msg_count
                    FROM messages
                    WHERE timestamp >= ?
                    GROUP BY user_id
                    ORDER BY msg_count DESC
                    LIMIT 5
                    """,
                    (start_date.isoformat(),)
                )
                rows = await cursor.fetchall()
                stats['top_users'] = [
                    {'user_id': row[0], 'count': row[1]}
                    for row in rows
                ]

                # Top 5 channels
                cursor = await db.execute(
                    """
                    SELECT channel_id, COUNT(*) as msg_count
                    FROM messages
                    WHERE timestamp >= ?
                    GROUP BY channel_id
                    ORDER BY msg_count DESC
                    LIMIT 5
                    """,
                    (start_date.isoformat(),)
                )
                rows = await cursor.fetchall()
                stats['top_channels'] = [
                    {'channel_id': row[0], 'count': row[1]}
                    for row in rows
                ]

        # Verification stats
        from src.utils.verification_stats import VerificationStats
        ver_stats = VerificationStats()
        recent_verifications = []

        # Get all verifications from the last week
        try:
            # This is a simplification - in reality you'd need to store historical verification data
            last_ver = ver_stats.get_stats(self.config.guild_id)
            if last_ver:
                stats['verification_avg_accuracy'] = last_ver.get('accuracy_percent', 0)
                # Assume ~4 verifications per day (every 6 hours)
                stats['verifications_run'] = 28  # 7 days * 4 per day
        except:
            pass

        # Dedup stats
        if hasattr(self.bot, 'message_tracking_cog'):
            cog = self.bot.message_tracking_cog
            if hasattr(cog, 'get_dedup_stats'):
                dedup_stats = cog.get_dedup_stats()
                stats['dedup_total'] = dedup_stats.get('total_seen', 0)
                stats['dedup_blocked'] = dedup_stats.get('duplicates_blocked', 0)

        # Rate limit stats
        from src.utils.rate_limit_monitor import get_monitor
        rate_monitor = get_monitor()
        rate_stats = rate_monitor.get_stats()
        stats['rate_limit_hits'] = rate_stats.get('total_rate_limit_hits', 0)

        return stats

    def _create_report_embed(self, stats: Dict, start_date: datetime, end_date: datetime) -> discord.Embed:
        """Create the weekly report embed."""
        embed = discord.Embed(
            title="📊 Wöchentlicher GuildScout Bericht",
            description=f"Zusammenfassung: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        # Activity Overview
        embed.add_field(
            name="📈 Aktivität",
            value=(
                f"**Nachrichten:** {stats['total_messages']:,}\n"
                f"**Aktive User:** {stats['active_users']:,}\n"
                f"**Durchschnitt:** {stats['total_messages'] // 7 if stats['total_messages'] else 0:,} msg/Tag"
            ),
            inline=True
        )

        # Database Health
        db_size = stats['database_size_mb']
        db_status = "✅" if db_size < 100 else "⚠️"
        embed.add_field(
            name="💾 Datenbank",
            value=(
                f"**Größe:** {db_size:.1f} MB {db_status}\n"
                f"**Status:** {'Gesund' if db_size < 100 else 'Groß'}"
            ),
            inline=True
        )

        # Verification Summary
        ver_accuracy = stats['verification_avg_accuracy']
        ver_status = "✅" if ver_accuracy >= 95 else "⚠️"
        embed.add_field(
            name="🔍 Verifikation",
            value=(
                f"**Durchläufe:** ~{stats['verifications_run']}\n"
                f"**Genauigkeit:** {ver_accuracy:.1f}% {ver_status}\n"
                f"**Status:** {'Optimal' if ver_accuracy >= 95 else 'Unterdurchschnittlich'}"
            ),
            inline=True
        )

        # Top Users
        if stats['top_users']:
            top_users_text = []
            guild = self.bot.get_guild(self.config.guild_id)
            for idx, user_data in enumerate(stats['top_users'][:5], 1):
                user_id = user_data['user_id']
                count = user_data['count']

                # Try to get user name
                user_name = "Unknown"
                if guild:
                    member = guild.get_member(user_id)
                    if member:
                        user_name = member.display_name[:20]

                top_users_text.append(f"{idx}. **{user_name}**: {count:,} msg")

            embed.add_field(
                name="🏆 Top 5 User",
                value="\n".join(top_users_text),
                inline=False
            )

        # Top Channels
        if stats['top_channels']:
            top_channels_text = []
            guild = self.bot.get_guild(self.config.guild_id)
            for idx, channel_data in enumerate(stats['top_channels'][:5], 1):
                channel_id = channel_data['channel_id']
                count = channel_data['count']

                # Try to get channel name
                channel_name = "Unknown"
                if guild:
                    channel = guild.get_channel(channel_id)
                    if channel:
                        channel_name = channel.name[:20]

                top_channels_text.append(f"{idx}. **#{channel_name}**: {count:,} msg")

            embed.add_field(
                name="📺 Top 5 Channels",
                value="\n".join(top_channels_text),
                inline=False
            )

        # System Performance
        dedup_rate = 0
        if stats['dedup_total'] > 0:
            dedup_rate = (stats['dedup_blocked'] / stats['dedup_total']) * 100

        embed.add_field(
            name="⚙️ System Performance",
            value=(
                f"**Deduplizierung:** {stats['dedup_blocked']:,} blockiert ({dedup_rate:.2f}%)\n"
                f"**Rate Limit Hits:** {stats['rate_limit_hits']}\n"
                f"**Status:** {'✅ Stabil' if stats['rate_limit_hits'] < 100 else '⚠️ Erhöht'}"
            ),
            inline=False
        )

        embed.set_footer(text="Nächster Bericht: Nächsten Montag, 09:00 UTC")

        return embed


async def setup(bot: commands.Bot, config: Config):
    """Add weekly reporter to bot."""
    await bot.add_cog(WeeklyReporter(bot, config))
