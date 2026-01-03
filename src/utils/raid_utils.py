"""Shared helpers for raid scheduling and roster formatting."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Iterable
from zoneinfo import ZoneInfo

import discord

from src.database.raid_store import RaidRecord


ROLE_TANK = "tank"
ROLE_HEALER = "healer"
ROLE_DPS = "dps"
ROLE_BENCH = "bench"
ROLE_CANCEL = "cancel"

ROLE_ORDER = [ROLE_TANK, ROLE_HEALER, ROLE_DPS, ROLE_BENCH]

ROLE_LABELS = {
    ROLE_TANK: "Tank",
    ROLE_HEALER: "Healer",
    ROLE_DPS: "DPS",
    ROLE_BENCH: "Reserve",
}

ROLE_EMOJIS = {
    ROLE_TANK: "🛡️",
    ROLE_HEALER: "💉",
    ROLE_DPS: "⚔️",
    ROLE_BENCH: "🪑",
    ROLE_CANCEL: "❌",
}

CONFIRM_EMOJI = "✅"


def parse_raid_datetime(date_str: str, time_str: str, timezone_name: str) -> datetime:
    """Parse raid date/time strings into a timezone-aware datetime."""
    base = None
    for fmt in ("%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M"):
        try:
            base = datetime.strptime(f"{date_str} {time_str}", fmt)
            break
        except ValueError:
            continue

    if base is None:
        raise ValueError(
            "Bitte Datum (DD.MM.YYYY oder YYYY-MM-DD) und Uhrzeit (HH:MM) angeben."
        )

    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = timezone.utc

    return base.replace(tzinfo=tz)


def get_role_limit(raid: RaidRecord, role: str) -> int:
    """Return configured limit for a role."""
    if role == ROLE_TANK:
        return raid.tanks_needed
    if role == ROLE_HEALER:
        return raid.healers_needed
    if role == ROLE_DPS:
        return raid.dps_needed
    if role == ROLE_BENCH:
        return raid.bench_needed
    return 0


def _format_user_list(user_ids: List[int]) -> str:
    if not user_ids:
        return "—"
    return ", ".join(f"<@{user_id}>" for user_id in user_ids)


def build_raid_embed(
    raid: RaidRecord,
    signups_by_role: Dict[str, List[int]],
    timezone_name: str = "UTC",
    confirmed_ids: Optional[Iterable[int]] = None,
    no_show_ids: Optional[Iterable[int]] = None,
) -> discord.Embed:
    """Build the public raid embed with roster details."""
    status_labels = {
        "open": "Offen",
        "locked": "Gesperrt",
        "closed": "Geschlossen",
        "cancelled": "Abgesagt",
    }
    status_label = status_labels.get(raid.status, "Unbekannt")

    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = timezone.utc

    local_dt = datetime.fromtimestamp(raid.start_time, tz)
    de_line = local_dt.strftime("%d.%m.%Y %H:%M")
    en_line = local_dt.strftime("%a, %b %d %Y %I:%M %p")
    tz_label = timezone_name

    main_needed = raid.tanks_needed + raid.healers_needed + raid.dps_needed
    bench_needed = raid.bench_needed
    main_filled = (
        len(signups_by_role.get(ROLE_TANK, []))
        + len(signups_by_role.get(ROLE_HEALER, []))
        + len(signups_by_role.get(ROLE_DPS, []))
    )
    bench_filled = len(signups_by_role.get(ROLE_BENCH, []))
    total_needed = main_needed + bench_needed
    total_filled = main_filled + bench_filled
    total_open = max(total_needed - total_filled, 0) if total_needed > 0 else 0

    signup_label = "SIGNUPS OPEN"
    if raid.status in ("locked", "closed", "cancelled") or total_open == 0:
        signup_label = "SIGNUPS CLOSED"
    elif total_open <= 2 or (total_needed > 0 and total_open <= max(1, total_needed // 5)):
        signup_label = "ALMOST FULL"

    if signup_label == "SIGNUPS OPEN":
        status_color = discord.Color.green()
    elif signup_label == "ALMOST FULL":
        status_color = discord.Color.gold()
    else:
        status_color = discord.Color.red()

    embed = discord.Embed(
        title=f"🗡️ Raid: {raid.title} · {signup_label}",
        description=raid.description or None,
        color=status_color,
    )

    embed.add_field(
        name="Startzeit",
        value=(
            f"<t:{raid.start_time}:F>\n"
            f"<t:{raid.start_time}:R>\n"
            f"DE: {de_line} ({tz_label})\n"
            f"EN: {en_line} ({tz_label})"
        ),
        inline=False,
    )

    embed.add_field(name="Erstellt von", value=f"<@{raid.creator_id}>", inline=True)
    embed.add_field(name="Status", value=status_label, inline=True)

    if bench_needed > 0:
        slots_value = (
            f"Gesamt: {total_filled}/{total_needed} · Frei: {total_open}\n"
            f"Kern: {main_filled}/{main_needed} · Reserve: {bench_filled}/{bench_needed}"
        )
    else:
        slots_value = f"Kern: {main_filled}/{main_needed} · Frei: {max(main_needed - main_filled, 0)}"
    embed.add_field(name="Slots", value=slots_value, inline=True)

    for role in ROLE_ORDER:
        limit = get_role_limit(raid, role)
        users = signups_by_role.get(role, [])
        if limit == 0 and not users:
            continue

        label = ROLE_LABELS.get(role, role.title())
        emoji = ROLE_EMOJIS.get(role, "")
        open_slots = max(limit - len(users), 0) if limit > 0 else 0
        count_text = f"{len(users)}/{limit}" if limit > 0 else f"{len(users)}"
        if limit > 0:
            count_text = f"{count_text} · Frei: {open_slots}"
        embed.add_field(
            name=f"{emoji} {label} ({count_text})",
            value=_format_user_list(users),
            inline=False,
        )

    all_signups: List[int] = []
    for role in ROLE_ORDER:
        all_signups.extend(signups_by_role.get(role, []))

    if confirmed_ids is not None and all_signups:
        confirmed_set = set(int(uid) for uid in (confirmed_ids or []))
        no_show_set = set(int(uid) for uid in (no_show_ids or []))
        confirmed_list = [uid for uid in all_signups if uid in confirmed_set]
        unconfirmed = [
            uid
            for uid in all_signups
            if uid not in confirmed_set and uid not in no_show_set
        ]
        confirmed_value = f"{len(confirmed_list)}/{len(all_signups)}"
        if unconfirmed:
            preview = ", ".join(f"<@{uid}>" for uid in unconfirmed[:15])
            if len(unconfirmed) > 15:
                preview = f"{preview}, +{len(unconfirmed) - 15} weitere"
            if len(preview) > 1024:
                preview = f"{len(unconfirmed)} offen"
            confirmed_value = f"{confirmed_value}\nOffen: {preview}"
        embed.add_field(name="Bestaetigt", value=confirmed_value, inline=False)
        if no_show_set:
            no_show_preview = ", ".join(f"<@{uid}>" for uid in list(no_show_set)[:15])
            if len(no_show_set) > 15:
                no_show_preview = f"{no_show_preview}, +{len(no_show_set) - 15} weitere"
            if len(no_show_preview) > 1024:
                no_show_preview = f"{len(no_show_set)} markiert"
            embed.add_field(
                name="No-Show",
                value=no_show_preview,
                inline=False,
            )

    if raid.status == "locked":
        embed.set_footer(text="Anmeldung gesperrt: nur Reserve moeglich.")
    elif raid.status == "closed":
        embed.set_footer(text="Raid gestartet/geschlossen.")
    elif raid.status == "cancelled":
        embed.set_footer(text="Raid wurde abgesagt.")

    return embed


def build_raid_log_embed(
    raid: RaidRecord,
    signups_by_role: Dict[str, List[int]],
    timezone_name: str = "UTC",
    confirmed_ids: Optional[Iterable[int]] = None,
    status_label: Optional[str] = None,
) -> discord.Embed:
    """Build an admin log embed for raid summaries."""
    status = status_label or raid.status
    embed = discord.Embed(
        title=f"🧾 Raid Log: {raid.title}",
        description=raid.description or None,
        color=discord.Color.blurple(),
    )

    embed.add_field(
        name="Status",
        value=status,
        inline=True,
    )
    embed.add_field(
        name="Startzeit",
        value=f"<t:{raid.start_time}:F>",
        inline=True,
    )
    embed.add_field(
        name="Erstellt von",
        value=f"<@{raid.creator_id}>",
        inline=True,
    )

    all_signups: List[int] = []
    for role in ROLE_ORDER:
        users = signups_by_role.get(role, [])
        all_signups.extend(users)
        label = ROLE_LABELS.get(role, role.title())
        embed.add_field(
            name=f"{ROLE_EMOJIS.get(role, '')} {label} ({len(users)})",
            value=_format_user_list(users),
            inline=False,
        )

    if all_signups:
        confirmed_set = set(int(uid) for uid in (confirmed_ids or []))
        confirmed_count = sum(1 for uid in all_signups if uid in confirmed_set)
        embed.add_field(
            name="Bestaetigt",
            value=f"{confirmed_count}/{len(all_signups)}",
            inline=False,
        )

    return embed
