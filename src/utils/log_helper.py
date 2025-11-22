"""Utility helpers for logging events to Discord log channel."""

import logging
from datetime import datetime
from typing import Optional

import discord

from .config import Config

logger = logging.getLogger("guildscout.log_helper")


class DiscordLogger:
    """Utility to send log embeds to the configured Discord log channel."""

    def __init__(self, bot: discord.Client, config: Config):
        self.bot = bot
        self.config = config

    def get_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        channel_id = None
        if hasattr(self.bot, "log_channels") and guild.id in self.bot.log_channels:
            channel_id = self.bot.log_channels[guild.id]
        elif self.config.log_channel_id:
            channel_id = self.config.log_channel_id

        if not channel_id:
            return None

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            logger.warning("Configured log channel %s not found", channel_id)
            return None
        return channel

    async def send(
        self,
        guild: discord.Guild,
        title: str,
        description: str,
        *,
        status: str,
        color: discord.Color = discord.Color.blurple(),
        message: Optional[discord.Message] = None,
        ping: Optional[str] = None
    ) -> Optional[discord.Message]:
        channel = self.get_channel(guild)
        if not channel:
            return None

        embed = discord.Embed(
            title=title,
            description=f"{description}\n\n**Status:** {status}",
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="GuildScout Logs")

        try:
            if message:
                await message.edit(embed=embed)
                return message
            return await channel.send(
                content=ping if ping else None,
                embed=embed
            )
        except Exception as exc:
            logger.warning("Failed to send Discord log entry: %s", exc)
            return None
