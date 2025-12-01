"""Performance profiling command showing execution metrics."""

import discord
from discord import app_commands
from discord.ext import commands
import psutil
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict, deque

from src.utils import Config


class PerformanceTracker:
    """
    Tracks performance metrics for bot operations.

    Singleton pattern to ensure single instance across all cogs.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Track execution times: {operation_name: deque([duration, ...])}
        self.execution_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

        # Track call counts
        self.call_counts: Dict[str, int] = defaultdict(int)

        # Track errors
        self.error_counts: Dict[str, int] = defaultdict(int)

        # Track start time
        self.tracker_start = datetime.utcnow()

        self._initialized = True

    def record_execution(self, operation: str, duration: float, error: bool = False):
        """
        Record execution time for an operation.

        Args:
            operation: Name of the operation
            duration: Execution time in seconds
            error: Whether the operation errored
        """
        self.execution_times[operation].append(duration)
        self.call_counts[operation] += 1

        if error:
            self.error_counts[operation] += 1

    def get_stats(self, operation: str) -> Dict:
        """Get statistics for a specific operation."""
        times = list(self.execution_times.get(operation, []))

        if not times:
            return {
                'count': 0,
                'avg': 0,
                'min': 0,
                'max': 0,
                'total': 0,
                'errors': 0
            }

        return {
            'count': len(times),
            'avg': sum(times) / len(times),
            'min': min(times),
            'max': max(times),
            'total': sum(times),
            'errors': self.error_counts.get(operation, 0)
        }

    def get_all_operations(self) -> List[Tuple[str, Dict]]:
        """Get all tracked operations sorted by total time."""
        operations = []

        for op_name in self.execution_times.keys():
            stats = self.get_stats(op_name)
            operations.append((op_name, stats))

        # Sort by total time descending
        operations.sort(key=lambda x: x[1]['total'], reverse=True)

        return operations

    def get_slowest_operations(self, limit: int = 5) -> List[Tuple[str, Dict]]:
        """Get the slowest operations by average execution time."""
        operations = []

        for op_name in self.execution_times.keys():
            stats = self.get_stats(op_name)
            if stats['count'] > 0:
                operations.append((op_name, stats))

        # Sort by average time descending
        operations.sort(key=lambda x: x[1]['avg'], reverse=True)

        return operations[:limit]

    def get_most_called(self, limit: int = 5) -> List[Tuple[str, int]]:
        """Get the most frequently called operations."""
        sorted_ops = sorted(
            self.call_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_ops[:limit]

    def reset(self):
        """Reset all tracking data."""
        self.execution_times.clear()
        self.call_counts.clear()
        self.error_counts.clear()
        self.tracker_start = datetime.utcnow()


# Global tracker instance
_tracker = PerformanceTracker()


def get_tracker() -> PerformanceTracker:
    """Get the global performance tracker instance."""
    return _tracker


class ProfileCommand(commands.Cog):
    """Provides /profile command for performance analysis."""

    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config
        self.tracker = get_tracker()

    @app_commands.command(name="profile", description="Shows performance profiling and bottleneck analysis")
    async def profile_command(self, interaction: discord.Interaction):
        """Display comprehensive performance profile."""
        await interaction.response.defer()

        # Get system metrics
        process = psutil.Process(os.getpid())
        cpu_percent = process.cpu_percent(interval=0.1)
        memory_mb = process.memory_info().rss / (1024 * 1024)
        threads = process.num_threads()

        # Get performance stats
        slowest = self.tracker.get_slowest_operations(limit=8)
        most_called = self.tracker.get_most_called(limit=8)

        # Build embed
        embed = discord.Embed(
            title="📊 Performance Profiling",
            description="Detaillierte Performance-Analyse der Bot-Operationen",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        # System Resources
        embed.add_field(
            name="💻 System Ressourcen",
            value=(
                f"**CPU:** {cpu_percent:.1f}%\n"
                f"**Speicher:** {memory_mb:.1f} MB\n"
                f"**Threads:** {threads}"
            ),
            inline=True
        )

        # Tracking Info
        uptime = datetime.utcnow() - self.tracker.tracker_start
        total_ops = sum(self.tracker.call_counts.values())
        total_errors = sum(self.tracker.error_counts.values())

        embed.add_field(
            name="📈 Tracking Info",
            value=(
                f"**Uptime:** {self._format_timedelta(uptime)}\n"
                f"**Operationen:** {total_ops:,}\n"
                f"**Fehler:** {total_errors}"
            ),
            inline=True
        )

        # Slowest Operations (by avg time)
        if slowest:
            slowest_text = []
            for op_name, stats in slowest:
                # Shorten operation name if too long
                display_name = op_name if len(op_name) <= 30 else op_name[:27] + "..."
                slowest_text.append(
                    f"**{display_name}**\n"
                    f"⏱️ Ø {stats['avg']*1000:.1f}ms | "
                    f"Max {stats['max']*1000:.1f}ms | "
                    f"Calls {stats['count']}"
                )

            embed.add_field(
                name="🐌 Langsamste Operationen (Durchschnitt)",
                value="\n\n".join(slowest_text[:5]),
                inline=False
            )

        # Most Called Operations
        if most_called:
            called_text = []
            for op_name, count in most_called:
                stats = self.tracker.get_stats(op_name)
                display_name = op_name if len(op_name) <= 30 else op_name[:27] + "..."
                called_text.append(
                    f"**{display_name}**\n"
                    f"📞 {count:,} Calls | "
                    f"⏱️ Ø {stats['avg']*1000:.1f}ms | "
                    f"Gesamt {stats['total']:.1f}s"
                )

            embed.add_field(
                name="🔥 Meistgenutzte Operationen",
                value="\n\n".join(called_text[:5]),
                inline=False
            )

        # Bottleneck Analysis
        bottlenecks = self._analyze_bottlenecks(slowest, most_called)
        if bottlenecks:
            embed.add_field(
                name="⚠️ Identifizierte Engpässe",
                value="\n".join(bottlenecks),
                inline=False
            )

        embed.set_footer(text="Verwende diesen Befehl regelmäßig zur Performance-Überwachung")

        await interaction.followup.send(embed=embed)

    def _analyze_bottlenecks(
        self,
        slowest: List[Tuple[str, Dict]],
        most_called: List[Tuple[str, int]]
    ) -> List[str]:
        """Analyze and identify performance bottlenecks."""
        bottlenecks = []

        # Check for slow operations that are also frequently called
        slow_ops = {name for name, _ in slowest[:3]}
        frequent_ops = {name for name, _ in most_called[:3]}

        critical_ops = slow_ops & frequent_ops
        if critical_ops:
            for op in critical_ops:
                stats = self.tracker.get_stats(op)
                bottlenecks.append(
                    f"🔴 **{op}**: Langsam ({stats['avg']*1000:.0f}ms) UND häufig ({stats['count']} Calls)"
                )

        # Check for operations with high error rates
        for op_name, stats in slowest:
            if stats['errors'] > 0:
                error_rate = (stats['errors'] / stats['count']) * 100
                if error_rate > 10:  # >10% error rate
                    bottlenecks.append(
                        f"⚠️ **{op_name}**: Hohe Fehlerrate ({error_rate:.1f}%)"
                    )

        # Check for very slow operations (>1s avg)
        for op_name, stats in slowest:
            if stats['avg'] > 1.0:
                bottlenecks.append(
                    f"🐌 **{op_name}**: Sehr langsam (Ø {stats['avg']:.1f}s)"
                )

        if not bottlenecks:
            bottlenecks.append("✅ Keine kritischen Engpässe erkannt")

        return bottlenecks[:5]  # Max 5 bottlenecks

    def _format_timedelta(self, td: timedelta) -> str:
        """Format timedelta as human-readable string."""
        days = td.days
        hours, remainder = divmod(td.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")

        return " ".join(parts)


async def setup(bot: commands.Bot, config: Config):
    """Add profile command to bot."""
    await bot.add_cog(ProfileCommand(bot, config))
