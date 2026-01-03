"""Event handlers for raid signups via reactions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands

from src.database.raid_store import RaidStore
from src.utils.config import Config
from src.utils.raid_utils import (
    CONFIRM_EMOJI,
    ROLE_BENCH,
    ROLE_CANCEL,
    ROLE_DPS,
    ROLE_HEALER,
    ROLE_TANK,
    ROLE_EMOJIS,
    build_raid_embed,
    get_role_limit,
)


logger = logging.getLogger("guildscout.events.raid")

ROLE_EMOJI_TO_ROLE = {
    ROLE_EMOJIS[ROLE_TANK]: ROLE_TANK,
    ROLE_EMOJIS[ROLE_HEALER]: ROLE_HEALER,
    ROLE_EMOJIS[ROLE_DPS]: ROLE_DPS,
    ROLE_EMOJIS[ROLE_BENCH]: ROLE_BENCH,
    ROLE_EMOJIS[ROLE_CANCEL]: ROLE_CANCEL,
}


class RaidEvents(commands.Cog):
    """Handle raid signup reactions."""

    def __init__(self, bot: commands.Bot, config: Config, raid_store: RaidStore):
        self.bot = bot
        self.config = config
        self.raid_store = raid_store

    async def _get_member(
        self,
        guild: discord.Guild,
        user_id: int,
    ) -> Optional[discord.Member]:
        member = guild.get_member(user_id)
        if member:
            return member
        try:
            return await guild.fetch_member(user_id)
        except Exception:
            return None

    async def _send_dm(self, member: Optional[discord.Member], message: str) -> None:
        if not member:
            return
        try:
            await member.send(message)
        except Exception:
            pass

    def _get_participant_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        role_id = self.config.raid_participant_role_id
        if not role_id:
            fallback = discord.utils.get(guild.roles, name="Raid Teilnehmer")
            if fallback:
                self.config.set_raid_participant_role_id(fallback.id)
            return fallback
        return guild.get_role(role_id)

    async def _ensure_participant_role(self, member: Optional[discord.Member]) -> None:
        if not member:
            return
        role = self._get_participant_role(member.guild)
        if not role or role in member.roles:
            return
        try:
            await member.add_roles(role, reason="Raid signup")
        except Exception:
            logger.warning("Failed to add raid participant role", exc_info=True)

    async def _remove_participant_role_if_unused(
        self,
        member: Optional[discord.Member],
    ) -> None:
        if not member:
            return
        role = self._get_participant_role(member.guild)
        if not role or role not in member.roles:
            return
        active_count = await self.raid_store.count_user_active_signups(
            member.guild.id,
            member.id,
        )
        if active_count > 0:
            return
        try:
            await member.remove_roles(role, reason="Raid signup removed")
        except Exception:
            logger.warning("Failed to remove raid participant role", exc_info=True)

    async def _get_message(
        self, guild: discord.Guild, channel_id: int, message_id: int
    ) -> Optional[discord.Message]:
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            try:
                channel = await guild.fetch_channel(channel_id)
            except Exception:
                return None
        try:
            return await channel.fetch_message(message_id)
        except Exception:
            return None

    async def _update_raid_message(
        self,
        message: discord.Message,
        raid_id: int,
    ) -> None:
        raid = await self.raid_store.get_raid(raid_id)
        if not raid:
            return
        signups = await self.raid_store.get_signups_by_role(raid_id)
        confirmation_message_id = await self.raid_store.get_confirmation_message_id(raid_id)
        confirmed = None
        no_shows = None
        if confirmation_message_id:
            confirmed = await self.raid_store.get_confirmed_user_ids(raid_id)
            no_shows = await self.raid_store.get_no_show_user_ids(raid_id)
        embed = build_raid_embed(
            raid, signups, self.config.raid_timezone, confirmed, no_shows
        )
        try:
            await message.edit(embed=embed)
        except Exception:
            logger.warning("Failed to update raid message %s", raid_id, exc_info=True)

    async def _handle_confirmation_reaction(
        self,
        payload: discord.RawReactionActionEvent,
    ) -> bool:
        raid_id = await self.raid_store.get_confirmation_raid_id(payload.message_id)
        if not raid_id:
            return False
        if str(payload.emoji) != CONFIRM_EMOJI:
            return True

        raid = await self.raid_store.get_raid(raid_id)
        if not raid:
            return True

        role = await self.raid_store.get_user_role(raid_id, payload.user_id)
        if not role:
            guild = self.bot.get_guild(payload.guild_id)
            if guild:
                message = await self._get_message(
                    guild, payload.channel_id, payload.message_id
                )
                member = await self._get_member(guild, payload.user_id)
                if message:
                    await self._remove_reaction(message, CONFIRM_EMOJI, member)
            return True

        await self.raid_store.set_signup_confirmed(raid_id, payload.user_id, True)

        guild = self.bot.get_guild(payload.guild_id)
        if not guild or not raid.message_id:
            return True

        raid_message = await self._get_message(guild, raid.channel_id, raid.message_id)
        if raid_message:
            await self._update_raid_message(raid_message, raid_id)
        return True

    async def _handle_confirmation_remove(
        self,
        payload: discord.RawReactionActionEvent,
    ) -> bool:
        raid_id = await self.raid_store.get_confirmation_raid_id(payload.message_id)
        if not raid_id:
            return False
        if str(payload.emoji) != CONFIRM_EMOJI:
            return True

        await self.raid_store.set_signup_confirmed(raid_id, payload.user_id, False)

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return True
        raid = await self.raid_store.get_raid(raid_id)
        if not raid or not raid.message_id:
            return True
        raid_message = await self._get_message(guild, raid.channel_id, raid.message_id)
        if raid_message:
            await self._update_raid_message(raid_message, raid_id)
        return True

    async def _remove_reaction(
        self,
        message: discord.Message,
        emoji: str,
        member: Optional[discord.Member],
    ) -> None:
        if not member:
            return
        try:
            await message.remove_reaction(emoji, member)
        except Exception:
            pass

    async def _clear_user_reactions(
        self,
        message: discord.Message,
        member: Optional[discord.Member],
    ) -> None:
        for emoji in ROLE_EMOJI_TO_ROLE.keys():
            await self._remove_reaction(message, emoji, member)

    async def _fill_open_slots(
        self,
        raid,
        message: discord.Message,
        guild: discord.Guild,
    ) -> bool:
        if raid.status != "open":
            return False
        updated = False

        for role in (ROLE_TANK, ROLE_HEALER, ROLE_DPS):
            limit = get_role_limit(raid, role)
            if limit <= 0:
                continue

            while True:
                signups = await self.raid_store.get_signups_by_role(raid.id)
                current_count = len(signups.get(role, []))
                if current_count >= limit:
                    break

                bench_candidates = await self.raid_store.get_bench_queue(
                    raid.id, preferred_role=role
                )
                if not bench_candidates:
                    bench_candidates = await self.raid_store.get_bench_queue(raid.id)
                if not bench_candidates:
                    break

                user_id = bench_candidates[0]
                await self.raid_store.upsert_signup(raid.id, user_id, role)
                member = await self._get_member(guild, user_id)
                await self._ensure_participant_role(member)
                await self._remove_reaction(message, ROLE_EMOJIS[ROLE_BENCH], member)
                await self._send_dm(
                    member,
                    f"✅ Du wurdest von Reserve auf {role.upper()} verschoben.",
                )
                updated = True
        return updated

    async def _maybe_ping_open_slots(
        self,
        raid,
        message: discord.Message,
        guild: discord.Guild,
    ) -> None:
        if raid.status != "open":
            return
        role = self._get_participant_role(guild)
        if not role:
            return

        signups = await self.raid_store.get_signups_by_role(raid.id)
        open_tanks = max(raid.tanks_needed - len(signups.get(ROLE_TANK, [])), 0)
        open_healers = max(raid.healers_needed - len(signups.get(ROLE_HEALER, [])), 0)
        open_dps = max(raid.dps_needed - len(signups.get(ROLE_DPS, [])), 0)
        total_open = open_tanks + open_healers + open_dps
        if total_open <= 0:
            return

        cooldown = self.config.raid_open_slot_ping_minutes * 60
        now_ts = int(datetime.now(timezone.utc).timestamp())
        last_sent = await self.raid_store.get_alert_sent_at(raid.id, "open_slots")
        if last_sent and now_ts - last_sent < cooldown:
            return

        parts = []
        if open_tanks:
            parts.append(f"Tanks: {open_tanks}")
        if open_healers:
            parts.append(f"Healer: {open_healers}")
        if open_dps:
            parts.append(f"DPS: {open_dps}")
        slot_text = " | ".join(parts)
        content = f"{role.mention} Slots frei fuer **{raid.title}**: {slot_text}"
        try:
            await message.channel.send(content)
            await self.raid_store.mark_alert_sent(raid.id, "open_slots")
        except Exception:
            logger.warning("Failed to send open slot ping", exc_info=True)

    async def _prompt_leave_reason(
        self,
        member: Optional[discord.Member],
        raid,
    ) -> None:
        if not member:
            return
        expires_at = int(datetime.now(timezone.utc).timestamp()) + (10 * 60)
        await self.raid_store.add_leave_request(member.id, raid.id, expires_at)
        await self._send_dm(
            member,
            (
                f"📝 Optionaler Grund fuer Abmeldung von **{raid.title}**?\n"
                "Antworte innerhalb von 10 Minuten auf diese DM.\n"
                "Oder schreibe 'skip', um zu ueberspringen."
            ),
        )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.guild_id is None:
            return
        if not self.config.raid_enabled:
            return
        if self.bot.user and payload.user_id == self.bot.user.id:
            return
        if await self._handle_confirmation_reaction(payload):
            return

        role = ROLE_EMOJI_TO_ROLE.get(str(payload.emoji))
        if not role:
            return

        raid = await self.raid_store.get_raid_by_message_id(payload.message_id)
        if not raid:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        member = await self._get_member(guild, payload.user_id)
        message = await self._get_message(guild, payload.channel_id, payload.message_id)
        if not message:
            return
        if member and member.bot:
            return

        if raid.status in ("closed", "cancelled"):
            await self._remove_reaction(message, str(payload.emoji), member)
            await self._send_dm(member, "❌ Dieser Raid ist bereits geschlossen.")
            return

        if role == ROLE_CANCEL:
            await self.raid_store.remove_signup(raid.id, payload.user_id)
            await self._clear_user_reactions(message, member)
            await self._remove_participant_role_if_unused(member)
            await self._fill_open_slots(raid, message, guild)
            await self._maybe_ping_open_slots(raid, message, guild)
            await self._update_raid_message(message, raid.id)
            await self._prompt_leave_reason(member, raid)
            return

        current_role = await self.raid_store.get_user_role(raid.id, payload.user_id)
        signups = await self.raid_store.get_signups_by_role(raid.id)

        effective_role = role
        preferred_role: Optional[str] = None

        bench_limit = get_role_limit(raid, ROLE_BENCH)
        bench_count = len(signups.get(ROLE_BENCH, []))
        bench_available = bench_limit > 0 and bench_count < bench_limit

        if raid.status == "locked" and role != ROLE_BENCH:
            if not bench_available:
                await self._remove_reaction(message, str(payload.emoji), member)
                await self._send_dm(
                    member,
                    "❌ Anmeldung gesperrt und Reserve ist voll.",
                )
                return
            effective_role = ROLE_BENCH
            preferred_role = role
            await self._remove_reaction(message, str(payload.emoji), member)
            await self._send_dm(
                member,
                "ℹ️ Anmeldung gesperrt: du wurdest auf Reserve gesetzt.",
            )
        elif role == ROLE_BENCH:
            if not bench_available:
                await self._remove_reaction(message, str(payload.emoji), member)
                await self._send_dm(
                    member,
                    "❌ Reserve ist bereits voll.",
                )
                return
            effective_role = ROLE_BENCH
        else:
            limit = get_role_limit(raid, role)
            current_count = len(signups.get(role, []))
            if limit <= 0 or current_count >= limit:
                if not bench_available:
                    await self._remove_reaction(message, str(payload.emoji), member)
                    await self._send_dm(
                        member,
                        "❌ Diese Rolle ist voll und Reserve ist ebenfalls voll.",
                    )
                    return
                effective_role = ROLE_BENCH
                preferred_role = role
                await self._remove_reaction(message, str(payload.emoji), member)
                await self._send_dm(
                    member,
                    "ℹ️ Rolle voll: du wurdest auf Reserve gesetzt.",
                )

        if current_role == effective_role and effective_role != ROLE_BENCH:
            return

        if effective_role == ROLE_BENCH:
            await self.raid_store.upsert_signup_with_preference(
                raid.id,
                payload.user_id,
                effective_role,
                preferred_role,
            )
        else:
            await self.raid_store.upsert_signup(raid.id, payload.user_id, effective_role)
        await self._ensure_participant_role(member)

        if current_role and current_role != effective_role:
            previous_emoji = ROLE_EMOJIS.get(current_role)
            if previous_emoji:
                await self._remove_reaction(message, previous_emoji, member)

        if current_role and current_role != effective_role and current_role != ROLE_BENCH:
            await self._fill_open_slots(raid, message, guild)
            await self._maybe_ping_open_slots(raid, message, guild)

        await self._update_raid_message(message, raid.id)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.guild_id is None:
            return
        if not self.config.raid_enabled:
            return
        if self.bot.user and payload.user_id == self.bot.user.id:
            return
        if await self._handle_confirmation_remove(payload):
            return

        role = ROLE_EMOJI_TO_ROLE.get(str(payload.emoji))
        if not role or role == ROLE_CANCEL:
            return

        raid = await self.raid_store.get_raid_by_message_id(payload.message_id)
        if not raid or raid.status not in ("open", "locked"):
            return

        current_role = await self.raid_store.get_user_role(raid.id, payload.user_id)
        if current_role != role:
            return

        await self.raid_store.remove_signup(raid.id, payload.user_id)

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        message = await self._get_message(guild, payload.channel_id, payload.message_id)
        if not message:
            return
        member = await self._get_member(guild, payload.user_id)
        await self._remove_participant_role_if_unused(member)
        await self._fill_open_slots(raid, message, guild)
        await self._maybe_ping_open_slots(raid, message, guild)
        await self._update_raid_message(message, raid.id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if message.guild is not None:
            return

        request = await self.raid_store.get_latest_leave_request(message.author.id)
        if not request:
            return
        expires_at = request.get("expires_at", 0)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if now_ts > expires_at:
            await self.raid_store.clear_leave_request(
                message.author.id, request["raid_id"]
            )
            return

        content = (message.content or "").strip()
        if not content:
            return
        normalized = content.lower()
        if normalized in {"skip", "nein", "no", "n", "x"}:
            await self.raid_store.clear_leave_request(
                message.author.id, request["raid_id"]
            )
            try:
                await message.channel.send("✅ Alles klar, danke.")
            except Exception:
                pass
            return

        reason = content[:300]
        await self.raid_store.add_leave_reason(
            request["raid_id"], message.author.id, reason
        )
        await self.raid_store.clear_leave_request(
            message.author.id, request["raid_id"]
        )
        try:
            await message.channel.send("✅ Danke fuer dein Feedback.")
        except Exception:
            pass


async def setup(bot: commands.Bot, config: Config, raid_store: RaidStore) -> None:
    """Setup the raid events cog."""
    await bot.add_cog(RaidEvents(bot, config, raid_store))
    logger.info("RaidEvents cog loaded")
