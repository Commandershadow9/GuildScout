"""FastAPI web UI for GuildScout."""

from __future__ import annotations

import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo
from urllib.parse import quote

from fastapi import FastAPI, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, TimestampSigner

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from web_api.config import load_bot_config, load_web_config, save_bot_config
from web_api.db import GuildSettings, WebSession, WebStore
from web_api.discord_client import (
    DiscordApiError,
    add_reaction,
    build_avatar_url,
    create_message,
    delete_message,
    edit_message,
    exchange_code_for_token,
    fetch_bot_guild,
    fetch_member,
    fetch_user,
    fetch_user_guilds,
)
from src.database.raid_store import RaidRecord, RaidStore
from src.database.raid_template_store import RaidTemplateStore
from web_api.analytics_api import get_analytics_service
from web_api.activity_api import get_activity_service
from web_api.websocket_manager import (
    get_websocket_manager,
    broadcast_raid_event,
    broadcast_activity,
    EventType,
)
from src.utils.raid_utils import (
    GAME_LABELS,
    GAME_WWM,
    MODE_GUILDWAR,
    MODE_LABELS,
    MODE_RAID,
    ROLE_BENCH,
    ROLE_CANCEL,
    ROLE_DPS,
    ROLE_EMOJIS,
    ROLE_HEALER,
    ROLE_TANK,
    build_raid_embed,
    parse_raid_datetime,
)


import json
import dataclasses

app = FastAPI(title="GuildScout Web UI")

def _json_default(obj):
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return str(obj)

templates = Jinja2Templates(directory=str(ROOT / "web_api" / "templates"))
templates.env.filters["tojson"] = lambda x: json.dumps(x, default=_json_default)
app.mount("/static", StaticFiles(directory=str(ROOT / "web_api" / "static")), name="static")

web_config = load_web_config()
web_store = WebStore(web_config.web_db_path)
raid_store = RaidStore()
template_store = RaidTemplateStore(str(web_config.web_db_path))

signer = TimestampSigner(web_config.session_secret)

# Cache TTLs (seconds) - increased for better performance
ACCESSIBLE_GUILDS_TTL = 300   # 5 minutes (was 2 min) - user's accessible guilds
BOT_GUILD_TTL = 600           # 10 minutes (was 5 min) - bot guild info
MEMBER_TTL = 300              # 5 minutes (was 3 min) - member info

_accessible_guilds_cache: dict[int, tuple[int, list[dict[str, Any]]]] = {}
_bot_guild_cache: dict[int, tuple[int, Optional[dict[str, Any]]]] = {}
_member_cache: dict[tuple[int, int], tuple[int, Optional[dict[str, Any]]]] = {}


def _cache_get(cache: dict, key: Any) -> Optional[Any]:
    now_ts = int(time.time())
    entry = cache.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if expires_at < now_ts:
        cache.pop(key, None)
        return None
    return value


def _cache_set(cache: dict, key: Any, ttl_seconds: int, value: Any) -> None:
    cache[key] = (int(time.time()) + ttl_seconds, value)


async def _fetch_bot_guild_cached(guild_id: int) -> Optional[dict[str, Any]]:
    cached = _cache_get(_bot_guild_cache, guild_id)
    if cached is not None:
        return cached
    bot_guild = await fetch_bot_guild(web_config.bot_token, guild_id)
    _cache_set(_bot_guild_cache, guild_id, BOT_GUILD_TTL, bot_guild)
    return bot_guild


async def _fetch_member_cached(
    guild_id: int, user_id: int
) -> Optional[dict[str, Any]]:
    key = (guild_id, user_id)
    cached = _cache_get(_member_cache, key)
    if cached is not None:
        return cached
    member = await fetch_member(web_config.bot_token, guild_id, user_id)
    _cache_set(_member_cache, key, MEMBER_TTL, member)
    return member


@app.on_event("startup")
async def startup() -> None:
    await web_store.initialize()
    await raid_store.initialize()
    await template_store.initialize()
    await web_store.purge_expired_sessions()


def build_manage_components() -> list[dict[str, Any]]:
    return [
        {
            "type": 1,
            "components": [
                {
                    "type": 2,
                    "style": 2,
                    "label": "Edit",
                    "custom_id": "guildscout_raid_edit_v1",
                },
                {
                    "type": 2,
                    "style": 2,
                    "label": "Lock/Unlock",
                    "custom_id": "guildscout_raid_lock_v1",
                },
                {
                    "type": 2,
                    "style": 4,
                    "label": "Close",
                    "custom_id": "guildscout_raid_close_v1",
                },
            ],
        },
        {
            "type": 1,
            "components": [
                {
                    "type": 2,
                    "style": 2,
                    "label": "Follow-up",
                    "custom_id": "guildscout_raid_followup_v1",
                },
                {
                    "type": 2,
                    "style": 2,
                    "label": "Slots",
                    "custom_id": "guildscout_raid_slots_v1",
                },
                {
                    "type": 2,
                    "style": 4,
                    "label": "Cancel",
                    "custom_id": "guildscout_raid_cancel_v1",
                },
            ],
        },
    ]


def _sign_session(session_id: str) -> str:
    return signer.sign(session_id).decode("utf-8")


def _unsign_session(cookie_value: str) -> Optional[str]:
    if not cookie_value:
        return None
    try:
        return signer.unsign(cookie_value, max_age=60 * 60 * 24 * 14).decode("utf-8")
    except BadSignature:
        return None


