"""Background scheduler for automatic verification runs."""

import asyncio
import logging
import random
from datetime import datetime, time
from typing import List, Optional

import discord
from discord.ext import commands, tasks

from src.utils import Config
from src.database import MessageCache
from src.database.message_store import MessageStore
from src.analytics.activity_tracker import ActivityTracker
from src.utils.validation import MessageCountValidator
from src.utils.verification_stats import VerificationStats


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
        self.verification_stats = VerificationStats()

        self.daily_enabled = config.daily_verification_enabled
        self.weekly_enabled = config.weekly_verification_enabled

        self._daily_last_run: Optional[datetime.date] = None
        self._weekly_last_run: Optional[datetime.date] = None
        self._run_lock = asyncio.Lock()
        # No initial_delay_done flag here anymore, delay is handled globally

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
        tolerance_percent: float = 1.0,
        enable_healing: bool = True
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
                    # Silently skip if no eligible users (common after restart/import)
                    logger.info("%s übersprungen: Keine User mit >=10 Nachrichten", label)
                    # Delete the "running" status message
                    if log_message:
                        try:
                            await log_message.delete()
                        except:
                            pass
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

                # Define progress callback to update status message
                async def progress_callback(
                    processed: int,
                    total: int,
                    member: discord.Member,
                    store_count: int,
                    api_count: int
                ):
                    # Only update every 20% or at end to avoid rate limits
                    if processed == total or processed == 1 or processed % max(1, total // 5) == 0:
                        await self._log_status(
                            guild,
                            title=f"🔍 {label}",
                            description=(
                                f"Fortschritt: **{processed}/{total}** User geprüft.\n"
                                f"Letzter Check: **{member.display_name}**\n"
                                "Vergleiche Datenbank mit Live-API…"
                            ),
                            status=f"🔄 {int(processed/total*100)}%",
                            color=discord.Color.orange(),
                            message=log_message
                        )

                results = await validator.validate_sample(
                    sample_members,
                    tolerance_percent=tolerance_percent,
                    progress_callback=progress_callback,
                    heal_mismatches=enable_healing
                )

                description = (
                    f"{label}\n"
                    f"**Stichprobe:** {results['total_users']} User\n"
                    f"**Accuracy:** {results['accuracy_percent']:.1f}%\n"
                    f"**Matches:** {results['matches']} ✅ | "
                    f"**Mismatches:** {results['mismatches']} ❌\n"
                    f"**Max Difference:** {results['max_difference']} Nachrichten"
                )
                
                if results.get("healed", 0) > 0:
                    description += f"\n**Korrigiert:** {results['healed']} User 🩹"

                if results["discrepancies"]:
                    top_disc = results["discrepancies"][:3]
                    diff_lines = []
                    for disc in top_disc:
                        healed_mark = " 🩹" if disc.get("healed") else ""
                        diff_lines.append(
                            f"- {disc['user']}: Store {disc['store_count']} | "
                            f"API {disc['api_count']} "
                            f"(Diff {disc['difference']}, {disc['difference_percent']:.1f}%){healed_mark}"
                    )
                    description += "\n\n**Auffällige User:**\n" + "\n".join(diff_lines)

                user_lines = []
                for user_res in results.get("user_results", []):
                    status_icon = "✅" if user_res["match"] else ("🩹" if user_res.get("healed") else "❌")
                    user_lines.append(
                        f"- {status_icon} {user_res['user']}: "
                        f"Store {user_res['store_count']} | API {user_res['api_count']} "
                        f"(Diff {user_res['difference']}, {user_res['difference_percent']:.1f}%)"
                    )
                if user_lines:
                    description += "\n\n**Geprüfte User:**\n" + "\n".join(user_lines)

                # Pass if accuracy is high OR if we successfully healed the mismatches
                passed = results["passed"] or (enable_healing and results.get("healed", 0) == results["mismatches"])
                
                status_text = "✅ Erfolgreich" if passed else "⚠️ Abweichungen"
                color = discord.Color.green() if passed else discord.Color.orange()
                ping = self.config.alert_ping if not passed else None

                # Record stats for dashboard
                self.verification_stats.record_verification(
                    guild.id,
                    passed=passed,
                    accuracy=results["accuracy_percent"],
                    sample_size=results["total_users"],
                    mismatches=results["mismatches"]
                )

                # If successful (or healed), delete the message (don't spam log channel)
                # If failed (unhealed mismatches), keep the message for visibility
                if passed:
                    if log_message:
                        try:
                            await log_message.delete()
                            logger.info(f"✅ {label} erfolgreich - Message gelöscht (clean logs)")
                        except:
                            pass
                else:
                    # Failed - post persistent warning message
                    await self._log_status(
                        guild,
                        title=f"🔍 {label}",
                        description=description,
                        status=status_text,
                        color=color,
                        message=log_message,
                        ping=ping
                    )

                # Update dashboard with new stats
                try:
                    from src.events.message_tracking import MessageTracker
                    message_tracker = self.bot.get_cog('MessageTracker')
                    if message_tracker and hasattr(message_tracker, 'dashboard_manager'):
                        dashboard_manager = message_tracker.dashboard_manager
                        if dashboard_manager:
                            lock = dashboard_manager._dashboard_locks.setdefault(guild.id, asyncio.Lock())
                            async with lock:
                                state = dashboard_manager._get_dashboard_state(guild.id)
                                await dashboard_manager._update_dashboard(guild, state)
                                logger.info("✅ Dashboard updated with verification stats")
                except Exception as dash_err:
                    logger.warning(f"Could not update dashboard after verification: {dash_err}")

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
        """Helper to send/update status messages via StatusManager."""
        if not hasattr(self.bot, 'status_manager'):
            return None

        # Determine if this is an error/warning (needs acknowledgment) or temp status
        is_error = "❌" in title or "⚠️" in title or "Fehler" in title.lower()

        if is_error:
            # Error/Warning: Send with acknowledgment button
            return await self.bot.status_manager.send_error(
                guild,
                title,
                description,
                ping=ping,
                color=color
            )
        else:
            # Temporary status (Running...): Send without button
            return await self.bot.status_manager.send_temp_status(
                guild,
                title,
                description,
                color=color,
                message=message
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
        # Wait until the initial startup sequence (cleanup, delta import) is complete
        await self.bot.wait_until_ready()
        if not hasattr(self.bot, '_initial_startup_complete') or not self.bot._initial_startup_complete:
            logger.debug("Daily verification task waiting for initial startup to complete.")
            return

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
        # Wait until the initial startup sequence (cleanup, delta import) is complete
        await self.bot.wait_until_ready()
        if not hasattr(self.bot, '_initial_startup_complete') or not self.bot._initial_startup_complete:
            logger.debug("Weekly verification task waiting for initial startup to complete.")
            return

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
