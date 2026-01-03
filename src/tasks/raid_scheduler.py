"""Background task to close raids after their start time."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

from src.database.raid_store import RaidStore
from src.utils.config import Config
from src.utils.raid_utils import build_raid_embed


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
        if not self.config.raid_auto_close_at_start:
            return
        raids = await self.raid_store.list_raids_to_close(now_ts)

        for raid in raids:
            await self.raid_store.close_raid(raid.id, closed_at=now_ts)

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
            embed = build_raid_embed(updated, signups, self.config.raid_timezone)

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

            await self._remove_participant_roles(guild, raid.id)

    async def _send_reminders(self, now_ts: int) -> None:
        reminder_hours = self.config.raid_reminder_hours
        if not reminder_hours:
            return

        raids = await self.raid_store.list_active_raids(now_ts)
        if not raids:
            return

        sent = await self.raid_store.get_sent_reminders([raid.id for raid in raids])

        for raid in raids:
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
                if now_ts < trigger_ts:
                    continue

                jump_url = None
                if raid.message_id:
                    jump_url = (
                        f"https://discord.com/channels/{raid.guild_id}/"
                        f"{raid.channel_id}/{raid.message_id}"
                    )
                hour_label = "Stunde" if hours == 1 else "Stunden"
                content = (
                    f"{role_mention}⏰ Erinnerung: **{raid.title}** startet in "
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

        for raid in raids:
            minutes_sent = set(sent.get(raid.id, []))
            for minutes in reminder_minutes:
                marker = -int(minutes)
                if marker in minutes_sent:
                    continue
                trigger_ts = raid.start_time - (minutes * 60)
                if now_ts < trigger_ts:
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
                        f"⏰ Erinnerung: **{raid.title}** startet in {minutes} Minuten "
                        f"(<t:{raid.start_time}:R>)."
                    )
                    if role_label:
                        message = f"{message}\nRolle: {role_label}"
                    if jump_url:
                        message = f"{message}\n{jump_url}"
                    try:
                        await member.send(message)
                    except Exception:
                        pass

                await self.raid_store.mark_reminder_sent(raid.id, marker)

    async def _remove_participant_roles(self, guild: discord.Guild, raid_id: int) -> None:
        role_id = self.config.raid_participant_role_id
        if not role_id:
            fallback = discord.utils.get(guild.roles, name="Raid Teilnehmer")
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

    @close_task.before_loop
    async def before_close_task(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot, config: Config, raid_store: RaidStore) -> None:
    """Setup the raid scheduler."""
    await bot.add_cog(RaidScheduler(bot, config, raid_store))
    logger.info("RaidScheduler cog loaded")