def _parse_int(value: Optional[str], default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _parse_int_list(raw: str) -> list[int]:
    if not raw:
        return []
    values = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            values.append(int(part))
        except ValueError:
            continue
    return values


def _parse_float(value: Optional[str], default: float) -> float:
    if value is None:
        return default
    if isinstance(value, str) and not value.strip():
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_optional_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value or value.lower() in ("none", "null"):
            return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_str_list(raw: str) -> list[str]:
    if not raw:
        return []
    values = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        values.append(part)
    return values


def _list_to_csv(values: list[Any]) -> str:
    if not values:
        return ""
    return ", ".join(str(value) for value in values)


def _build_control_context(config_data: dict) -> dict[str, Any]:
    discord_cfg = config_data.get("discord", {})
    scoring_cfg = config_data.get("scoring", {})
    scoring_weights = scoring_cfg.get("weights", {})
    analytics_cfg = config_data.get("analytics", {})
    permissions_cfg = config_data.get("permissions", {})
    export_cfg = config_data.get("export", {})
    guild_cfg = config_data.get("guild_management", {})
    raid_cfg = config_data.get("raid_management", {})
    logging_cfg = config_data.get("logging", {})
    verification_cfg = config_data.get("verification", {})
    shadowops_cfg = config_data.get("shadowops", {})

    return {
        "discord": {
            "guild_id": discord_cfg.get("guild_id") or "",
            "service_logs_enabled": bool(discord_cfg.get("discord_service_logs_enabled", False)),
            "token_set": bool(discord_cfg.get("token")),
        },
        "scoring": {
            "days_in_server": scoring_weights.get("days_in_server", 0.1),
            "message_count": scoring_weights.get("message_count", 0.55),
            "voice_activity": scoring_weights.get("voice_activity", 0.35),
            "min_messages": scoring_cfg.get("min_messages", 10),
            "max_days_lookback": scoring_cfg.get("max_days_lookback") or "",
        },
        "analytics": {
            "cache_ttl": analytics_cfg.get("cache_ttl") or "",
            "excluded_channels": _list_to_csv(analytics_cfg.get("excluded_channels", [])),
            "excluded_channel_names": _list_to_csv(analytics_cfg.get("excluded_channel_names", [])),
        },
        "permissions": {
            "admin_roles": _list_to_csv(permissions_cfg.get("admin_roles", [])),
            "admin_users": _list_to_csv(permissions_cfg.get("admin_users", [])),
        },
        "export": {
            "max_users_per_embed": export_cfg.get("max_users_per_embed", 25),
            "csv_delimiter": export_cfg.get("csv_delimiter", ","),
            "csv_encoding": export_cfg.get("csv_encoding", "utf-8-sig"),
        },
        "guild_management": {
            "max_spots": guild_cfg.get("max_spots", 50),
            "guild_role_id": guild_cfg.get("guild_role_id") or "",
            "exclusion_roles": _list_to_csv(guild_cfg.get("exclusion_roles", [])),
            "exclusion_users": _list_to_csv(guild_cfg.get("exclusion_users", [])),
            "status_channel_id": guild_cfg.get("status_channel_id") or "",
            "dashboard_channel_id": guild_cfg.get("dashboard_channel_id") or "",
            "ranking_channel_message_id": guild_cfg.get("ranking_channel_message_id") or "",
            "ranking_channel_message_version": guild_cfg.get("ranking_channel_message_version", 0),
        },
        "raid_system": {
            "enabled": bool(raid_cfg.get("enabled", True)),
            "manage_channel_id": raid_cfg.get("manage_channel_id") or "",
            "info_message_id": raid_cfg.get("info_message_id") or "",
            "history_message_id": raid_cfg.get("history_message_id") or "",
        },
        "logging": {
            "level": logging_cfg.get("level", "INFO"),
            "file": logging_cfg.get("file", "logs/guildscout.log"),
            "format": logging_cfg.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            "alert_ping": logging_cfg.get("alert_ping") or "",
            "dashboard_update_interval_seconds": logging_cfg.get("dashboard_update_interval_seconds", 300),
            "dashboard_idle_gap_seconds": logging_cfg.get("dashboard_idle_gap_seconds", 120),
        },
        "verification": {
            "enable_daily": bool(verification_cfg.get("enable_daily", False)),
            "daily_sample_size": verification_cfg.get("daily_sample_size", 25),
            "daily_hour_utc": verification_cfg.get("daily_hour_utc", 3),
            "daily_minute": verification_cfg.get("daily_minute", 0),
            "enable_6h": bool(verification_cfg.get("enable_6h", False)),
            "sixhour_sample_size": verification_cfg.get("sixhour_sample_size", 30),
            "sixhour_hours_utc": _list_to_csv(verification_cfg.get("sixhour_hours_utc", [])),
            "enable_weekly": bool(verification_cfg.get("enable_weekly", False)),
            "weekly_sample_size": verification_cfg.get("weekly_sample_size", 150),
            "weekly_weekday": verification_cfg.get("weekly_weekday", 0),
            "weekly_hour_utc": verification_cfg.get("weekly_hour_utc", 4),
            "weekly_minute": verification_cfg.get("weekly_minute", 30),
        },
        "shadowops": {
            "enabled": bool(shadowops_cfg.get("enabled", False)),
            "webhook_url": shadowops_cfg.get("webhook_url") or "",
            "webhook_secret_set": bool(shadowops_cfg.get("webhook_secret")),
            "notify_on_verification": bool(shadowops_cfg.get("notify_on_verification", False)),
            "notify_on_errors": bool(shadowops_cfg.get("notify_on_errors", False)),
            "notify_on_health": bool(shadowops_cfg.get("notify_on_health", False)),
        },
    }


def _format_timestamp(ts: Optional[int], tz: Optional[ZoneInfo]) -> str:
    if not ts:
        return "—"
    zone = tz or timezone.utc
    return datetime.fromtimestamp(int(ts), zone).strftime("%d.%m.%Y %H:%M")


def _format_age(ts: Optional[int]) -> str:
    if not ts:
        return "—"
    now_ts = int(time.time())
    delta = int(ts) - now_ts
    suffix = "from now" if delta > 0 else "ago"
    delta = abs(delta)
    if delta < 60:
        return f"{delta}s {suffix}"
    minutes = delta // 60
    if minutes < 60:
        return f"{minutes}m {suffix}"
    hours = minutes // 60
    minutes = minutes % 60
    if hours < 24:
        return f"{hours}h {minutes}m {suffix}"
    days = hours // 24
    hours = hours % 24
    return f"{days}d {hours}h {suffix}"


def _get_mtime(path: Path) -> Optional[int]:
    try:
        return int(path.stat().st_mtime)
    except (FileNotFoundError, OSError):
        return None


async def _build_raid_payload(raid: RaidRecord, settings: GuildSettings) -> dict[str, Any]:
    signups = await raid_store.get_signups_by_role(raid.id)
    bench_preferences = await raid_store.get_bench_preferences(raid.id)
    embed = build_raid_embed(
        raid,
        signups,
        settings.timezone,
        None,
        None,
        bench_preferences,
    )
    return {
        "embeds": [embed.to_dict()],
        "components": build_manage_components(),
        "allowed_mentions": {"parse": []},
    }


async def _ensure_reactions(
    channel_id: int,
    message_id: int,
    raid: RaidRecord,
) -> None:
    for emoji, count in [
        (ROLE_EMOJIS[ROLE_TANK], raid.tanks_needed),
        (ROLE_EMOJIS[ROLE_HEALER], raid.healers_needed),
        (ROLE_EMOJIS[ROLE_DPS], raid.dps_needed),
        (ROLE_EMOJIS[ROLE_BENCH], raid.bench_needed),
    ]:
        if int(count) > 0:
            try:
                await add_reaction(web_config.bot_token, channel_id, message_id, emoji)
            except DiscordApiError:
                pass
    try:
        await add_reaction(
            web_config.bot_token,
            channel_id,
            message_id,
            ROLE_EMOJIS[ROLE_CANCEL],
        )
    except DiscordApiError:
        pass


async def _sync_raid_message(raid: RaidRecord, settings: GuildSettings) -> None:
    if not raid.message_id:
        return
    payload = await _build_raid_payload(raid, settings)
    await edit_message(
        web_config.bot_token,
        raid.channel_id,
        raid.message_id,
        payload,
    )


async def _post_raid_message(
    channel_id: int,
    raid: RaidRecord,
    settings: GuildSettings,
) -> int:
    payload = await _build_raid_payload(raid, settings)
    message = await create_message(web_config.bot_token, channel_id, payload)
    message_id = int(message.get("id"))
    await _ensure_reactions(channel_id, message_id, raid)
    return message_id


def _build_icon_url(guild_id: int, icon_hash: Optional[str]) -> Optional[str]:
    if not icon_hash:
        return None
    return f"https://cdn.discordapp.com/icons/{guild_id}/{icon_hash}.png?size=128"


def _settings_from_config(config_data: dict, guild_id: int, name: str) -> GuildSettings:
    raid_cfg = config_data.get("raid_management", {})
    return GuildSettings(
        guild_id=guild_id,
        name=name,
        raid_channel_id=raid_cfg.get("post_channel_id"),
        guildwar_channel_id=raid_cfg.get("guildwar_post_channel_id"),
        info_channel_id=raid_cfg.get("info_channel_id"),
        log_channel_id=raid_cfg.get("log_channel_id"),
        participant_role_id=raid_cfg.get("participant_role_id"),
        creator_roles=[int(role_id) for role_id in raid_cfg.get("creator_roles", [])],
        timezone=raid_cfg.get("timezone", "UTC"),
        reminder_hours=[int(val) for val in raid_cfg.get("reminder_hours", [])],
        dm_reminder_minutes=[int(val) for val in raid_cfg.get("dm_reminder_minutes", [])],
        checkin_enabled=bool(raid_cfg.get("checkin_enabled", False)),
        open_slot_ping_enabled=bool(raid_cfg.get("open_slot_ping_enabled", False)),
        auto_close_at_start=bool(raid_cfg.get("auto_close_at_start", False)),
        auto_close_after_hours=int(raid_cfg.get("auto_close_after_hours", 12)),
        confirmation_minutes=int(raid_cfg.get("confirmation_minutes", 15)),
        confirmation_reminder_minutes=int(raid_cfg.get("confirmation_reminder_minutes", 5)),
        open_slot_ping_minutes=int(raid_cfg.get("open_slot_ping_minutes", 30)),
    )


def _apply_settings_to_config(config_data: dict, settings: GuildSettings) -> dict:
    raid_cfg = config_data.setdefault("raid_management", {})
    raid_cfg["post_channel_id"] = settings.raid_channel_id
    raid_cfg["guildwar_post_channel_id"] = settings.guildwar_channel_id
    raid_cfg["info_channel_id"] = settings.info_channel_id
    raid_cfg["log_channel_id"] = settings.log_channel_id
    raid_cfg["participant_role_id"] = settings.participant_role_id
    raid_cfg["creator_roles"] = settings.creator_roles
    raid_cfg["timezone"] = settings.timezone
    raid_cfg["reminder_hours"] = settings.reminder_hours
    raid_cfg["dm_reminder_minutes"] = settings.dm_reminder_minutes
    raid_cfg["checkin_enabled"] = settings.checkin_enabled
    raid_cfg["open_slot_ping_enabled"] = settings.open_slot_ping_enabled
    raid_cfg["auto_close_at_start"] = settings.auto_close_at_start
    raid_cfg["auto_close_after_hours"] = settings.auto_close_after_hours
    raid_cfg["confirmation_minutes"] = settings.confirmation_minutes
    raid_cfg["confirmation_reminder_minutes"] = settings.confirmation_reminder_minutes
    raid_cfg["open_slot_ping_minutes"] = settings.open_slot_ping_minutes
    return config_data


async def _get_session(request: Request) -> Optional[WebSession]:
    cookie = request.cookies.get(web_config.cookie_name)
    session_id = _unsign_session(cookie) if cookie else None
    if not session_id:
        return None
    session = await web_store.get_session(session_id)
    if not session:
        return None
    if session.expires_at < int(time.time()):
        await web_store.delete_session(session_id)
        return None
    return session


async def _require_session(request: Request) -> Optional[WebSession]:
    session = await _get_session(request)
    if not session:
        return None
    return session


async def _get_guild_settings(guild_id: int, name: str) -> GuildSettings:
    stored = await web_store.get_guild_settings(guild_id)
    if stored:
        return stored
    config_data = load_bot_config(web_config.config_path)
    settings = _settings_from_config(config_data, guild_id, name)
    await web_store.upsert_guild_settings(settings)
    return settings


async def _user_can_manage(
    session: WebSession, guild_id: int, permissions: int
) -> bool:
    if permissions & 0x8 or permissions & 0x20:
        return True
    settings = await web_store.get_guild_settings(guild_id)
    creator_roles = settings.creator_roles if settings else []
    if not creator_roles:
        config_data = load_bot_config(web_config.config_path)
        if config_data.get("discord", {}).get("guild_id") == guild_id:
            raid_cfg = config_data.get("raid_management", {})
            creator_roles = [int(role_id) for role_id in raid_cfg.get("creator_roles", [])]
    if not creator_roles:
        return False
    member = await _fetch_member_cached(guild_id, session.user_id)
    if not member:
        return False
    role_ids = {int(role_id) for role_id in member.get("roles", [])}
    return any(role_id in role_ids for role_id in creator_roles)


async def _accessible_guilds(session: WebSession) -> list[dict[str, Any]]:
    """Get list of guilds the user can access.

    Note: Guild IDs are stored as integers internally for database operations,
    but a separate "id_str" field is provided for safe JSON serialization
    to JavaScript (which cannot handle integers > 2^53-1).
    """
    cached = _cache_get(_accessible_guilds_cache, session.user_id)
    if cached is not None:
        return cached
    guilds = await fetch_user_guilds(session.access_token)
    visible = []
    for guild in guilds:
        guild_id = int(guild["id"])
        permissions = int(guild.get("permissions", 0))
        bot_guild = await _fetch_bot_guild_cached(guild_id)
        if not bot_guild:
            continue
        if not await _user_can_manage(session, guild_id, permissions):
            continue
        visible.append(
            {
                "id": guild_id,  # Integer for backend operations
                "id_str": str(guild_id),  # String for frontend (BigInt safe)
                "name": guild.get("name", "Unknown"),
                "icon": _build_icon_url(guild_id, guild.get("icon")),
                "permissions": permissions,
            }
        )
    _cache_set(_accessible_guilds_cache, session.user_id, ACCESSIBLE_GUILDS_TTL, visible)
    return visible


def _guild_for_frontend(guild: dict[str, Any]) -> dict[str, Any]:
    """Convert guild dict to frontend-safe format with string ID.

    JavaScript cannot safely handle integers > 2^53-1, so we use id_str
    for the frontend while keeping the original integer id for backend ops.
    """
    return {**guild, "id": guild["id_str"]}


async def _require_guild_access(
    request: Request, guild_id: int
) -> tuple[Optional[WebSession], Optional[dict[str, Any]], Optional[dict[str, Any]]]:
    """Require session and guild access.

    This is the centralized function for checking guild access in all
    API endpoints, ensuring consistent multi-guild isolation.

    Args:
        request: The FastAPI request
        guild_id: The guild ID to check access for

    Returns:
        Tuple of (session, guild, error_response)
        If error_response is not None, return it immediately.
        Otherwise, session and guild are guaranteed to be valid.
    """
    session = await _require_session(request)
    if not session:
        return None, None, {"error": "Unauthorized", "success": False}

    guilds = await _accessible_guilds(session)
    guild = next((g for g in guilds if g["id"] == guild_id), None)
    if not guild:
        return session, None, {"error": "Guild not accessible", "success": False}

    return session, guild, None


@app.get("/", response_class=HTMLResponse)
async def root(request: Request) -> HTMLResponse:
    session = await _get_session(request)
    if not session:
        return RedirectResponse("/login")
    return RedirectResponse("/guilds")


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "client_id": web_config.discord_client_id,
        },
    )


