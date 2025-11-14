"""Main bot file for GuildScout Discord Bot."""

import logging
import discord
from discord.ext import commands
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import Config, setup_logger
from src.commands.analyze import setup as setup_analyze


class GuildScoutBot(commands.Bot):
    """Main GuildScout Bot class."""

    def __init__(self, config: Config, *args, **kwargs):
        """
        Initialize the GuildScout bot.

        Args:
            config: Configuration object
        """
        self.config = config
        self.logger = logging.getLogger("guildscout.bot")

        # Initialize bot with intents
        intents = discord.Intents.default()
        intents.members = True  # Required for member list
        intents.message_content = True  # Required for message counting

        super().__init__(
            command_prefix="!",  # Prefix for text commands (not used in slash commands)
            intents=intents,
            *args,
            **kwargs
        )

    async def setup_hook(self):
        """Setup hook called when bot is starting."""
        self.logger.info("Setting up bot...")

        # Load commands
        await setup_analyze(self, self.config)

        # Sync commands to guild
        try:
            guild = discord.Object(id=self.config.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            self.logger.info(f"Synced commands to guild {self.config.guild_id}")
        except Exception as e:
            self.logger.error(f"Failed to sync commands: {e}")

    async def on_ready(self):
        """Called when bot is ready."""
        self.logger.info(f"Bot is ready! Logged in as {self.user.name} ({self.user.id})")
        self.logger.info(f"Connected to {len(self.guilds)} guild(s)")

        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="guild activity | /analyze"
            )
        )

    async def on_command_error(self, ctx, error):
        """Handle command errors."""
        self.logger.error(f"Command error: {error}", exc_info=True)

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError
    ):
        """Handle application command errors."""
        self.logger.error(f"App command error: {error}", exc_info=True)

        if not interaction.response.is_done():
            await interaction.response.send_message(
                f"❌ An error occurred: {str(error)}",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"❌ An error occurred: {str(error)}",
                ephemeral=True
            )


def main():
    """Main entry point for the bot."""
    # Load configuration
    try:
        config = Config()
    except FileNotFoundError as e:
        print(f"❌ Configuration Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        sys.exit(1)

    # Setup logging
    logger = setup_logger(
        name="guildscout",
        level=config.log_level,
        log_file=config.log_file,
        log_format=config.log_format
    )

    logger.info("=" * 50)
    logger.info("GuildScout Bot Starting...")
    logger.info("=" * 50)

    # Create and run bot
    bot = GuildScoutBot(config)

    try:
        bot.run(config.discord_token)
    except discord.LoginFailure:
        logger.error("❌ Failed to login. Please check your bot token.")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
