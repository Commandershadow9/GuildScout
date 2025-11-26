"""Status Manager for Error and Warning Messages with Acknowledgment."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import discord
from discord.ext import commands

from src.utils.config import Config

logger = logging.getLogger("guildscout.status")


class AcknowledgeButton(discord.ui.View):
    """Button view for acknowledging status messages."""

    def __init__(self, status_manager, guild_id: int, message_id: int):
        super().__init__(timeout=None)  # No timeout - button stays forever
        self.status_manager = status_manager
        self.guild_id = guild_id
        self.message_id = message_id

    @discord.ui.button(label="✅ Bestätigt", style=discord.ButtonStyle.success, custom_id="acknowledge_status")
    async def acknowledge(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle acknowledgment button click."""
        try:
            # Check if user has permission (admin)
            if not self.status_manager._has_admin_permission(interaction.user, interaction.guild):
                await interaction.response.send_message(
                    "❌ Nur Admins können Fehler bestätigen.",
                    ephemeral=True
                )
                return

            # Record acknowledgment
            self.status_manager._record_acknowledgment(
                self.guild_id,
                self.message_id,
                interaction.user
            )

            # Delete message
            await interaction.message.delete()
            logger.info(
                f"Status message {self.message_id} acknowledged and deleted by {interaction.user} "
                f"in guild {self.guild_id}"
            )

            # Send ephemeral confirmation
            await interaction.response.send_message(
                "✅ Fehler bestätigt und gelöscht.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Failed to handle acknowledgment: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "❌ Fehler beim Löschen der Nachricht.",
                    ephemeral=True
                )
            except:
                pass


class StatusManager:
    """Manages error and warning messages in status channel with acknowledgment system."""

    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config
        self._acknowledgments: Dict[int, list] = {}  # guild_id -> list of acknowledgments
        self._lock = asyncio.Lock()

    def _get_status_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Get the status channel for a guild."""
        channel_id = self.config.status_channel_id
        if not channel_id:
            return None

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            logger.warning(f"Status channel {channel_id} not found or not a text channel")
            return None

        return channel

    def _has_admin_permission(self, user: discord.Member, guild: discord.Guild) -> bool:
        """Check if user has admin permission."""
        # Check admin roles
        for role_id in self.config.admin_roles:
            role = guild.get_role(role_id)
            if role and role in user.roles:
                return True

        # Check admin users
        if user.id in self.config.admin_users:
            return True

        # Check server administrator permission
        if user.guild_permissions.administrator:
            return True

        return False

    def _record_acknowledgment(self, guild_id: int, message_id: int, user: discord.Member):
        """Record that a status message was acknowledged."""
        if guild_id not in self._acknowledgments:
            self._acknowledgments[guild_id] = []

        self._acknowledgments[guild_id].append({
            "message_id": message_id,
            "user_id": user.id,
            "user_name": str(user),
            "timestamp": datetime.utcnow().isoformat()
        })

        # Keep only last 50 acknowledgments per guild
        self._acknowledgments[guild_id] = self._acknowledgments[guild_id][-50:]

    async def send_error(
        self,
        guild: discord.Guild,
        title: str,
        description: str,
        *,
        ping: Optional[str] = None,
        color: discord.Color = discord.Color.red()
    ) -> Optional[discord.Message]:
        """
        Send an error message to status channel with acknowledgment button.

        Args:
            guild: Discord guild
            title: Error title
            description: Error description
            ping: Optional mention/ping (@here, <@&role>, etc.)
            color: Embed color (default red)

        Returns:
            Sent message or None if failed
        """
        async with self._lock:
            channel = self._get_status_channel(guild)
            if not channel:
                logger.warning(f"No status channel configured for guild {guild.name}")
                return None

            # Create embed
            embed = discord.Embed(
                title=title,
                description=description,
                color=color,
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="Fehler bestätigen um zu löschen")

            # Create acknowledgment button
            view = AcknowledgeButton(self, guild.id, 0)  # message_id will be set after sending

            try:
                # Send with ping if provided
                content = ping if ping else None
                message = await channel.send(content=content, embed=embed, view=view)

                # Update button with actual message ID
                view.message_id = message.id

                logger.info(f"Sent error message {message.id} to status channel in {guild.name}")
                return message

            except Exception as e:
                logger.error(f"Failed to send error to status channel: {e}", exc_info=True)
                return None

    async def send_warning(
        self,
        guild: discord.Guild,
        title: str,
        description: str,
        *,
        ping: Optional[str] = None
    ) -> Optional[discord.Message]:
        """
        Send a warning message to status channel with acknowledgment button.

        Args:
            guild: Discord guild
            title: Warning title
            description: Warning description
            ping: Optional mention/ping

        Returns:
            Sent message or None if failed
        """
        return await self.send_error(
            guild,
            title,
            description,
            ping=ping,
            color=discord.Color.orange()
        )

    def get_unacknowledged_count(self, guild_id: int) -> int:
        """Get count of unacknowledged status messages (not yet implemented - would need tracking)."""
        # TODO: Track active messages and count unacknowledged ones
        return 0

    def get_acknowledgments(self, guild_id: int, limit: int = 10) -> list:
        """Get recent acknowledgments for a guild."""
        return self._acknowledgments.get(guild_id, [])[:limit]
