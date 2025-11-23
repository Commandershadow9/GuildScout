"""Main bot file for GuildScout Discord Bot."""

import logging
import discord
from discord.ext import commands
import sys
from pathlib import Path
from typing import Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import Config, setup_logger
from src.utils.log_helper import DiscordLogger
from src.utils.health_server import HealthCheckServer
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
from src.tasks.verification_scheduler import setup as setup_verification_scheduler


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

        # Health check HTTP server
        self.health_server = HealthCheckServer(bot=self, port=self.config.health_check_port)

        # Background task management
        self._import_task = None  # Store background import task to prevent garbage collection
        self._import_lock = None  # Lock for auto-import to prevent race conditions
        self._ready_called = False  # Flag to track if on_ready initialization is complete
        self._chunking_done = False  # Flag to track if chunking is complete
        self._chunking_task = None  # Store chunking task to prevent garbage collection

        # Initialize bot with intents
        intents = discord.Intents.default()
        intents.members = True  # Required for member list
        intents.message_content = True  # Required for message counting

        super().__init__(
            command_prefix=None,  # No prefix for text commands, using slash commands
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
        await setup_guild_events(self, self.config, self.message_store)
        await setup_message_tracking(self, self.config, self.message_store)
        self.logger.info("Event handlers loaded")

        # Load background tasks
        await setup_verification_scheduler(self, self.config, self.message_store)
        self.logger.info("Background tasks loaded")

        # Sync commands to guild
        try:
            guild = discord.Object(id=self.config.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            self.logger.info(f"Synced commands to guild {self.config.guild_id}")
        except Exception as e:
            self.logger.error(f"Failed to sync commands: {e}")

        # Start health check server
        try:
            await self.health_server.start()
        except Exception as e:
            self.logger.error(f"Failed to start health check server: {e}")

    async def on_ready(self):
        """
        Called when bot is ready.

        Note: This can be called multiple times (on reconnects).
        We use flags to ensure one-time initialization is only done once.
        """
        self.logger.info(f"Bot is ready! Logged in as {self.user.name} ({self.user.id})")

        # Initialize lock on first call
        if self._import_lock is None:
            import asyncio
            self._import_lock = asyncio.Lock()

        # Only run full initialization once
        if not self._ready_called:
            self._ready_called = True
            self.logger.info(f"First ready event - initializing bot...")
            self.logger.info(f"Connected to {len(self.guilds)} guild(s)")

            # Set bot status
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name="guild activity | /analyze /my-score"
                )
            )

            # Start chunking in background (non-blocking)
            if not self._chunking_done:
                import asyncio
                self._chunking_task = asyncio.create_task(self._chunk_all_guilds())

            # Send startup notification and start auto-import
            guild = self.get_guild(self.config.guild_id)
            if guild:
                await self._ensure_log_channel_exists(guild)
                description = (
                    f"Verbunden mit **{len(self.guilds)}** Server(n)\n"
                    f"Cache bereit, Commands synchronisiert\n"
                    f"Member-Cache wird geladen..."
                )
                await self._log_service_status(
                    guild,
                    "🤖 GuildScout gestartet",
                    description,
                    status="✅ Online",
                    color=discord.Color.green()
                )

                # Always run a fresh historical import on startup
                await self._check_and_start_auto_import(guild, force_reimport=True)
        else:
            # Reconnect event - just log it
            self.logger.info(f"Bot reconnected (ready event #{2 if self._ready_called else 1})")
            guild = self.get_guild(self.config.guild_id)
            if guild:
                await self._ensure_log_channel_exists(guild)
                await self._log_service_status(
                    guild,
                    "♻️ GuildScout verbunden",
                    "Bot hat die Verbindung zu Discord wiederhergestellt.",
                    status="🔄 Reconnected",
                    color=discord.Color.blurple()
                )

    async def _chunk_all_guilds(self):
        """
        Chunk all guilds in background to load all members into cache.
        This runs asynchronously to not block bot startup.
        """
        import asyncio

        self.logger.info("Starting guild chunking in background...")

        for guild in self.guilds:
            try:
                self.logger.info(f"Chunking guild {guild.name} ({guild.member_count} members)...")
                await guild.chunk()
                self.logger.info(
                    f"✅ Guild chunked: {guild.name} - "
                    f"Loaded {len(guild.members)} members into cache"
                )
            except Exception as e:
                self.logger.error(f"Failed to chunk guild {guild.name}: {e}", exc_info=True)

            # Small delay between chunks to avoid rate limits
            await asyncio.sleep(1)

        self._chunking_done = True
        self.logger.info("✅ All guilds chunked successfully")

    async def _log_service_status(
        self,
        guild: discord.Guild,
        title: str,
        description: str,
        *,
        status: str,
        color: discord.Color
    ):
        """Send lifecycle updates to the configured Discord log channel."""
        if not self.config.discord_service_logs_enabled:
            return

        try:
            await self.discord_logger.send(
                guild,
                title,
                description,
                status=status,
                color=color
            )
        except Exception as exc:
            self.logger.warning("Failed to send service status to Discord: %s", exc)

    async def _update_import_progress_embed(
        self,
        guild: discord.Guild,
        status_message: discord.Message,
        channel_name: str,
        current: int,
        total: int
    ):
        """Update the log embed with the latest auto-import progress."""
        try:
            stats = await self.message_store.get_stats(guild.id)
            total_messages = stats.get('total_messages', 0)
            import_start_time = await self.message_store.get_import_start_time(guild.id)

            if import_start_time:
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                duration = now - import_start_time
                minutes = int(duration.total_seconds() // 60)
                seconds = int(duration.total_seconds() % 60)
                duration_str = f"{minutes}m {seconds}s"
            else:
                duration_str = "N/A"

            embed = discord.Embed(
                title="📥 Historischer Datenimport",
                description="Der automatische Import läuft.",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(
                name="Status",
                value=f"🔄 {current}/{total} Channels",
                inline=True
            )
            embed.add_field(
                name="Aktueller Kanal",
                value=f"`{channel_name}`",
                inline=True
            )
            embed.add_field(
                name="Importierte Nachrichten",
                value=f"{total_messages:,}",
                inline=True
            )
            embed.add_field(
                name="Dauer",
                value=duration_str,
                inline=False
            )
            embed.set_footer(text="Live-Update")

            await status_message.edit(embed=embed)
        except Exception as exc:
            self.logger.debug("Failed to update import progress embed: %s", exc)

    async def _ensure_log_channel_exists(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """
        Make sure there is a Discord channel available for service logs.
        Falls back to creating #guildscout-logs if necessary.
        """
        channel_id = self.config.log_channel_id
        channel = guild.get_channel(channel_id) if channel_id else None

        if not channel:
            # Try to find an existing channel by name
            channel = discord.utils.get(guild.text_channels, name="guildscout-logs")

        if not channel:
            # Create a dedicated log channel
            try:
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

                channel = await guild.create_text_channel(
                    name="guildscout-logs",
                    topic="🧾 GuildScout Logs – Analysen und Systemereignisse",
                    overwrites=overwrites
                )
                embed = discord.Embed(
                    title="🧾 GuildScout Logs",
                    description="Analysen, Systemereignisse und Fehler werden hier protokolliert.",
                    color=discord.Color.dark_gold(),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(
                    name="Was wird geloggt?",
                    value="• /analyze Starts & Ergebnisse\n• Cache-Infos\n• Fehler / Warnungen",
                    inline=False
                )
                embed.set_footer(text="GuildScout Monitoring")
                await channel.send(embed=embed)
            except discord.Forbidden:
                self.logger.warning("Cannot create log channel in guild %s", guild.name)
                return None
            except Exception as exc:
                self.logger.error("Failed to ensure log channel: %s", exc, exc_info=True)
                return None

        if not hasattr(self, 'log_channels'):
            self.log_channels = {}
        self.log_channels[guild.id] = channel.id
        if self.config.log_channel_id != channel.id:
            self.config.set_log_channel_id(channel.id)

        return channel

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
        log_channel_id = self.config.log_channel_id
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

    async def _check_and_start_auto_import(
        self,
        guild: discord.Guild,
        *,
        force_reimport: bool = False
    ):
        """
        Check if historical import is needed and start it automatically.
        Uses a lock to prevent race conditions on multiple on_ready() calls.

        Args:
            guild: Discord guild
            force_reimport: Whether to reset data and re-import regardless of status
        """
        import asyncio

        # Use lock to prevent multiple simultaneous import starts
        async with self._import_lock:
            try:
                # Check if import already running (task exists and not done)
                if self._import_task and not self._import_task.done():
                    self.logger.warning(
                        f"⚠️ Historical import already running for {guild.name} "
                        "(task exists)"
                    )
                    return

                # Check if import already completed
                if not force_reimport:
                    is_completed = await self.message_store.is_import_completed(guild.id)
                    if is_completed:
                        self.logger.info(f"✅ Historical import already completed for {guild.name}")
                        return
                else:
                    self.logger.info(f"♻️ Forcing historical re-import for {guild.name}")
                    await self.message_store.reset_guild(guild.id)

                # Check if import is already running (in database)
                is_running = await self.message_store.is_import_running(guild.id)

                if is_running:
                    self.logger.warning(
                        f"⚠️ Historical import already running for {guild.name} "
                        "(marked in database)"
                    )
                    return

                # Import not completed - start it in background
                self.logger.info(f"📥 Starting automatic historical import for {guild.name}")

                # Send Discord notification
                if self.config.discord_service_logs_enabled:
                    await self.discord_logger.send(
                        guild,
                        "📥 Re-Import gestartet" if force_reimport else "📥 Automatischer Datenimport gestartet",
                        (
                            "Der Bot importiert jetzt alle historischen Nachrichten erneut.\n"
                            "Dies kann einige Minuten dauern.\n\n"
                            "**Bot bleibt währenddessen voll funktionsfähig!**\n"
                            "Commands funktionieren normal (ggf. etwas langsamer).\n\n"
                            "Fortschritt wird in den Logs angezeigt."
                        ) if force_reimport else (
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

            async def progress_callback(channel_name: str, current: int, total: int):
                if status_message:
                    await self._update_import_progress_embed(
                        guild,
                        status_message,
                        channel_name,
                        current,
                        total
                    )

            # Start periodic status update task
            if status_message:
                update_task = asyncio.create_task(
                    self._update_import_status_periodically(guild, status_message)
                )

            # Import with logging
            result = await importer.import_guild_history(progress_callback=progress_callback)

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

    async def close(self):
        """Clean shutdown of the bot"""
        self.logger.info("Shutting down GuildScout...")

        # Stop health check server
        try:
            await self.health_server.stop()
        except Exception as e:
            self.logger.error(f"Error stopping health server: {e}")

        # Close parent bot
        await super().close()

        self.logger.info("GuildScout shutdown complete")


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

