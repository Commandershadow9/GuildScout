"""Voice activity tracking module."""

import logging
from datetime import datetime, timezone
from typing import Dict, Tuple
import discord
from discord.ext import commands

from src.utils.config import Config
from src.database.message_store import MessageStore

logger = logging.getLogger("guildscout.voice_tracking")


class VoiceTracking(commands.Cog):
    """Tracks voice channel activity."""

    def __init__(self, bot: commands.Bot, config: Config, message_store: MessageStore):
        self.bot = bot
        self.config = config
        self.message_store = message_store
        # Memory storage for active sessions: (guild_id, user_id) -> start_time
        self.active_sessions: Dict[Tuple[int, int], datetime] = {}

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        """Handle voice state updates (join, leave, move)."""
        if member.bot or not self.config.voice_tracking_enabled:
            return

        guild_id = member.guild.id
        user_id = member.id
        now = datetime.now(timezone.utc)
        key = (guild_id, user_id)

        # Case 1: User left a voice channel (or moved)
        if before.channel is not None:
            if key in self.active_sessions:
                start_time = self.active_sessions.pop(key)
                
                # Was the previous channel AFK?
                was_afk = self.config.voice_exclude_afk and before.channel == member.guild.afk_channel
                
                if not was_afk:
                    await self.message_store.log_voice_session(
                        guild_id=guild_id,
                        user_id=user_id,
                        channel_id=before.channel.id,
                        start_time=start_time,
                        end_time=now
                    )
                    logger.debug(f"Logged voice session for {member.display_name}: {(now - start_time).total_seconds()}s")

        # Case 2: User joined a voice channel (or moved)
        if after.channel is not None:
            # Check for AFK channel exclusion
            is_afk = self.config.voice_exclude_afk and after.channel == member.guild.afk_channel
            
            if not is_afk:
                self.active_sessions[key] = now
                logger.debug(f"Started voice session for {member.display_name} in {after.channel.name}")

    def scan_active_users(self):
        """Scan all guilds for currently active voice users (use on startup)."""
        if not self.config.voice_tracking_enabled:
            return

        count = 0
        now = datetime.now(timezone.utc)

        for guild in self.bot.guilds:
            for channel in guild.voice_channels:
                # Skip AFK channels if configured
                if self.config.voice_exclude_afk and channel == guild.afk_channel:
                    continue

                for member in channel.members:
                    if member.bot:
                        continue
                    
                    key = (guild.id, member.id)
                    if key not in self.active_sessions:
                        self.active_sessions[key] = now
                        count += 1
        
        logger.info(f"Initialized {count} active voice sessions from scan.")

    @commands.Cog.listener()
    async def on_ready(self):
        """Called when bot is ready. Perform initial scan."""
        # We use a task to avoid blocking on_ready if it takes long, 
        # though iterating guild cache is usually fast.
        self.scan_active_users()


async def setup(bot: commands.Bot, config: Config, message_store: MessageStore):
    """Setup the voice tracking cog."""
    await bot.add_cog(VoiceTracking(bot, config, message_store))
