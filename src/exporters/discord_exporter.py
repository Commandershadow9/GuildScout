"""Discord embed exporter for displaying rankings."""

import logging
from typing import List
import discord
from datetime import datetime, timezone


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

        Splits users across multiple fields if needed (max 8 users per field).

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
            timestamp=datetime.now(timezone.utc)
        )

        # Split users into chunks (8 per field to stay under 1024 char limit)
        users_per_field = 8
        total_users = len(ranked_users)

        # Add user fields (up to 20 fields max, leaving room for stats)
        max_fields = 20
        fields_added = 0

        for i in range(0, total_users, users_per_field):
            if fields_added >= max_fields:
                break

            chunk = ranked_users[i:i + users_per_field]
            chunk_start = i + 1
            chunk_end = min(i + users_per_field, total_users)

            field_text = self._create_users_chunk_text(chunk)

            if i == 0:
                field_name = f"🏆 Top Users (Ranks {chunk_start}-{chunk_end})"
            else:
                field_name = f"📋 Ranks {chunk_start}-{chunk_end}"

            embed.add_field(
                name=field_name,
                value=field_text,
                inline=False
            )
            fields_added += 1

        # Add statistics
        embed.add_field(
            name="📈 Statistics",
            value=self._create_stats_text(stats),
            inline=False
        )

        # Footer with CSV reminder
        embed.set_footer(
            text=f"Showing all {total_users} ranked users. Download CSV for full data export."
        )

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
            f"Msgs {scoring_info['weight_messages']:.0%} | "
            f"Voice {scoring_info['weight_voice']:.0%}"
        )

    def _create_users_chunk_text(self, users_chunk: List[tuple]) -> str:
        """Create formatted text for a chunk of users (fits in 1024 char Discord limit)."""
        lines = []

        for rank, score in users_chunk:
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
                f"   └ {score.days_in_server} days | {score.message_count:,} msgs | {score.voice_seconds // 60} min voice"
            )
            lines.append(line)

        result = "\n\n".join(lines)

        # Safety check: truncate if still too long (should not happen with 8 users)
        if len(result) > 1020:
            result = result[:1020] + "..."

        return result

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
            timestamp=datetime.now(timezone.utc)
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
            timestamp=datetime.now(timezone.utc)
        )

        # Progress bar
        bar_length = 20
        filled = int(bar_length * current / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_length - filled)
        embed.add_field(name="Progress", value=f"`{bar}`", inline=False)

        return embed
