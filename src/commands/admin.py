"""Admin commands for bot management."""

import logging
import discord
from discord import app_commands
from discord.ext import commands
import platform
import psutil
import os
from datetime import datetime

from ..utils import Config
from ..database import MessageCache


logger = logging.getLogger("guildscout.commands.admin")


class AdminCommands(commands.Cog):
    """Cog for admin commands."""

    def __init__(self, bot: commands.Bot, config: Config, cache: MessageCache):
        """
        Initialize admin commands.

        Args:
            bot: Discord bot instance
            config: Configuration object
            cache: MessageCache instance
        """
        self.bot = bot
        self.config = config
        self.cache = cache
        self.start_time = datetime.utcnow()

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

    @app_commands.command(
        name="cache-clear",
        description="[Admin] Clear the message count cache"
    )
    @app_commands.describe(
        scope="What to clear: 'guild' (this server), 'all' (everything), or 'expired' (old entries)"
    )
    @app_commands.choices(scope=[
        app_commands.Choice(name="This Guild Only", value="guild"),
        app_commands.Choice(name="All Guilds", value="all"),
        app_commands.Choice(name="Expired Entries Only", value="expired")
    ])
    async def cache_clear(
        self,
        interaction: discord.Interaction,
        scope: app_commands.Choice[str]
    ):
        """
        Clear the message count cache.

        Args:
            interaction: Discord interaction
            scope: Scope of cache clearing
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
            logger.warning(f"Interaction expired - bot may have been reconnecting")
            return
        except Exception as e:
            logger.error(f"Error during defer: {e}", exc_info=True)
            return

        try:
            deleted = 0

            if scope.value == "guild":
                deleted = await self.cache.clear_guild(interaction.guild.id)
                message = f"✅ Cleared cache for this guild ({deleted} entries removed)"
            elif scope.value == "all":
                deleted = await self.cache.clear_all()
                message = f"✅ Cleared entire cache ({deleted} entries removed)"
            elif scope.value == "expired":
                deleted = await self.cache.cleanup_expired()
                message = f"✅ Cleaned up expired cache entries ({deleted} entries removed)"
            else:
                message = "❌ Invalid scope"

            await interaction.followup.send(message, ephemeral=True)

            logger.info(
                f"Cache cleared by {interaction.user.name} - "
                f"Scope: {scope.value}, Deleted: {deleted}"
            )

        except Exception as e:
            logger.error(f"Error clearing cache: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error clearing cache: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(
        name="cache-stats",
        description="[Admin] View cache statistics"
    )
    async def cache_stats(self, interaction: discord.Interaction):
        """
        Show cache statistics.

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
            logger.warning(f"Interaction expired - bot may have been reconnecting")
            return
        except Exception as e:
            logger.error(f"Error during defer: {e}", exc_info=True)
            return

        try:
            stats = await self.cache.get_stats()

            embed = discord.Embed(
                title="💾 Cache Statistics",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )

            embed.add_field(
                name="📊 Entries",
                value=(
                    f"Total: {stats['total_entries']:,}\n"
                    f"Valid: {stats['valid_entries']:,}\n"
                    f"Expired: {stats['expired_entries']:,}"
                ),
                inline=True
            )

            embed.add_field(
                name="💿 Storage",
                value=(
                    f"Size: {stats['db_size_mb']} MB\n"
                    f"TTL: {stats['ttl_seconds']}s ({stats['ttl_seconds'] / 3600:.1f}h)"
                ),
                inline=True
            )

            # Hit rate (if available)
            if stats['valid_entries'] > 0:
                efficiency = round(stats['valid_entries'] / stats['total_entries'] * 100, 1)
                embed.add_field(
                    name="⚡ Efficiency",
                    value=f"{efficiency}% valid entries",
                    inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error getting cache stats: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(
        name="bot-info",
        description="[Admin] View bot information and statistics"
    )
    async def botinfo(self, interaction: discord.Interaction):
        """
        Show bot information and statistics.

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
            logger.warning(f"Interaction expired - bot may have been reconnecting")
            return
        except Exception as e:
            logger.error(f"Error during defer: {e}", exc_info=True)
            return

        try:
            # System info
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent(interval=1)

            # Uptime
            uptime = datetime.utcnow() - self.start_time
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            # Cache stats
            cache_stats = await self.cache.get_stats()

            # Create embed
            embed = discord.Embed(
                title="🤖 GuildScout Bot Information",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )

            # Bot info
            embed.add_field(
                name="📊 Bot Stats",
                value=(
                    f"Guilds: {len(self.bot.guilds)}\n"
                    f"Users: {len(self.bot.users):,}\n"
                    f"Uptime: {days}d {hours}h {minutes}m {seconds}s"
                ),
                inline=True
            )

            # System info
            embed.add_field(
                name="💻 System",
                value=(
                    f"Python: {platform.python_version()}\n"
                    f"discord.py: {discord.__version__}\n"
                    f"Platform: {platform.system()}"
                ),
                inline=True
            )

            # Resources
            embed.add_field(
                name="⚙️ Resources",
                value=(
                    f"Memory: {memory_mb:.1f} MB\n"
                    f"CPU: {cpu_percent:.1f}%\n"
                    f"Threads: {process.num_threads()}"
                ),
                inline=True
            )

            # Cache info
            embed.add_field(
                name="💾 Cache",
                value=(
                    f"Entries: {cache_stats['valid_entries']:,}\n"
                    f"Size: {cache_stats['db_size_mb']} MB\n"
                    f"TTL: {cache_stats['ttl_seconds'] / 3600:.1f}h"
                ),
                inline=True
            )

            # Config info
            embed.add_field(
                name="⚙️ Configuration",
                value=(
                    f"Days Weight: {self.config.scoring_weights['days_in_server']:.0%}\n"
                    f"Activity Weight: {self.config.scoring_weights['message_count']:.0%}\n"
                    f"Min Messages: {self.config.min_messages}"
                ),
                inline=True
            )

            embed.set_footer(text=f"Bot ID: {self.bot.user.id}")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error getting bot info: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error getting bot info: {str(e)}",
                ephemeral=True
            )


async def setup(bot: commands.Bot, config: Config, cache: MessageCache):
    """
    Setup function for admin commands.

    Args:
        bot: Discord bot instance
        config: Configuration object
        cache: MessageCache instance
    """
    await bot.add_cog(AdminCommands(bot, config, cache))
