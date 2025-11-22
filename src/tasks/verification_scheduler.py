"""Background scheduler for automatic verification runs."""

import asyncio
import logging
import random
from datetime import datetime, time
from typing import List, Optional

import discord
from discord.ext import commands, tasks

from src.utils import Config
from src.utils.log_helper import DiscordLogger
from src.database import MessageCache
from src.database.message_store import MessageStore
from src.analytics.activity_tracker import ActivityTracker
from src.utils.validation import MessageCountValidator


logger = logging.getLogger("guildscout.verification_scheduler")


def _combine_datetime(now: datetime, hour: int, minute: int) -> datetime:
    """Return today's datetime at the given hour/minute (UTC)."""
    target_time = time(hour=hour, minute=minute)
    return datetime.combine(now.date(), target_time)


class VerificationScheduler(commands.Cog):
    """Runs scheduled verification jobs and logs their results."""

    def __init__(
        self,
        bot: commands.Bot,
        config: Config,
        message_store: MessageStore
    ):
        self.bot = bot
        self.config = config
        self.message_store = message_store
        self.discord_logger = DiscordLogger(bot, config)

        self.daily_enabled = config.daily_verification_enabled
        self.weekly_enabled = config.weekly_verification_enabled

        self._daily_last_run: Optional[datetime.date] = None
        self._weekly_last_run: Optional[datetime.date] = None
        self._run_lock = asyncio.Lock()

        if self.daily_enabled:
            self.daily_verification_task.start()
            logger.info(
                "Daily verification scheduled for %02d:%02d UTC",
                config.daily_verification_hour,
                config.daily_verification_minute
            )
        else:
            logger.info("Daily verification disabled via config.")

        if self.weekly_enabled:
            self.weekly_verification_task.start()
            logger.info(
                "Weekly verification scheduled for weekday %d at %02d:%02d UTC",
                config.weekly_verification_weekday,
                config.weekly_verification_hour,
                config.weekly_verification_minute
            )
        else:
            logger.info("Weekly verification disabled via config.")

    def cog_unload(self):
        if self.daily_verification_task.is_running():
            self.daily_verification_task.cancel()
        if self.weekly_verification_task.is_running():
            self.weekly_verification_task.cancel()

    async def _run_verification_job(
        self,
        *,
        label: str,
        sample_size: int,
        tolerance_percent: float = 1.0
    ):
        """Execute a verification job and log the results."""
        async with self._run_lock:
            guild = self.bot.get_guild(self.config.guild_id)
            if not guild:
                logger.warning("Scheduled verification skipped: guild not found.")
                return

            if await self.message_store.is_import_running(guild.id):
                logger.info("Skipping %s - import currently running.", label)
                await self._log_status(
                    guild,
                    title=f"🔄 {label} übersprungen",
                    description="Import läuft – Verifikation wird nach Abschluss nachgeholt.",
                    status="⏸️ Wartet",
                    color=discord.Color.orange()
                )
                return

            stats = await self.message_store.get_stats(guild.id)
            if not stats.get("import_completed"):
                logger.info("Skipping %s - import noch nicht abgeschlossen.", label)
                await self._log_status(
                    guild,
                    title=f"⚠️ {label} nicht möglich",
                    description="Historischer Import ist noch nicht abgeschlossen.",
                    status="⏸️ Wartet",
                    color=discord.Color.orange()
                )
                return

            # Clean up stale channels so counts match current guild state
            try:
                pruned = await self.message_store.prune_deleted_channels(guild)
                if pruned:
                    logger.info("Pruned %d deleted channels before %s", pruned, label)
            except Exception as cleanup_exc:
                logger.warning(
                    "Failed to prune deleted channels before %s: %s",
                    label,
                    cleanup_exc
                )

            log_message = await self._log_status(
                guild,
                title=f"🔍 {label}",
                description=(
                    f"Stichprobe mit **{sample_size}** Usern gestartet.\n"
                    "Vergleiche Datenbank mit Live-API…"
                ),
                status="🔄 Läuft",
                color=discord.Color.orange()
            )

            try:
                totals = await self.message_store.get_guild_totals(guild.id)
                eligible_ids = [
                    user_id for user_id, count in totals.items() if count >= 10
                ]

                if not eligible_ids:
                    await self._log_status(
                        guild,
                        title=f"⚠️ {label}",
                        description="Keine passenden User (>=10 Nachrichten) für die Stichprobe gefunden.",
                        status="⚠️ Abgebrochen",
                        color=discord.Color.red(),
                        message=log_message
                    )
                    return

                actual_sample_size = min(sample_size, len(eligible_ids))
                sampled_ids = random.sample(eligible_ids, actual_sample_size)
                sample_members: List[discord.Member] = []
                for uid in sampled_ids:
                    member = guild.get_member(uid)
                    if member:
                        sample_members.append(member)

                if not sample_members:
                    await self._log_status(
                        guild,
                        title=f"⚠️ {label}",
                        description="Konnte keine Mitglieder für die Stichprobe im Server finden.",
                        status="⚠️ Abgebrochen",
                        color=discord.Color.red(),
                        message=log_message
                    )
                    return

                cache = MessageCache(ttl=self.config.cache_ttl)
                activity_tracker = ActivityTracker(
                    guild,
                    excluded_channels=self.config.excluded_channels,
                    excluded_channel_names=self.config.excluded_channel_names,
                    cache=cache
                )
                validator = MessageCountValidator(
                    guild,
                    self.message_store,
                    activity_tracker
                )

                results = await validator.validate_sample(
                    sample_members,
                    tolerance_percent=tolerance_percent
                )

                description = (
                    f"{label}\n"
                    f"**Stichprobe:** {results['total_users']} User\n"
                    f"**Accuracy:** {results['accuracy_percent']:.1f}%\n"
                    f"**Matches:** {results['matches']} ✅ | "
                    f"**Mismatches:** {results['mismatches']} ❌\n"
                    f"**Max Difference:** {results['max_difference']} Nachrichten"
                )

                if results["discrepancies"]:
                    top_disc = results["discrepancies"][:3]
                    diff_lines = []
                    for disc in top_disc:
                        diff_lines.append(
                            f"- {disc['user']}: Store {disc['store_count']} | "
                            f"API {disc['api_count']} "
                            f"(Diff {disc['difference']}, {disc['difference_percent']:.1f}%)"
                    )
                    description += "\n\n**Auffällige User:**\n" + "\n".join(diff_lines)

                user_lines = []
                for user_res in results.get("user_results", []):
                    status_icon = "✅" if user_res["match"] else "❌"
                    user_lines.append(
                        f"- {status_icon} {user_res['user']}: "
                        f"Store {user_res['store_count']} | API {user_res['api_count']} "
                        f"(Diff {user_res['difference']}, {user_res['difference_percent']:.1f}%)"
                    )
                if user_lines:
                    description += "\n\n**Geprüfte User:**\n" + "\n".join(user_lines)

                status_text = "✅ Erfolgreich" if results["passed"] else "⚠️ Abweichungen"
                color = discord.Color.green() if results["passed"] else discord.Color.orange()
                ping = self.config.alert_ping if not results["passed"] else None

                await self._log_status(
                    guild,
                    title=f"🔍 {label}",
                    description=description,
                    status=status_text,
                    color=color,
                    message=log_message,
                    ping=ping
                )

                logger.info(
                    "%s abgeschlossen: %s (Accuracy %.1f%%)",
                    label,
                    status_text,
                    results["accuracy_percent"]
                )

            except Exception as exc:
                logger.error("Scheduled verification failed: %s", exc, exc_info=True)
                await self._log_status(
                    guild,
                    title=f"❌ {label}",
                    description=f"Fehler: {exc}",
                    status="❌ Fehler",
                    color=discord.Color.red(),
                    message=log_message,
                    ping=self.config.alert_ping
                )

    async def _log_status(
        self,
        guild: discord.Guild,
        title: str,
        description: str,
        *,
        status: str,
        color: discord.Color,
        message: Optional[discord.Message] = None,
        ping: Optional[str] = None
    ) -> Optional[discord.Message]:
        """Helper to send/update log messages via DiscordLogger."""
        if not self.discord_logger:
            return None
        return await self.discord_logger.send(
            guild,
            title,
            description,
            status=status,
            color=color,
            message=message,
            ping=ping
        )

    def _should_run_today(self, now: datetime) -> bool:
        target_dt = _combine_datetime(
            now,
            self.config.daily_verification_hour,
            self.config.daily_verification_minute
        )
        return now >= target_dt

    def _should_run_weekly(self, now: datetime) -> bool:
        if now.weekday() != self.config.weekly_verification_weekday:
            return False
        target_dt = _combine_datetime(
            now,
            self.config.weekly_verification_hour,
            self.config.weekly_verification_minute
        )
        return now >= target_dt

    @tasks.loop(minutes=5)
    async def daily_verification_task(self):
        if not self.daily_enabled:
            return
        now = datetime.utcnow()
        if self._daily_last_run == now.date():
            return
        if not self._should_run_today(now):
            return
        await self._run_verification_job(
            label="Tägliche Stichproben-Verifikation",
            sample_size=self.config.daily_verification_sample_size
        )
        self._daily_last_run = now.date()

    @daily_verification_task.before_loop
    async def before_daily(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=10)
    async def weekly_verification_task(self):
        if not self.weekly_enabled:
            return
        now = datetime.utcnow()
        if self._weekly_last_run == now.date():
            return
        if not self._should_run_weekly(now):
            return
        await self._run_verification_job(
            label="Wöchentliche Tiefenprüfung",
            sample_size=self.config.weekly_verification_sample_size
        )
        self._weekly_last_run = now.date()

    @weekly_verification_task.before_loop
    async def before_weekly(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot, config: Config, message_store: MessageStore):
    """Add the verification scheduler cog to the bot."""
    await bot.add_cog(VerificationScheduler(bot, config, message_store))