@app.get("/auth/login")
async def auth_login() -> RedirectResponse:
    redirect_uri = quote(web_config.discord_redirect_uri, safe="")
    params = (
        f"client_id={web_config.discord_client_id}"
        f"&redirect_uri={redirect_uri}"
        "&response_type=code"
        "&scope=identify%20guilds"
    )
    return RedirectResponse(f"https://discord.com/api/oauth2/authorize?{params}")


@app.get("/auth/callback")
async def auth_callback(request: Request, code: str = "") -> RedirectResponse:
    if not code:
        return RedirectResponse("/login")
    try:
        token_data = await exchange_code_for_token(
            web_config.discord_client_id,
            web_config.discord_client_secret,
            web_config.discord_redirect_uri,
            code,
        )
        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token", "")
        expires_in = int(token_data.get("expires_in", 3600))
        user_data = await fetch_user(access_token)
    except DiscordApiError:
        return RedirectResponse("/login")

    session_id = uuid.uuid4().hex
    now_ts = int(time.time())
    session = WebSession(
        session_id=session_id,
        user_id=int(user_data["id"]),
        username=f"{user_data.get('username')}#{user_data.get('discriminator', '0')}",
        avatar=user_data.get("avatar"),
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=now_ts + expires_in,
        created_at=now_ts,
    )
    await web_store.create_session(session)

    response = RedirectResponse("/guilds", status_code=302)
    response.set_cookie(
        web_config.cookie_name,
        _sign_session(session_id),
        httponly=True,
        secure=web_config.cookie_secure,
        samesite="lax",
    )
    return response


@app.post("/auth/logout")
async def auth_logout(request: Request) -> RedirectResponse:
    session = await _get_session(request)
    if session:
        await web_store.delete_session(session.session_id)
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(web_config.cookie_name)
    return response


@app.get("/guilds", response_class=HTMLResponse)
async def guilds(request: Request) -> HTMLResponse:
    session = await _require_session(request)
    if not session:
        return RedirectResponse("/login")
    guild_list = await _accessible_guilds(session)
    avatar_url = build_avatar_url(session.user_id, session.avatar)

    # Use id_str for frontend to avoid JavaScript BigInt issues
    guilds_for_frontend = [
        {**g, "id": g["id_str"]} for g in guild_list
    ]

    return templates.TemplateResponse(
        "guilds.html",
        {
            "request": request,
            "session": session,
            "avatar_url": avatar_url,
            "guilds": guilds_for_frontend,
        },
    )


