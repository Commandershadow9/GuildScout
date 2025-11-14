"""Analyze command for user ranking."""

import logging
import discord
from discord import app_commands
from discord.ext import commands
import time
from typing import Optional
from datetime import datetime

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

            # Step 8: Post to ranking channel if configured
            await self._post_to_ranking_channel(
                guild,
                role,
                ranked_users,
                stats,
                scoring_info,
                duration,
                csv_path,
                cache_stats
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

    async def _post_to_ranking_channel(
        self,
        guild: discord.Guild,
        role: discord.Role,
        ranked_users: list,
        stats: dict,
        scoring_info: dict,
        duration: float,
        csv_path: str,
        cache_stats: dict
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
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

            # Main embed
            main_embed = discord.Embed(
                title=f"📊 Ranking Results: @{role.name}",
                description=(
                    f"**Analysis completed at {timestamp}**\n\n"
                    f"🔍 **Total Users Scanned:** {stats['total_users']}\n"
                    f"⏱️ **Analysis Duration:** {duration:.1f}s\n"
                    f"💾 **Cache Hit Rate:** {cache_stats.get('cache_hit_rate', 0):.1f}%\n"
                ),
                color=discord.Color.gold(),
                timestamp=datetime.utcnow()
            )

            # Scoring formula
            main_embed.add_field(
                name="📐 Scoring Formula",
                value=(
                    f"```\n"
                    f"Score = (Days × {scoring_info['weight_days']:.0%}) + "
                    f"(Messages × {scoring_info['weight_messages']:.0%})\n"
                    f"```"
                ),
                inline=False
            )

            # Statistics
            main_embed.add_field(
                name="📈 Statistics",
                value=(
                    f"**Average Score:** {stats['avg_score']:.1f}\n"
                    f"**Average Days:** {stats['avg_days']:.1f}\n"
                    f"**Average Messages:** {stats['avg_messages']:.1f}\n"
                    f"**Highest Score:** {stats['max_score']:.1f}\n"
                    f"**Lowest Score:** {stats['min_score']:.1f}"
                ),
                inline=True
            )

            main_embed.set_footer(text="Scroll down for complete ranking list ⬇️")

            await channel.send(embed=main_embed)

            # Send detailed rankings in chunks
            chunk_size = 25
            total_users = len(ranked_users)

            for chunk_start in range(0, total_users, chunk_size):
                chunk_end = min(chunk_start + chunk_size, total_users)
                chunk = ranked_users[chunk_start:chunk_end]

                chunk_embed = discord.Embed(
                    title=f"🏆 Rankings {chunk_start + 1}-{chunk_end} of {total_users}",
                    color=discord.Color.blue()
                )

                ranking_text = []
                for rank, score in chunk:
                    # Medal for top 3
                    if rank == 1:
                        medal = "🥇"
                    elif rank == 2:
                        medal = "🥈"
                    elif rank == 3:
                        medal = "🥉"
                    else:
                        medal = f"`#{rank:02d}`"

                    ranking_text.append(
                        f"{medal} **{score.display_name}**\n"
                        f"    Score: **{score.final_score}** | "
                        f"Days: {score.days_in_server} | "
                        f"Messages: {score.message_count:,}"
                    )

                chunk_embed.description = "\n\n".join(ranking_text)

                if chunk_end == total_users:
                    chunk_embed.set_footer(text="End of rankings ✓")

                await channel.send(embed=chunk_embed)

            # Send transparency breakdown for top 10
            transparency_embed = discord.Embed(
                title="🔍 Score Breakdown (Top 10)",
                description="Detailed calculation for transparency",
                color=discord.Color.green()
            )

            top_10 = ranked_users[:10]
            for rank, score in top_10:
                medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"][rank - 1]

                breakdown = (
                    f"{medal} **{score.display_name}**\n"
                    f"```\n"
                    f"Days Score:     {score.days_score:.1f}/100 × 0.4 = {score.days_score * 0.4:.1f}\n"
                    f"Activity Score: {score.activity_score:.1f}/100 × 0.6 = {score.activity_score * 0.6:.1f}\n"
                    f"                                    ───────────\n"
                    f"Final Score:                         {score.final_score:.1f}\n"
                    f"```"
                )

                transparency_embed.add_field(
                    name=f"Rank {rank}",
                    value=breakdown,
                    inline=False
                )

            await channel.send(embed=transparency_embed)

            # Send CSV file
            try:
                file = discord.File(csv_path)
                await channel.send(
                    content="📥 **Complete ranking data (CSV)**",
                    file=file
                )
            except Exception as e:
                logger.error(f"Failed to send CSV to ranking channel: {e}")

            # Send decision helper
            decision_embed = discord.Embed(
                title="✅ Next Steps: Making Fair Decisions",
                description=(
                    "**How to use this ranking:**\n\n"
                    "1️⃣ **Review the scores** - Higher = more deserving (longer membership + more active)\n"
                    "2️⃣ **Download the CSV** - For detailed analysis in Excel/Sheets\n"
                    "3️⃣ **Draw the line** - Decide cutoff score based on available guild spots\n"
                    "4️⃣ **Communicate clearly** - Users can check their own score with `/my-score`\n\n"
                    "**Score Calculation:**\n"
                    f"• 40% based on days in server (loyalty/commitment)\n"
                    f"• 60% based on message count (activity/engagement)\n\n"
                    "**All users can verify their score** using `/my-score` command for full transparency!"
                ),
                color=discord.Color.blurple()
            )

            decision_embed.set_footer(text="GuildScout - Fair & Transparent Rankings")

            await channel.send(embed=decision_embed)

            logger.info(f"Posted rankings to channel {channel.name} (ID: {channel.id})")

        except Exception as e:
            logger.error(f"Error posting to ranking channel: {e}", exc_info=True)


async def setup(bot: commands.Bot, config: Config, cache: MessageCache):
    """
    Setup function for the analyze command.

    Args:
        bot: Discord bot instance
        config: Configuration object
        cache: MessageCache instance
    """
    await bot.add_cog(AnalyzeCommand(bot, config, cache))
