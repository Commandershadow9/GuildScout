"""Admin commands for message store management."""

import logging
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from typing import Optional

from ..utils import Config
from ..database.message_store import MessageStore
from ..database import MessageCache
from ..utils.historical_import import HistoricalImporter
from ..utils.validation import MessageCountValidator
from ..analytics.activity_tracker import ActivityTracker
from ..utils.log_helper import DiscordLogger
import random


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
        self.discord_logger = DiscordLogger(bot, config)

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

    async def _log_event(
        self,
        guild: discord.Guild,
        title: str,
        description: str,
        *,
        status: str,
        color: discord.Color = discord.Color.blurple(),
        message: Optional[discord.Message] = None
    ) -> Optional[discord.Message]:
        """Send or update status embeds in the log channel."""
        if not self.discord_logger:
            return None
        return await self.discord_logger.send(
            guild,
            title,
            description,
            status=status,
            color=color,
            message=message
        )

    @app_commands.command(
        name="import-status",
        description="[Admin] Check the status of message import"
    )
    async def import_status(self, interaction: discord.Interaction):
        """
        Check the current status of historical message import.

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

        try:
            await interaction.response.defer(ephemeral=True)
        except discord.errors.NotFound:
            logger.warning(
                f"Interaction expired for /import-status by {interaction.user.name}"
            )
            return
        except Exception as e:
            logger.error(f"Unexpected error during defer: {e}", exc_info=True)
            return

        try:
            is_completed = await self.message_store.is_import_completed(
                interaction.guild.id
            )
            is_running = await self.message_store.is_import_running(
                interaction.guild.id
            )
            await self.message_store.sync_guild_members(interaction.guild)
            stats = await self.message_store.get_stats(interaction.guild.id)

            embed = discord.Embed(
                title="📊 Import Status",
                timestamp=discord.utils.utcnow()
            )

            if is_completed:
                # Import completed
                embed.color = discord.Color.green()
                embed.add_field(
                    name="Status",
                    value="✅ **Abgeschlossen**",
                    inline=False
                )

                if stats.get('import_date'):
                    import_date = datetime.fromisoformat(stats['import_date'])
                    embed.add_field(
                        name="Importiert am",
                        value=import_date.strftime('%d.%m.%Y %H:%M UTC'),
                        inline=True
                    )

                embed.add_field(
                    name="Importierte Nachrichten",
                    value=f"{stats['total_messages']:,}",
                    inline=True
                )

                embed.add_field(
                    name="Getrackte Mitglieder",
                    value=f"{stats['total_members']:,} (ohne Bots)",
                    inline=True
                )

                embed.add_field(
                    name="Aktive Schreiber",
                    value=f"{stats['total_users']:,}",
                    inline=True
                )

                embed.add_field(
                    name="💡 Info",
                    value=(
                        "Der Bot nutzt jetzt die schnelle Datenbank.\n"
                        "Neue Nachrichten werden in Echtzeit getrackt."
                    ),
                    inline=False
                )

            elif is_running:
                # Import currently running
                start_time = await self.message_store.get_import_start_time(
                    interaction.guild.id
                )

                embed.color = discord.Color.blue()
                embed.add_field(
                    name="Status",
                    value="🔄 **Läuft gerade**",
                    inline=False
                )

                if start_time:
                    # Calculate duration
                    from datetime import timezone as tz
                    now = datetime.now(tz.utc)
                    duration = now - start_time
                    minutes = int(duration.total_seconds() / 60)

                    embed.add_field(
                        name="Gestartet",
                        value=start_time.strftime('%H:%M UTC'),
                        inline=True
                    )

                    embed.add_field(
                        name="Dauer",
                        value=f"{minutes} Minuten",
                        inline=True
                    )

                # Get current stats (partial data)
                embed.add_field(
                    name="Bisher importiert",
                    value=f"{stats['total_messages']:,} Nachrichten",
                    inline=False
                )

                embed.add_field(
                    name="Erfasste Mitglieder",
                    value=f"{stats['total_members']:,}",
                    inline=True
                )

                embed.add_field(
                    name="Davon aktiv",
                    value=f"{stats['total_users']:,}",
                    inline=True
                )

                embed.add_field(
                    name="📋 Logs",
                    value=(
                        "Detaillierte Logs in der Konsole:\n"
                        "- Aktueller Channel\n"
                        "- Nachrichtenanzahl pro Channel\n"
                        "- Rate-Limit Status\n"
                        "- Fehler/Warnungen"
                    ),
                    inline=False
                )

                embed.set_footer(
                    text="Import läuft im Hintergrund. Bot bleibt funktionsfähig!"
                )

            else:
                # Import not started
                embed.color = discord.Color.orange()
                embed.add_field(
                    name="Status",
                    value="⚠️ **Nicht gestartet**",
                    inline=False
                )

                embed.add_field(
                    name="📝 Hinweis",
                    value=(
                        "Der automatische Import sollte beim Bot-Start erfolgen.\n\n"
                        "Mögliche Gründe:\n"
                        "• Bot wurde gerade erst gestartet\n"
                        "• Import wurde deaktiviert\n"
                        "• Import-Fehler beim Start\n\n"
                        "Führe `/import-messages` manuell aus."
                    ),
                    inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error getting import status: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error getting status: {str(e)}",
                ephemeral=True
            )

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

        try:
            await interaction.response.defer(ephemeral=True)
        except discord.errors.NotFound:
            logger.warning(
                f"Interaction expired for /import-messages by {interaction.user.name}"
            )
            return
        except Exception as e:
            logger.error(f"Unexpected error during defer: {e}", exc_info=True)
            return

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
                "📥 Starte historischen Nachrichtenimport...\n"
                "Das kann je nach Servergröße einige Minuten dauern.",
                ephemeral=True
            )

            log_message = await self._log_event(
                interaction.guild,
                "📥 Import gestartet",
                (
                    f"{interaction.user.mention} hat den historischen Import gestartet.\n"
                    f"Force-Reimport: {'Ja' if force else 'Nein'}"
                ),
                status="🔄 Läuft",
                color=discord.Color.blue()
            )

            # Progress callback
            last_update = discord.utils.utcnow()
            log_state = {"message": log_message}

            async def progress_callback(channel_name: str, current: int, total: int):
                nonlocal last_update
                # Update every 5 seconds to avoid rate limits
                now = discord.utils.utcnow()
                if (now - last_update).total_seconds() >= 5:
                    try:
                        await progress_msg.edit(
                            content=(
                                "📥 Nachrichten werden importiert...\n"
                                f"Aktueller Kanal: **#{channel_name}**\n"
                                f"Fortschritt: **{current}/{total}** Channels"
                            )
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update progress message: {e}")
                    finally:
                        last_update = now
                        if log_state["message"]:
                            updated = await self._log_event(
                                interaction.guild,
                                "📥 Import läuft",
                                (
                                    f"{interaction.user.mention} importiert `#{channel_name}`.\n"
                                    f"Fortschritt: {current}/{total} Channels."
                                ),
                                status=f"{current}/{total}",
                                color=discord.Color.blue(),
                                message=log_state["message"]
                            )
                            if updated:
                                log_state["message"] = updated

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
                color = (
                    discord.Color.green() if result['channels_failed'] == 0
                    else discord.Color.orange()
                )

                embed = discord.Embed(
                    title="✅ Historical Import Completed",
                    color=color,
                    timestamp=discord.utils.utcnow()
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

                # Show failed channels if any
                if result.get('failed_channels'):
                    failed_text = ""
                    for fc in result['failed_channels'][:5]:  # Show max 5
                        failed_text += f"• **{fc['name']}**: {fc['reason']}\n"

                    if len(result['failed_channels']) > 5:
                        failed_text += f"\n_...and {len(result['failed_channels']) - 5} more (see logs)_"

                    embed.add_field(
                        name="⚠️ Failed Channels",
                        value=failed_text,
                        inline=False
                    )

                embed.add_field(
                    name="🚀 What's Next?",
                    value=(
                        "The bot will now track new messages in real-time!\n"
                        "✅ Use `/analyze` to see accurate message counts\n"
                        "🔍 Use `/verify-message-counts` to validate accuracy"
                    ),
                    inline=False
                )

                await progress_msg.edit(content=None, embed=embed)

                logger.info(
                    f"Import completed for guild {interaction.guild.name}: "
                    f"{result['total_messages']} messages imported"
                )
                if log_state["message"]:
                    await self._log_event(
                        interaction.guild,
                        "📥 Import abgeschlossen",
                        (
                            f"{interaction.user.mention} hat den Import beendet.\n"
                            f"Nachrichten: {result['total_messages']:,}\n"
                            f"Channels: {result['channels_processed']}/{result['total_channels']}"
                        ),
                        status="✅ Fertig",
                        color=discord.Color.green(),
                        message=log_state["message"]
                    )
            else:
                await progress_msg.edit(
                    content=f"❌ Import failed: {result.get('error', 'Unknown error')}"
                )
                if log_state["message"]:
                    await self._log_event(
                        interaction.guild,
                        "📥 Import fehlgeschlagen",
                        result.get('error', 'Unknown error'),
                        status="❌ Fehler",
                        color=discord.Color.red(),
                        message=log_state["message"]
                    )

        except Exception as e:
            logger.error(f"Error during message import: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error during import: {str(e)}",
                ephemeral=True
            )
            if 'log_state' in locals() and log_state.get("message"):
                await self._log_event(
                    interaction.guild,
                    "📥 Import fehlgeschlagen",
                    str(e),
                    status="❌ Fehler",
                    color=discord.Color.red(),
                    message=log_state["message"]
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

        try:
            await interaction.response.defer(ephemeral=True)
        except discord.errors.NotFound:
            logger.warning(
                f"Interaction expired for /message-store-stats by {interaction.user.name}"
            )
            return
        except Exception as e:
            logger.error(f"Unexpected error during defer: {e}", exc_info=True)
            return

        try:
            await self.message_store.sync_guild_members(interaction.guild)
            stats = await self.message_store.get_stats(interaction.guild.id)

            embed = discord.Embed(
                title="📊 Message Store Statistics",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
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
                    f"**Tracked Members:** {stats['total_members']:,}\n"
                    f"**Active Users:** {stats['total_users']:,}\n"
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

    @app_commands.command(
        name="verify-message-counts",
        description="[Admin] Verify accuracy of message counts by sampling users"
    )
    @app_commands.describe(
        sample_size="Number of users to check (default: 10)"
    )
    async def verify_message_counts(
        self,
        interaction: discord.Interaction,
        sample_size: int = 10
    ):
        """
        Verify message count accuracy by comparing with Discord API.

        Args:
            interaction: Discord interaction
            sample_size: Number of users to sample
        """
        # Check permissions
        if not self._has_permission(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return

        try:
            await interaction.response.defer(ephemeral=True)
        except discord.errors.NotFound:
            logger.warning(
                f"Interaction expired for /verify-message-counts by {interaction.user.name}"
            )
            try:
                await interaction.followup.send(
                    "⚠️ Command timed out (bot was busy or reconnecting). Please try again.",
                    ephemeral=True
                )
            except Exception:
                pass
            return
        except Exception as e:
            logger.error(f"Unexpected error during defer: {e}", exc_info=True)
            return

        try:
            # Check if import completed
            is_imported = await self.message_store.is_import_completed(
                interaction.guild.id
            )

            if not is_imported:
                await interaction.followup.send(
                    "❌ Cannot verify: Historical import not completed yet.\n"
                    "Please run `/import-messages` first.",
                    ephemeral=True
                )
                return

            status_message = await interaction.followup.send(
                f"🔍 Starte Verifikation mit {sample_size} zufälligen Usern...\n"
                "Das kann ein paar Minuten dauern.",
                ephemeral=True
            )

            log_message = await self._log_event(
                interaction.guild,
                "🔍 Verifikation gestartet",
                (
                    f"{interaction.user.mention} überprüft Nachrichtenzähler "
                    f"für {sample_size} zufällig ausgewählte Mitglieder."
                ),
                status="🔄 Läuft",
                color=discord.Color.orange()
            )

            # Get random sample of members with messages
            guild_totals = await self.message_store.get_guild_totals(
                interaction.guild.id
            )

            # Filter to members with at least 10 messages
            eligible_user_ids = [
                uid for uid, count in guild_totals.items() if count >= 10
            ]

            if not eligible_user_ids:
                await status_message.edit(
                    content="❌ Keine passenden User gefunden (mind. 10 Nachrichten erforderlich)."
                )
                if log_message:
                    await self._log_event(
                        interaction.guild,
                        "🔍 Verifikation abgebrochen",
                        "Keine User mit genügend Nachrichten vorhanden.",
                        status="⚠️ Abgebrochen",
                        color=discord.Color.red(),
                        message=log_message
                    )
                return

            # Sample random users
            sample_size = min(sample_size, len(eligible_user_ids))
            sampled_user_ids = random.sample(eligible_user_ids, sample_size)

            # Get Member objects
            sample_users = []
            for uid in sampled_user_ids:
                member = interaction.guild.get_member(uid)
                if member:
                    sample_users.append(member)

            if not sample_users:
                await status_message.edit(
                    content="❌ Konnte keine der zufälligen User im Server finden."
                )
                if log_message:
                    await self._log_event(
                        interaction.guild,
                        "🔍 Verifikation abgebrochen",
                        "Keine Mitglieder für die Stichprobe gefunden.",
                        status="⚠️ Abgebrochen",
                        color=discord.Color.red(),
                        message=log_message
                    )
                return

            total_to_check = len(sample_users)
            await status_message.edit(
                content=(
                    "🔍 Verifiziere Nachrichtenzähler...\n"
                    f"Fortschritt: **0/{total_to_check}**"
                )
            )

            progress_state = {
                "last_update": discord.utils.utcnow(),
                "log_message": log_message,
                "total_users": total_to_check
            }
            channel_state = {
                "last_update": discord.utils.utcnow(),
                "log_message": log_message
            }

            async def progress_callback(
                processed: int,
                total: int,
                member: discord.Member,
                store_count: int,
                api_count: int
            ):
                now = discord.utils.utcnow()
                if (
                    (now - progress_state["last_update"]).total_seconds() >= 4
                    or processed == total
                ):
                    progress_state["last_update"] = now
                    content = (
                        "🔍 Verifiziere Nachrichtenzähler...\n"
                        f"Fortschritt: **{processed}/{total}**\n"
                        f"Zuletzt geprüft: **{member.display_name}** "
                        f"(Store {store_count:,} | API {api_count:,})"
                    )
                    try:
                        await status_message.edit(content=content)
                    except Exception as exc:
                        logger.debug("Progress edit failed: %s", exc)

                    if progress_state["log_message"]:
                        updated = await self._log_event(
                            interaction.guild,
                            "🔍 Verifikation läuft",
                            (
                                f"{interaction.user.mention} prüft Nachrichten.\n"
                                f"{processed}/{total} abgeschlossen.\n"
                                f"Letzter User: {member.display_name} "
                                f"(Store {store_count:,} | API {api_count:,})"
                            ),
                            status=f"{processed}/{total}",
                            color=discord.Color.orange(),
                            message=progress_state["log_message"]
                        )
                    if updated:
                        progress_state["log_message"] = updated

            async def channel_progress(
                member: discord.Member,
                user_index: int,
                user_total: int,
                channel: discord.TextChannel,
                channel_index: int,
                channel_total: int,
                channel_count: int
            ):
                if channel_total == 0:
                    return

                now = discord.utils.utcnow()
                # Update every ~3s or at the end of the channel list
                if (
                    channel_index != channel_total
                    and (now - channel_state["last_update"]).total_seconds() < 3
                ):
                    return

                channel_state["last_update"] = now
                content = (
                    "🔍 Verifiziere Nachrichtenzähler...\n"
                    f"Aktueller User: **{member.display_name}** "
                    f"({user_index}/{user_total})\n"
                    f"Kanal {channel_index}/{channel_total}: #{channel.name}\n"
                    f"Gezählte Nachrichten in diesem Kanal: {channel_count}"
                )
                try:
                    await status_message.edit(content=content)
                except Exception as exc:
                    logger.debug("Channel progress edit failed: %s", exc)

                if channel_state["log_message"]:
                    updated = await self._log_event(
                        interaction.guild,
                        "🔍 Verifikation läuft",
                        (
                            f"{interaction.user.mention} prüft {member.mention}.\n"
                            f"Kanal: #{channel.name} "
                            f"({channel_index}/{channel_total}) – "
                            f"{channel_count} Nachrichten gezählt."
                        ),
                        status=f"User {user_index}/{user_total}",
                        color=discord.Color.orange(),
                        message=channel_state["log_message"]
                    )
                    if updated:
                        channel_state["log_message"] = updated

            # Create validator
            cache = MessageCache(ttl=self.config.cache_ttl)
            activity_tracker = ActivityTracker(
                interaction.guild,
                excluded_channels=self.config.excluded_channels,
                excluded_channel_names=self.config.excluded_channel_names,
                cache=cache
            )

            validator = MessageCountValidator(
                interaction.guild,
                self.message_store,
                activity_tracker
            )

            # Run validation
            logger.info(
                f"Running verification for {len(sample_users)} users "
                f"in guild {interaction.guild.name}"
            )

            results = await validator.validate_sample(
                sample_users,
                tolerance_percent=1.0,
                progress_callback=progress_callback,
                channel_progress_callback=channel_progress
            )

            # Create results embed
            color = discord.Color.green() if results["passed"] else discord.Color.red()
            status = "✅ PASSED" if results["passed"] else "❌ FAILED"

            embed = discord.Embed(
                title=f"🔍 Message Count Verification: {status}",
                color=color,
                timestamp=discord.utils.utcnow()
            )

            embed.add_field(
                name="📊 Overall Results",
                value=(
                    f"**Sample Size:** {results['total_users']} users\n"
                    f"**Accuracy:** {results['accuracy_percent']:.1f}%\n"
                    f"**Matches:** {results['matches']} ✅\n"
                    f"**Mismatches:** {results['mismatches']} ❌\n"
                ),
                inline=False
            )

            embed.add_field(
                name="📈 Differences",
                value=(
                    f"**Max Difference:** {results['max_difference']} messages\n"
                    f"**Avg Difference:** {results['avg_difference']:.1f} messages"
                ),
                inline=False
            )

            # Show discrepancies if any
            if results["discrepancies"]:
                discrepancy_text = ""
                for disc in results["discrepancies"][:5]:  # Show max 5
                    discrepancy_text += (
                        f"**{disc['user']}**: "
                        f"Store={disc['store_count']}, "
                        f"API={disc['api_count']} "
                        f"(Diff: {disc['difference']}, "
                        f"{disc['difference_percent']:.1f}%)\n"
                    )

                if len(results["discrepancies"]) > 5:
                    discrepancy_text += f"\n_...and {len(results['discrepancies']) - 5} more_"

                embed.add_field(
                    name="⚠️ Discrepancies Found",
                    value=discrepancy_text or "None",
                    inline=False
                )

            # Add interpretation
            if results["passed"]:
                embed.add_field(
                    name="✅ Interpretation",
                    value=(
                        "Message counts are accurate! The tracking system is "
                        "working correctly. Small differences (<1%) can occur "
                        "due to messages sent during verification."
                    ),
                    inline=False
                )
            else:
                embed.add_field(
                    name="❌ Interpretation",
                    value=(
                        "Significant discrepancies detected. Consider:\n"
                        "1. Re-running import with `force=True`\n"
                        "2. Checking bot permissions in all channels\n"
                        "3. Checking logs for errors during import"
                    ),
                    inline=False
                )

            # Try to update the (ephemeral) status message. Those webhooks can
            # expire after ~15 minutes, so provide a fallback.
            try:
                await status_message.edit(content=None, embed=embed)
            except discord.errors.HTTPException as exc:
                error_code = getattr(exc, "code", None)
                if exc.status in (401, 404) or error_code in (50027, 10008):
                    logger.warning(
                        "Status message edit failed (likely expired webhook token). "
                        "Sending fallback follow-up. status=%s code=%s",
                        exc.status,
                        error_code
                    )
                    fallback_text = (
                        "⏱️ Die ursprüngliche Statusmeldung war abgelaufen, "
                        "hier ist das finale Ergebnis:"
                    )
                    try:
                        await interaction.followup.send(
                            fallback_text,
                            embed=embed,
                            ephemeral=True
                        )
                    except Exception as followup_exc:
                        logger.error(
                            "Failed to send fallback verification result: %s",
                            followup_exc,
                            exc_info=True
                        )
                else:
                    raise

            logger.info(f"Verification completed: {status}")
            if progress_state["log_message"]:
                await self._log_event(
                    interaction.guild,
                    "🔍 Verifikation abgeschlossen",
                    (
                        f"{interaction.user.mention} hat {results['total_users']} User geprüft.\n"
                        f"Accuracy: {results['accuracy_percent']:.1f}%\n"
                        f"Mismatches: {results['mismatches']}"
                    ),
                    status="✅ Erfolgreich" if results["passed"] else "⚠️ Abweichungen",
                    color=discord.Color.green() if results["passed"] else discord.Color.orange(),
                    message=progress_state["log_message"]
                )

        except Exception as e:
            logger.error(f"Error during verification: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error during verification: {str(e)}",
                ephemeral=True
            )
            if 'progress_state' in locals() and progress_state.get("log_message"):
                await self._log_event(
                    interaction.guild,
                    "🔍 Verifikation fehlgeschlagen",
                    str(e),
                    status="❌ Fehler",
                    color=discord.Color.red(),
                    message=progress_state["log_message"]
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