@app.get("/guilds/{guild_id}", response_class=HTMLResponse)
async def dashboard(request: Request, guild_id: int) -> HTMLResponse:
    session = await _require_session(request)
    if not session:
        return RedirectResponse("/login")

    guilds = await _accessible_guilds(session)
    guild = next((g for g in guilds if g["id"] == guild_id), None)
    if not guild:
        return RedirectResponse("/guilds")

    settings = await _get_guild_settings(guild_id, guild["name"])
    control = _build_control_context(load_bot_config(web_config.config_path))
    await template_store.ensure_default_templates(guild_id)
    templates_list = await template_store.list_templates(guild_id)

    open_raids = await raid_store.list_raids_by_guild(guild_id, status="open", limit=25)
    locked_raids = await raid_store.list_raids_by_guild(guild_id, status="locked", limit=25)
    active_raids = sorted(open_raids + locked_raids, key=lambda raid: raid.start_time)

    try:
        tz = ZoneInfo(settings.timezone)
    except Exception:
        tz = None

    latest_activity = await raid_store.get_latest_raid_activity(guild_id)
    latest_ts = None
    latest_label = "—"
    if latest_activity:
        latest_ts = latest_activity.get("closed_at") or latest_activity.get("created_at")
        latest_label = (
            f"{latest_activity.get('title', 'Raid')} ({latest_activity.get('status', 'unknown')})"
        )

    bot_pid_mtime = _get_mtime(ROOT / "bot-service.pid")
    log_mtime = _get_mtime(ROOT / "logs" / "guildscout.log")
    config_mtime = _get_mtime(web_config.config_path)
    health = {
        "bot_started_at": _format_timestamp(bot_pid_mtime, tz),
        "bot_uptime": _format_age(bot_pid_mtime),
        "bot_last_activity": _format_age(log_mtime),
        "config_updated_at": _format_timestamp(config_mtime, tz),
        "config_age": _format_age(config_mtime),
        "last_raid_label": latest_label,
        "last_raid_activity": _format_age(latest_ts),
    }

    cards = []
    for raid in active_raids:
        signups = await raid_store.get_signups_by_role(raid.id)
        tank_count = len(signups.get(ROLE_TANK, []))
        healer_count = len(signups.get(ROLE_HEALER, []))
        dps_count = len(signups.get(ROLE_DPS, []))
        bench_count = len(signups.get(ROLE_BENCH, []))
        total_main = raid.tanks_needed + raid.healers_needed + raid.dps_needed
        filled_main = tank_count + healer_count + dps_count
        total_needed = total_main + raid.bench_needed
        filled_total = filled_main + bench_count
        open_slots = max(total_needed - filled_total, 0)
        start_dt = datetime.fromtimestamp(raid.start_time, tz)
        cards.append(
            {
                "id": raid.id,
                "title": raid.title,
                "description": raid.description or "",
                "status": raid.status,
                "game": GAME_LABELS.get(raid.game, raid.game),
                "mode": MODE_LABELS.get(raid.mode, raid.mode),
                "game_id": raid.game,
                "mode_id": raid.mode,
                "start_time": start_dt.strftime("%d.%m.%Y %H:%M"),
                "timestamp": raid.start_time,
                "raid_date": start_dt.strftime("%Y-%m-%d"),
                "raid_time": start_dt.strftime("%H:%M"),
                "tanks_needed": raid.tanks_needed,
                "healers_needed": raid.healers_needed,
                "dps_needed": raid.dps_needed,
                "bench_needed": raid.bench_needed,
                "title_encoded": quote(raid.title, safe=""),
                "description_encoded": quote(raid.description or "", safe=""),
                "counts": {
                    "tank": f"{tank_count}/{raid.tanks_needed}",
                    "healer": f"{healer_count}/{raid.healers_needed}",
                    "dps": f"{dps_count}/{raid.dps_needed}",
                    "bench": f"{bench_count}/{raid.bench_needed}",
                },
                "open_slots": open_slots,
            }
        )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "session": session,
            "avatar_url": build_avatar_url(session.user_id, session.avatar),
            "guild": _guild_for_frontend(guild),
            "settings": settings,
            "control": control,
            "games": [{"id": GAME_WWM, "label": GAME_LABELS.get(GAME_WWM, GAME_WWM)}],
            "modes": [
                {"id": MODE_RAID, "label": MODE_LABELS.get(MODE_RAID, MODE_RAID)},
                {"id": MODE_GUILDWAR, "label": MODE_LABELS.get(MODE_GUILDWAR, MODE_GUILDWAR)},
            ],
            "health": health,
            "templates": templates_list,
            "raids": cards,
        },
    )


@app.get("/guilds/{guild_id}/raids/new", response_class=HTMLResponse)
async def new_raid(request: Request, guild_id: int) -> HTMLResponse:
    session = await _require_session(request)
    if not session:
        return RedirectResponse("/login")

    guilds = await _accessible_guilds(session)
    guild = next((g for g in guilds if g["id"] == guild_id), None)
    if not guild:
        return RedirectResponse("/guilds")

    settings = await _get_guild_settings(guild_id, guild["name"])
    await template_store.ensure_default_templates(guild_id)
    templates_list = await template_store.list_templates(guild_id)

    params = request.query_params
    prefill = {
        "title": str(params.get("title", "")).strip(),
        "description": str(params.get("description", "")).strip(),
        "game": str(params.get("game", "")).strip(),
        "mode": str(params.get("mode", "")).strip(),
        "raid_date": str(params.get("raid_date", "")).strip(),
        "raid_time": str(params.get("raid_time", "")).strip(),
        "tanks": _parse_optional_int(params.get("tanks")),
        "healers": _parse_optional_int(params.get("healers")),
        "dps": _parse_optional_int(params.get("dps")),
        "bench": _parse_optional_int(params.get("bench")),
    }
    prefill_has_slots = any(
        prefill.get(key) is not None for key in ("tanks", "healers", "dps", "bench")
    )

    template_cards = [
        {
            "id": template.template_id,
            "name": template.name,
            "tanks": template.tanks,
            "healers": template.healers,
            "dps": template.dps,
            "bench": template.bench,
            "is_default": template.is_default,
        }
        for template in templates_list
    ]

    return templates.TemplateResponse(
        "raid_create.html",
        {
            "request": request,
            "session": session,
            "avatar_url": build_avatar_url(session.user_id, session.avatar),
            "guild": _guild_for_frontend(guild),
            "settings": settings,
            "templates": template_cards,
            "games": [{"id": GAME_WWM, "label": GAME_LABELS.get(GAME_WWM, GAME_WWM)}],
            "modes": [
                {"id": MODE_RAID, "label": MODE_LABELS.get(MODE_RAID, MODE_RAID)},
                {"id": MODE_GUILDWAR, "label": MODE_LABELS.get(MODE_GUILDWAR, MODE_GUILDWAR)},
            ],
            "prefill": prefill,
            "prefill_has_slots": prefill_has_slots,
        },
    )


@app.post("/guilds/{guild_id}/raids")
async def create_raid(
    request: Request,
    guild_id: int,
    title: str = Form(...),
    description: str = Form(""),
    game: str = Form(GAME_WWM),
    mode: str = Form(MODE_RAID),
    raid_date: str = Form(...),
    raid_time: str = Form(...),
    tanks: int = Form(0),
    healers: int = Form(0),
    dps: int = Form(0),
    bench: int = Form(0),
) -> RedirectResponse:
    session = await _require_session(request)
    if not session:
        return RedirectResponse("/login")

    guilds = await _accessible_guilds(session)
    guild = next((g for g in guilds if g["id"] == guild_id), None)
    if not guild:
        return RedirectResponse("/guilds")

    settings = await _get_guild_settings(guild_id, guild["name"])
    post_channel_id = settings.raid_channel_id
    if mode == MODE_GUILDWAR:
        post_channel_id = settings.guildwar_channel_id

    if not post_channel_id:
        return RedirectResponse(f"/guilds/{guild_id}/raids/new?error=missing_channel")

    try:
        dt = parse_raid_datetime(raid_date, raid_time, settings.timezone)
    except ValueError:
        return RedirectResponse(f"/guilds/{guild_id}/raids/new?error=invalid_time")

    if int(dt.timestamp()) <= int(time.time()):
        return RedirectResponse(f"/guilds/{guild_id}/raids/new?error=past_time")

    if _parse_int(str(tanks)) + _parse_int(str(healers)) + _parse_int(str(dps)) <= 0:
        return RedirectResponse(f"/guilds/{guild_id}/raids/new?error=missing_slots")

    raid_id = await raid_store.create_raid(
        guild_id=guild_id,
        channel_id=post_channel_id,
        creator_id=session.user_id,
        title=title.strip(),
        description=description.strip() or None,
        game=game,
        mode=mode,
        start_time=int(dt.timestamp()),
        tanks_needed=_parse_int(str(tanks)),
        healers_needed=_parse_int(str(healers)),
        dps_needed=_parse_int(str(dps)),
        bench_needed=_parse_int(str(bench)),
    )

    raid = await raid_store.get_raid(raid_id)
    if not raid:
        return RedirectResponse(f"/guilds/{guild_id}/raids/new?error=save_failed")

    try:
        message = await create_message(
            web_config.bot_token,
            post_channel_id,
            await _build_raid_payload(raid, settings),
        )
    except DiscordApiError:
        return RedirectResponse(f"/guilds/{guild_id}/raids/new?error=post_failed")

    message_id = int(message.get("id"))
    await raid_store.set_message_id(raid_id, message_id)
    await _ensure_reactions(post_channel_id, message_id, raid)

    return RedirectResponse(f"/guilds/{guild_id}?created=1", status_code=302)


