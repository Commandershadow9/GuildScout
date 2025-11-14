"""
Where Winds Meet Release Timer Command
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timezone
import logging

from src.utils.config import Config

logger = logging.getLogger(__name__)

# Release date: November 14, 2025 at 22:00 GMT (10 PM UK Time)
RELEASE_DATE = datetime(2025, 11, 14, 22, 0, 0, tzinfo=timezone.utc)


class WWMTimerCommand(commands.Cog):
    """Where Winds Meet Release Countdown Timer"""

    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config
        self.timer_channel_id = None
        self.timer_message_id = None
        # Start auto-setup task
        self.bot.loop.create_task(self._auto_setup_timer())
        # Start update loop
        self.update_timer.start()

    async def cog_load(self):
        """Called when cog is loaded - auto-setup timer"""
        logger.info("WWM Timer cog loaded, will auto-setup timer on ready")

    def cog_unload(self):
        """Stop the timer when cog is unloaded"""
        self.update_timer.cancel()

    async def _auto_setup_timer(self):
        """Automatically setup timer on bot ready"""
        try:
            # Wait for bot to be ready
            await self.bot.wait_until_ready()

            # Get the guild
            guild = self.bot.get_guild(self.config.guild_id)
            if not guild:
                logger.error("Could not find guild for WWM timer auto-setup")
                return

            # Check if channel already exists
            existing_channel = discord.utils.get(guild.text_channels, name="where-winds-meet-countdown")

            if existing_channel:
                channel = existing_channel
                logger.info(f"Found existing WWM timer channel: {channel.name}")

                # Try to find and update existing message
                async for message in channel.history(limit=50):
                    if message.author.id == self.bot.user.id and message.embeds:
                        # Found our timer message
                        self.timer_channel_id = channel.id
                        self.timer_message_id = message.id
                        logger.info(f"Found existing timer message (ID: {message.id}), will update it")
                        return

                # No message found, create new one
                logger.info("No timer message found in channel, creating new one")
            else:
                # Create channel
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=False
                    ),
                    guild.me: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        embed_links=True,
                        manage_messages=True
                    )
                }

                channel = await guild.create_text_channel(
                    name="where-winds-meet-countdown",
                    topic="🎮 Where Winds Meet Global Release Countdown Timer",
                    overwrites=overwrites
                )
                logger.info(f"Created WWM timer channel: {channel.name}")

            # Create initial message
            self.timer_channel_id = channel.id
            embed = self._create_countdown_embed()
            message = await channel.send(embed=embed)
            await message.pin()
            self.timer_message_id = message.id
            logger.info(f"Auto-setup complete! Timer message created (ID: {message.id})")

        except Exception as e:
            logger.error(f"Error in auto-setup timer: {e}", exc_info=True)

    @app_commands.command(
        name="setup-wwm-timer",
        description="[Admin] Setup Where Winds Meet release countdown timer"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_timer(self, interaction: discord.Interaction):
        """Setup the countdown timer channel and message"""
        await interaction.response.defer(ephemeral=True)

        try:
            guild = interaction.guild

            # Check if channel already exists
            existing_channel = discord.utils.get(guild.text_channels, name="where-winds-meet-countdown")

            if existing_channel:
                # Use existing channel and update/replace old message
                channel = existing_channel
                logger.info(f"Using existing WWM timer channel: {channel.name} (ID: {channel.id})")

                # Try to delete old timer message if it exists
                if self.timer_message_id:
                    try:
                        old_message = await channel.fetch_message(self.timer_message_id)
                        await old_message.delete()
                        logger.info(f"Deleted old timer message (ID: {self.timer_message_id})")
                    except discord.NotFound:
                        logger.info("Old timer message not found, continuing...")
                    except Exception as e:
                        logger.warning(f"Could not delete old timer message: {e}")
            else:
                # Create channel visible to everyone
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=False  # Read-only for members
                    ),
                    guild.me: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        embed_links=True,
                        manage_messages=True
                    )
                }

                # Create the channel
                channel = await guild.create_text_channel(
                    name="where-winds-meet-countdown",
                    topic="🎮 Where Winds Meet Global Release Countdown Timer",
                    overwrites=overwrites
                )

                logger.info(f"Created WWM timer channel: {channel.name} (ID: {channel.id})")

            # Store channel ID
            self.timer_channel_id = channel.id

            # Create new countdown message with updated design
            embed = self._create_countdown_embed()
            message = await channel.send(embed=embed)

            # Pin the message
            await message.pin()

            # Store message ID
            self.timer_message_id = message.id

            logger.info(f"Created and pinned timer message (ID: {message.id})")

            await interaction.followup.send(
                f"✅ **Where Winds Meet Countdown Timer Updated!**\n\n"
                f"Channel: {channel.mention}\n"
                f"Timer will update automatically every minute with the new design! 🔥",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Missing permissions to create channel or pin messages.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error setting up WWM timer: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    def _create_countdown_embed(self) -> discord.Embed:
        """Create the countdown embed"""
        now = datetime.now(timezone.utc)
        time_left = RELEASE_DATE - now

        if time_left.total_seconds() <= 0:
            # Game is released!
            embed = discord.Embed(
                title="🎉 WHERE WINDS MEET IS OUT NOW! 🎉",
                description=(
                    "**THE WAIT IS OVER!**\n\n"
                    "⚔️ Where Winds Meet has officially launched! ⚔️\n\n"
                    "Jump into the world of martial arts and adventure!\n"
                    "Your journey through ancient China begins NOW!"
                ),
                color=discord.Color.gold(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_image(url="https://cdn.cloudflare.steamstatic.com/steam/apps/2134450/library_hero.jpg")
            embed.add_field(
                name="🔗 PLAY NOW",
                value="[🎮 **Launch on Steam**](https://store.steampowered.com/app/2134450/Where_Winds_Meet/)",
                inline=False
            )
            embed.set_footer(text="Have fun on your adventure! ⚔️🎮")
            return embed

        # Calculate time remaining
        days = time_left.days
        hours, remainder = divmod(time_left.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        # Dynamic hype text and color based on time left
        if days > 7:
            hype_title = "⚔️ **THE EPIC ADVENTURE AWAITS** ⚔️"
            hype_text = (
                "Prepare yourself for an **open-world martial arts masterpiece!**\n"
                "Explore ancient China, master legendary combat, and forge your destiny!\n\n"
                "*An epic journey through history and martial arts awaits you...*"
            )
            color = discord.Color.from_rgb(30, 144, 255)  # Dodger Blue
        elif days > 3:
            hype_title = "🔥 **LESS THAN A WEEK TO GO** 🔥"
            hype_text = (
                "The countdown is **ON!** Get ready to experience:\n"
                "• Breathtaking landscapes of ancient China\n"
                "• Intense martial arts combat system\n"
                "• An unforgettable open-world adventure!\n\n"
                "*The wait is almost over...*"
            )
            color = discord.Color.from_rgb(138, 43, 226)  # Blue Violet
        elif days > 1:
            hype_title = "⚡ **FINAL DAYS REMAINING** ⚡"
            hype_text = (
                "The release is **ALMOST HERE!**\n"
                "Sharpen your blades, prepare your PC, and get ready!\n\n"
                "This is going to be the **adventure of a lifetime!**\n"
                "*Are you ready to become a martial arts legend?*"
            )
            color = discord.Color.from_rgb(255, 140, 0)  # Dark Orange
        elif days == 1:
            hype_title = "🚨 **TOMORROW IS THE DAY** 🚨"
            hype_text = (
                "**ONE MORE DAY** until Where Winds Meet launches!\n\n"
                "The wait is almost over - the journey begins tomorrow!\n"
                "Make sure your PC is ready and Steam is updated!\n\n"
                "*See you in ancient China tomorrow!* ⚔️"
            )
            color = discord.Color.from_rgb(255, 69, 0)  # Red Orange
        elif hours > 1:
            hype_title = "🔴 **LAUNCH DAY - FINAL HOURS** 🔴"
            hype_text = (
                "**IT'S HAPPENING!**\n\n"
                "Just a few more hours until you can begin your journey!\n"
                "The martial arts adventure you've been waiting for is almost here!\n\n"
                "**GET HYPED!** 🔥"
            )
            color = discord.Color.from_rgb(220, 20, 60)  # Crimson
        else:
            hype_title = "⏰ **LAUNCHING VERY SOON** ⏰"
            hype_text = (
                "**THIS IS IT!** The game is about to launch!\n\n"
                "Refresh Steam and get ready to **PLAY!**\n"
                "Your adventure in ancient China begins in minutes!\n\n"
                "**LET'S GO!** 🚀"
            )
            color = discord.Color.from_rgb(178, 34, 34)  # Fire Brick

        embed = discord.Embed(
            title="🎮 **WHERE WINDS MEET - GLOBAL RELEASE** 🎮",
            description=f"{hype_title}\n\n{hype_text}",
            color=color,
            timestamp=datetime.now(timezone.utc)
        )

        # ═══════════════════════════════════════════════
        # COUNTDOWN TIMER - BIG AND CLEAR
        # ═══════════════════════════════════════════════

        if days > 0:
            # Show days, hours, minutes
            countdown_display = (
                f"```ansi\n"
                f"\n"
                f"╔══════════════════════════════════════╗\n"
                f"║                                      ║\n"
                f"║      {days:3d}d : {hours:02d}h : {minutes:02d}m : {seconds:02d}s      ║\n"
                f"║                                      ║\n"
                f"╚══════════════════════════════════════╝\n"
                f"\n"
                f"```"
            )
        elif hours > 0:
            # Show hours and minutes
            countdown_display = (
                f"```ansi\n"
                f"\n"
                f"╔══════════════════════════════════════╗\n"
                f"║                                      ║\n"
                f"║        {hours:02d}h : {minutes:02d}m : {seconds:02d}s        ║\n"
                f"║                                      ║\n"
                f"╚══════════════════════════════════════╝\n"
                f"\n"
                f"```"
            )
        else:
            # Final minutes - RED ALERT
            countdown_display = (
                f"```diff\n"
                f"\n"
                f"╔══════════════════════════════════════╗\n"
                f"║                                      ║\n"
                f"-         {minutes:02d}m : {seconds:02d}s REMAINING!         -\n"
                f"║                                      ║\n"
                f"╚══════════════════════════════════════╝\n"
                f"\n"
                f"```"
            )

        embed.add_field(
            name="⏱️ **TIME UNTIL LAUNCH**",
            value=countdown_display,
            inline=False
        )

        # ═══════════════════════════════════════════════
        # RELEASE INFORMATION
        # ═══════════════════════════════════════════════

        embed.add_field(
            name="📅 **RELEASE DATE**",
            value="**November 14, 2025**",
            inline=True
        )

        embed.add_field(
            name="🕐 **RELEASE TIME**",
            value=(
                "🇬🇧 **10:00 PM** GMT\n"
                "🇩🇪 **11:00 PM** MEZ"
            ),
            inline=True
        )

        embed.add_field(
            name="🎯 **PLATFORM**",
            value="**PC (Steam)**\nGlobal Release",
            inline=True
        )

        # ═══════════════════════════════════════════════
        # PROGRESS BAR
        # ═══════════════════════════════════════════════

        total_seconds_until_release = (RELEASE_DATE - datetime(2025, 11, 1, 0, 0, 0, tzinfo=timezone.utc)).total_seconds()
        seconds_passed = (now - datetime(2025, 11, 1, 0, 0, 0, tzinfo=timezone.utc)).total_seconds()
        progress = min(100, (seconds_passed / total_seconds_until_release) * 100)

        # Create smooth progress bar
        bar_length = 30
        filled = int(bar_length * progress / 100)
        bar = "█" * filled + "░" * (bar_length - filled)

        embed.add_field(
            name="",
            value=f"**PROGRESS TO LAUNCH**\n`{bar}` **{progress:.1f}%**",
            inline=False
        )

        embed.set_image(url="https://cdn.cloudflare.steamstatic.com/steam/apps/2134450/library_hero.jpg")

        embed.set_footer(text="Updates every 10 seconds • Get ready! 🎮")

        return embed

    @tasks.loop(seconds=10)
    async def update_timer(self):
        """Update the countdown timer every 10 seconds"""
        if not self.timer_channel_id or not self.timer_message_id:
            return

        try:
            channel = self.bot.get_channel(self.timer_channel_id)
            if not channel:
                logger.warning("WWM timer channel not found")
                return

            message = await channel.fetch_message(self.timer_message_id)
            if not message:
                logger.warning("WWM timer message not found")
                return

            # Update the embed
            embed = self._create_countdown_embed()
            await message.edit(embed=embed)

            logger.debug("Updated WWM countdown timer")

        except discord.NotFound:
            logger.warning("WWM timer message was deleted")
            self.timer_message_id = None
        except Exception as e:
            logger.error(f"Error updating WWM timer: {e}", exc_info=True)

    @update_timer.before_loop
    async def before_update_timer(self):
        """Wait until the bot is ready before starting the timer loop"""
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot, config: Config):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(WWMTimerCommand(bot, config))
    logger.info("WWMTimerCommand cog loaded")
