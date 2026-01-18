"""Configuration helpers for the GuildScout web UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv
import yaml


@dataclass(frozen=True)
class WebConfig:
    discord_client_id: str
    discord_client_secret: str
    discord_redirect_uri: str
    session_secret: str
    bot_token: str
    guild_id: int | None
    config_path: Path
    web_db_path: Path
    cookie_name: str
    cookie_secure: bool


DEFAULT_COOKIE_NAME = "guildscout_session"


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)


def load_web_config(config_path: Path | None = None) -> WebConfig:
    load_dotenv()

    config_path = config_path or Path("config/config.yaml")
    config_data = _read_yaml(config_path)

    discord_cfg = config_data.get("discord", {})
    bot_token = discord_cfg.get("token")
    guild_id = discord_cfg.get("guild_id")

    client_id = os.getenv("DISCORD_CLIENT_ID", "").strip()
    client_secret = os.getenv("DISCORD_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("DISCORD_REDIRECT_URI", "").strip()
    session_secret = os.getenv("SESSION_SECRET", "").strip()

    cookie_name = os.getenv("WEB_COOKIE_NAME", DEFAULT_COOKIE_NAME).strip()
    cookie_secure = os.getenv("WEB_COOKIE_SECURE", "false").strip().lower() == "true"

    db_path_raw = os.getenv("WEB_DB_PATH", "data/web_ui.db")
    web_db_path = Path(db_path_raw)

    if not bot_token:
        raise RuntimeError("Discord bot token missing in config/config.yaml")
    if not client_id or not client_secret or not redirect_uri:
        raise RuntimeError("Discord OAuth env vars missing")
    if not session_secret:
        raise RuntimeError("SESSION_SECRET missing")

    return WebConfig(
        discord_client_id=client_id,
        discord_client_secret=client_secret,
        discord_redirect_uri=redirect_uri,
        session_secret=session_secret,
        bot_token=bot_token,
        guild_id=int(guild_id) if guild_id else None,
        config_path=config_path,
        web_db_path=web_db_path,
        cookie_name=cookie_name,
        cookie_secure=cookie_secure,
    )


def load_bot_config(config_path: Path | None = None) -> dict:
    config_path = config_path or Path("config/config.yaml")
    return _read_yaml(config_path)


def save_bot_config(config_data: dict, config_path: Path | None = None) -> None:
    config_path = config_path or Path("config/config.yaml")
    _write_yaml(config_path, config_data)


__all__ = [
    "WebConfig",
    "load_web_config",
    "load_bot_config",
    "save_bot_config",
]