@app.get("/guilds/{guild_id}/raids/{raid_id}/edit", response_class=HTMLResponse)
async def edit_raid_page(request: Request, guild_id: int, raid_id: int) -> HTMLResponse:
    session = await _require_session(request)
    if not session:
        return RedirectResponse("/login")

    guilds = await _accessible_guilds(session)
    guild = next((g for g in guilds if g["id"] == guild_id), None)
    if not guild:
        return RedirectResponse("/guilds")

    raid = await raid_store.get_raid(raid_id)
    if not raid or raid.guild_id != guild_id:
        return RedirectResponse(f"/guilds/{guild_id}")

    settings = await _get_guild_settings(guild_id, guild["name"])
    await template_store.ensure_default_templates(guild_id)
    templates_list = await template_store.list_templates(guild_id)

    try:
        tz = ZoneInfo(settings.timezone)
    except Exception:
        tz = timezone.utc

    start_dt = datetime.fromtimestamp(raid.start_time, tz)
    prefill = {
        "title": raid.title,
        "description": raid.description or "",
        "game": raid.game,
        "mode": raid.mode,
        "raid_date": start_dt.strftime("%Y-%m-%d"),
        "raid_time": start_dt.strftime("%H:%M"),
        "tanks": raid.tanks_needed,
        "healers": raid.healers_needed,
        "dps": raid.dps_needed,
        "bench": raid.bench_needed,
    }

    return templates.TemplateResponse(
        "raid_edit.html",
        {
            "request": request,
            "session": session,
            "avatar_url": build_avatar_url(session.user_id, session.avatar),
            "guild": _guild_for_frontend(guild),
            "settings": settings,
            "raid": raid,
            "templates": templates_list,
            "games": [{"id": GAME_WWM, "label": GAME_LABELS.get(GAME_WWM, GAME_WWM)}],
            "modes": [
                {"id": MODE_RAID, "label": MODE_LABELS.get(MODE_RAID, MODE_RAID)},
                {"id": MODE_GUILDWAR, "label": MODE_LABELS.get(MODE_GUILDWAR, MODE_GUILDWAR)},
            ],
            "prefill": prefill,
        },
    )


@app.post("/guilds/{guild_id}/raids/{raid_id}/edit")
async def update_raid(
    request: Request,
    guild_id: int,
    raid_id: int,
    title: str = Form(...),
    description: str = Form(""),
    game: str = Form(GAME_WWM),
    mode: str = Form(MODE_RAID),
    raid_date: str = Form(...),
    raid_time: str = Form(...),
    tanks: int = Form(0),
    healers: int = Form(0),
    dps: int = Form(0),
    bench: int = Form(0),
    return_to: str = Form(""),
) -> RedirectResponse:
    session = await _require_session(request)
    if not session:
        return RedirectResponse("/login")

    guilds = await _accessible_guilds(session)
    guild = next((g for g in guilds if g["id"] == guild_id), None)
    if not guild:
        return RedirectResponse("/guilds")

    raid = await raid_store.get_raid(raid_id)
    if not raid or raid.guild_id != guild_id:
        return RedirectResponse(f"/guilds/{guild_id}")

    settings = await _get_guild_settings(guild_id, guild["name"])

    def _redirect_edit_error(code: str) -> RedirectResponse:
        if return_to == "dashboard":
            return RedirectResponse(
                f"/guilds/{guild_id}?edit_error={code}&raid_id={raid_id}", status_code=302
            )
        return RedirectResponse(
            f"/guilds/{guild_id}/raids/{raid_id}/edit?error={code}", status_code=302
        )

    try:
        dt = parse_raid_datetime(raid_date, raid_time, settings.timezone)
    except ValueError:
        return _redirect_edit_error("invalid_time")

    if int(dt.timestamp()) <= int(time.time()):
        return _redirect_edit_error("past_time")

    if _parse_int(str(tanks)) + _parse_int(str(healers)) + _parse_int(str(dps)) <= 0:
        return _redirect_edit_error("missing_slots")

    target_channel_id = settings.raid_channel_id
    if mode == MODE_GUILDWAR:
        target_channel_id = settings.guildwar_channel_id

    if not target_channel_id:
        return _redirect_edit_error("missing_channel")

    await raid_store.update_raid_details(
        raid_id=raid_id,
        title=title.strip(),
        description=description.strip() or None,
        start_time=int(dt.timestamp()),
    )
    await raid_store.update_raid_slots(
        raid_id=raid_id,
        tanks_needed=_parse_int(str(tanks)),
        healers_needed=_parse_int(str(healers)),
        dps_needed=_parse_int(str(dps)),
        bench_needed=_parse_int(str(bench)),
    )
    await raid_store.update_raid_game_mode(
        raid_id=raid_id,
        game=game,
        mode=mode,
    )

    updated = await raid_store.get_raid(raid_id)
    if updated:
        if updated.channel_id != target_channel_id or not updated.message_id:
            try:
                message_id = await _post_raid_message(target_channel_id, updated, settings)
            except DiscordApiError:
                return _redirect_edit_error("post_failed")
            await raid_store.update_raid_message_location(
                raid_id,
                target_channel_id,
                message_id,
            )
            old_message_id = updated.message_id
            old_channel_id = updated.channel_id
            if old_message_id:
                try:
                    await delete_message(
                        web_config.bot_token,
                        old_channel_id,
                        old_message_id,
                    )
                except DiscordApiError:
                    pass
        else:
            try:
                await _sync_raid_message(updated, settings)
            except DiscordApiError:
                pass

        synced = await raid_store.get_raid(raid_id)
        if synced and synced.message_id:
            await _ensure_reactions(synced.channel_id, synced.message_id, synced)

    return RedirectResponse(f"/guilds/{guild_id}?edited=1", status_code=302)


@app.post("/guilds/{guild_id}/raids/{raid_id}/close")
async def close_raid(
    request: Request,
    guild_id: int,
    raid_id: int,
) -> RedirectResponse:
    session = await _require_session(request)
    if not session:
        return RedirectResponse("/login")

    guilds = await _accessible_guilds(session)
    guild = next((g for g in guilds if g["id"] == guild_id), None)
    if not guild:
        return RedirectResponse("/guilds")

    raid = await raid_store.get_raid(raid_id)
    if not raid or raid.guild_id != guild_id:
        return RedirectResponse(f"/guilds/{guild_id}")

    await raid_store.update_status(raid_id, "closed")

    if raid.message_id:
        try:
            await delete_message(
                web_config.bot_token,
                raid.channel_id,
                raid.message_id,
            )
        except DiscordApiError:
            pass

    return RedirectResponse(f"/guilds/{guild_id}?closed=1", status_code=302)


@app.post("/guilds/{guild_id}/raids/{raid_id}/lock")
async def lock_raid(
    request: Request,
    guild_id: int,
    raid_id: int,
) -> RedirectResponse:
    session = await _require_session(request)
    if not session:
        return RedirectResponse("/login")

    guilds = await _accessible_guilds(session)
    guild = next((g for g in guilds if g["id"] == guild_id), None)
    if not guild:
        return RedirectResponse("/guilds")

    raid = await raid_store.get_raid(raid_id)
    if not raid or raid.guild_id != guild_id:
        return RedirectResponse(f"/guilds/{guild_id}")

    await raid_store.update_status(raid_id, "locked")
    updated = await raid_store.get_raid(raid_id)
    settings = await _get_guild_settings(guild_id, guild["name"])
    if updated:
        try:
            await _sync_raid_message(updated, settings)
        except DiscordApiError:
            pass

    return RedirectResponse(f"/guilds/{guild_id}?locked=1", status_code=302)


