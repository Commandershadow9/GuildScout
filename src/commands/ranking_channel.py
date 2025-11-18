"""Ranking channel management for persistent ranking posts."""

import logging
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from datetime import datetime

from ..utils import Config


logger = logging.getLogger("guildscout.commands.ranking_channel")


class RankingChannelCommands(commands.Cog):
    """Cog for ranking channel management."""

    def __init__(self, bot: commands.Bot, config: Config):
        """
        Initialize ranking channel commands.

        Args:
            bot: Discord bot instance
            config: Configuration object
        """
        self.bot = bot
        self.config = config

    def _has_permission(self, interaction: discord.Interaction) -> bool:
        """Check if user has admin permission."""
        if interaction.user.id in self.config.admin_users:
            return True

        if hasattr(interaction.user, 'roles'):
            user_role_ids = [role.id for role in interaction.user.roles]
            for admin_role_id in self.config.admin_roles:
                if admin_role_id in user_role_ids:
                    return True

        return False

    @app_commands.command(
        name="setup-ranking-channel",
        description="[Admin] Create or set a dedicated channel for ranking posts"
    )
    @app_commands.describe(
        channel="The channel to use for rankings (creates new if not specified)"
    )
    async def setup_ranking_channel(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None
    ):
        """
        Set up a dedicated ranking channel.

        Args:
            interaction: Discord interaction
            channel: Optional existing channel to use
        """
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
            guild = interaction.guild

            # Use existing channel or create new
            if channel:
                ranking_channel = channel
                created = False
            else:
                # Create new channel
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(
                        read_messages=False
                    ),
                    guild.me: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        embed_links=True,
                        attach_files=True
                    )
                }

                # Add admin roles to overwrites
                for role_id in self.config.admin_roles:
                    role = guild.get_role(role_id)
                    if role:
                        overwrites[role] = discord.PermissionOverwrite(
                            read_messages=True,
                            send_messages=True
                        )

                ranking_channel = await guild.create_text_channel(
                    name="guild-rankings",
                    topic="📊 GuildScout Rankings - Automated ranking results and score breakdowns",
                    overwrites=overwrites
                )
                created = True

            previous_channel_id = self.config.ranking_channel_id

            await post_welcome_message(
                self.config,
                ranking_channel,
                previous_channel_id=previous_channel_id,
                force=True
            )

            if not hasattr(self.bot, 'ranking_channels'):
                self.bot.ranking_channels = {}

            self.bot.ranking_channels[guild.id] = ranking_channel.id
            self.config.set_ranking_channel_id(ranking_channel.id)

            # Send setup confirmation
            embed = discord.Embed(
                title="✅ Ranking Channel Configured",
                description=f"Rankings will now be posted to {ranking_channel.mention}",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )

            if created:
                embed.add_field(
                    name="📢 Channel Created",
                    value=(
                        f"Channel: {ranking_channel.mention}\n"
                        f"Permissions: Admin-only visibility\n"
                        f"Auto-post: Enabled"
                    ),
                    inline=False
                )
            else:
                embed.add_field(
                    name="📢 Channel Set",
                    value=(
                        f"Channel: {ranking_channel.mention}\n"
                        f"Auto-post: Enabled\n"
                        f"⚠️ Make sure bot has permissions to post here"
                    ),
                    inline=False
                )

            embed.add_field(
                name="🎯 Next Steps",
                value=(
                    "1. Run `/analyze role:@YourRole` to create rankings\n"
                    "2. Results will be posted in this channel automatically\n"
                    "3. Detailed score breakdowns will be included\n"
                    "4. CSV file will be attached for full data"
                ),
                inline=False
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(
                f"Ranking channel configured by {interaction.user.name}: "
                f"{ranking_channel.name} (ID: {ranking_channel.id})"
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Missing permissions to create/configure channel. "
                "Bot needs 'Manage Channels' permission.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error setting up ranking channel: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error setting up ranking channel: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(
        name="ranking-channel-info",
        description="[Admin] Show current ranking channel configuration"
    )
    async def ranking_channel_info(self, interaction: discord.Interaction):
        """Show ranking channel configuration."""
        if not self._has_permission(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return

        guild = interaction.guild

        if not hasattr(self.bot, 'ranking_channels') or guild.id not in self.bot.ranking_channels:
            await interaction.response.send_message(
                "❌ No ranking channel configured.\n"
                "Use `/setup-ranking-channel` to set one up!",
                ephemeral=True
            )
            return

        channel_id = self.bot.ranking_channels[guild.id]
        channel = guild.get_channel(channel_id)

        if not channel:
            await interaction.response.send_message(
                "⚠️ Ranking channel was deleted.\n"
                "Use `/setup-ranking-channel` to set up a new one!",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📊 Ranking Channel Configuration",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        embed.add_field(
            name="Channel",
            value=f"{channel.mention}\n`#{channel.name}` (ID: {channel.id})",
            inline=False
        )

        embed.add_field(
            name="Status",
            value="✅ Active - Rankings will auto-post here",
            inline=False
        )

        embed.add_field(
            name="Permissions",
            value=(
                f"Bot can post: {'✅' if channel.permissions_for(guild.me).send_messages else '❌'}\n"
                f"Bot can embed: {'✅' if channel.permissions_for(guild.me).embed_links else '❌'}\n"
                f"Bot can attach files: {'✅' if channel.permissions_for(guild.me).attach_files else '❌'}"
            ),
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot, config: Config):
    """
    Setup function for ranking channel commands.

    Args:
        bot: Discord bot instance
        config: Configuration object
    """
    await bot.add_cog(RankingChannelCommands(bot, config))
