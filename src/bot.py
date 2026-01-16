"""Main bot file for GuildScout Discord Bot."""

import logging
import discord
from discord.ext import commands
import sys
from pathlib import Path
from typing import Optional
import asyncio # Moved from on_ready

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import Config, setup_logger
from src.utils.log_helper import DiscordLogger
from src.utils.status_manager import StatusManager
from src.utils.health_server import HealthCheckServer
from src.utils.config_watcher import setup_config_watcher
from src.database import MessageCache
from src.database.message_store import MessageStore
from src.database.raid_store import RaidStore
from src.commands.analyze import setup as setup_analyze
from src.commands.my_score import setup as setup_my_score
from src.commands.admin import setup as setup_admin
from src.commands.ranking_channel import setup as setup_ranking_channel
from src.commands.assign_guild_role import setup as setup_assign_guild_role
from src.commands.guild_status import setup as setup_guild_status
from src.commands.set_max_spots import setup as setup_set_max_spots
from src.commands.status import setup as setup_status
from src.commands.profile import setup as setup_profile
from src.commands.raid import setup as setup_raid

from src.commands.message_store_admin import setup as setup_message_store_admin
from src.events.guild_events import setup as setup_guild_events
from src.events.message_tracking import setup as setup_message_tracking
from src.events.rate_limit_tracking import setup as setup_rate_limit_tracking
from src.events.voice_tracking import setup as setup_voice_tracking
from src.events.raid_events import setup as setup_raid_events
from src.tasks.verification_scheduler import setup as setup_verification_scheduler
from src.tasks.backup_scheduler import setup as setup_backup_scheduler
from src.tasks.db_maintenance import setup as setup_db_maintenance
from src.tasks.health_monitor import setup as setup_health_monitor
from src.tasks.weekly_reporter import setup as setup_weekly_reporter
from src.tasks.raid_scheduler import setup as setup_raid_scheduler


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
        self.raid_store = RaidStore()
        self.logger = logging.getLogger("guildscout.bot")
        self.discord_logger = DiscordLogger(bot=self, config=config)
        self.status_manager = StatusManager(bot=self, config=config)

        # Health check HTTP server
        self.health_server = HealthCheckServer(bot=self, port=self.config.health_check_port)

        # Background task management
        self._import_task = None  # Store background import task to prevent garbage collection
        self._import_lock = None  # Lock for auto-import to prevent race conditions
        self._ready_called = False  # Flag to track if on_ready initialization is complete
        self._chunking_done = False  # Flag to track if chunking is complete
        self._chunking_task = None  # Store chunking task to prevent garbage collection
        self._initial_startup_complete = False # Flag for initial setup completion

        # Initialize bot with intents
        intents = discord.Intents.default()
        intents.members = True  # Required for member list
        intents.message_content = True  # Required for message counting

        super().__init__(
            command_prefix="!",  # Use a dummy prefix to avoid "NoneType is not iterable" error in on_message
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

        # Initialize raid store
        await self.raid_store.initialize()
        self.logger.info("Raid store initialized")

        # Load commands
        await setup_analyze(self, self.config, self.cache)
        await setup_my_score(self, self.config, self.cache)
        await setup_admin(self, self.config, self.cache)
        await setup_ranking_channel(self, self.config)
        await setup_assign_guild_role(self, self.config, self.cache)
        await setup_guild_status(self, self.config)
        await setup_set_max_spots(self, self.config)
        await setup_status(self, self.config)
        await setup_profile(self, self.config)
        await setup_raid(self, self.config, self.raid_store)

        await setup_message_store_admin(self, self.config, self.message_store)
        self.logger.info("Commands loaded")

        # Load event handlers
        await setup_guild_events(self, self.config, self.message_store)
        await setup_message_tracking(self, self.config, self.message_store)
        await setup_rate_limit_tracking(self)
        await setup_voice_tracking(self, self.config, self.message_store)
        await setup_raid_events(self, self.config, self.raid_store)
        self.logger.info("Event handlers loaded")

        # Load background tasks
        await setup_verification_scheduler(self, self.config, self.message_store)
        await setup_backup_scheduler(self, self.config)
        await setup_db_maintenance(self, self.config)
        await setup_health_monitor(self, self.config)
        await setup_weekly_reporter(self, self.config)
        await setup_raid_scheduler(self, self.config, self.raid_store)
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

            # Start initial startup sequence in background with delay
            import asyncio
            self._initial_startup_task = asyncio.create_task(self._perform_initial_startup_sequence())
        else:
            # Reconnect event - just log it
            self.logger.info(f"Bot reconnected (ready event #{2 if self._ready_called else 1})")
            guild = self.get_guild(self.config.guild_id)
            if guild:
                await self._log_service_status(
                    guild,
                    "♻️ GuildScout verbunden",
                    "Bot hat die Verbindung zu Discord wiederhergestellt.",
                    status="🔄 Reconnected",
                    color=discord.Color.blurple()
                )

    async def _perform_initial_startup_sequence(self):
        """
        Performs initial startup sequence including logging, cleanup, and import checks.
        This runs only once after the first on_ready event.
        """
        guild = self.get_guild(self.config.guild_id)
        if not guild:
            self.logger.error("Initial startup sequence failed: Guild not found.")
            return

        # Initial log entry
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

        # Cleanup old status messages
        await self.status_manager.cleanup_status_channel(guild)

        # Check for missed messages or start full import if needed
        await self._check_and_start_auto_import(guild, force_reimport=False)

        # Refresh active raid posts after restart.
        try:
            raid_cog = self.get_cog("RaidCommand")
            if raid_cog and hasattr(raid_cog, "refresh_active_raids"):
                refreshed = await raid_cog.refresh_active_raids(guild)
                self.logger.info("Refreshed %s raid posts after startup", refreshed)
        except Exception:
            self.logger.warning("Failed to refresh raid posts after startup", exc_info=True)

        # Signal that initial startup is complete after a short delay
        # This allows verification tasks to start after everything else is settled
        self.logger.info("Initial startup sequence completed. Waiting 10 seconds before enabling background tasks...")
        await asyncio.sleep(10) # Give some time for dashboard to update, etc.
        self._initial_startup_complete = True
        self.logger.info("Background tasks enabled.")

        # Start config file watcher for automatic git commits
        try:
            self.config_watcher = await setup_config_watcher()
        except Exception as e:
            self.logger.warning(f"Failed to start config watcher: {e}")

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

    async def _create_import_status_message(self, guild: discord.Guild):
        """
        Create initial import status message in Ranking Channel.

        Args:
            guild: Discord guild

        Returns:
            Discord message object for updating
        """
        # Post import status in dashboard channel (user-facing)
        dashboard_channel_id = self.config.dashboard_channel_id
        if not dashboard_channel_id:
            return None

        dashboard_channel = guild.get_channel(dashboard_channel_id)
        if not dashboard_channel:
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
            message = await dashboard_channel.send(embed=embed)
            self.logger.info(f"Created import status message in #{dashboard_channel.name}")
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
                        # Import completed, but check for missed messages during downtime
                        self.logger.info(f"✅ Historical import already completed for {guild.name}")
                        await self._import_missed_messages(guild)
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

                # Note: Live status message is created in _run_auto_import()
                # No separate notification needed here

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

            # Create initial status message in ranking channel (always show to users)
            status_message = await self._create_import_status_message(guild)

            # Protect import status message from dashboard cleanup
            if status_message:
                try:
                    from src.events.message_tracking import MessageTracker
                    message_tracker = self.get_cog('MessageTracker')
                    if message_tracker and hasattr(message_tracker, 'dashboard_manager'):
                        dashboard_manager = message_tracker.dashboard_manager
                        if dashboard_manager:
                            dashboard_manager.protect_message(status_message.id)
                except Exception as protect_err:
                    self.logger.warning(f"Could not protect import status message: {protect_err}")

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
            if status_message:
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

                # Update dashboard with final message count
                try:
                    from src.events.message_tracking import MessageTracker
                    message_tracker = self.get_cog('MessageTracker')
                    if message_tracker and hasattr(message_tracker, 'dashboard_manager'):
                        dashboard_manager = message_tracker.dashboard_manager
                        if dashboard_manager:
                            # Force dashboard update after import completion
                            lock = dashboard_manager._dashboard_locks.setdefault(guild.id, asyncio.Lock())
                            async with lock:
                                state = dashboard_manager._get_dashboard_state(guild.id)
                                await dashboard_manager._update_dashboard(guild, state)
                                self.logger.info("✅ Dashboard updated with import results")
                except Exception as dash_err:
                    self.logger.warning(f"Could not update dashboard after import: {dash_err}")

                # Delete import status message (success = clean channel)
                if status_message:
                    try:
                        # Unprotect before deleting
                        try:
                            from src.events.message_tracking import MessageTracker
                            message_tracker = self.get_cog('MessageTracker')
                            if message_tracker and hasattr(message_tracker, 'dashboard_manager'):
                                dashboard_manager = message_tracker.dashboard_manager
                                if dashboard_manager:
                                    dashboard_manager.unprotect_message(status_message.id)
                        except:
                            pass

                        await status_message.delete()
                        self.logger.info("🧹 Deleted import status message (import successful)")
                    except Exception as del_err:
                        self.logger.warning(f"Could not delete import status message: {del_err}")

                # Success notification removed - info already visible in dashboard

            else:
                self.logger.error(f"❌ Auto-import failed: {result.get('error', 'Unknown error')}")

                # Send error to status channel with acknowledgment button
                await self.status_manager.send_error(
                    guild,
                    "❌ Import fehlgeschlagen",
                    f"Fehler: {result.get('error', 'Unbekannter Fehler')}\n\n"
                    "Bitte `/import-messages force=True` manuell ausführen.",
                    ping=self.config.alert_ping
                )

        except Exception as e:
            self.logger.error(f"❌ CRITICAL: Auto-import failed with exception: {e}", exc_info=True)

            # Send critical error to status channel with ping
            await self.status_manager.send_error(
                guild,
                "❌ Import-Fehler",
                f"Kritischer Fehler beim Import:\n```{str(e)}```\n\n"
                "Bitte Logs prüfen und `/import-messages` manuell ausführen.",
                ping=self.config.alert_ping
            )

    async def _import_missed_messages(self, guild: discord.Guild):
        """
        Import messages that were missed during bot downtime.
        Called on every restart to catch up with messages sent while bot was offline.
        """
        try:
            import asyncio
            from datetime import datetime, timedelta, timezone
            from src.utils.historical_import import HistoricalImporter

            # Get last known message timestamp from database
            stats = await self.message_store.get_stats(guild.id)
            last_import_time = stats.get("last_message_timestamp")

            if not last_import_time:
                self.logger.info("No last import timestamp found - skipping delta import")
                return

            # Parse timestamp
            if isinstance(last_import_time, str):
                from dateutil import parser
                last_import_time = parser.parse(last_import_time)

            # Ensure timezone-aware datetime
            if last_import_time.tzinfo is None:
                last_import_time = last_import_time.replace(tzinfo=timezone.utc)

            # Add small buffer to avoid duplicates (already have messages up to this point)
            since_time = last_import_time + timedelta(milliseconds=1)
            now = datetime.now(timezone.utc)

            # Calculate time since last message was in the server
            time_since_last_message = now - last_import_time

            # Only import if last message is recent enough (avoid full scan on old servers)
            if time_since_last_message.total_seconds() > 3600:  # > 1 hour
                self.logger.info(f"⏱️ Last message too old ({time_since_last_message.total_seconds():.0f}s) - skipping delta import")
                return

            self.logger.info(
                f"🔄 Checking for missed messages since last tracked message "
                f"({time_since_last_message.total_seconds():.0f}s ago)"
            )

            # Create status message in dashboard (without misleading "offline" claim)
            dashboard_channel_id = self.config.dashboard_channel_id
            if dashboard_channel_id:
                dashboard_channel = guild.get_channel(dashboard_channel_id)
                if dashboard_channel:
                    embed = discord.Embed(
                        title="🔄 Delta-Import",
                        description=(
                            f"Prüfe auf neue Nachrichten seit letztem Restart...\n"
                            f"Letzte Nachricht: **<t:{int(last_import_time.timestamp())}:R>**"
                        ),
                        color=discord.Color.orange()
                    )
                    status_msg = await dashboard_channel.send(embed=embed)

                    # Protect message from cleanup
                    try:
                        from src.events.message_tracking import MessageTracker
                        message_tracker = self.get_cog('MessageTracker')
                        if message_tracker and hasattr(message_tracker, 'dashboard_manager'):
                            dashboard_manager = message_tracker.dashboard_manager
                            if dashboard_manager:
                                dashboard_manager.protect_message(status_msg.id)
                    except:
                        pass
                else:
                    status_msg = None
            else:
                status_msg = None

            # Perform delta import
            importer = HistoricalImporter(
                guild=guild,
                message_store=self.message_store,
                excluded_channel_names=self.config.excluded_channel_names
            )

            # Import only messages after last known timestamp
            result = await importer.import_guild_history(after=since_time)

            # Update status message
            if status_msg:
                try:
                    # Unprotect before deleting
                    from src.events.message_tracking import MessageTracker
                    message_tracker = self.get_cog('MessageTracker')
                    if message_tracker and hasattr(message_tracker, 'dashboard_manager'):
                        dashboard_manager = message_tracker.dashboard_manager
                        if dashboard_manager:
                            dashboard_manager.unprotect_message(status_msg.id)
                except:
                    pass

                if result['success'] and result['total_messages'] > 0:
                    embed = discord.Embed(
                        title="✅ Delta-Import abgeschlossen",
                        description=f"**{result['total_messages']:,}** verpasste Nachrichten importiert",
                        color=discord.Color.green()
                    )
                    await status_msg.edit(embed=embed)
                    await asyncio.sleep(5)
                    await status_msg.delete()
                    self.logger.info(
                        f"✅ Delta-Import completed: {result['total_messages']:,} messages caught up"
                    )
                elif result['total_messages'] == 0:
                    # No missed messages - delete status quietly
                    await status_msg.delete()
                    self.logger.info("✅ No missed messages - bot was up to date")
                else:
                    # Error
                    embed = discord.Embed(
                        title="⚠️ Delta-Import Warnung",
                        description=f"Fehler beim Import verpasster Nachrichten",
                        color=discord.Color.orange()
                    )
                    await status_msg.edit(embed=embed)

        except Exception as e:
            self.logger.error(f"Error during delta import: {e}", exc_info=True)

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