@app.post("/guilds/{guild_id}/raids/{raid_id}/unlock")
async def unlock_raid(
    request: Request,
    guild_id: int,
    raid_id: int,
) -> RedirectResponse:
    session = await _require_session(request)
    if not session:
        return RedirectResponse("/login")

    guilds = await _accessible_guilds(session)
    guild = next((g for g in guilds if g["id"] == guild_id), None)
    if not guild:
        return RedirectResponse("/guilds")

    raid = await raid_store.get_raid(raid_id)
    if not raid or raid.guild_id != guild_id:
        return RedirectResponse(f"/guilds/{guild_id}")

    await raid_store.update_status(raid_id, "open")
    updated = await raid_store.get_raid(raid_id)
    settings = await _get_guild_settings(guild_id, guild["name"])
    if updated:
        try:
            await _sync_raid_message(updated, settings)
        except DiscordApiError:
            pass

    return RedirectResponse(f"/guilds/{guild_id}?unlocked=1", status_code=302)


@app.get("/guilds/{guild_id}/templates", response_class=HTMLResponse)
async def templates_page(request: Request, guild_id: int) -> HTMLResponse:
    session = await _require_session(request)
    if not session:
        return RedirectResponse("/login")

    guilds = await _accessible_guilds(session)
    guild = next((g for g in guilds if g["id"] == guild_id), None)
    if not guild:
        return RedirectResponse("/guilds")

    await template_store.ensure_default_templates(guild_id)
    templates_list = await template_store.list_templates(guild_id)

    return templates.TemplateResponse(
        "templates.html",
        {
            "request": request,
            "session": session,
            "avatar_url": build_avatar_url(session.user_id, session.avatar),
            "guild": _guild_for_frontend(guild),
            "templates": templates_list,
        },
    )


@app.get("/guilds/{guild_id}/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request, guild_id: int) -> HTMLResponse:
    session = await _require_session(request)
    if not session:
        return RedirectResponse("/login")

    guilds = await _accessible_guilds(session)
    guild = next((g for g in guilds if g["id"] == guild_id), None)
    if not guild:
        return RedirectResponse("/guilds")

    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request,
            "session": session,
            "avatar_url": build_avatar_url(session.user_id, session.avatar),
            "guild": _guild_for_frontend(guild),
        },
    )


@app.get("/guilds/{guild_id}/my-score", response_class=HTMLResponse)
async def my_score_page(request: Request, guild_id: int) -> HTMLResponse:
    """User's personal score page."""
    session = await _require_session(request)
    if not session:
        return RedirectResponse("/login")

    guilds = await _accessible_guilds(session)
    guild = next((g for g in guilds if g["id"] == guild_id), None)
    if not guild:
        return RedirectResponse("/guilds")

    return templates.TemplateResponse(
        "my_score.html",
        {
            "request": request,
            "session": session,
            "avatar_url": build_avatar_url(session.user_id, session.avatar),
            "guild": _guild_for_frontend(guild),
        },
    )


@app.get("/guilds/{guild_id}/members", response_class=HTMLResponse)
async def members_page(request: Request, guild_id: int) -> HTMLResponse:
    """Member ranking page."""
    session = await _require_session(request)
    if not session:
        return RedirectResponse("/login")

    guilds = await _accessible_guilds(session)
    guild = next((g for g in guilds if g["id"] == guild_id), None)
    if not guild:
        return RedirectResponse("/guilds")

    return templates.TemplateResponse(
        "members.html",
        {
            "request": request,
            "session": session,
            "avatar_url": build_avatar_url(session.user_id, session.avatar),
            "guild": _guild_for_frontend(guild),
        },
    )


@app.post("/guilds/{guild_id}/templates")
async def create_template(
    request: Request,
    guild_id: int,
    name: str = Form(...),
    tanks: int = Form(0),
    healers: int = Form(0),
    dps: int = Form(0),
    bench: int = Form(0),
    is_default: Optional[str] = Form(None),
    return_to: str = Form(""),
) -> RedirectResponse:
    session = await _require_session(request)
    if not session:
        return RedirectResponse("/login")

    await template_store.create_template(
        guild_id=guild_id,
        name=name.strip(),
        tanks=_parse_int(str(tanks)),
        healers=_parse_int(str(healers)),
        dps=_parse_int(str(dps)),
        bench=_parse_int(str(bench)),
        is_default=bool(is_default),
    )
    if return_to == "dashboard":
        return RedirectResponse(f"/guilds/{guild_id}?templates_saved=1", status_code=302)
    return RedirectResponse(f"/guilds/{guild_id}/templates", status_code=302)


@app.post("/guilds/{guild_id}/templates/{template_id}/update")
async def update_template(
    request: Request,
    guild_id: int,
    template_id: int,
    name: str = Form(...),
    tanks: int = Form(0),
    healers: int = Form(0),
    dps: int = Form(0),
    bench: int = Form(0),
    is_default: Optional[str] = Form(None),
    return_to: str = Form(""),
) -> RedirectResponse:
    session = await _require_session(request)
    if not session:
        return RedirectResponse("/login")

    await template_store.update_template(
        template_id=template_id,
        name=name.strip(),
        tanks=_parse_int(str(tanks)),
        healers=_parse_int(str(healers)),
        dps=_parse_int(str(dps)),
        bench=_parse_int(str(bench)),
        is_default=bool(is_default),
    )
    if return_to == "dashboard":
        return RedirectResponse(f"/guilds/{guild_id}?templates_saved=1", status_code=302)
    return RedirectResponse(f"/guilds/{guild_id}/templates", status_code=302)


@app.post("/guilds/{guild_id}/templates/{template_id}/delete")
async def delete_template(
    request: Request,
    guild_id: int,
    template_id: int,
    return_to: str = Form(""),
) -> RedirectResponse:
    session = await _require_session(request)
    if not session:
        return RedirectResponse("/login")

    await template_store.delete_template(template_id)
    if return_to == "dashboard":
        return RedirectResponse(f"/guilds/{guild_id}?templates_saved=1", status_code=302)
    return RedirectResponse(f"/guilds/{guild_id}/templates", status_code=302)


@app.post("/guilds/{guild_id}/templates/{template_id}/default")
async def set_default_template(
    request: Request,
    guild_id: int,
    template_id: int,
) -> RedirectResponse:
    session = await _require_session(request)
    if not session:
        return RedirectResponse("/login")

    await template_store.set_default_template(template_id)
    return RedirectResponse(f"/guilds/{guild_id}/templates", status_code=302)


@app.get("/guilds/{guild_id}/settings", response_class=HTMLResponse)
async def settings_page(request: Request, guild_id: int) -> HTMLResponse:
    session = await _require_session(request)
    if not session:
        return RedirectResponse("/login")

    guilds = await _accessible_guilds(session)
    guild = next((g for g in guilds if g["id"] == guild_id), None)
    if not guild:
        return RedirectResponse("/guilds")

    settings = await _get_guild_settings(guild_id, guild["name"])
    config_data = load_bot_config(web_config.config_path)
    control = _build_control_context(config_data)

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "session": session,
            "avatar_url": build_avatar_url(session.user_id, session.avatar),
            "guild": _guild_for_frontend(guild),
            "settings": settings,
            "control": control,
        },
    )


