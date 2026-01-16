"""Background task to close raids after their start time."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

from src.database.raid_store import RaidStore
from src.utils.config import Config
from src.utils.raid_utils import CONFIRM_EMOJI, build_raid_embed, build_raid_log_embed


logger = logging.getLogger("guildscout.tasks.raid_scheduler")


class RaidScheduler(commands.Cog):
    """Closes raids automatically and updates final roster."""

    def __init__(self, bot: commands.Bot, config: Config, raid_store: RaidStore):
        self.bot = bot
        self.config = config
        self.raid_store = raid_store
        if self.config.raid_enabled:
            self.close_task.start()

    def cog_unload(self) -> None:
        if self.close_task.is_running():
            self.close_task.cancel()

    @tasks.loop(minutes=1)
    async def close_task(self) -> None:
        now_ts = int(datetime.now(timezone.utc).timestamp())
        await self._send_reminders(now_ts)
        await self._send_dm_reminders(now_ts)
        await self._send_confirmation_checks(now_ts)
        await self._send_confirmation_reminders(now_ts)
        await self._mark_no_shows(now_ts)

        raids_to_close = {}
        if self.config.raid_auto_close_at_start:
            for raid in await self.raid_store.list_raids_to_close(now_ts):
                raids_to_close[raid.id] = raid

        grace_hours = self.config.raid_auto_close_after_hours
        if grace_hours > 0:
            grace_seconds = grace_hours * 3600
            for raid in await self.raid_store.list_raids_past_grace(now_ts, grace_seconds):
                raids_to_close[raid.id] = raid

        for raid in raids_to_close.values():
            await self.raid_store.close_raid(raid.id, closed_at=now_ts)
            await self.raid_store.archive_participation(raid.id, "auto-closed")

            guild = self.bot.get_guild(raid.guild_id)
            if not guild:
                continue

            channel = guild.get_channel(raid.channel_id)
            if not isinstance(channel, discord.TextChannel):
                try:
                    channel = await guild.fetch_channel(raid.channel_id)
                except Exception:
                    continue

            if not raid.message_id:
                continue

            try:
                message = await channel.fetch_message(raid.message_id)
            except Exception:
                continue

            updated = await self.raid_store.get_raid(raid.id)
            if not updated:
                continue

            signups = await self.raid_store.get_signups_by_role(raid.id)
            bench_preferences = await self.raid_store.get_bench_preferences(raid.id)
            confirmed = await self.raid_store.get_confirmed_user_ids(raid.id)
            no_shows = await self.raid_store.get_no_show_user_ids(raid.id)
            embed = build_raid_embed(
                updated,
                signups,
                self.config.raid_timezone,
                confirmed,
                no_shows,
                bench_preferences=bench_preferences,
            )

            try:
                await message.delete()
            except Exception:
                try:
                    await message.edit(embed=embed)
                    await message.clear_reactions()
                except Exception:
                    logger.warning(
                        "Failed to update raid message %s", raid.id, exc_info=True
                    )

            await self._cleanup_reminder_messages(channel, raid.title)
            await self._cleanup_slot_pings(channel, raid.title)
            await self._cleanup_confirmation_message(channel, raid.id)
            await self._send_raid_log(guild, updated, signups, confirmed, "auto-closed")
            await self._remove_participant_roles(guild, raid.id)
            await self._refresh_history_embed(guild)

    async def _send_reminders(self, now_ts: int) -> None:
        reminder_hours = self.config.raid_reminder_hours
        if not reminder_hours:
            return

        raids = await self.raid_store.list_active_raids(now_ts)
        if not raids:
            return

        sent = await self.raid_store.get_sent_reminders([raid.id for raid in raids])
        window_seconds = 120

        for raid in raids:
            remaining = raid.start_time - now_ts
            if remaining <= 0:
                continue

            guild = self.bot.get_guild(raid.guild_id)
            if not guild:
                continue

            channel = guild.get_channel(raid.channel_id)
            if not isinstance(channel, discord.TextChannel):
                try:
                    channel = await guild.fetch_channel(raid.channel_id)
                except Exception:
                    continue

            role_mention = ""
            role_id = self.config.raid_participant_role_id
            if role_id:
                role = guild.get_role(role_id)
                if role:
                    role_mention = f"{role.mention} "

            sent_hours = set(sent.get(raid.id, []))
            for hours in reminder_hours:
                if hours in sent_hours:
                    continue
                trigger_ts = raid.start_time - (hours * 3600)
                if now_ts < trigger_ts or (now_ts - trigger_ts) > window_seconds:
                    continue

                jump_url = None
                if raid.message_id:
                    jump_url = (
                        f"https://discord.com/channels/{raid.guild_id}/"
                        f"{raid.channel_id}/{raid.message_id}"
                    )
                hour_label = "hour" if hours == 1 else "hours"
                content = (
                    f"{role_mention}⏰ Reminder: **{raid.title}** starts in "
                    f"{hours} {hour_label} (<t:{raid.start_time}:R>)."
                )
                if jump_url:
                    content = f"{content}\n{jump_url}"

                try:
                    await channel.send(content)
                    await self.raid_store.mark_reminder_sent(raid.id, hours)
                except Exception:
                    logger.warning(
                        "Failed to send reminder for raid %s", raid.id, exc_info=True
                    )

    async def _send_dm_reminders(self, now_ts: int) -> None:
        reminder_minutes = self.config.raid_dm_reminder_minutes
        if not reminder_minutes:
            return

        raids = await self.raid_store.list_active_raids(now_ts)
        if not raids:
            return

        sent = await self.raid_store.get_sent_reminders([raid.id for raid in raids])
        window_seconds = 120

        for raid in raids:
            remaining = raid.start_time - now_ts
            if remaining <= 0:
                continue

            minutes_sent = set(sent.get(raid.id, []))
            for minutes in reminder_minutes:
                marker = -int(minutes)
                if marker in minutes_sent:
                    continue
                trigger_ts = raid.start_time - (minutes * 60)
                if now_ts < trigger_ts or (now_ts - trigger_ts) > window_seconds:
                    continue

                signups = await self.raid_store.list_signups(raid.id)
                if not signups:
                    continue

                guild = self.bot.get_guild(raid.guild_id)
                if not guild:
                    continue

                jump_url = None
                if raid.message_id:
                    jump_url = (
                        f"https://discord.com/channels/{raid.guild_id}/"
                        f"{raid.channel_id}/{raid.message_id}"
                    )
                for entry in signups:
                    user_id = entry.get("user_id")
                    if not user_id:
                        continue
                    member = guild.get_member(int(user_id))
                    if not member:
                        try:
                            member = await guild.fetch_member(int(user_id))
                        except Exception:
                            continue
                    role_label = entry.get("role", "").upper()
                    message = (
                        f"⏰ Reminder: **{raid.title}** starts in {minutes} minutes "
                        f"(<t:{raid.start_time}:R>)."
                    )
                    if role_label:
                        message = f"{message}\nRole: {role_label}"
                    if jump_url:
                        message = f"{message}\n{jump_url}"
                    try:
                        await member.send(message)
                    except Exception:
                        pass

                await self.raid_store.mark_reminder_sent(raid.id, marker)

    async def _send_confirmation_checks(self, now_ts: int) -> None:
        if not self.config.raid_checkin_enabled:
            return
        minutes = self.config.raid_confirmation_minutes
        if minutes <= 0:
            return

        raids = await self.raid_store.list_active_raids(now_ts)
        if not raids:
            return

        window_seconds = 120

        for raid in raids:
            trigger_ts = raid.start_time - (minutes * 60)
            if now_ts < trigger_ts or (now_ts - trigger_ts) > window_seconds:
                continue

            existing = await self.raid_store.get_confirmation_message_id(raid.id)
            if existing:
                continue

            signups = await self.raid_store.get_signups_by_role(raid.id)
            if not any(signups.values()):
                continue

            guild = self.bot.get_guild(raid.guild_id)
            if not guild:
                continue

            channel = guild.get_channel(raid.channel_id)
            if not isinstance(channel, discord.TextChannel):
                try:
                    channel = await guild.fetch_channel(raid.channel_id)
                except Exception:
                    continue

            role_mention = ""
            role_id = self.config.raid_participant_role_id
            if role_id:
                role = guild.get_role(role_id)
                if role:
                    role_mention = f"{role.mention} "

            content = (
                f"{role_mention}Please confirm your attendance for "
                f"**{raid.title}** with {CONFIRM_EMOJI}."
            )
            try:
                message = await channel.send(content)
                await message.add_reaction(CONFIRM_EMOJI)
                await self.raid_store.reset_confirmations(raid.id)
                await self.raid_store.set_confirmation_message(raid.id, message.id)
                if raid.message_id:
                    try:
                        raid_message = await channel.fetch_message(raid.message_id)
                    except Exception:
                        raid_message = None
                    if raid_message:
                        signups = await self.raid_store.get_signups_by_role(raid.id)
                        bench_preferences = await self.raid_store.get_bench_preferences(
                            raid.id
                        )
                        confirmed = await self.raid_store.get_confirmed_user_ids(raid.id)
                        no_shows = await self.raid_store.get_no_show_user_ids(raid.id)
                        embed = build_raid_embed(
                            raid,
                            signups,
                            self.config.raid_timezone,
                            confirmed,
                            no_shows,
                            bench_preferences=bench_preferences,
                        )
                        await raid_message.edit(embed=embed)
            except Exception:
                logger.warning(
                    "Failed to send confirmation check for raid %s", raid.id, exc_info=True
                )

    async def _send_confirmation_reminders(self, now_ts: int) -> None:
        if not self.config.raid_checkin_enabled:
            return
        minutes = self.config.raid_confirmation_reminder_minutes
        if minutes <= 0:
            return

        raids = await self.raid_store.list_active_raids(now_ts)
        if not raids:
            return

        window_seconds = 120

        for raid in raids:
            confirmation_message_id = await self.raid_store.get_confirmation_message_id(
                raid.id
            )
            if not confirmation_message_id:
                continue

            trigger_ts = raid.start_time - (minutes * 60)
            if now_ts < trigger_ts or (now_ts - trigger_ts) > window_seconds:
                continue

            alert_type = f"confirm_reminder_{minutes}"
            if await self.raid_store.get_alert_sent_at(raid.id, alert_type):
                continue

            unconfirmed = await self.raid_store.get_unconfirmed_user_ids(raid.id)
            if not unconfirmed:
                await self.raid_store.mark_alert_sent(raid.id, alert_type)
                continue

            guild = self.bot.get_guild(raid.guild_id)
            if not guild:
                continue

            channel = guild.get_channel(raid.channel_id)
            if not isinstance(channel, discord.TextChannel):
                try:
                    channel = await guild.fetch_channel(raid.channel_id)
                except Exception:
                    continue

            mentions = [f"<@{user_id}>" for user_id in unconfirmed]
            chunk_size = 20
            for idx in range(0, len(mentions), chunk_size):
                chunk = ", ".join(mentions[idx : idx + chunk_size])
                content = (
                    f"⏰ Check-in missing for **{raid.title}**. "
                    f"Please confirm with {CONFIRM_EMOJI}: {chunk}"
                )
                try:
                    await channel.send(content)
                except Exception:
                    logger.warning(
                        "Failed to send confirmation reminder for raid %s",
                        raid.id,
                        exc_info=True,
                    )
                    break

            await self.raid_store.mark_alert_sent(raid.id, alert_type)

    async def _mark_no_shows(self, now_ts: int) -> None:
        if not self.config.raid_checkin_enabled:
            return
        raids = await self.raid_store.list_raids_to_close(now_ts)
        if not raids:
            return

        for raid in raids:
            if await self.raid_store.get_alert_sent_at(raid.id, "no_show_marked"):
                continue

            no_shows = await self.raid_store.mark_no_shows(raid.id)
            await self.raid_store.mark_alert_sent(raid.id, "no_show_marked")

            if not raid.message_id:
                continue

            guild = self.bot.get_guild(raid.guild_id)
            if not guild:
                continue

            channel = guild.get_channel(raid.channel_id)
            if not isinstance(channel, discord.TextChannel):
                try:
                    channel = await guild.fetch_channel(raid.channel_id)
                except Exception:
                    continue

            try:
                message = await channel.fetch_message(raid.message_id)
            except Exception:
                continue

            signups = await self.raid_store.get_signups_by_role(raid.id)
            bench_preferences = await self.raid_store.get_bench_preferences(raid.id)
            confirmed = await self.raid_store.get_confirmed_user_ids(raid.id)
            no_show_ids = await self.raid_store.get_no_show_user_ids(raid.id)
            embed = build_raid_embed(
                raid,
                signups,
                self.config.raid_timezone,
                confirmed,
                no_show_ids,
                bench_preferences=bench_preferences,
            )
            try:
                await message.edit(embed=embed)
            except Exception:
                logger.warning(
                    "Failed to update raid message for no-shows %s", raid.id, exc_info=True
                )

    async def _send_raid_log(
        self,
        guild: discord.Guild,
        raid,
        signups,
        confirmed,
        status_label: str,
    ) -> None:
        channel_id = self.config.raid_log_channel_id
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            try:
                channel = await guild.fetch_channel(channel_id)
            except Exception:
                return
        no_shows = await self.raid_store.get_no_show_user_ids(raid.id)
        leave_reasons = await self.raid_store.list_leave_reasons(raid.id)
        embed = build_raid_log_embed(
            raid,
            signups,
            self.config.raid_timezone,
            confirmed,
            no_shows,
            leave_reasons,
            status_label=status_label,
        )
        try:
            await channel.send(embed=embed)
        except Exception:
            logger.warning("Failed to send raid log", exc_info=True)

    async def _cleanup_reminder_messages(
        self,
        channel: discord.TextChannel,
        raid_title: str,
        limit: int = 50,
    ) -> None:
        title_key = (raid_title or "").lower()
        async for message in channel.history(limit=limit):
            if not message.author or not message.author.bot:
                continue
            content = (message.content or "").lower()
            if "reminder" not in content and "erinnerung" not in content:
                continue
            if title_key and title_key not in content:
                continue
            try:
                await message.delete()
            except Exception:
                pass

    async def _cleanup_slot_pings(
        self,
        channel: discord.TextChannel,
        raid_title: str,
        limit: int = 50,
    ) -> None:
        title_key = (raid_title or "").lower()
        async for message in channel.history(limit=limit):
            if not message.author or not message.author.bot:
                continue
            content = (message.content or "").lower()
            if "open slots" not in content and "slots frei" not in content:
                continue
            if title_key and title_key not in content:
                continue
            try:
                await message.delete()
            except Exception:
                pass

    async def _cleanup_confirmation_message(
        self,
        channel: discord.TextChannel,
        raid_id: int,
    ) -> None:
        message_id = await self.raid_store.get_confirmation_message_id(raid_id)
        if not message_id:
            return
        try:
            message = await channel.fetch_message(message_id)
        except Exception:
            await self.raid_store.clear_confirmation_message(raid_id)
            return
        try:
            await message.delete()
        except Exception:
            pass
        await self.raid_store.clear_confirmation_message(raid_id)

    async def _remove_participant_roles(self, guild: discord.Guild, raid_id: int) -> None:
        role_id = self.config.raid_participant_role_id
        if not role_id:
            fallback = None
            for name in ("Raid Participants", "Raid Teilnehmer"):
                fallback = discord.utils.get(guild.roles, name=name)
                if fallback:
                    break
            if fallback:
                self.config.set_raid_participant_role_id(fallback.id)
                role_id = fallback.id
            else:
                return
        role = guild.get_role(role_id)
        if not role:
            return

        signups = await self.raid_store.list_signups(raid_id)
        for entry in signups:
            user_id = entry.get("user_id")
            if not user_id:
                continue
            member = guild.get_member(int(user_id))
            if not member:
                try:
                    member = await guild.fetch_member(int(user_id))
                except Exception:
                    continue
            if role not in member.roles:
                continue
            active_count = await self.raid_store.count_user_active_signups(
                guild.id, member.id
            )
            if active_count == 0:
                try:
                    await member.remove_roles(role, reason="Raid ended")
                except Exception:
                    logger.warning(
                        "Failed to remove raid participant role", exc_info=True
                    )

    async def _refresh_history_embed(self, guild: discord.Guild) -> None:
        cog = self.bot.get_cog("RaidCommand")
        if not cog or not hasattr(cog, "refresh_raid_history"):
            return
        try:
            await cog.refresh_raid_history(guild)
        except Exception:
            logger.warning("Failed to refresh raid history embed", exc_info=True)

    @close_task.before_loop
    async def before_close_task(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot, config: Config, raid_store: RaidStore) -> None:
    """Setup the raid scheduler."""
    await bot.add_cog(RaidScheduler(bot, config, raid_store))
    logger.info("RaidScheduler cog loaded")
