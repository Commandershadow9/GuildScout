"""
Set Max Spots Command - Adjust the maximum number of guild spots.
"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
import yaml
from pathlib import Path

from src.utils.config import Config
from src.utils.welcome import refresh_welcome_message

logger = logging.getLogger(__name__)


class SetMaxSpotsCommand(commands.Cog):
    """Command for adjusting maximum guild spots."""

    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config

    @app_commands.command(
        name="set-max-spots",
        description="[Admin] Set the maximum number of guild spots"
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        count="New maximum number of guild spots (must be positive)"
    )
    async def set_max_spots(
        self,
        interaction: discord.Interaction,
        count: int
    ):
        """
        Adjust the maximum number of guild spots.

        Args:
            count: New maximum number of spots (must be > 0)

        This command updates the config.yaml file and immediately applies the new limit.
        If the new limit is lower than currently filled spots, you'll receive a warning.
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
            # Validate input
            if count <= 0:
                await interaction.followup.send(
                    "❌ **Invalid Input**: Maximum spots must be a positive number (greater than 0).",
                    ephemeral=True
                )
                return

            # Get current guild members with the role
            guild = interaction.guild
            guild_role_id = self.config.guild_role_id
            current_max = self.config.max_guild_spots

            # Count currently filled spots
            filled_spots = 0
            if guild_role_id:
                guild_role = guild.get_role(guild_role_id)
                if guild_role:
                    filled_spots = len([m for m in guild.members if guild_role in m.roles and not m.bot])

            # Warning if new limit is lower than filled spots
            if count < filled_spots:
                warning_embed = discord.Embed(
                    title="⚠️ Warning: New Limit Below Current Usage",
                    description=(
                        f"You're setting the maximum to **{count}** spots, but **{filled_spots}** spots are already filled.\n\n"
                        f"This will not remove existing members, but you won't be able to assign new spots until "
                        f"the count drops below {count}."
                    ),
                    color=discord.Color.orange()
                )
                warning_embed.add_field(
                    name="Current Status",
                    value=(
                        f"**Current Max:** {current_max}\n"
                        f"**New Max:** {count}\n"
                        f"**Currently Filled:** {filled_spots}\n"
                        f"**Overage:** {filled_spots - count} spots"
                    )
                )
                await interaction.followup.send(embed=warning_embed)

            # Update config file
            config_path = Path("config/config.yaml")
            if not config_path.exists():
                await interaction.followup.send(
                    "❌ **Error**: Config file not found at `config/config.yaml`.",
                    ephemeral=True
                )
                return

            # Read current config
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}

            # Update max_spots
            if 'guild_management' not in config_data:
                config_data['guild_management'] = {}

            old_value = config_data['guild_management'].get('max_spots', current_max)
            config_data['guild_management']['max_spots'] = count

            # Write updated config
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

            # Reload config in bot
            self.config.reload()

            # Refresh overview
            await refresh_welcome_message(self.config, guild, force=True)

            # Success message
            embed = discord.Embed(
                title="✅ Maximum Spots Updated",
                description=f"Guild spot limit has been successfully updated.",
                color=discord.Color.green()
            )

            embed.add_field(
                name="Previous Maximum",
                value=f"{old_value} spots",
                inline=True
            )

            embed.add_field(
                name="New Maximum",
                value=f"**{count} spots**",
                inline=True
            )

            embed.add_field(
                name="Currently Filled",
                value=f"{filled_spots} spots",
                inline=True
            )

            available = max(0, count - filled_spots)
            embed.add_field(
                name="Available Spots",
                value=f"**{available}** spots available for new assignments",
                inline=False
            )

            embed.set_footer(text=f"Updated by {interaction.user.name}")

            await interaction.followup.send(embed=embed)

            logger.info(
                f"Max guild spots updated by {interaction.user.name}: {old_value} -> {count} "
                f"(filled: {filled_spots})"
            )

        except yaml.YAMLError as e:
            logger.error(f"YAML error while updating config: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ **Configuration Error**: Failed to update config file.\n```{str(e)}```",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in set_max_spots command: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ **Error**: An unexpected error occurred: {str(e)}",
                ephemeral=True
            )

    @set_max_spots.error
    async def set_max_spots_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Error handler for set_max_spots command."""
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message(
                "❌ **Permission Denied**: This command requires Administrator permissions.",
                ephemeral=True
            )
        else:
            logger.error(f"Error in set_max_spots command: {error}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"❌ **Error**: {str(error)}",
                    ephemeral=True
                )


async def setup(bot: commands.Bot, config: Config):
    """Setup function to add this cog to the bot."""
    await bot.add_cog(SetMaxSpotsCommand(bot, config))
    logger.info("SetMaxSpotsCommand cog loaded")
