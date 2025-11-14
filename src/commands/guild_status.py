"""
Guild Status Command - View current guild members and spot availability.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import logging
from datetime import datetime
import pandas as pd
from pathlib import Path

from src.utils.config import Config

logger = logging.getLogger(__name__)


class GuildStatusCommand(commands.Cog):
    """Command for viewing current guild member status and spot availability."""

    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config

    @app_commands.command(
        name="guild-status",
        description="[Admin] View current guild members and spot availability"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def guild_status(
        self,
        interaction: discord.Interaction
    ):
        """
        Display overview of current guild members.

        Shows:
        - Total spots and availability
        - List of all users with the guild role
        - CSV export of current guild members
        - Breakdown by how they got the role (manual vs. auto-assigned)
        """
        await interaction.response.defer(ephemeral=False)

        try:
            guild = interaction.guild
            guild_role_id = self.config.guild_role_id
            max_spots = self.config.max_guild_spots

            # Validate configuration
            if not guild_role_id:
                await interaction.followup.send(
                    "⚠️ **Configuration Error**\n"
                    "Guild role ID not configured in `config.yaml`.\n"
                    "Please set `guild_management.guild_role_id`.",
                    ephemeral=True
                )
                return

            # Get the guild role
            guild_role = guild.get_role(guild_role_id)
            if not guild_role:
                await interaction.followup.send(
                    f"⚠️ **Error**: Guild role with ID `{guild_role_id}` not found in this server.",
                    ephemeral=True
                )
                return

            # Get all members with the guild role
            guild_members = [member for member in guild.members if guild_role in member.roles and not member.bot]

            # Calculate scores for all guild members
            from src.analytics import RoleScanner, ActivityTracker, Scorer, Ranker
            from src.database import MessageCache

            scanner = RoleScanner(
                guild,
                exclusion_role_ids=self.config.exclusion_roles,
                exclusion_user_ids=self.config.exclusion_users
            )

            # Quick scoring for guild members
            member_scores = {}
            if guild_members:
                cache = MessageCache(ttl=self.config.cache_ttl)
                activity_tracker = ActivityTracker(
                    guild,
                    excluded_channels=self.config.excluded_channels,
                    excluded_channel_names=self.config.excluded_channel_names,
                    cache=cache
                )
                scorer = Scorer(
                    weight_days=self.config.scoring_weights["days_in_server"],
                    weight_messages=self.config.scoring_weights["message_count"],
                    min_messages=self.config.min_messages
                )

                # Count messages and calculate scores
                message_counts, _ = await activity_tracker.count_messages_for_users(guild_members)
                scores = scorer.calculate_scores(guild_members, message_counts)
                ranked = Ranker.rank_users(scores)

                # Create dict for easy lookup
                for rank, score in ranked:
                    member_scores[score.user_id] = {
                        'rank': rank,
                        'score': score.final_score,
                        'messages': score.message_count,
                        'days': score.days_in_server
                    }

            filled_spots = scanner.count_all_excluded_members()

            total_spots = max_spots
            available_spots = max(0, total_spots - filled_spots)
            percentage_filled = (filled_spots / total_spots * 100) if total_spots > 0 else 0

            # Create main embed
            embed = discord.Embed(
                title="📊 Guild Status Overview",
                description=(
                    f"Current status of guild role **@{guild_role.name}**\n"
                    f"Updated: {discord.utils.format_dt(datetime.now(), style='F')}"
                ),
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )

            # Spot availability
            embed.add_field(
                name="🎯 Spot Availability",
                value=(
                    f"**Total Spots:** {total_spots}\n"
                    f"**Filled:** {filled_spots} ({percentage_filled:.1f}%)\n"
                    f"**Available:** {available_spots}"
                ),
                inline=False
            )

            # Progress bar
            filled_blocks = int(percentage_filled / 10)
            empty_blocks = 10 - filled_blocks
            progress_bar = "█" * filled_blocks + "░" * empty_blocks

            embed.add_field(
                name="📈 Fill Status",
                value=f"`{progress_bar}` {percentage_filled:.1f}%",
                inline=False
            )

            # List ALL current members (sorted by score, highest first)
            if guild_members:
                # Sort members by score (highest first)
                sorted_members = sorted(
                    guild_members,
                    key=lambda m: member_scores.get(m.id, {}).get('score', 0),
                    reverse=True
                )

                # Show ALL members, split into multiple fields if needed (max 8 per field for safety)
                members_per_field = 8
                for i in range(0, len(sorted_members), members_per_field):
                    chunk = sorted_members[i:i + members_per_field]
                    member_list = []

                    for member in chunk:
                        score_info = member_scores.get(member.id, {})
                        score = score_info.get('score', 0)
                        messages = score_info.get('messages', 0)
                        rank = score_info.get('rank', '?')

                        member_list.append(
                            f"#{rank} `{member.name}` - **{score}** ({messages} msgs)"
                        )

                    members_text = "\n".join(member_list)

                    # Field title
                    if i == 0:
                        field_name = f"🏆 Guild Members - Höchste Scores ({len(guild_members)} total)"
                    else:
                        field_name = f"📋 Guild Members (continued)"

                    embed.add_field(
                        name=field_name,
                        value=members_text,
                        inline=False
                    )
            else:
                embed.add_field(
                    name="👥 Current Guild Members (0)",
                    value="*Noch keine Members mit der Guild-Rolle*",
                    inline=False
                )

            embed.set_footer(text=f"Requested by {interaction.user.name}")

            # Create CSV export (sorted by score, highest first)
            csv_path = None
            if guild_members:
                csv_data = []
                sorted_members = sorted(
                    guild_members,
                    key=lambda m: member_scores.get(m.id, {}).get('score', 0),
                    reverse=True
                )

                for member in sorted_members:
                    score_info = member_scores.get(member.id, {})
                    csv_data.append({
                        'Rank': score_info.get('rank', '?'),
                        'Username': member.name,
                        'User ID': member.id,
                        'Score': score_info.get('score', 0),
                        'Messages': score_info.get('messages', 0),
                        'Days': score_info.get('days', 0),
                        'Joined Server': member.joined_at.isoformat() if member.joined_at else 'N/A'
                    })

                df = pd.DataFrame(csv_data)

                # Save CSV
                output_dir = Path("output")
                output_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                csv_path = output_dir / f"guild_members_{timestamp}.csv"
                df.to_csv(csv_path, index=False)
                logger.info(f"Exported guild members to {csv_path}")

            # Send response
            if csv_path and csv_path.exists():
                await interaction.followup.send(
                    embed=embed,
                    file=discord.File(csv_path, filename=f"guild_members_{datetime.now().strftime('%Y%m%d')}.csv")
                )
            else:
                await interaction.followup.send(embed=embed)

            logger.info(f"Guild status viewed by {interaction.user.name} - {filled_spots}/{total_spots} spots filled")

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ **Permission Error**: I don't have permission to view members or roles.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in guild_status command: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ **Error**: An unexpected error occurred: {str(e)}",
                ephemeral=True
            )

    @guild_status.error
    async def guild_status_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Error handler for guild_status command."""
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message(
                "❌ **Permission Denied**: This command requires Administrator permissions.",
                ephemeral=True
            )
        else:
            logger.error(f"Error in guild_status command: {error}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"❌ **Error**: {str(error)}",
                    ephemeral=True
                )


async def setup(bot: commands.Bot, config: Config):
    """Setup function to add this cog to the bot."""
    await bot.add_cog(GuildStatusCommand(bot, config))
    logger.info("GuildStatusCommand cog loaded")
