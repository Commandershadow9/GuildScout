"""Discord API Rate Limit Event Tracking."""

import logging
from discord.ext import commands

from src.utils.rate_limit_monitor import get_monitor

logger = logging.getLogger("guildscout.rate_limits")


class RateLimitTracking(commands.Cog):
    """Tracks Discord API rate limits using bot events."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.monitor = get_monitor()
        logger.info("📊 Rate limit tracking enabled")

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context):
        """Track command invocation as an API request."""
        self.monitor.track_request()

    @commands.Cog.listener()
    async def on_message(self, message):
        """Track message events (potential API requests)."""
        # Only track if bot processes this message
        if not message.author.bot:
            self.monitor.track_request()

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        """Track channel updates."""
        self.monitor.track_request()

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Track member updates."""
        self.monitor.track_request()


async def setup(bot: commands.Bot):
    """Add rate limit tracking to the bot."""
    await bot.add_cog(RateLimitTracking(bot))
