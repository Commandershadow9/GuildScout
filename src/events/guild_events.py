"""
Guild Events - Handle bot joining servers and auto-setup.
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands

from src.utils.config import Config
from src.utils.welcome import post_welcome_message, refresh_welcome_message
from src.database.message_store import MessageStore

logger = logging.getLogger(__name__)


class GuildEvents(commands.Cog):
    """Event handlers for guild-related events."""

    def __init__(self, bot: commands.Bot, config: Config, message_store: MessageStore):
        self.bot = bot
        self.config = config
        self._refresh_tasks = {}  # Track pending refresh tasks per guild
        self.message_store = message_store

    @commands.Cog.listener()
    async def on_ready(self):
        """Ensure ranking channel exists when the bot becomes ready."""
        for guild in self.bot.guilds:
            if guild.id != self.config.guild_id:
                continue
            await self._ensure_ranking_channel(guild)
            await self._ensure_log_channel(guild)
            await refresh_welcome_message(self.config, guild, force=True)
            await self._sync_members(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """
        Automatically create admin channel when bot joins a server.

        Creates:
        - Admin-only ranking channel (#guild-rankings)
        - Sends welcome message to server owner
        - Logs the join event
        """
        try:
            logger.info(f"Bot joined new guild: {guild.name} (ID: {guild.id})")
            await self._create_ranking_channel(guild, notify_owner=True)
            await self._create_log_channel(guild)
            await refresh_welcome_message(self.config, guild, force=True)
            await self._sync_members(guild)
            logger.info(f"Auto-setup completed for guild: {guild.name}")
        except discord.Forbidden:
            logger.error(f"Missing permissions to create channel in {guild.name} (ID: {guild.id})")
        except Exception as e:
            logger.error(f"Error during auto-setup for {guild.name}: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        """Log when bot is removed from a server."""
        logger.info(f"Bot removed from guild: {guild.name} (ID: {guild.id})")

        # Clean up stored ranking channel reference
        if hasattr(self.bot, 'ranking_channels') and guild.id in self.bot.ranking_channels:
            del self.bot.ranking_channels[guild.id]
            logger.info(f"Removed ranking channel reference for guild {guild.id}")

        if guild.id == self.config.guild_id:
            self.config.set_ranking_channel_id(None)
            if self.config.ranking_channel_message_id:
                self.config.set_ranking_channel_message_id(None)
            if self.config.ranking_channel_message_version:
                self.config.set_ranking_channel_message_version(0)
            self.config.set_log_channel_id(None)
            # Clear tracked members for that guild
            if self.message_store:
                await self.message_store.reset_guild(guild.id)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Track member joins for accurate stats."""
        if member.guild.id != self.config.guild_id or member.bot:
            return

        try:
            await self.message_store.upsert_member(member)
        except Exception as exc:
            logger.error(
                "Failed to record joined member %s: %s",
                member.display_name,
                exc,
                exc_info=True
            )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Remove departed members from stats."""
        if member.guild.id != self.config.guild_id:
            return

        try:
            await self.message_store.remove_member(member.guild.id, member.id)
        except Exception as exc:
            logger.error(
                "Failed to remove departed member %s: %s",
                getattr(member, "display_name", member.id),
                exc,
                exc_info=True
            )

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Refresh overview when guild role membership changes (with debouncing)."""
        if after.guild.id != self.config.guild_id:
            return

        try:
            await self.message_store.upsert_member(after)
        except Exception as exc:
            logger.warning(
                "Failed to update member snapshot for %s: %s",
                after.display_name,
                exc
            )

        role_id = self.config.guild_role_id
        if not role_id:
            return

        before_has = any(role.id == role_id for role in before.roles)
        after_has = any(role.id == role_id for role in after.roles)

        if before_has != after_has:
            # Debounce: Cancel existing task and schedule new one
            guild_id = after.guild.id
            if guild_id in self._refresh_tasks:
                self._refresh_tasks[guild_id].cancel()

            # Schedule refresh after 3 seconds (allows batching multiple updates)
            async def delayed_refresh():
                await asyncio.sleep(3)
                await refresh_welcome_message(self.config, after.guild, force=True)
                if guild_id in self._refresh_tasks:
                    del self._refresh_tasks[guild_id]

            self._refresh_tasks[guild_id] = asyncio.create_task(delayed_refresh())

    async def _create_ranking_channel(self, guild: discord.Guild, notify_owner: bool = False) -> discord.TextChannel:
        """Create the ranking channel with correct permissions."""
        overwrites = self._build_channel_overwrites(guild)

        ranking_channel = await guild.create_text_channel(
            name="guild-rankings",
            topic="📊 GuildScout Rankings - Automated ranking results and score breakdowns (Admin Only)",
            overwrites=overwrites
        )

        previous_channel_id = self.config.ranking_channel_id
        await post_welcome_message(
            self.config,
            ranking_channel,
            previous_channel_id=previous_channel_id,
            force=True
        )

        self._store_ranking_channel(guild, ranking_channel.id)
        logger.info(f"Created ranking channel: #{ranking_channel.name} (ID: {ranking_channel.id})")

        if notify_owner:
            await self._notify_owner(guild, ranking_channel)

        return ranking_channel

    async def _ensure_ranking_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Ensure the configured guild has a usable ranking channel."""
        stored_id = None
        if hasattr(self.bot, 'ranking_channels') and guild.id in self.bot.ranking_channels:
            stored_id = self.bot.ranking_channels[guild.id]
        elif self.config.ranking_channel_id:
            stored_id = self.config.ranking_channel_id

        existing_channel = guild.get_channel(stored_id) if stored_id else None

        if not existing_channel:
            existing_channel = discord.utils.get(guild.text_channels, name="guild-rankings")

        if existing_channel:
            previous_channel_id = self.config.ranking_channel_id
            await post_welcome_message(
                self.config,
                existing_channel,
                previous_channel_id=previous_channel_id,
                force=False
            )
            self._store_ranking_channel(guild, existing_channel.id)
            logger.info(
                f"Using existing ranking channel {existing_channel.name} for guild {guild.name}"
            )
            return existing_channel

        logger.info(f"No ranking channel found for guild {guild.name}. Creating one automatically.")
        try:
            return await self._create_ranking_channel(guild, notify_owner=False)
        except discord.Forbidden:
            logger.error(f"Missing permissions to create channel in {guild.name} (ID: {guild.id})")
        except Exception as exc:
            logger.error(f"Failed to auto-create ranking channel in {guild.name}: {exc}", exc_info=True)

        return None

    async def _create_log_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Create the Discord log channel"""
        overwrites = self._build_channel_overwrites(guild)
        log_channel = await guild.create_text_channel(
            name="guildscout-logs",
            topic="🧾 GuildScout Logs – Analysen und Systemereignisse",
            overwrites=overwrites
        )

        self._store_log_channel(guild, log_channel.id)
        await self._post_log_intro(log_channel)
        logger.info("Created log channel #%s (%s)", log_channel.name, log_channel.id)
        return log_channel

    async def _ensure_log_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        channel_id = self.config.log_channel_id
        channel = guild.get_channel(channel_id) if channel_id else None
        if channel:
            self._store_log_channel(guild, channel.id)
            return channel

        existing = discord.utils.get(guild.text_channels, name="guildscout-logs")
        if existing:
            self._store_log_channel(guild, existing.id)
            return existing

        try:
            return await self._create_log_channel(guild)
        except discord.Forbidden:
            logger.error("Missing permissions to create log channel in %s", guild.name)
        except Exception as exc:
            logger.error("Failed to create log channel in %s: %s", guild.name, exc, exc_info=True)
        return None

    def _build_channel_overwrites(self, guild: discord.Guild) -> dict:
        """Build permission overwrites for the ranking channel."""
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                embed_links=True,
                attach_files=True
            )
        }

        for role_id in self.config.admin_roles:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True
                )
                logger.info(f"Added admin role {role.name} to ranking channel permissions")

        return overwrites

    def _store_ranking_channel(self, guild: discord.Guild, channel_id: int) -> None:
        """Remember ranking channel mapping and persist to config."""
        if not hasattr(self.bot, 'ranking_channels'):
            self.bot.ranking_channels = {}

        self.bot.ranking_channels[guild.id] = channel_id
        if self.config.ranking_channel_id != channel_id:
            self.config.set_ranking_channel_id(channel_id)

    def _store_log_channel(self, guild: discord.Guild, channel_id: int) -> None:
        if not hasattr(self.bot, 'log_channels'):
            self.bot.log_channels = {}
        self.bot.log_channels[guild.id] = channel_id
        if self.config.log_channel_id != channel_id:
            self.config.set_log_channel_id(channel_id)

    async def _post_log_intro(self, channel: discord.TextChannel) -> None:
        embed = discord.Embed(
            title="🧾 GuildScout Logs",
            description=(
                "Automatische Protokolle: Analyse-Starts, Ergebnisse und Fehler werden hier festgehalten."
            ),
            color=discord.Color.dark_gold(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="Was wird geloggt?",
            value=(
                "• `/analyze` Start & Ergebnis\n"
                "• Cache-Informationen\n"
                "• Fehlermeldungen"
            ),
            inline=False
        )
        embed.set_footer(text="GuildScout Monitoring")
        await channel.send(embed=embed)

    async def _notify_owner(self, guild: discord.Guild, ranking_channel: discord.TextChannel) -> None:
        """Send setup confirmation to the guild owner."""
        try:
            if guild.owner:
                owner_embed = discord.Embed(
                    title="🎉 GuildScout Setup Complete!",
                    description=(
                        f"GuildScout has been successfully added to **{guild.name}**!\n\n"
                        f"An admin-only ranking channel has been created: {ranking_channel.mention}\n"
                        f"Check there for commands and setup instructions."
                    ),
                    color=discord.Color.green()
                )
                owner_embed.add_field(
                    name="⚙️ Next Steps",
                    value=(
                        f"1. Go to {ranking_channel.mention} in your server\n"
                        "2. Follow the Quick Start Guide\n"
                        "3. Configure `config/config.yaml` with your role IDs\n"
                        "4. Start analyzing and ranking members!"
                    ),
                    inline=False
                )
                await guild.owner.send(embed=owner_embed)
                logger.info(f"Sent setup confirmation to server owner: {guild.owner.name}")
        except discord.Forbidden:
            logger.warning(
                f"Could not send DM to server owner: {guild.owner.name if guild.owner else 'Unknown'}"
            )

    async def _sync_members(self, guild: discord.Guild) -> None:
        """Ensure the message store knows all members of the guild."""
        if not self.message_store:
            return

        try:
            await self.message_store.sync_guild_members(guild)
        except Exception as exc:
            logger.error(
                "Failed to sync members for %s: %s",
                guild.name,
                exc,
                exc_info=True
            )


async def setup(bot: commands.Bot, config: Config, message_store: MessageStore):
    """Setup function to add this cog to the bot."""
    await bot.add_cog(GuildEvents(bot, config, message_store))
    logger.info("GuildEvents cog loaded")
