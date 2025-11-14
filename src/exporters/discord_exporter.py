"""Discord embed exporter for displaying rankings."""

import logging
from typing import List
import discord
from datetime import datetime


logger = logging.getLogger("guildscout.discord_exporter")


class DiscordExporter:
    """Exports rankings as Discord embeds."""

    def __init__(self, max_users_per_embed: int = 25):
        """
        Initialize the Discord exporter.

        Args:
            max_users_per_embed: Maximum users to show in embed
        """
        self.max_users_per_embed = max_users_per_embed

    def create_ranking_embed(
        self,
        ranked_users: List[tuple],
        role_name: str,
        total_scanned: int,
        duration_seconds: float,
        scoring_info: dict,
        stats: dict
    ) -> discord.Embed:
        """
        Create a Discord embed with ranking results.

        Args:
            ranked_users: List of (rank, UserScore) tuples
            role_name: Name of the role that was analyzed
            total_scanned: Total number of users scanned
            duration_seconds: Time taken for analysis
            scoring_info: Scoring configuration info
            stats: Statistics dictionary

        Returns:
            Discord Embed object
        """
        # Create embed
        embed = discord.Embed(
            title=f"📊 User Ranking for @{role_name}",
            description=self._create_description(
                total_scanned,
                duration_seconds,
                scoring_info
            ),
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        # Add top users
        top_users_text = self._create_top_users_text(ranked_users)
        if top_users_text:
            embed.add_field(
                name=f"🏆 Top {min(len(ranked_users), self.max_users_per_embed)} Users",
                value=top_users_text,
                inline=False
            )

        # Add statistics
        embed.add_field(
            name="📈 Statistics",
            value=self._create_stats_text(stats),
            inline=False
        )

        # Footer
        if len(ranked_users) > self.max_users_per_embed:
            embed.set_footer(
                text=f"Showing top {self.max_users_per_embed} of {len(ranked_users)} users. "
                f"Download CSV for complete list."
            )
        else:
            embed.set_footer(text="GuildScout Bot")

        return embed

    def _create_description(
        self,
        total_scanned: int,
        duration_seconds: float,
        scoring_info: dict
    ) -> str:
        """Create embed description with analysis info."""
        return (
            f"🔍 **Scanned:** {total_scanned} users\n"
            f"⏱️ **Duration:** {duration_seconds:.1f} seconds\n"
            f"📐 **Formula:** {scoring_info['formula']}\n"
            f"⚖️ **Weights:** Days {scoring_info['weight_days']:.0%} | "
            f"Messages {scoring_info['weight_messages']:.0%}"
        )

    def _create_top_users_text(self, ranked_users: List[tuple]) -> str:
        """Create formatted text for top users."""
        lines = []
        display_count = min(len(ranked_users), self.max_users_per_embed)

        for rank, score in ranked_users[:display_count]:
            # Medal emojis for top 3
            if rank == 1:
                medal = "🥇"
            elif rank == 2:
                medal = "🥈"
            elif rank == 3:
                medal = "🥉"
            else:
                medal = f"**{rank}.**"

            line = (
                f"{medal} `{score.display_name}`\n"
                f"   ├ Score: **{score.final_score}** "
                f"({score.days_score:.1f} days + {score.activity_score:.1f} activity)\n"
                f"   └ {score.days_in_server} days | {score.message_count:,} messages"
            )
            lines.append(line)

        return "\n\n".join(lines)

    def _create_stats_text(self, stats: dict) -> str:
        """Create formatted statistics text."""
        return (
            f"**Total Users:** {stats['total_users']}\n"
            f"**Average Score:** {stats['avg_score']:.1f}\n"
            f"**Average Days:** {stats['avg_days']:.1f}\n"
            f"**Average Messages:** {stats['avg_messages']:.1f}\n"
            f"**Highest Score:** {stats['max_score']:.1f}\n"
            f"**Lowest Score:** {stats['min_score']:.1f}"
        )

    def create_error_embed(
        self,
        error_message: str,
        error_type: str = "Error"
    ) -> discord.Embed:
        """
        Create an error embed.

        Args:
            error_message: Error message to display
            error_type: Type of error (for title)

        Returns:
            Discord Embed object
        """
        embed = discord.Embed(
            title=f"❌ {error_type}",
            description=error_message,
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        return embed

    def create_progress_embed(
        self,
        current: int,
        total: int,
        operation: str = "Processing"
    ) -> discord.Embed:
        """
        Create a progress embed.

        Args:
            current: Current progress
            total: Total items
            operation: Operation being performed

        Returns:
            Discord Embed object
        """
        percentage = (current / total * 100) if total > 0 else 0

        embed = discord.Embed(
            title=f"⏳ {operation}...",
            description=f"Progress: {current}/{total} ({percentage:.1f}%)",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )

        # Progress bar
        bar_length = 20
        filled = int(bar_length * current / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_length - filled)
        embed.add_field(name="Progress", value=f"`{bar}`", inline=False)

        return embed