@app.post("/guilds/{guild_id}/settings")
async def update_settings(
    request: Request,
    guild_id: int,
    raid_channel_id: str = Form(""),
    guildwar_channel_id: str = Form(""),
    info_channel_id: str = Form(""),
    log_channel_id: str = Form(""),
    participant_role_id: str = Form(""),
    creator_roles: str = Form(""),
    timezone: str = Form("UTC"),
    reminder_hours: str = Form(""),
    dm_reminder_minutes: str = Form(""),
    checkin_enabled: Optional[str] = Form(None),
    open_slot_ping_enabled: Optional[str] = Form(None),
    auto_close_at_start: Optional[str] = Form(None),
    auto_close_after_hours: str = Form("12"),
    confirmation_minutes: str = Form("15"),
    confirmation_reminder_minutes: str = Form("5"),
    open_slot_ping_minutes: str = Form("30"),
    return_to: str = Form(""),
) -> RedirectResponse:
    session = await _require_session(request)
    if not session:
        return RedirectResponse("/login")

    guilds = await _accessible_guilds(session)
    guild = next((g for g in guilds if g["id"] == guild_id), None)
    if not guild:
        return RedirectResponse("/guilds")

    settings = GuildSettings(
        guild_id=guild_id,
        name=guild["name"],
        raid_channel_id=_parse_int(raid_channel_id) or None,
        guildwar_channel_id=_parse_int(guildwar_channel_id) or None,
        info_channel_id=_parse_int(info_channel_id) or None,
        log_channel_id=_parse_int(log_channel_id) or None,
        participant_role_id=_parse_int(participant_role_id) or None,
        creator_roles=_parse_int_list(creator_roles),
        timezone=timezone.strip() or "UTC",
        reminder_hours=_parse_int_list(reminder_hours),
        dm_reminder_minutes=_parse_int_list(dm_reminder_minutes),
        checkin_enabled=bool(checkin_enabled),
        open_slot_ping_enabled=bool(open_slot_ping_enabled),
        auto_close_at_start=bool(auto_close_at_start),
        auto_close_after_hours=_parse_int(auto_close_after_hours, 12),
        confirmation_minutes=_parse_int(confirmation_minutes, 15),
        confirmation_reminder_minutes=_parse_int(confirmation_reminder_minutes, 5),
        open_slot_ping_minutes=_parse_int(open_slot_ping_minutes, 30),
    )
    await web_store.upsert_guild_settings(settings)

    config_data = load_bot_config(web_config.config_path)
    if config_data.get("discord", {}).get("guild_id") == guild_id:
        config_data = _apply_settings_to_config(config_data, settings)
        save_bot_config(config_data, web_config.config_path)

    if return_to == "dashboard":
        return RedirectResponse(f"/guilds/{guild_id}?settings_saved=1", status_code=302)
    return RedirectResponse(f"/guilds/{guild_id}/settings?saved=1", status_code=302)


@app.post("/guilds/{guild_id}/config")
async def update_config(request: Request, guild_id: int) -> RedirectResponse:
    session = await _require_session(request)
    if not session:
        return RedirectResponse("/login")

    guilds = await _accessible_guilds(session)
    guild = next((g for g in guilds if g["id"] == guild_id), None)
    if not guild:
        return RedirectResponse("/guilds")

    form = await request.form()
    section = str(form.get("section", "")).strip().lower()
    config_data = load_bot_config(web_config.config_path)

    if section == "scoring":
        scoring_cfg = config_data.setdefault("scoring", {})
        weights = scoring_cfg.setdefault("weights", {})
        weights["days_in_server"] = _parse_float(
            form.get("weight_days"), float(weights.get("days_in_server", 0.1))
        )
        weights["message_count"] = _parse_float(
            form.get("weight_messages"), float(weights.get("message_count", 0.55))
        )
        weights["voice_activity"] = _parse_float(
            form.get("weight_voice"), float(weights.get("voice_activity", 0.35))
        )
        scoring_cfg["min_messages"] = _parse_int(form.get("min_messages"), 10)
        scoring_cfg["max_days_lookback"] = _parse_optional_int(form.get("max_days_lookback"))

    elif section == "analytics":
        analytics_cfg = config_data.setdefault("analytics", {})
        analytics_cfg["cache_ttl"] = _parse_optional_int(form.get("cache_ttl"))
        analytics_cfg["excluded_channels"] = _parse_int_list(
            str(form.get("excluded_channels", ""))
        )
        analytics_cfg["excluded_channel_names"] = _parse_str_list(
            str(form.get("excluded_channel_names", ""))
        )

    elif section == "permissions":
        permissions_cfg = config_data.setdefault("permissions", {})
        permissions_cfg["admin_roles"] = _parse_int_list(str(form.get("admin_roles", "")))
        permissions_cfg["admin_users"] = _parse_int_list(str(form.get("admin_users", "")))

    elif section == "export":
        export_cfg = config_data.setdefault("export", {})
        export_cfg["max_users_per_embed"] = _parse_int(
            form.get("max_users_per_embed"), 25
        )
        export_cfg["csv_delimiter"] = str(form.get("csv_delimiter", ",")).strip() or ","
        export_cfg["csv_encoding"] = str(form.get("csv_encoding", "utf-8-sig")).strip() or "utf-8-sig"

    elif section == "guild_management":
        guild_cfg = config_data.setdefault("guild_management", {})
        guild_cfg["max_spots"] = _parse_int(form.get("max_spots"), 50)
        guild_cfg["guild_role_id"] = _parse_optional_int(form.get("guild_role_id"))
        guild_cfg["exclusion_roles"] = _parse_int_list(str(form.get("exclusion_roles", "")))
        guild_cfg["exclusion_users"] = _parse_int_list(str(form.get("exclusion_users", "")))
        guild_cfg["status_channel_id"] = _parse_optional_int(form.get("status_channel_id"))
        guild_cfg["dashboard_channel_id"] = _parse_optional_int(form.get("dashboard_channel_id"))
        guild_cfg["ranking_channel_message_id"] = _parse_optional_int(
            form.get("ranking_channel_message_id")
        )
        guild_cfg["ranking_channel_message_version"] = _parse_int(
            form.get("ranking_channel_message_version"), 0
        )

    elif section == "raid_system":
        raid_cfg = config_data.setdefault("raid_management", {})
        raid_cfg["enabled"] = bool(form.get("raid_enabled"))
        raid_cfg["manage_channel_id"] = _parse_optional_int(form.get("manage_channel_id"))
        raid_cfg["info_message_id"] = _parse_optional_int(form.get("info_message_id"))
        raid_cfg["history_message_id"] = _parse_optional_int(form.get("history_message_id"))

    elif section == "logging":
        logging_cfg = config_data.setdefault("logging", {})
        logging_cfg["level"] = str(form.get("log_level", "INFO")).strip() or "INFO"
        logging_cfg["file"] = str(form.get("log_file", "logs/guildscout.log")).strip() or "logs/guildscout.log"
        logging_cfg["format"] = str(form.get("log_format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")).strip()
        logging_cfg["alert_ping"] = str(form.get("alert_ping", "")).strip() or None
        logging_cfg["dashboard_update_interval_seconds"] = _parse_int(
            form.get("dashboard_update_interval_seconds"), 300
        )
        logging_cfg["dashboard_idle_gap_seconds"] = _parse_int(
            form.get("dashboard_idle_gap_seconds"), 120
        )

    elif section == "verification":
        verification_cfg = config_data.setdefault("verification", {})
        verification_cfg["enable_daily"] = bool(form.get("enable_daily"))
        verification_cfg["daily_sample_size"] = _parse_int(form.get("daily_sample_size"), 25)
        verification_cfg["daily_hour_utc"] = _parse_int(form.get("daily_hour_utc"), 3)
        verification_cfg["daily_minute"] = _parse_int(form.get("daily_minute"), 0)
        verification_cfg["enable_6h"] = bool(form.get("enable_6h"))
        verification_cfg["sixhour_sample_size"] = _parse_int(
            form.get("sixhour_sample_size"), 30
        )
        verification_cfg["sixhour_hours_utc"] = _parse_int_list(
            str(form.get("sixhour_hours_utc", ""))
        )
        verification_cfg["enable_weekly"] = bool(form.get("enable_weekly"))
        verification_cfg["weekly_sample_size"] = _parse_int(form.get("weekly_sample_size"), 150)
        verification_cfg["weekly_weekday"] = _parse_int(form.get("weekly_weekday"), 0)
        verification_cfg["weekly_hour_utc"] = _parse_int(form.get("weekly_hour_utc"), 4)
        verification_cfg["weekly_minute"] = _parse_int(form.get("weekly_minute"), 30)

    elif section == "shadowops":
        shadowops_cfg = config_data.setdefault("shadowops", {})
        shadowops_cfg["enabled"] = bool(form.get("shadowops_enabled"))
        shadowops_cfg["webhook_url"] = str(form.get("shadowops_webhook_url", "")).strip() or None
        secret = str(form.get("shadowops_webhook_secret", "")).strip()
        if secret:
            shadowops_cfg["webhook_secret"] = secret
        shadowops_cfg["notify_on_verification"] = bool(form.get("notify_on_verification"))
        shadowops_cfg["notify_on_errors"] = bool(form.get("notify_on_errors"))
        shadowops_cfg["notify_on_health"] = bool(form.get("notify_on_health"))

    elif section == "discord":
        discord_cfg = config_data.setdefault("discord", {})
        guild_id_value = _parse_optional_int(form.get("discord_guild_id"))
        if guild_id_value:
            discord_cfg["guild_id"] = guild_id_value
        discord_cfg["discord_service_logs_enabled"] = bool(
            form.get("discord_service_logs_enabled")
        )
        token = str(form.get("discord_token", "")).strip()
        if token:
            discord_cfg["token"] = token

    save_bot_config(config_data, web_config.config_path)

    anchor = f"#{section}" if section else ""
    return RedirectResponse(
        f"/guilds/{guild_id}/settings?saved=1{anchor}", status_code=302
    )


