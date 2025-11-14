"""
Guild Events - Handle bot joining servers and auto-setup.
"""

import discord
from discord.ext import commands
import logging
from datetime import datetime

from src.utils.config import Config

logger = logging.getLogger(__name__)


class GuildEvents(commands.Cog):
    """Event handlers for guild-related events."""

    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """
        Automatically create admin channel when bot joins a server.

        Creates:
        - Admin-only ranking channel (#guild-rankings)
        - Sends welcome message to server owner
        - Logs the join event
        """
        try:
            logger.info(f"Bot joined new guild: {guild.name} (ID: {guild.id})")

            # Create admin channel with proper permissions
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
                    logger.info(f"Added admin role {role.name} to ranking channel permissions")

            # Create ranking channel
            ranking_channel = await guild.create_text_channel(
                name="guild-rankings",
                topic="📊 GuildScout Rankings - Automated ranking results and score breakdowns (Admin Only)",
                overwrites=overwrites
            )

            # Save to bot's ranking channels
            if not hasattr(self.bot, 'ranking_channels'):
                self.bot.ranking_channels = {}
            self.bot.ranking_channels[guild.id] = ranking_channel.id

            logger.info(f"Created ranking channel: #{ranking_channel.name} (ID: {ranking_channel.id})")

            # Send welcome message to ranking channel
            welcome_embed = discord.Embed(
                title="👋 Welcome to GuildScout!",
                description=(
                    "Thank you for adding GuildScout to your server!\n\n"
                    "**This is your dedicated admin-only ranking channel.**\n"
                    "Only administrators can see and use this channel.\n\n"
                    "GuildScout helps you fairly select guild members based on:\n"
                    "• **40%** Membership Duration (days in server)\n"
                    "• **60%** Activity (message count)\n"
                ),
                color=discord.Color.green(),
                timestamp=datetime.now()
            )

            welcome_embed.add_field(
                name="🚀 Quick Start Guide",
                value=(
                    "1. **Configure** your settings in `config/config.yaml`\n"
                    "2. **Set guild role** (the role to assign to selected members)\n"
                    "3. **Set max spots** (e.g., 50 total guild spots)\n"
                    "4. **Analyze** candidates: `/analyze role:@YourRole`\n"
                    "5. **Assign roles**: `/assign-guild-role ranking_role:@YourRole count:42`\n"
                ),
                inline=False
            )

            welcome_embed.add_field(
                name="📊 Available Commands",
                value=(
                    "**Analysis:**\n"
                    "• `/analyze` - Analyze and rank users by role\n"
                    "• `/guild-status` - View current guild members\n\n"
                    "**Management:**\n"
                    "• `/assign-guild-role` - Assign guild role to top N users\n"
                    "• `/set-max-spots` - Adjust maximum guild spots\n\n"
                    "**User Commands:**\n"
                    "• `/my-score` - Users can check their own ranking\n\n"
                    "**System:**\n"
                    "• `/bot-info` - Bot information and stats\n"
                    "• `/cache-stats` - Cache performance stats\n"
                    "• `/cache-clear` - Clear message cache\n"
                ),
                inline=False
            )

            welcome_embed.add_field(
                name="⚙️ Configuration",
                value=(
                    "Before using the bot, configure `config/config.yaml`:\n"
                    "```yaml\n"
                    "guild_management:\n"
                    "  max_spots: 50  # Total guild spots\n"
                    "  guild_role_id: YOUR_GUILD_ROLE_ID\n"
                    "```\n"
                    "See `config/config.example.yaml` for full options."
                ),
                inline=False
            )

            welcome_embed.add_field(
                name="🔒 Admin-Only",
                value=(
                    "All management commands require Administrator permissions.\n"
                    "Regular users can only use `/my-score` to check their own ranking."
                ),
                inline=False
            )

            welcome_embed.add_field(
                name="📖 Documentation",
                value=(
                    "• `WORKFLOW_GUIDE.md` - Complete workflow guide\n"
                    "• `GUILD_MANAGEMENT_GUIDE.md` - Guild management features\n"
                    "• `README.md` - Setup and installation\n"
                ),
                inline=False
            )

            welcome_embed.set_footer(text="GuildScout Bot - Fair & Transparent Rankings")

            await ranking_channel.send(embed=welcome_embed)

            # Try to send DM to server owner
            try:
                if guild.owner:
                    owner_embed = discord.Embed(
                        title="🎉 GuildScout Setup Complete!",
                        description=(
                            f"GuildScout has been successfully added to **{guild.name}**!\n\n"
                            f"An admin-only ranking channel has been created: {ranking_channel.mention}\n"
                            f"Check there for commands and setup instructions."
                        ),
                        color=discord.Color.green()
                    )
                    owner_embed.add_field(
                        name="⚙️ Next Steps",
                        value=(
                            f"1. Go to {ranking_channel.mention} in your server\n"
                            "2. Follow the Quick Start Guide\n"
                            "3. Configure `config/config.yaml` with your role IDs\n"
                            "4. Start analyzing and ranking members!"
                        ),
                        inline=False
                    )
                    await guild.owner.send(embed=owner_embed)
                    logger.info(f"Sent setup confirmation to server owner: {guild.owner.name}")
            except discord.Forbidden:
                logger.warning(f"Could not send DM to server owner: {guild.owner.name if guild.owner else 'Unknown'}")

            logger.info(f"Auto-setup completed for guild: {guild.name}")

        except discord.Forbidden:
            logger.error(f"Missing permissions to create channel in {guild.name} (ID: {guild.id})")
        except Exception as e:
            logger.error(f"Error during auto-setup for {guild.name}: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        """Log when bot is removed from a server."""
        logger.info(f"Bot removed from guild: {guild.name} (ID: {guild.id})")

        # Clean up stored ranking channel reference
        if hasattr(self.bot, 'ranking_channels') and guild.id in self.bot.ranking_channels:
            del self.bot.ranking_channels[guild.id]
            logger.info(f"Removed ranking channel reference for guild {guild.id}")


async def setup(bot: commands.Bot, config: Config):
    """Setup function to add this cog to the bot."""
    await bot.add_cog(GuildEvents(bot, config))
    logger.info("GuildEvents cog loaded")
