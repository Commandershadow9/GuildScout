"""Main bot file for GuildScout Discord Bot."""

import logging
import discord
from discord.ext import commands
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import Config, setup_logger
from src.utils.log_helper import DiscordLogger
from src.database import MessageCache
from src.database.message_store import MessageStore
from src.commands.analyze import setup as setup_analyze
from src.commands.my_score import setup as setup_my_score
from src.commands.admin import setup as setup_admin
from src.commands.ranking_channel import setup as setup_ranking_channel
from src.commands.assign_guild_role import setup as setup_assign_guild_role
from src.commands.guild_status import setup as setup_guild_status
from src.commands.set_max_spots import setup as setup_set_max_spots
from src.commands.log_channel import setup as setup_log_channel
from src.commands.message_store_admin import setup as setup_message_store_admin
from src.events.guild_events import setup as setup_guild_events
from src.events.message_tracking import setup as setup_message_tracking


class GuildScoutBot(commands.Bot):
    """Main GuildScout Bot class."""

    def __init__(
        self,
        config: Config,
        cache: MessageCache,
        message_store: MessageStore,
        *args,
        **kwargs
    ):
        """
        Initialize the GuildScout bot.

        Args:
            config: Configuration object
            cache: MessageCache instance
            message_store: MessageStore instance
        """
        self.config = config
        self.cache = cache
        self.message_store = message_store
        self.logger = logging.getLogger("guildscout.bot")
        self.discord_logger = DiscordLogger(bot=self, config=config)
        self._import_task = None  # Store background import task to prevent garbage collection

        # Initialize bot with intents
        intents = discord.Intents.default()
        intents.members = True  # Required for member list
        intents.message_content = True  # Required for message counting

        super().__init__(
            command_prefix="!",  # Prefix for text commands (not used in slash commands)
            intents=intents,
            *args,
            **kwargs
        )

    async def setup_hook(self):
        """Setup hook called when bot is starting."""
        self.logger.info("Setting up bot...")

        # Initialize cache
        await self.cache.initialize()
        self.logger.info("Cache initialized")

        # Initialize message store
        await self.message_store.initialize()
        self.logger.info("Message store initialized")

        # Load commands
        await setup_analyze(self, self.config, self.cache)
        await setup_my_score(self, self.config, self.cache)
        await setup_admin(self, self.config, self.cache)
        await setup_ranking_channel(self, self.config)
        await setup_assign_guild_role(self, self.config, self.cache)
        await setup_guild_status(self, self.config)
        await setup_set_max_spots(self, self.config)
        await setup_log_channel(self, self.config)
        await setup_message_store_admin(self, self.config, self.message_store)
        self.logger.info("Commands loaded")

        # Load event handlers
        await setup_guild_events(self, self.config)
        await setup_message_tracking(self, self.config, self.message_store)
        self.logger.info("Event handlers loaded")

        # Sync commands to guild
        try:
            guild = discord.Object(id=self.config.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            self.logger.info(f"Synced commands to guild {self.config.guild_id}")
        except Exception as e:
            self.logger.error(f"Failed to sync commands: {e}")

    async def on_ready(self):
        """Called when bot is ready."""
        self.logger.info(f"Bot is ready! Logged in as {self.user.name} ({self.user.id})")
        self.logger.info(f"Connected to {len(self.guilds)} guild(s)")

        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="guild activity | /analyze /my-score"
            )
        )

        if self.config.discord_service_logs_enabled:
            guild = self.get_guild(self.config.guild_id)
            if guild:
                description = (
                    f"Verbunden mit **{len(self.guilds)}** Server(n)\n"
                    f"Cache bereit, Commands synchronisiert"
                )
                await self.discord_logger.send(
                    guild,
                    "🤖 GuildScout gestartet",
                    description,
                    status="✅ Online",
                    color=discord.Color.green()
                )

                # Auto-start historical import if not completed
                await self._check_and_start_auto_import(guild)

    async def _create_import_status_message(self, guild: discord.Guild):
        """
        Create initial import status message in Discord.

        Args:
            guild: Discord guild

        Returns:
            Discord message object for updating
        """
        if not self.config.discord_service_logs_enabled:
            return None

        # Get log channel
        log_channel_id = getattr(self.config, 'discord_service_log_channel_id', None)
        if not log_channel_id:
            return None

        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            return None

        # Create initial embed
        embed = discord.Embed(
            title="📥 Historischer Datenimport",
            description="Import läuft...\nDieser Status wird automatisch aktualisiert.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Status", value="🔄 Import gestartet", inline=True)
        embed.add_field(name="Dauer", value="0s", inline=True)
        embed.add_field(name="Nachrichten", value="0", inline=True)
        embed.set_footer(text="Letztes Update")
        embed.timestamp = discord.utils.utcnow()

        try:
            message = await log_channel.send(embed=embed)
            self.logger.info(f"Created live status message in #{log_channel.name}")
            return message
        except Exception as e:
            self.logger.error(f"Failed to create status message: {e}")
            return None

    async def _update_import_status_periodically(
        self,
        guild: discord.Guild,
        status_message: discord.Message
    ):
        """
        Periodically update import status message.

        Args:
            guild: Discord guild
            status_message: Discord message to update
        """
        import asyncio
        from datetime import datetime, timezone

        while True:
            try:
                # Check if import is still running
                is_running = await self.message_store.is_import_running(guild.id)
                if not is_running:
                    # Import completed or stopped
                    self.logger.info("Import completed - stopping status updates")
                    break

                # Get import start time
                import_start_time = await self.message_store.get_import_start_time(guild.id)
                if not import_start_time:
                    break

                # Calculate duration
                now = datetime.now(timezone.utc)
                duration = now - import_start_time
                duration_minutes = int(duration.total_seconds() // 60)
                duration_seconds = int(duration.total_seconds() % 60)
                duration_str = f"{duration_minutes}m {duration_seconds}s"

                # Get current stats
                stats = await self.message_store.get_stats(guild.id)
                total_messages = stats.get('total_messages', 0)

                # Update embed
                embed = discord.Embed(
                    title="📥 Historischer Datenimport",
                    description="Import läuft...\nDieser Status wird automatisch aktualisiert.",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Status", value="🔄 Aktiv", inline=True)
                embed.add_field(name="Dauer", value=duration_str, inline=True)
                embed.add_field(name="Nachrichten", value=f"{total_messages:,}", inline=True)
                embed.set_footer(text="Letztes Update")
                embed.timestamp = discord.utils.utcnow()

                await status_message.edit(embed=embed)
                self.logger.debug(f"Updated status: {total_messages:,} messages, {duration_str}")

                # Sleep before next update (30 seconds)
                await asyncio.sleep(30)

            except asyncio.CancelledError:
                # Task was cancelled - import finished
                self.logger.info("Status update task cancelled - import finished")
                break
            except Exception as e:
                self.logger.error(f"Error updating status message: {e}", exc_info=True)
                # Continue trying

    async def _check_and_start_auto_import(self, guild: discord.Guild):
        """
        Check if historical import is needed and start it automatically.

        Args:
            guild: Discord guild
        """
        try:
            # Check if import already completed
            is_completed = await self.message_store.is_import_completed(guild.id)

            if is_completed:
                self.logger.info(f"✅ Historical import already completed for {guild.name}")
                return

            # Check if import is already running
            is_running = await self.message_store.is_import_running(guild.id)

            if is_running:
                self.logger.warning(f"⚠️ Historical import already running for {guild.name}")
                return

            # Import not completed - start it in background
            self.logger.info(f"📥 Starting automatic historical import for {guild.name}")

            # Send Discord notification
            if self.config.discord_service_logs_enabled:
                await self.discord_logger.send(
                    guild,
                    "📥 Automatischer Datenimport gestartet",
                    (
                        "Der Bot importiert jetzt alle historischen Nachrichten.\n"
                        "Dies kann 30-60 Minuten dauern.\n\n"
                        "**Bot bleibt währenddessen voll funktionsfähig!**\n"
                        "Commands funktionieren normal (ggf. etwas langsamer).\n\n"
                        "Fortschritt wird in den Logs angezeigt."
                    ),
                    status="🔄 Import läuft",
                    color=discord.Color.blue()
                )

            # Start import in background
            import asyncio
            self._import_task = asyncio.create_task(self._run_auto_import(guild))

        except Exception as e:
            self.logger.error(f"Error checking/starting auto-import: {e}", exc_info=True)

    async def _run_auto_import(self, guild: discord.Guild):
        """
        Run the historical import in background.

        Args:
            guild: Discord guild
        """
        from src.utils.historical_import import HistoricalImporter
        import asyncio

        status_message = None
        update_task = None

        try:
            self.logger.info("=" * 70)
            self.logger.info("🚀 AUTOMATIC HISTORICAL IMPORT STARTED")
            self.logger.info("=" * 70)

            # Create initial status message in Discord
            if self.config.discord_service_logs_enabled:
                status_message = await self._create_import_status_message(guild)

            # Create importer
            excluded_channel_names = getattr(
                self.config,
                'excluded_channel_names',
                ['nsfw', 'bot-spam']
            )

            importer = HistoricalImporter(
                guild=guild,
                message_store=self.message_store,
                excluded_channel_names=excluded_channel_names
            )

            # Start periodic status update task
            if status_message:
                update_task = asyncio.create_task(
                    self._update_import_status_periodically(guild, status_message)
                )

            # Import with logging
            result = await importer.import_guild_history()

            # Cancel the update task
            if update_task:
                update_task.cancel()
                try:
                    await update_task
                except asyncio.CancelledError:
                    pass

            # Update the live status message with final result
            if status_message and self.config.discord_service_logs_enabled:
                try:
                    if result['success']:
                        # Calculate final duration
                        import_start_time = await self.message_store.get_import_start_time(guild.id)
                        if import_start_time:
                            from datetime import datetime, timezone
                            now = datetime.now(timezone.utc)
                            duration = now - import_start_time
                            duration_minutes = int(duration.total_seconds() // 60)
                            duration_seconds = int(duration.total_seconds() % 60)
                            duration_str = f"{duration_minutes}m {duration_seconds}s"
                        else:
                            duration_str = "N/A"

                        # Create final success embed
                        final_color = (
                            discord.Color.green() if result['channels_failed'] == 0
                            else discord.Color.orange()
                        )

                        final_embed = discord.Embed(
                            title="📥 Historischer Datenimport",
                            description="Import erfolgreich abgeschlossen!",
                            color=final_color
                        )
                        final_embed.add_field(name="Status", value="✅ Abgeschlossen", inline=True)
                        final_embed.add_field(name="Dauer", value=duration_str, inline=True)
                        final_embed.add_field(name="Nachrichten", value=f"{result['total_messages']:,}", inline=True)
                        final_embed.add_field(
                            name="Channels",
                            value=f"{result['channels_processed']}/{result['total_channels']} verarbeitet",
                            inline=False
                        )
                        if result['channels_failed'] > 0:
                            final_embed.add_field(
                                name="⚠️ Fehlgeschlagen",
                                value=f"{result['channels_failed']} Channel(s)",
                                inline=False
                            )
                        final_embed.set_footer(text="Import abgeschlossen")
                        final_embed.timestamp = discord.utils.utcnow()

                        await status_message.edit(embed=final_embed)
                    else:
                        # Create final error embed
                        error_embed = discord.Embed(
                            title="📥 Historischer Datenimport",
                            description="Import fehlgeschlagen!",
                            color=discord.Color.red()
                        )
                        error_embed.add_field(name="Status", value="❌ Fehler", inline=True)
                        error_embed.add_field(
                            name="Fehler",
                            value=result.get('error', 'Unbekannter Fehler'),
                            inline=False
                        )
                        error_embed.set_footer(text="Import abgebrochen")
                        error_embed.timestamp = discord.utils.utcnow()

                        await status_message.edit(embed=error_embed)
                except Exception as e:
                    self.logger.error(f"Failed to update final status message: {e}", exc_info=True)

            if result['success']:
                self.logger.info("=" * 70)
                self.logger.info("✅ AUTOMATIC IMPORT COMPLETED SUCCESSFULLY")
                self.logger.info("=" * 70)

                # Send success notification
                if self.config.discord_service_logs_enabled:
                    color = (
                        discord.Color.green() if result['channels_failed'] == 0
                        else discord.Color.orange()
                    )

                    description = (
                        f"**Importierte Nachrichten:** {result['total_messages']:,}\n"
                        f"**Verarbeitete Channels:** {result['channels_processed']}\n"
                        f"**Fehlgeschlagene Channels:** {result['channels_failed']}\n"
                        f"**Gesamt Channels:** {result['total_channels']}\n\n"
                        "✅ Der Bot nutzt jetzt die schnelle Datenbank!\n"
                        "Commands wie `/analyze` sind jetzt instant."
                    )

                    await self.discord_logger.send(
                        guild,
                        "✅ Historischer Import abgeschlossen",
                        description,
                        status="✅ Bereit",
                        color=color
                    )

            else:
                self.logger.error(f"❌ Auto-import failed: {result.get('error', 'Unknown error')}")

                if self.config.discord_service_logs_enabled:
                    await self.discord_logger.send(
                        guild,
                        "❌ Import fehlgeschlagen",
                        f"Fehler: {result.get('error', 'Unbekannter Fehler')}\n\n"
                        "Bitte `/import-messages force=True` manuell ausführen.",
                        status="❌ Fehler",
                        color=discord.Color.red()
                    )

        except Exception as e:
            self.logger.error(f"❌ CRITICAL: Auto-import failed with exception: {e}", exc_info=True)

            if self.config.discord_service_logs_enabled:
                await self.discord_logger.send(
                    guild,
                    "❌ Import-Fehler",
                    f"Kritischer Fehler beim Import:\n```{str(e)}```\n\n"
                    "Bitte Logs prüfen und `/import-messages` manuell ausführen.",
                    status="❌ Fehler",
                    color=discord.Color.red()
                )

    async def on_command_error(self, ctx, error):
        """Handle command errors."""
        self.logger.error(f"Command error: {error}", exc_info=True)

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError
    ):
        """Handle application command errors."""
        self.logger.error(f"App command error: {error}", exc_info=True)

        if not interaction.response.is_done():
            await interaction.response.send_message(
                f"❌ An error occurred: {str(error)}",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"❌ An error occurred: {str(error)}",
                ephemeral=True
            )


def main():
    """Main entry point for the bot."""
    # Load configuration
    try:
        config = Config()
    except FileNotFoundError as e:
        print(f"❌ Configuration Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        sys.exit(1)

    # Setup logging
    logger = setup_logger(
        name="guildscout",
        level=config.log_level,
        log_file=config.log_file,
        log_format=config.log_format
    )

    logger.info("=" * 50)
    logger.info("GuildScout Bot Starting...")
    logger.info("=" * 50)

    # Initialize cache
    cache = MessageCache(ttl=config.cache_ttl)
    logger.info("Cache system initialized")

    # Initialize message store
    message_store = MessageStore()
    logger.info("Message store system initialized")

    # Create and run bot
    bot = GuildScoutBot(config, cache, message_store)

    try:
        bot.run(config.discord_token)
    except discord.LoginFailure:
        logger.error("❌ Failed to login. Please check your bot token.")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
