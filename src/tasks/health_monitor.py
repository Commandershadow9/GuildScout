"""Automated health monitoring and alerting system."""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import aiosqlite
from discord.ext import commands, tasks

from src.utils import Config

logger = logging.getLogger("guildscout.health_monitor")


class HealthMonitor(commands.Cog):
    """
    Monitors system health and sends automated alerts.

    Monitors:
    - Bot uptime and connectivity
    - Consecutive verification failures
    - Rate limit critical status
    - Database growth anomalies
    - ShadowOps integration health
    """

    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config

        # Health tracking
        self.consecutive_verification_failures = 0
        self.last_verification_check = datetime.utcnow()
        self.last_health_report = datetime.utcnow()
        self.last_db_size = 0.0

        # Alert cooldowns to prevent spam
        self.alert_cooldowns = {
            'verification_failure': timedelta(hours=1),
            'rate_limit_critical': timedelta(minutes=30),
            'db_growth': timedelta(hours=6),
            'shadowops_offline': timedelta(hours=1)
        }
        self.last_alerts = {}

        # Start monitoring tasks
        self.health_check_task.start()
        logger.info("🏥 Health monitoring system started")

    def cog_unload(self):
        self.health_check_task.cancel()

    @tasks.loop(minutes=5)
    async def health_check_task(self):
        """Run health checks every 5 minutes."""
        await self.bot.wait_until_ready()

        try:
            await self._check_verification_health()
            await self._check_rate_limit_health()
            await self._check_database_health()
            await self._check_shadowops_health()

            # Send periodic health report every 24h
            if datetime.utcnow() - self.last_health_report > timedelta(hours=24):
                await self._send_health_report()
                self.last_health_report = datetime.utcnow()

        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)

    async def _check_verification_health(self):
        """Monitor verification system health."""
        from src.utils.verification_stats import VerificationStats

        ver_stats = VerificationStats()
        last_ver = ver_stats.get_stats(self.config.guild_id)

        if not last_ver:
            return

        # Check if verification is running on schedule (should be every 6 hours)
        timestamp_str = last_ver.get('timestamp', '')
        if timestamp_str and timestamp_str != 'Unknown':
            try:
                last_run = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                time_since = datetime.utcnow() - last_run.replace(tzinfo=None)

                # Alert if no verification in 8+ hours (missed at least one cycle)
                if time_since > timedelta(hours=8):
                    await self._send_alert(
                        'verification_failure',
                        "⚠️ Verifikation überfällig",
                        f"Letzte Verifikation war vor {time_since.total_seconds()/3600:.1f}h.\n"
                        f"Erwartet: alle 6 Stunden\n\n"
                        f"Möglicherweise ist der Scheduler ausgefallen.",
                        severity='warning'
                    )
            except Exception as e:
                logger.debug(f"Could not parse verification timestamp: {e}")

        # Check accuracy
        accuracy = last_ver.get('accuracy_percent', 100)
        if accuracy < 95.0:
            # Track consecutive failures
            self.consecutive_verification_failures += 1

            if self.consecutive_verification_failures >= 2:
                await self._send_alert(
                    'verification_failure',
                    "❌ Verifikation schlägt fehl",
                    f"**Genauigkeit:** {accuracy:.1f}% (< 95%)\n"
                    f"**Fehlschläge:** {self.consecutive_verification_failures} aufeinanderfolgend\n\n"
                    f"Überprüfe Discord API oder Netzwerkverbindung.",
                    severity='critical'
                )
        else:
            # Reset counter on success
            if self.consecutive_verification_failures > 0:
                logger.info(f"✅ Verification recovered after {self.consecutive_verification_failures} failures")
                self.consecutive_verification_failures = 0

    async def _check_rate_limit_health(self):
        """Monitor Discord rate limit status."""
        from src.utils.rate_limit_monitor import get_monitor

        rate_monitor = get_monitor()
        stats = rate_monitor.get_stats()

        # Alert if status is critical
        if stats['status'] == 'critical':
            await self._send_alert(
                'rate_limit_critical',
                "🚨 Rate Limit kritisch",
                f"**Requests/s:** {stats['requests_per_second']}\n"
                f"**Limit Hits:** {stats['total_rate_limit_hits']}\n\n"
                f"Bot könnte verlangsamt oder geblockt werden.\n"
                f"Erwäge Reduzierung der API-Aufrufe.",
                severity='critical'
            )
        elif stats['status'] == 'warning':
            await self._send_alert(
                'rate_limit_critical',
                "⚠️ Rate Limit erhöht",
                f"**Requests/s:** {stats['requests_per_second']}\n"
                f"**Limit Hits:** {stats['total_rate_limit_hits']}\n\n"
                f"API-Nutzung ist erhöht, aber noch im sicheren Bereich.",
                severity='warning'
            )

    async def _check_database_health(self):
        """Monitor database growth and health."""
        db_path = Path("data/messages.db")

        if not db_path.exists():
            return

        current_size = db_path.stat().st_size / (1024 * 1024)  # MB

        # Check for rapid growth (>50MB since last check)
        if self.last_db_size > 0:
            growth = current_size - self.last_db_size

            if growth > 50:
                await self._send_alert(
                    'db_growth',
                    "📈 Datenbank wächst schnell",
                    f"**Wachstum:** +{growth:.1f} MB (seit letztem Check)\n"
                    f"**Aktuelle Größe:** {current_size:.1f} MB\n\n"
                    f"Ungewöhnlich schnelles Wachstum erkannt.\n"
                    f"Überprüfe auf Anomalien oder erwäge VACUUM.",
                    severity='warning'
                )

        self.last_db_size = current_size

        # Check for corruption
        try:
            async with aiosqlite.connect(db_path) as db:
                cursor = await db.execute("PRAGMA integrity_check")
                result = await cursor.fetchone()

                if result and result[0] != 'ok':
                    await self._send_alert(
                        'db_growth',
                        "🔴 Datenbank-Korruption",
                        f"**PRAGMA integrity_check:** {result[0]}\n\n"
                        f"Datenbank könnte beschädigt sein!\n"
                        f"Erwäge Backup und Reparatur.",
                        severity='critical'
                    )
        except Exception as e:
            logger.error(f"Database integrity check failed: {e}")

    async def _check_shadowops_health(self):
        """Monitor ShadowOps integration health."""
        if not self.config.shadowops_enabled:
            return

        # Check if ShadowOps notifier is responsive
        if hasattr(self.bot, 'verification_scheduler_cog'):
            cog = self.bot.verification_scheduler_cog

            if hasattr(cog, 'shadowops_notifier'):
                notifier = cog.shadowops_notifier

                # Check queue size
                queue_size = len(notifier.retry_queue)

                if queue_size > 10:
                    await self._send_alert(
                        'shadowops_offline',
                        "📡 ShadowOps Warteschlange voll",
                        f"**Wartende Events:** {queue_size}\n\n"
                        f"ShadowOps könnte offline oder überlastet sein.\n"
                        f"Events werden weiter versucht, aber verzögert.",
                        severity='warning'
                    )

                # Check if health endpoint is reachable
                if hasattr(notifier, 'last_health_check'):
                    last_health = notifier.last_health_check

                    if last_health:
                        time_since = datetime.utcnow() - last_health

                        # Alert if no successful health check in 30+ minutes
                        if time_since > timedelta(minutes=30):
                            await self._send_alert(
                                'shadowops_offline',
                                "🔴 ShadowOps nicht erreichbar",
                                f"**Letzter Kontakt:** vor {time_since.total_seconds()/60:.0f} Minuten\n\n"
                                f"Health Check schlägt fehl.\n"
                                f"Überprüfe ShadowOps-Bot Status.",
                                severity='critical'
                            )

    async def _send_alert(self, alert_type: str, title: str, description: str, severity: str = 'warning'):
        """
        Send health alert if not in cooldown.

        Args:
            alert_type: Alert category for cooldown tracking
            title: Alert title
            description: Alert description
            severity: 'warning' or 'critical'
        """
        # Check cooldown
        if alert_type in self.last_alerts:
            time_since = datetime.utcnow() - self.last_alerts[alert_type]
            cooldown = self.alert_cooldowns.get(alert_type, timedelta(hours=1))

            if time_since < cooldown:
                logger.debug(f"Alert '{alert_type}' in cooldown, skipping")
                return

        # Send alert
        logger.warning(f"Health Alert: {title}")

        # Send to ShadowOps if enabled
        if self.config.shadowops_enabled and hasattr(self.bot, 'verification_scheduler_cog'):
            cog = self.bot.verification_scheduler_cog

            if hasattr(cog, 'shadowops_notifier'):
                try:
                    await cog.shadowops_notifier.send_event({
                        'event_type': 'health_alert',
                        'severity': severity,
                        'title': title,
                        'description': description,
                        'timestamp': datetime.utcnow().isoformat()
                    })
                except Exception as e:
                    logger.error(f"Failed to send health alert to ShadowOps: {e}")

        # Also send to Discord status channel
        if hasattr(self.bot, 'status_manager'):
            import discord
            guild = self.bot.get_guild(self.config.guild_id)

            if guild:
                color = discord.Color.red() if severity == 'critical' else discord.Color.orange()

                try:
                    await self.bot.status_manager.send_temp_status(
                        guild,
                        title=title,
                        description=description,
                        color=color
                    )
                except Exception as e:
                    logger.error(f"Failed to send health alert to Discord: {e}")

        # Update cooldown
        self.last_alerts[alert_type] = datetime.utcnow()

    async def _send_health_report(self):
        """Send daily health summary report."""
        import discord

        # Gather all health metrics
        from src.utils.rate_limit_monitor import get_monitor
        from src.utils.verification_stats import VerificationStats

        rate_stats = get_monitor().get_stats()
        ver_stats_obj = VerificationStats()
        last_ver = ver_stats_obj.get_stats(self.config.guild_id)

        db_path = Path("data/messages.db")
        db_size = db_path.stat().st_size / (1024 * 1024) if db_path.exists() else 0

        # Dedup stats
        dedup_stats = {"total_seen": 0, "duplicates_blocked": 0}
        if hasattr(self.bot, 'message_tracking_cog'):
            cog = self.bot.message_tracking_cog
            if hasattr(cog, 'get_dedup_stats'):
                dedup_stats = cog.get_dedup_stats()

        # Build health report
        embed = discord.Embed(
            title="📊 Täglicher Gesundheitsbericht",
            description="Zusammenfassung der letzten 24 Stunden",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        # Overall health status
        health_status = "✅ Gesund"
        if self.consecutive_verification_failures > 0:
            health_status = "⚠️ Eingeschränkt"
        if rate_stats['status'] == 'critical':
            health_status = "🔴 Kritisch"

        embed.add_field(
            name="🏥 Systemstatus",
            value=health_status,
            inline=False
        )

        # Verification health
        ver_status = "✅ OK"
        if last_ver:
            accuracy = last_ver.get('accuracy_percent', 0)
            if accuracy < 95:
                ver_status = f"⚠️ {accuracy:.1f}%"
            else:
                ver_status = f"✅ {accuracy:.1f}%"

        embed.add_field(
            name="🔍 Verifikation",
            value=ver_status,
            inline=True
        )

        # Rate limit health
        rate_status_emoji = {
            'healthy': '✅',
            'warning': '⚠️',
            'critical': '🔴'
        }.get(rate_stats['status'], '❓')

        embed.add_field(
            name="📊 Rate Limits",
            value=f"{rate_status_emoji} {rate_stats['status'].title()}",
            inline=True
        )

        # Database health
        db_status = "✅ Normal" if db_size < 100 else f"⚠️ {db_size:.0f} MB"
        embed.add_field(
            name="💾 Datenbank",
            value=db_status,
            inline=True
        )

        # Deduplication effectiveness
        total_seen = dedup_stats.get('total_seen', 0)
        duplicates = dedup_stats.get('duplicates_blocked', 0)
        dedup_rate = (duplicates / total_seen * 100) if total_seen > 0 else 0

        embed.add_field(
            name="🔄 Deduplizierung",
            value=f"{duplicates:,} blockiert ({dedup_rate:.1f}%)",
            inline=True
        )

        # ShadowOps health
        shadowops_status = "❌ Deaktiviert"
        if self.config.shadowops_enabled:
            queue_size = 0
            if hasattr(self.bot, 'verification_scheduler_cog'):
                cog = self.bot.verification_scheduler_cog
                if hasattr(cog, 'shadowops_notifier'):
                    queue_size = len(cog.shadowops_notifier.retry_queue)

            if queue_size == 0:
                shadowops_status = "✅ Verbunden"
            else:
                shadowops_status = f"⚠️ {queue_size} pending"

        embed.add_field(
            name="📡 ShadowOps",
            value=shadowops_status,
            inline=True
        )

        embed.set_footer(text="Nächster Bericht in 24 Stunden")

        # Send report
        if hasattr(self.bot, 'status_manager'):
            guild = self.bot.get_guild(self.config.guild_id)
            if guild:
                try:
                    await self.bot.status_manager.send_temp_status(
                        guild,
                        title=embed.title,
                        description=embed.description or "",
                        color=embed.color,
                        fields=[
                            {"name": field.name, "value": field.value, "inline": field.inline}
                            for field in embed.fields
                        ]
                    )
                    logger.info("📊 Daily health report sent")
                except Exception as e:
                    logger.error(f"Failed to send health report: {e}")


async def setup(bot: commands.Bot, config: Config):
    """Add health monitor to bot."""
    await bot.add_cog(HealthMonitor(bot, config))
