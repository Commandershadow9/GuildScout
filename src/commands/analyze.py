"""Analyze command for user ranking."""

import logging
import discord
from discord import app_commands
from discord.ext import commands
import time
from typing import Optional

from ..analytics import RoleScanner, ActivityTracker, Scorer, Ranker
from ..exporters import DiscordExporter, CSVExporter
from ..utils import Config
from ..database import MessageCache


logger = logging.getLogger("guildscout.commands.analyze")


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
        await interaction.response.defer()

        try:
            start_time = time.time()

            # Initialize components
            guild = interaction.guild
            role_scanner = RoleScanner(guild)
            activity_tracker = ActivityTracker(
                guild,
                excluded_channels=self.config.excluded_channels,
                excluded_channel_names=self.config.excluded_channel_names,
                cache=self.cache
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

            # Step 1: Get members with role
            members = await role_scanner.get_members_with_role(role)

            if not members:
                await interaction.followup.send(
                    embed=discord_exporter.create_error_embed(
                        f"No members found with role @{role.name}",
                        "No Users Found"
                    )
                )
                return

            # Step 2: Count messages
            logger.info(f"Counting messages for {len(members)} members...")

            # Send initial progress message
            progress_msg = await interaction.followup.send(
                embed=discord_exporter.create_progress_embed(
                    0, len(members), "Counting messages"
                )
            )

            # Progress callback
            async def progress_callback(current: int, total: int):
                # Update every 10 users or at completion
                if current % 10 == 0 or current == total:
                    try:
                        await progress_msg.edit(
                            embed=discord_exporter.create_progress_embed(
                                current, total, "Counting messages"
                            )
                        )
                    except:
                        pass  # Ignore edit errors

            message_counts, cache_stats = await activity_tracker.count_messages_for_users(
                members,
                days_lookback=days,
                progress_callback=progress_callback
            )

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

            # Step 4: Rank users
            ranked_users = Ranker.rank_users(scores, top_n=top_n)
            stats = Ranker.get_statistics(scores)

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

            # Send embed
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

            logger.info(
                f"Analysis completed in {duration:.1f}s - "
                f"{len(ranked_users)} users ranked"
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


async def setup(bot: commands.Bot, config: Config, cache: MessageCache):
    """
    Setup function for the analyze command.

    Args:
        bot: Discord bot instance
        config: Configuration object
        cache: MessageCache instance
    """
    await bot.add_cog(AnalyzeCommand(bot, config, cache))
