"""My-Score command for users to check their own ranking."""

import logging
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from ..analytics import RoleScanner, ActivityTracker, Scorer, Ranker
from ..utils import Config
from ..database import MessageCache


logger = logging.getLogger("guildscout.commands.my_score")


class MyScoreCommand(commands.Cog):
    """Cog for the /my-score command."""

    def __init__(self, bot: commands.Bot, config: Config, cache: MessageCache):
        """
        Initialize the my-score command.

        Args:
            bot: Discord bot instance
            config: Configuration object
            cache: MessageCache instance
        """
        self.bot = bot
        self.config = config
        self.cache = cache

    @app_commands.command(
        name="my-score",
        description="Check your own ranking score"
    )
    @app_commands.describe(
        role="Optional: Check your score within a specific role"
    )
    async def my_score(
        self,
        interaction: discord.Interaction,
        role: Optional[discord.Role] = None
    ):
        """
        Show the user their own ranking score.

        Args:
            interaction: Discord interaction
            role: Optional role to check score within
        """
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.errors.NotFound:
            logger.warning(f"Interaction expired - bot may have been reconnecting")
            return
        except Exception as e:
            logger.error(f"Error during defer: {e}", exc_info=True)
            return

        try:
            guild = interaction.guild
            user = interaction.user

            # Initialize components
            activity_tracker = ActivityTracker(
                guild,
                excluded_channels=self.config.excluded_channels,
                excluded_channel_names=self.config.excluded_channel_names,
                cache=self.cache,
                message_store=getattr(self.bot, 'message_store', None)
            )

            # If role specified, check if user has it
            if role:
                if role not in user.roles:
                    await interaction.followup.send(
                        f"❌ You don't have the role @{role.name}",
                        ephemeral=True
                    )
                    return

                # Get all members with this role for comparison
                role_scanner = RoleScanner(guild)
                members = await role_scanner.get_members_with_role(role)
            else:
                # Use all members
                members = [m for m in guild.members if not m.bot]

            if not members:
                await interaction.followup.send(
                    "❌ No members found for comparison",
                    ephemeral=True
                )
                return

            # Count messages for all members (will use cache when available)
            message_counts, cache_stats = await activity_tracker.count_messages_for_users(
                members,
                days_lookback=self.config.max_days_lookback
            )

            # Calculate scores
            scorer = Scorer(
                weight_days=self.config.scoring_weights["days_in_server"],
                weight_messages=self.config.scoring_weights["message_count"],
                min_messages=0  # Don't filter anyone out
            )

            scores = scorer.calculate_scores(members, message_counts)

            # Find user's score
            user_score = None
            for score in scores:
                if score.user_id == user.id:
                    user_score = score
                    break

            if user_score is None:
                await interaction.followup.send(
                    "❌ Could not calculate your score. You might not meet the minimum requirements.",
                    ephemeral=True
                )
                return

            # Rank all users
            ranked_users = Ranker.rank_users(scores)

            # Find user's rank
            user_rank = None
            for rank, score in ranked_users:
                if score.user_id == user.id:
                    user_rank = rank
                    break

            # Get scoring info
            scoring_info = scorer.get_scoring_info()

            # Create embed
            embed = self._create_score_embed(
                user_score,
                user_rank,
                len(ranked_users),
                scoring_info,
                role.name if role else None,
                cache_stats
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(
                f"User {user.name} checked their score: "
                f"{user_score.final_score} (rank {user_rank}/{len(ranked_users)})"
            )

        except Exception as e:
            logger.error(f"Error in my-score command: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

    def _create_score_embed(
        self,
        user_score,
        rank: int,
        total_users: int,
        scoring_info: dict,
        role_name: Optional[str],
        cache_stats: dict
    ) -> discord.Embed:
        """
        Create an embed showing the user's score.

        Args:
            user_score: UserScore object
            rank: User's rank
            total_users: Total number of ranked users
            scoring_info: Scoring configuration
            role_name: Optional role name
            cache_stats: Cache statistics

        Returns:
            Discord Embed
        """
        # Determine medal/emoji
        if rank == 1:
            rank_emoji = "🥇"
        elif rank == 2:
            rank_emoji = "🥈"
        elif rank == 3:
            rank_emoji = "🥉"
        elif rank <= 10:
            rank_emoji = "🏆"
        elif rank <= 25:
            rank_emoji = "⭐"
        else:
            rank_emoji = "📊"

        # Create title
        title = f"{rank_emoji} Your Ranking Score"
        if role_name:
            title += f" (@{role_name})"

        # Calculate percentile
        percentile = round((1 - (rank - 1) / total_users) * 100, 1) if total_users > 1 else 100

        # Create embed
        embed = discord.Embed(
            title=title,
            description=f"**Score: {user_score.final_score}/100**",
            color=self._get_color_for_rank(rank, total_users),
        )

        # Rank field
        embed.add_field(
            name="📈 Your Rank",
            value=f"**#{rank}** of {total_users} users\n(Top {percentile}%)",
            inline=False
        )

        # Score breakdown
        breakdown = (
            f"📅 **Membership Duration:**\n"
            f"   • {user_score.days_in_server} days in server\n"
            f"   • Score: {user_score.days_score}/100\n"
            f"   • Weight: {scoring_info['weight_days']:.0%}\n"
            f"   • Contribution: {user_score.days_score * scoring_info['weight_days']:.1f}\n\n"
            f"💬 **Activity Level:**\n"
            f"   • {user_score.message_count:,} messages sent\n"
            f"   • Score: {user_score.activity_score}/100\n"
            f"   • Weight: {scoring_info['weight_messages']:.0%}\n"
            f"   • Contribution: {user_score.activity_score * scoring_info['weight_messages']:.1f}"
        )

        embed.add_field(
            name="🔍 Score Breakdown",
            value=breakdown,
            inline=False
        )

        # Formula
        formula = (
            f"```\n"
            f"Final Score = (Days Score × {scoring_info['weight_days']:.1f}) + "
            f"(Activity Score × {scoring_info['weight_messages']:.1f})\n"
            f"            = ({user_score.days_score} × {scoring_info['weight_days']:.1f}) + "
            f"({user_score.activity_score} × {scoring_info['weight_messages']:.1f})\n"
            f"            = {user_score.final_score}\n"
            f"```"
        )

        embed.add_field(
            name="📐 Calculation",
            value=formula,
            inline=False
        )

        # Cache info
        if cache_stats.get('cache_hit_rate', 0) > 0:
            cache_icon = "💾" if cache_stats['cache_hit_rate'] > 50 else "🔍"
            embed.set_footer(
                text=f"{cache_icon} Cache hit rate: {cache_stats['cache_hit_rate']:.1f}% | Analysis cached for faster results"
            )
        else:
            embed.set_footer(text="GuildScout Bot")

        return embed

    def _get_color_for_rank(self, rank: int, total: int) -> discord.Color:
        """Get color based on rank."""
        percentile = (1 - (rank - 1) / total) * 100 if total > 1 else 100

        if percentile >= 90:
            return discord.Color.gold()
        elif percentile >= 75:
            return discord.Color.green()
        elif percentile >= 50:
            return discord.Color.blue()
        elif percentile >= 25:
            return discord.Color.orange()
        else:
            return discord.Color.red()


async def setup(bot: commands.Bot, config: Config, cache: MessageCache):
    """
    Setup function for the my-score command.

    Args:
        bot: Discord bot instance
        config: Configuration object
        cache: MessageCache instance
    """
    await bot.add_cog(MyScoreCommand(bot, config, cache))
