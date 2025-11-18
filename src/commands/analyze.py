"""Analyze command for user ranking."""

import logging
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import time
from typing import Optional
from datetime import datetime, timezone

from ..analytics import RoleScanner, ActivityTracker, Scorer, Ranker
from ..exporters import DiscordExporter, CSVExporter
from ..utils import Config
from ..utils.log_helper import DiscordLogger
from ..database import MessageCache


logger = logging.getLogger("guildscout.commands.analyze")


class RoleAssignmentView(discord.ui.View):
    """Interactive view for role assignment confirmation."""

    def __init__(self, bot: commands.Bot, ranking_role: discord.Role, ranked_users: list, count: int, config: Config, interaction_user: discord.User):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.bot = bot
        self.ranking_role = ranking_role
        self.ranked_users = ranked_users
        self.count = count
        self.config = config
        self.interaction_user = interaction_user

    @discord.ui.button(label="✅ Ja, Rollen vergeben", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Assign guild role to top candidates and remove ranking role."""
        # Permission check: Only the user who ran /analyze can click
        if interaction.user.id != self.interaction_user.id:
            await interaction.response.send_message(
                "❌ Nur der User, der `/analyze` ausgeführt hat, kann diese Buttons verwenden.",
                ephemeral=True
            )
            return

        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            logger.warning(
                f"Button interaction expired for {interaction.user.name}. "
                "This can happen during bot reconnects."
            )
            try:
                await interaction.followup.send(
                    "⚠️ Aktion fehlgeschlagen (bot was reconnecting). Bitte nochmal versuchen.",
                    ephemeral=True
                )
            except Exception:
                pass
            return
        except Exception as e:
            logger.error(f"Unexpected error during button defer: {e}", exc_info=True)
            return

        # Get top candidates
        top_candidates = self.ranked_users[:self.count]

        # Get guild role to assign
        guild_role = interaction.guild.get_role(self.config.guild_role_id)
        if not guild_role:
            await interaction.followup.send(
                "❌ Guild-Rolle nicht gefunden! Bitte Config prüfen.",
                ephemeral=True
            )
            self.stop()
            return

        logger.info(
            f"Starting role assignment: {len(top_candidates)} users will receive {guild_role.name}"
        )

        # Assign roles with detailed logging
        successful = []
        failed = []
        logs = []

        for rank, score in top_candidates:
            try:
                member = interaction.guild.get_member(score.user_id)
                if not member:
                    msg = f"❌ Rank {rank}: {score.display_name} - Member nicht gefunden"
                    logger.warning(msg)
                    logs.append(msg)
                    failed.append(score.display_name)
                    continue

                # Add guild role
                await member.add_roles(guild_role, reason=f"GuildScout Ranking (Rank {rank})")
                msg = f"✅ Rank {rank}: {score.display_name} - {guild_role.name} vergeben"

                logger.info(msg)
                logs.append(msg)
                successful.append(score.display_name)

            except discord.Forbidden as e:
                msg = f"❌ Rank {rank}: {score.display_name} - Keine Berechtigung"
                logger.error(f"{msg}: {e}")
                logs.append(msg)
                failed.append(score.display_name)
            except Exception as e:
                msg = f"❌ Rank {rank}: {score.display_name} - Fehler: {str(e)}"
                logger.error(msg, exc_info=True)
                logs.append(msg)
                failed.append(score.display_name)

        logger.info(
            f"Role assignment completed: {len(successful)} successful, {len(failed)} failed"
        )

        # Send detailed result embed
        result_embed = discord.Embed(
            title="✅ Rollenvergabe abgeschlossen",
            description=(
                f"**Erfolgreich:** {len(successful)}/{self.count}\n"
                f"**Fehlgeschlagen:** {len(failed)}\n\n"
                f"Die Rolle {guild_role.mention} wurde an die Top {len(successful)} Kandidaten vergeben."
            ),
            color=discord.Color.green() if len(failed) == 0 else discord.Color.orange()
        )

        # Add successful users (first 15)
        if successful:
            result_embed.add_field(
                name=f"✅ Erfolgreich ({len(successful)})",
                value=", ".join(successful[:15]) + ("..." if len(successful) > 15 else ""),
                inline=False
            )

        # Add failed users (if any)
        if failed:
            result_embed.add_field(
                name=f"⚠️ Fehlgeschlagen ({len(failed)})",
                value=", ".join(failed[:10]) + ("..." if len(failed) > 10 else ""),
                inline=False
            )

        await interaction.followup.send(embed=result_embed)

        # Send detailed logs as follow-up message (for transparency)
        log_text = "\n".join(logs[:25])  # First 25 logs
        if len(log_text) > 1900:
            log_text = log_text[:1900] + "\n... (siehe Server-Logs für vollständige Details)"

        await interaction.followup.send(
            f"**📋 Detaillierte Logs:**\n```\n{log_text}\n```",
            ephemeral=False
        )

        # Create downloadable summary file
        if successful:
            from pathlib import Path
            from datetime import datetime, timezone

            summary_dir = Path("exports")
            summary_dir.mkdir(exist_ok=True)

            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"rollenvergabe_{guild_role.name}_{timestamp}.txt"
            filepath = summary_dir / filename

            # Write summary
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"═══════════════════════════════════════════════════════\n")
                f.write(f"  GuildScout - Rollenvergabe Zusammenfassung\n")
                f.write(f"═══════════════════════════════════════════════════════\n\n")
                f.write(f"Datum: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
                f.write(f"Guild-Rolle: {guild_role.name} (ID: {guild_role.id})\n")
                f.write(f"Ranking-Rolle: {self.ranking_role.name} (ID: {self.ranking_role.id})\n\n")
                f.write(f"Erfolgreich: {len(successful)}/{self.count}\n")
                f.write(f"Fehlgeschlagen: {len(failed)}\n\n")

                f.write(f"───────────────────────────────────────────────────────\n")
                f.write(f"  ✅ Erfolgreiche Rollenvergaben ({len(successful)})\n")
                f.write(f"───────────────────────────────────────────────────────\n\n")
                for i, username in enumerate(successful, 1):
                    f.write(f"{i:3d}. {username}\n")

                if failed:
                    f.write(f"\n───────────────────────────────────────────────────────\n")
                    f.write(f"  ❌ Fehlgeschlagene Rollenvergaben ({len(failed)})\n")
                    f.write(f"───────────────────────────────────────────────────────\n\n")
                    for i, username in enumerate(failed, 1):
                        f.write(f"{i:3d}. {username}\n")

                f.write(f"\n───────────────────────────────────────────────────────\n")
                f.write(f"  📋 Detaillierte Logs\n")
                f.write(f"───────────────────────────────────────────────────────\n\n")
                for log in logs:
                    f.write(f"{log}\n")

                f.write(f"\n═══════════════════════════════════════════════════════\n")
                f.write(f"  Ende der Zusammenfassung\n")
                f.write(f"═══════════════════════════════════════════════════════\n")

            # Send file
            try:
                file = discord.File(str(filepath))
                summary_embed = discord.Embed(
                    title="📥 Vollständige Zusammenfassung",
                    description=(
                        f"**{len(successful)} User** haben die Rolle {guild_role.mention} erhalten.\n\n"
                        f"Alle Details findest du in der angehängten Datei."
                    ),
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=summary_embed, file=file)
                logger.info(f"Sent role assignment summary file: {filepath}")
            except Exception as e:
                logger.error(f"Failed to send summary file: {e}")
                await interaction.followup.send(
                    f"⚠️ Zusammenfassung gespeichert unter: `{filepath}` (Upload fehlgeschlagen)"
                )

        # Disable buttons
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
        self.stop()

    @discord.ui.button(label="❌ Nein, abbrechen", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel role assignment."""
        # Permission check: Only the user who ran /analyze can click
        if interaction.user.id != self.interaction_user.id:
            await interaction.response.send_message(
                "❌ Nur der User, der `/analyze` ausgeführt hat, kann diese Buttons verwenden.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "❌ Rollenvergabe abgebrochen. Du kannst sie später mit `/assign-guild-role` manuell durchführen.",
            ephemeral=True
        )

        logger.info(f"Role assignment cancelled by {interaction.user.name}")

        # Disable buttons
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
        self.stop()


class AnalyzeCommand(commands.Cog):
    """Cog for the /analyze command."""

    def __init__(self, bot: commands.Bot, config: Config, cache: MessageCache):
        """
        Initialize the analyze command.

        Args:
            bot: Discord bot instance
            config: Configuration object
            cache: MessageCache instance
        """
        self.bot = bot
        self.config = config
        self.discord_logger = DiscordLogger(bot, config)
        self.cache = cache

    def _has_permission(self, interaction: discord.Interaction) -> bool:
        """
        Check if user has permission to use the command.

        Args:
            interaction: Discord interaction

        Returns:
            True if user has permission
        """
        # Check if user is in admin users list
        if interaction.user.id in self.config.admin_users:
            return True

        # Check if user has any of the admin roles
        if hasattr(interaction.user, 'roles'):
            user_role_ids = [role.id for role in interaction.user.roles]
            for admin_role_id in self.config.admin_roles:
                if admin_role_id in user_role_ids:
                    return True

        return False

    @app_commands.command(
        name="analyze",
        description="Analyze and rank users with a specific role"
    )
    @app_commands.describe(
        role="The role to analyze",
        days="Only count messages from the last X days (optional)",
        top_n="Show only top N users (optional)"
    )
    async def analyze(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        days: Optional[int] = None,
        top_n: Optional[int] = None
    ):
        """
        Analyze users with a specific role and generate ranking.

        Args:
            interaction: Discord interaction
            role: Role to analyze
            days: Optional days lookback
            top_n: Optional limit to top N users
        """
        # Check permissions
        if not self._has_permission(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return

        # Defer response (this will take time)
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            # Interaction expired (took > 3 seconds to reach this point)
            # This can happen during bot reconnects or high load
            logger.warning(
                f"Interaction expired for /analyze by {interaction.user.name}. "
                "This usually happens during bot reconnects or high load."
            )
            # Try to send ephemeral message if possible
            try:
                await interaction.followup.send(
                    "⚠️ Command took too long to start (bot was reconnecting or busy). "
                    "Please try again.",
                    ephemeral=True
                )
            except Exception:
                pass  # Nothing we can do
            return
        except Exception as e:
            logger.error(f"Unexpected error during defer: {e}", exc_info=True)
            return

        try:
            start_time = time.time()
            log_message = None

            # Initialize components
            guild = interaction.guild
            role_scanner = RoleScanner(
                guild,
                exclusion_role_ids=self.config.exclusion_roles,
                exclusion_user_ids=self.config.exclusion_users
            )
            activity_tracker = ActivityTracker(
                guild,
                excluded_channels=self.config.excluded_channels,
                excluded_channel_names=self.config.excluded_channel_names,
                cache=self.cache,
                message_store=getattr(self.bot, 'message_store', None)
            )
            scorer = Scorer(
                weight_days=self.config.scoring_weights["days_in_server"],
                weight_messages=self.config.scoring_weights["message_count"],
                min_messages=self.config.min_messages
            )
            discord_exporter = DiscordExporter(
                max_users_per_embed=self.config.max_users_per_embed
            )
            csv_exporter = CSVExporter(
                delimiter=self.config.csv_delimiter,
                encoding=self.config.csv_encoding
            )

            logger.info(
                f"Starting analysis for role {role.name} by user {interaction.user.name}"
            )

            # Step 1: Get members with role (excluding those who already have spots)
            members, excluded_members = await role_scanner.get_members_with_role(role)

            total_with_role = len(members) + len(excluded_members)
            logger.info(
                f"Total users with role: {total_with_role} "
                f"(Ranking: {len(members)}, Already have spots: {len(excluded_members)})"
            )

            if not members:
                # Check if there are only excluded members
                if excluded_members:
                    await interaction.followup.send(
                        embed=discord_exporter.create_error_embed(
                            f"All {len(excluded_members)} members with role @{role.name} "
                            f"already have reserved guild spots.\n\n"
                            f"No users available for ranking.",
                            "All Spots Reserved"
                        )
                    )
                else:
                    await interaction.followup.send(
                        embed=discord_exporter.create_error_embed(
                            f"No members found with role @{role.name}",
                            "No Users Found"
                        )
                    )
                return

            log_message = await self._log_event(
                guild,
                "Analyse gestartet",
                (
                    f"Rolle: **@{role.name}**\n"
                    f"Kandidaten: {len(members)}\n"
                    f"Reservierte Plätze: {len(excluded_members)}"
                ),
                status="⏳ Läuft",
                color=discord.Color.orange()
            )

            # Step 2: Count messages
            logger.info(f"Counting messages for {len(members)} members...")

            # Send initial progress message
            progress_msg = await interaction.followup.send(
                embed=discord_exporter.create_progress_embed(
                    0, len(members), "Counting messages"
                )
            )

            # Progress callback
            last_progress = 0
            heartbeat_stop = asyncio.Event()

            async def heartbeat():
                while not heartbeat_stop.is_set():
                    await asyncio.sleep(30)
                    if heartbeat_stop.is_set():
                        break
                    if log_message:
                        await self._log_event(
                            guild,
                            "Analyse läuft",
                            (
                                f"Rolle: **@{role.name}**\n"
                                f"Fortschritt: {last_progress}/{len(members)} Mitglieder"
                            ),
                            status="⏳ Läuft weiter",
                            color=discord.Color.orange(),
                            message=log_message
                        )

            heartbeat_task = asyncio.create_task(heartbeat())

            async def progress_callback(current: int, total: int):
                nonlocal last_progress
                last_progress = current
                try:
                    await progress_msg.edit(
                        embed=discord_exporter.create_progress_embed(
                            current, total, "Counting messages"
                        )
                    )
                except:
                    pass  # Ignore edit errors

                if log_message and (current == 1 or current % 5 == 0 or current == total):
                    await self._log_event(
                        guild,
                        "Analyse läuft",
                        (
                            f"Rolle: **@{role.name}**\n"
                            f"Fortschritt: {current}/{total} Mitglieder"
                        ),
                        status=f"🔍 {current}/{total}",
                        color=discord.Color.orange(),
                        message=log_message
                    )

            try:
                message_counts, cache_stats = await activity_tracker.count_messages_for_users(
                    members,
                    days_lookback=days,
                    progress_callback=progress_callback
                )
            finally:
                heartbeat_stop.set()
                await heartbeat_task

            # Step 3: Calculate scores
            scores = scorer.calculate_scores(members, message_counts)

            if not scores:
                await progress_msg.delete()
                await interaction.followup.send(
                    embed=discord_exporter.create_error_embed(
                        f"No users met the minimum requirements "
                        f"({self.config.min_messages} messages)",
                        "No Valid Users"
                    )
                )
                return

            # Step 3.5: Determine how many users to show
            # If top_n not specified, show as many as there are available spots
            if top_n is None:
                # Count ALL members with exclusion roles (not just those with ranking role)
                spots_already_filled = role_scanner.count_all_excluded_members()
                available_spots = self.config.max_guild_spots - spots_already_filled
                display_limit = max(1, available_spots)  # At least show 1 user
                logger.info(
                    f"No top_n specified. Showing {display_limit} users "
                    f"(available spots: {available_spots}, filled: {spots_already_filled})"
                )
            else:
                display_limit = top_n
                logger.info(f"User requested top {top_n} users")

            # Step 4: Rank users
            ranked_users = Ranker.rank_users(scores, top_n=display_limit)
            stats = Ranker.get_statistics(scores)

            # Count users below minimum message recommendation
            users_below_min = sum(1 for _, score in ranked_users if score.message_count < self.config.min_messages)

            # Step 5: Export to CSV
            csv_path = csv_exporter.export_ranking(
                ranked_users,
                role_name=role.name
            )

            # Step 6: Create Discord embed
            duration = time.time() - start_time
            scoring_info = scorer.get_scoring_info()

            embed = discord_exporter.create_ranking_embed(
                ranked_users=ranked_users,
                role_name=role.name,
                total_scanned=len(members),
                duration_seconds=duration,
                scoring_info=scoring_info,
                stats=stats
            )

            # Step 7: Send results
            await progress_msg.delete()

            # Send embed to command channel
            await interaction.followup.send(embed=embed)

            # Send CSV file
            try:
                file = discord.File(csv_path)
                await interaction.followup.send(
                    content="📥 Complete ranking data:",
                    file=file
                )
            except Exception as e:
                logger.error(f"Failed to send CSV file: {e}")
                await interaction.followup.send(
                    f"⚠️ CSV saved to: `{csv_path}` (failed to upload)"
                )

            # Step 7.5: Ask about role assignment with interactive buttons
            # Count ALL members with exclusion roles (not just those with ranking role)
            spots_already_filled = role_scanner.count_all_excluded_members()
            available_spots = self.config.max_guild_spots - spots_already_filled
            users_to_assign = min(available_spots, len(ranked_users))

            if users_to_assign > 0:
                # Get guild role for display
                guild_role = guild.get_role(self.config.guild_role_id)
                guild_role_name = guild_role.name if guild_role else "Guild-Rolle"

                # Create View with buttons
                view = RoleAssignmentView(
                    bot=self.bot,
                    ranking_role=role,
                    ranked_users=ranked_users,
                    count=users_to_assign,
                    config=self.config,
                    interaction_user=interaction.user
                )

                action_embed = discord.Embed(
                    title="✅ Ranking abgeschlossen!",
                    description=(
                        f"**{len(ranked_users)} Kandidaten** wurden gerankt.\n"
                        f"**{available_spots} Plätze** sind noch verfügbar.\n\n"
                        f"**🎯 Rollenvergabe:**\n"
                        f"Sollen die **Top {users_to_assign} Kandidaten** automatisch die Guild-Rolle {guild_role.mention if guild_role else '@' + guild_role_name} erhalten?\n\n"
                        f"Die Ranking-Rolle @{role.name} bleibt bei diesen Usern erhalten.\n\n"
                        f"Klicke unten auf einen Button um zu entscheiden."
                    ),
                    color=discord.Color.green()
                )
                action_embed.set_footer(text="Diese Frage läuft in 5 Minuten ab.")
                await interaction.followup.send(embed=action_embed, view=view)

            # Step 8: Post to ranking channel if configured
            await self._post_to_ranking_channel(
                guild,
                role,
                ranked_users,
                stats,
                scoring_info,
                duration,
                csv_path,
                cache_stats,
                excluded_members,
                self.config.max_guild_spots,
                users_below_min
            )

            logger.info(
                f"Analysis completed in {duration:.1f}s - "
                f"{len(ranked_users)} users ranked"
            )

            await self._log_event(
                guild,
                "Analyse abgeschlossen",
                (
                    f"Rolle: **@{role.name}**\n"
                    f"Platzierte Nutzer: {len(ranked_users)}\n"
                    f"Dauer: {duration:.1f}s\n"
                    f"Cache: {cache_stats['cache_hits']} Hits / {cache_stats['cache_misses']} Misses"
                ),
                status="✅ Abgeschlossen",
                color=discord.Color.green(),
                message=log_message
            )

        except Exception as e:
            logger.error(f"Error in analyze command: {e}", exc_info=True)

            error_embed = discord_exporter.create_error_embed(
                f"An error occurred during analysis:\n```{str(e)}```",
                "Analysis Error"
            )

            # Try to delete progress message if it exists
            try:
                await progress_msg.delete()
            except:
                pass

            await interaction.followup.send(embed=error_embed)

            await self._log_event(
                interaction.guild,
                "Analyse fehlgeschlagen",
                (
                    f"Rolle: **@{role.name}**\n"
                    f"Fehler: {e}"
                ),
                status="❌ Fehlgeschlagen",
                color=discord.Color.red(),
                message=log_message
            )

    async def _post_to_ranking_channel(
        self,
        guild: discord.Guild,
        role: discord.Role,
        ranked_users: list,
        stats: dict,
        scoring_info: dict,
        duration: float,
        csv_path: str,
        cache_stats: dict,
        excluded_members: list,
        max_guild_spots: int,
        users_below_min: int = 0
    ):
        """
        Post ranking results to dedicated ranking channel if configured.

        Args:
            guild: Discord guild
            role: Role that was analyzed
            ranked_users: List of ranked users
            stats: Statistics dictionary
            scoring_info: Scoring information
            duration: Analysis duration
            csv_path: Path to CSV file
            cache_stats: Cache statistics
        """
        try:
            # Check if ranking channel is configured
            if not hasattr(self.bot, 'ranking_channels'):
                return

            if guild.id not in self.bot.ranking_channels:
                return

            channel_id = self.bot.ranking_channels[guild.id]
            channel = guild.get_channel(channel_id)

            if not channel:
                logger.warning(f"Ranking channel {channel_id} not found")
                return

            # Create detailed ranking post
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

            # Calculate spot management info
            # Count ALL members with exclusion roles (not just those with ranking role)
            temp_scanner = RoleScanner(
                guild,
                exclusion_role_ids=self.config.exclusion_roles,
                exclusion_user_ids=self.config.exclusion_users
            )
            spots_already_filled = temp_scanner.count_all_excluded_members()
            spots_available = max_guild_spots - spots_already_filled
            total_candidates = len(ranked_users)

            # Berechne finale Belegung
            spots_after_assignment = spots_already_filled + min(spots_available, total_candidates)
            spots_remaining = max_guild_spots - spots_after_assignment

            # Info über User unter Mindestempfehlung
            warning_text = ""
            if users_below_min > 0:
                warning_text = f"\n⚠️ **Hinweis:** {users_below_min} User haben <10 Messages\n"

            # Kompaktes Embed nur mit wichtigen Infos für Rollenvergabe
            action_embed = discord.Embed(
                title=f"📊 Ranking abgeschlossen: @{role.name}",
                description=(
                    f"**🎯 Plätze-Übersicht:**\n"
                    f"• Gesamt: {max_guild_spots} Plätze\n"
                    f"• Bereits belegt: {spots_already_filled}\n"
                    f"• Noch frei: {spots_available}\n"
                    f"• Gerankte Kandidaten: {total_candidates}{warning_text}\n"
                    f"**📊 Nach Rollenvergabe:**\n"
                    f"• Belegt: {spots_after_assignment}/{max_guild_spots}\n"
                    f"• Verbleibend: {spots_remaining}\n\n"
                    f"**💡 Empfohlener Command:**\n"
                    f"```\n"
                    f"/assign-guild-role ranking_role:@{role.name} count:{min(spots_available, total_candidates)}\n"
                    f"```\n"
                    f"→ Vergibt Rolle an Top {min(spots_available, total_candidates)} Kandidaten\n\n"
                    f"📥 Vollständige Daten in CSV unten ⬇️"
                ),
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )

            action_embed.set_footer(text=f"Analyse: {duration:.1f}s | Cache: {cache_stats.get('cache_hit_rate', 0):.1f}%")

            await channel.send(embed=action_embed)

            # CSV-Datei mit allen Rankings
            try:
                file = discord.File(csv_path)
                await channel.send(
                    content=f"📥 **Vollständiges Ranking ({total_candidates} User)**",
                    file=file
                )
            except Exception as e:
                logger.error(f"Failed to send CSV to ranking channel: {e}")

            logger.info(f"Posted rankings to channel {channel.name} (ID: {channel.id})")

        except Exception as e:
            logger.error(f"Error posting to ranking channel: {e}", exc_info=True)

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
        """Send or update log entries in the configured Discord log channel."""
        return await self.discord_logger.send(
            guild,
            title,
            description,
            status=status,
            color=color,
            message=message
        )


async def setup(bot: commands.Bot, config: Config, cache: MessageCache):
    """
    Setup function for the analyze command.

    Args:
        bot: Discord bot instance
        config: Configuration object
        cache: MessageCache instance
    """
    await bot.add_cog(AnalyzeCommand(bot, config, cache))
