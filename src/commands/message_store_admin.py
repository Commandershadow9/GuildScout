"""Admin commands for message store management."""

import logging
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

from ..utils import Config
from ..database.message_store import MessageStore
from ..utils.historical_import import HistoricalImporter


logger = logging.getLogger("guildscout.commands.message_store_admin")


class MessageStoreAdminCommands(commands.Cog):
    """Cog for message store admin commands."""

    def __init__(
        self,
        bot: commands.Bot,
        config: Config,
        message_store: MessageStore
    ):
        """
        Initialize message store admin commands.

        Args:
            bot: Discord bot instance
            config: Configuration object
            message_store: MessageStore instance
        """
        self.bot = bot
        self.config = config
        self.message_store = message_store

    def _has_permission(self, interaction: discord.Interaction) -> bool:
        """
        Check if user has admin permission.

        Args:
            interaction: Discord interaction

        Returns:
            True if user has permission
        """
        # Check admin users list
        if interaction.user.id in self.config.admin_users:
            return True

        # Check admin roles
        if hasattr(interaction.user, 'roles'):
            user_role_ids = [role.id for role in interaction.user.roles]
            for admin_role_id in self.config.admin_roles:
                if admin_role_id in user_role_ids:
                    return True

        return False

    @app_commands.command(
        name="import-messages",
        description="[Admin] Import historical messages for accurate tracking"
    )
    @app_commands.describe(
        force="Force re-import even if already completed (resets all data)"
    )
    async def import_messages(
        self,
        interaction: discord.Interaction,
        force: bool = False
    ):
        """
        Import all historical messages for the guild.

        Args:
            interaction: Discord interaction
            force: Force re-import
        """
        # Check permissions
        if not self._has_permission(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Check if already imported
            is_imported = await self.message_store.is_import_completed(
                interaction.guild.id
            )

            if is_imported and not force:
                await interaction.followup.send(
                    "ℹ️ Historical data has already been imported for this guild.\n"
                    "Use `force=True` to re-import (this will reset all data).",
                    ephemeral=True
                )
                return

            if force and is_imported:
                # Reset guild data first
                await self.message_store.reset_guild(interaction.guild.id)
                await interaction.followup.send(
                    "🔄 Guild data reset. Starting re-import...",
                    ephemeral=True
                )

            # Create importer
            excluded_channel_names = getattr(
                self.config,
                'excluded_channel_names',
                ['nsfw', 'bot-spam']
            )

            importer = HistoricalImporter(
                guild=interaction.guild,
                message_store=self.message_store,
                excluded_channel_names=excluded_channel_names
            )

            # Send initial message
            progress_msg = await interaction.followup.send(
                "📥 Starting historical message import...\n"
                "This may take a while depending on server size.",
                ephemeral=True
            )

            # Progress callback
            last_update = datetime.utcnow()

            async def progress_callback(channel_name: str, current: int, total: int):
                nonlocal last_update
                # Update every 5 seconds to avoid rate limits
                now = datetime.utcnow()
                if (now - last_update).total_seconds() >= 5:
                    try:
                        await progress_msg.edit(
                            content=f"📥 Importing messages...\n"
                            f"Processing channel: **{channel_name}**\n"
                            f"Progress: **{current}/{total}** channels"
                        )
                        last_update = now
                    except Exception as e:
                        logger.warning(f"Failed to update progress message: {e}")

            # Run import
            logger.info(
                f"Starting message import for guild {interaction.guild.name} "
                f"by {interaction.user.name}"
            )

            result = await importer.import_guild_history(
                progress_callback=progress_callback
            )

            if result['success']:
                # Create success embed
                embed = discord.Embed(
                    title="✅ Historical Import Completed",
                    color=discord.Color.green(),
                    timestamp=datetime.utcnow()
                )

                embed.add_field(
                    name="📊 Import Statistics",
                    value=(
                        f"**Total Messages:** {result['total_messages']:,}\n"
                        f"**Channels Processed:** {result['channels_processed']}\n"
                        f"**Channels Failed:** {result['channels_failed']}\n"
                        f"**Total Channels:** {result['total_channels']}"
                    ),
                    inline=False
                )

                embed.add_field(
                    name="🚀 What's Next?",
                    value=(
                        "The bot will now track new messages in real-time!\n"
                        "Use `/analyze` to see accurate message counts."
                    ),
                    inline=False
                )

                await progress_msg.edit(content=None, embed=embed)

                logger.info(
                    f"Import completed for guild {interaction.guild.name}: "
                    f"{result['total_messages']} messages imported"
                )
            else:
                await progress_msg.edit(
                    content=f"❌ Import failed: {result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            logger.error(f"Error during message import: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error during import: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(
        name="message-store-stats",
        description="[Admin] View message store statistics"
    )
    async def message_store_stats(self, interaction: discord.Interaction):
        """
        Show message store statistics.

        Args:
            interaction: Discord interaction
        """
        # Check permissions
        if not self._has_permission(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            stats = await self.message_store.get_stats(interaction.guild.id)

            embed = discord.Embed(
                title="📊 Message Store Statistics",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )

            # Import status
            if stats['import_completed']:
                status = "✅ Completed"
                if stats['import_date']:
                    import_date = datetime.fromisoformat(stats['import_date'])
                    status += f" on {import_date.strftime('%Y-%m-%d %H:%M UTC')}"
            else:
                status = "❌ Not Completed - Use `/import-messages` to start"

            embed.add_field(
                name="📥 Import Status",
                value=status,
                inline=False
            )

            # Data statistics
            embed.add_field(
                name="📈 Tracked Data",
                value=(
                    f"**Total Messages:** {stats['total_messages']:,}\n"
                    f"**Total Users:** {stats['total_users']:,}\n"
                    f"**Total Channels:** {stats['total_channels']:,}"
                ),
                inline=False
            )

            # Database info
            embed.add_field(
                name="💾 Database",
                value=(
                    f"**Size:** {stats['db_size_mb']} MB\n"
                    f"**Path:** `data/messages.db`"
                ),
                inline=False
            )

            embed.set_footer(text="Real-time tracking active for new messages")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error getting message store stats: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error getting stats: {str(e)}",
                ephemeral=True
            )


async def setup(bot: commands.Bot, config: Config, message_store: MessageStore):
    """
    Setup the message store admin commands cog.

    Args:
        bot: Discord bot instance
        config: Configuration object
        message_store: MessageStore instance
    """
    cog = MessageStoreAdminCommands(bot, config, message_store)
    await bot.add_cog(cog)
    logger.info("Message store admin commands loaded")
