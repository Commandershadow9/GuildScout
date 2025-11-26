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

    async def send_temp_status(
        self,
        guild: discord.Guild,
        title: str,
        description: str,
        *,
        color: discord.Color = discord.Color.blue(),
        message: Optional[discord.Message] = None
    ) -> Optional[discord.Message]:
        """
        Send or update a temporary status message (without acknowledgment button).
        Used for "Running..." or progress messages that will be deleted later.

        Args:
            guild: Discord guild
            title: Status title
            description: Status description
            color: Embed color (default blue)
            message: Existing message to update (or None to create new)

        Returns:
            Sent/updated message or None if failed
        """
        async with self._lock:
            channel = self._get_status_channel(guild)
            if not channel:
                return None

            # Create embed
            embed = discord.Embed(
                title=title,
                description=description,
                color=color,
                timestamp=datetime.utcnow()
            )

            try:
                if message:
                    # Update existing message
                    await message.edit(embed=embed)
                    return message
                else:
                    # Send new message
                    message = await channel.send(embed=embed)
                    return message

            except Exception as e:
                logger.error(f"Failed to send temp status: {e}", exc_info=True)
                return None

    async def cleanup_status_channel(self, guild: discord.Guild):
        """
        Clean up obsolete status messages (e.g., old startup/success messages).
        Preserves active errors and warnings.
        """
        async with self._lock:
            channel = self._get_status_channel(guild)
            if not channel:
                return

            try:
                # Define phrases that indicate a message can be safely deleted
                cleanup_phrases = [
                    "GuildScout gestartet",
                    "GuildScout verbunden",
                    "Verifikation abgeschlossen",
                    "Verifikation erfolgreich",
                    "Delta-Import abgeschlossen",
                    "Import abgeschlossen",
                    "Stichproben-Verifikation",
                    "Tiefenprüfung"
                ]

                deleted_count = 0
                
                # Check last 50 messages
                async for message in channel.history(limit=50):
                    # Only check messages from this bot
                    if message.author.id != self.bot.user.id:
                        continue

                    # Skip if it has no embeds (unlikely for us, but safe check)
                    if not message.embeds:
                        continue

                    embed = message.embeds[0]
                    title = embed.title or ""
                    
                    # CRITICAL: Do NOT delete errors or warnings
                    # These usually have "❌" or "⚠️" in the title, or color red/orange
                    if "❌" in title or "⚠️" in title or "Fehler" in title:
                        continue
                        
                    if embed.color == discord.Color.red():
                        continue

                    # Delete if title matches known cleanup phrases
                    should_delete = False
                    for phrase in cleanup_phrases:
                        if phrase in title:
                            should_delete = True
                            break
                    
                    # Also cleanup temporary "Running" messages that might have stuck
                    if "Läuft" in title or "Verifiziere" in title or "Import läuft" in title:
                        # Only delete if older than 30 minutes (stuck process)
                        age = datetime.utcnow() - message.created_at
                        if age.total_seconds() > 1800:
                            should_delete = True

                    if should_delete:
                        try:
                            await message.delete()
                            deleted_count += 1
                            await asyncio.sleep(0.5)  # Avoid rate limits
                        except Exception:
                            pass

                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} obsolete messages in status channel for {guild.name}")

            except Exception as e:
                logger.error(f"Failed to cleanup status channel: {e}")

    def get_unacknowledged_count(self, guild_id: int) -> int:
        """Get count of unacknowledged status messages (not yet implemented - would need tracking)."""
        # TODO: Track active messages and count unacknowledged ones
        return 0

    def get_acknowledgments(self, guild_id: int, limit: int = 10) -> list:
        """Get recent acknowledgments for a guild."""
        return self._acknowledgments.get(guild_id, [])[:limit]
