"""Discord API helpers for the web UI."""

from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx


DISCORD_API_BASE = "https://discord.com/api/v10"


class DiscordApiError(RuntimeError):
    pass


def _headers(token: str, token_type: str = "Bot") -> Dict[str, str]:
    return {
        "Authorization": f"{token_type} {token}",
        "User-Agent": "GuildScoutWebUI (https://github.com/zerodoxx/guildscout, 1.0)",
    }


async def exchange_code_for_token(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
) -> Dict[str, Any]:
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{DISCORD_API_BASE}/oauth2/token", data=data, headers=headers)
    if resp.status_code != 200:
        raise DiscordApiError(f"Token exchange failed ({resp.status_code})")
    return resp.json()


async def fetch_user(access_token: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{DISCORD_API_BASE}/users/@me",
            headers=_headers(access_token, token_type="Bearer"),
        )
    if resp.status_code != 200:
        raise DiscordApiError("Failed to fetch user profile")
    return resp.json()


async def fetch_user_guilds(access_token: str) -> list[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{DISCORD_API_BASE}/users/@me/guilds",
            headers=_headers(access_token, token_type="Bearer"),
        )
    if resp.status_code != 200:
        raise DiscordApiError("Failed to fetch user guilds")
    return resp.json()


async def fetch_bot_guild(bot_token: str, guild_id: int) -> Optional[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{DISCORD_API_BASE}/guilds/{guild_id}",
            headers=_headers(bot_token, token_type="Bot"),
        )
    if resp.status_code == 200:
        return resp.json()
    return None


async def fetch_member(bot_token: str, guild_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{DISCORD_API_BASE}/guilds/{guild_id}/members/{user_id}",
            headers=_headers(bot_token, token_type="Bot"),
        )
    if resp.status_code == 200:
        return resp.json()
    return None


async def create_message(
    bot_token: str,
    channel_id: int,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{DISCORD_API_BASE}/channels/{channel_id}/messages",
            headers=_headers(bot_token, token_type="Bot"),
            json=payload,
        )
    if resp.status_code not in (200, 201):
        raise DiscordApiError(f"Failed to create message ({resp.status_code})")
    return resp.json()


async def edit_message(
    bot_token: str,
    channel_id: int,
    message_id: int,
    payload: Dict[str, Any],
) -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.patch(
            f"{DISCORD_API_BASE}/channels/{channel_id}/messages/{message_id}",
            headers=_headers(bot_token, token_type="Bot"),
            json=payload,
        )
    if resp.status_code not in (200, 204):
        raise DiscordApiError(f"Failed to edit message ({resp.status_code})")


async def delete_message(bot_token: str, channel_id: int, message_id: int) -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.delete(
            f"{DISCORD_API_BASE}/channels/{channel_id}/messages/{message_id}",
            headers=_headers(bot_token, token_type="Bot"),
        )
    if resp.status_code not in (200, 204):
        raise DiscordApiError("Failed to delete message")


async def add_reaction(
    bot_token: str,
    channel_id: int,
    message_id: int,
    emoji: str,
) -> None:
    encoded = quote(emoji)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.put(
            f"{DISCORD_API_BASE}/channels/{channel_id}/messages/{message_id}/reactions/{encoded}/@me",
            headers=_headers(bot_token, token_type="Bot"),
        )
    if resp.status_code not in (200, 204):
        raise DiscordApiError("Failed to add reaction")


async def remove_role(
    bot_token: str,
    guild_id: int,
    user_id: int,
    role_id: int,
) -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.delete(
            f"{DISCORD_API_BASE}/guilds/{guild_id}/members/{user_id}/roles/{role_id}",
            headers=_headers(bot_token, token_type="Bot"),
        )
    if resp.status_code not in (204, 200):
        raise DiscordApiError("Failed to remove role")


def build_avatar_url(user_id: int, avatar_hash: Optional[str]) -> Optional[str]:
    if not avatar_hash:
        return None
    ext = "gif" if avatar_hash.startswith("a_") else "png"
    return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.{ext}?size=128"


__all__ = [
    "DiscordApiError",
    "exchange_code_for_token",
    "fetch_user",
    "fetch_user_guilds",
    "fetch_bot_guild",
    "fetch_member",
    "create_message",
    "edit_message",
    "delete_message",
    "add_reaction",
    "remove_role",
    "build_avatar_url",
]