# =============================================================================
# API ENDPOINTS (JSON)
# =============================================================================


@app.get("/api/guilds/{guild_id}/analytics/rankings")
async def api_analytics_rankings(
    request: Request,
    guild_id: int,
    limit: int = 50,
    offset: int = 0,
):
    """Get member rankings with scores.

    Multi-Guild Isolation: Rankings are filtered by guild_id in all
    database queries. User must have access to the guild.
    """
    session, guild, error = await _require_guild_access(request, guild_id)
    if error:
        return error

    # Load scoring weights from config
    config_data = load_bot_config(web_config.config_path)
    scoring_cfg = config_data.get("scoring", {})
    weights = scoring_cfg.get("weights", {})

    analytics = get_analytics_service(str(ROOT / "data" / "messages.db"))
    analytics.set_weights(
        days=weights.get("days_in_server", 0.10),
        messages=weights.get("message_count", 0.55),
        voice=weights.get("voice_activity", 0.35),
    )

    result = await analytics.get_member_rankings(
        guild_id=guild_id,
        limit=limit,
        offset=offset,
        days_lookback=scoring_cfg.get("max_days_lookback"),
    )

    return {"success": True, "data": result}


@app.get("/api/guilds/{guild_id}/analytics/overview")
async def api_analytics_overview(
    request: Request,
    guild_id: int,
    days: int = 7,
):
    """Get activity overview (daily/hourly stats).

    Multi-Guild Isolation: All activity data is filtered by guild_id.
    """
    session, guild, error = await _require_guild_access(request, guild_id)
    if error:
        return error

    analytics = get_analytics_service(str(ROOT / "data" / "messages.db"))
    result = await analytics.get_activity_overview(guild_id=guild_id, days=days)

    return {"success": True, "data": result}


@app.get("/api/guilds/{guild_id}/members/{user_id}/score")
async def api_member_score(
    request: Request,
    guild_id: int,
    user_id: int,
):
    """Get score for a specific member.

    Multi-Guild Isolation: Score is calculated only using data from the
    specified guild. User must have access to the guild.
    """
    session, guild, error = await _require_guild_access(request, guild_id)
    if error:
        return error

    # Load scoring weights from config
    config_data = load_bot_config(web_config.config_path)
    scoring_cfg = config_data.get("scoring", {})
    weights = scoring_cfg.get("weights", {})

    analytics = get_analytics_service(str(ROOT / "data" / "messages.db"))
    analytics.set_weights(
        days=weights.get("days_in_server", 0.10),
        messages=weights.get("message_count", 0.55),
        voice=weights.get("voice_activity", 0.35),
    )

    result = await analytics.get_member_score(
        guild_id=guild_id,
        user_id=user_id,
        days_lookback=scoring_cfg.get("max_days_lookback"),
    )

    if result is None:
        return {"error": "Member not found", "success": False}

    return {"success": True, "data": result}


@app.get("/api/guilds/{guild_id}/my-score")
async def api_my_score(request: Request, guild_id: int):
    """Get the current user's score.

    Multi-Guild Isolation: Returns the user's score only for the specified
    guild. The user must be a member of the guild.
    """
    session, guild, error = await _require_guild_access(request, guild_id)
    if error:
        return error

    # Load scoring weights from config
    config_data = load_bot_config(web_config.config_path)
    scoring_cfg = config_data.get("scoring", {})
    weights = scoring_cfg.get("weights", {})

    analytics = get_analytics_service(str(ROOT / "data" / "messages.db"))
    analytics.set_weights(
        days=weights.get("days_in_server", 0.10),
        messages=weights.get("message_count", 0.55),
        voice=weights.get("voice_activity", 0.35),
    )

    result = await analytics.get_member_score(
        guild_id=guild_id,
        user_id=session.user_id,
        days_lookback=scoring_cfg.get("max_days_lookback"),
    )

    if result is None:
        return {"error": "Score not found", "success": False}

    return {"success": True, "data": result}


@app.get("/api/guilds/{guild_id}/status")
async def api_guild_status(request: Request, guild_id: int):
    """Get system status for a guild.

    Multi-Guild Isolation: Returns status information specific to the guild.
    """
    session, guild, error = await _require_guild_access(request, guild_id)
    if error:
        return error

    # Bot status from PID file
    bot_pid_path = ROOT / "bot-service.pid"
    bot_running = bot_pid_path.exists()
    bot_started_at = None
    if bot_running:
        try:
            bot_started_at = datetime.fromtimestamp(
                bot_pid_path.stat().st_mtime, timezone.utc
            ).isoformat()
        except OSError:
            pass

    # Database stats
    db_path = ROOT / "data" / "messages.db"
    db_size_mb = 0
    if db_path.exists():
        db_size_mb = round(db_path.stat().st_size / 1024 / 1024, 2)

    # Config last modified
    config_path = web_config.config_path
    config_modified = None
    if config_path.exists():
        try:
            config_modified = datetime.fromtimestamp(
                config_path.stat().st_mtime, timezone.utc
            ).isoformat()
        except OSError:
            pass

    # Latest raid activity
    latest_activity = await raid_store.get_latest_raid_activity(guild_id)

    return {
        "success": True,
        "data": {
            "bot": {
                "running": bot_running,
                "started_at": bot_started_at,
            },
            "database": {
                "size_mb": db_size_mb,
                "path": str(db_path),
            },
            "config": {
                "modified_at": config_modified,
            },
            "latest_raid": latest_activity,
        }
    }


@app.get("/api/guilds/{guild_id}/activity")
async def api_guild_activity(
    request: Request,
    guild_id: int,
    limit: int = 20,
    hours: int = 48,
):
    """Get recent activity events for a guild.

    Multi-Guild Isolation: Activity events are filtered by guild_id.
    User must have access to the guild.
    """
    session, guild, error = await _require_guild_access(request, guild_id)
    if error:
        return error

    activity_service = get_activity_service(
        messages_db_path=str(ROOT / "data" / "messages.db"),
        raids_db_path=str(ROOT / "data" / "raids.db"),
    )

    activities = await activity_service.get_recent_activity(
        guild_id=guild_id,
        limit=limit,
        hours=hours,
    )

    summary = await activity_service.get_activity_summary(
        guild_id=guild_id,
        days=7,
    )

    return {
        "success": True,
        "data": {
            "activities": activities,
            "summary": summary,
        }
    }


# =============================================================================
# WEBSOCKET ENDPOINT
# =============================================================================


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    # Get session from cookie
    session_cookie = websocket.cookies.get("session")
    if not session_cookie:
        await websocket.close(code=4001, reason="No session")
        return

    try:
        session_id = signer.unsign(session_cookie, max_age=86400 * 7).decode()
    except BadSignature:
        await websocket.close(code=4001, reason="Invalid session")
        return

    session = await web_store.get_session(session_id)
    if not session:
        await websocket.close(code=4001, reason="Session expired")
        return

    # Get user's accessible guilds
    guilds = await _accessible_guilds(session)
    guild_ids = [g["id"] for g in guilds]

    # Connect to WebSocket manager
    ws_manager = get_websocket_manager()
    connection_id = await ws_manager.connect(
        websocket=websocket,
        user_id=session.user_id,
        guild_ids=guild_ids,
    )

    try:
        while True:
            # Receive and handle messages
            message = await websocket.receive_text()
            response = await ws_manager.handle_message(connection_id, message)
            if response:
                await websocket.send_text(response.to_json())
    except WebSocketDisconnect:
        await ws_manager.disconnect(connection_id)
    except Exception as e:
        await ws_manager.disconnect(connection_id)


@app.get("/api/ws/stats")
async def websocket_stats(request: Request):
    """Get WebSocket connection statistics."""
    session = await _require_session(request)
    if not session:
        return {"error": "Unauthorized", "success": False}

    ws_manager = get_websocket_manager()
    return {"success": True, "data": ws_manager.get_stats()}


if os.getenv("WEB_UI_DEBUG"):
    import uvicorn

    uvicorn.run("web_api.app:app", host="0.0.0.0", port=8080, reload=True)
