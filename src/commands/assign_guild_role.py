"""Guild role assignment command for assigning guild roles to top ranked users."""

import logging
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from ..analytics import RoleScanner, ActivityTracker, Scorer, Ranker
from ..utils import Config
from ..utils.welcome import refresh_welcome_message
from ..database import MessageCache


logger = logging.getLogger("guildscout.commands.assign_guild_role")


class AssignGuildRoleCommand(commands.Cog):
    """Cog for the /assign-guild-role command."""

    def __init__(self, bot: commands.Bot, config: Config, cache: MessageCache):
        """
        Initialize the assign guild role command.

        Args:
            bot: Discord bot instance
            config: Configuration object
            cache: MessageCache instance
        """
        self.bot = bot
        self.config = config
        self.cache = cache

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
        name="assign-guild-role",
        description="[Admin] Assign guild role to top N ranked users"
    )
    @app_commands.describe(
        ranking_role="The role that was analyzed (to get the ranking)",
        count="Number of top users to assign guild role to",
        score_cutoff="Optional: Only assign to users with score >= this value"
    )
    async def assign_guild_role(
        self,
        interaction: discord.Interaction,
        ranking_role: discord.Role,
        count: int,
        score_cutoff: Optional[float] = None
    ):
        """
        Assign guild role to top ranked users.

        Args:
            interaction: Discord interaction
            ranking_role: Role that was used for ranking
            count: Number of top users to assign
            score_cutoff: Optional minimum score requirement
        """
        # Check permissions
        if not self._has_permission(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return

        # Check if guild role is configured
        if not self.config.guild_role_id:
            await interaction.response.send_message(
                "❌ Guild role not configured!\n"
                "Please set `guild_management.guild_role_id` in config.yaml",
                ephemeral=True
            )
            return

        guild = interaction.guild
        guild_role = guild.get_role(self.config.guild_role_id)

        if not guild_role:
            await interaction.response.send_message(
                f"❌ Guild role with ID {self.config.guild_role_id} not found!",
                ephemeral=True
            )
            return

        # Check bot permissions BEFORE attempting role assignment
        bot_member = guild.me

        # Check 1: Does bot have "Manage Roles" permission?
        if not bot_member.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "❌ **Bot Permission Error**\n"
                f"Der Bot hat keine `Manage Roles` Berechtigung!\n\n"
                f"**Lösung:** Gib dem Bot die `Manage Roles` Permission in den Server-Einstellungen.",
                ephemeral=True
            )
            return

        # Check 2: Is guild_role BELOW bot's highest role? (Discord role hierarchy)
        bot_top_role = bot_member.top_role
        if guild_role.position >= bot_top_role.position:
            await interaction.response.send_message(
                "❌ **Role Hierarchy Error**\n"
                f"Die Guild-Rolle `@{guild_role.name}` (Position {guild_role.position}) ist ÜBER oder GLEICH "
                f"der Bot-Rolle `@{bot_top_role.name}` (Position {bot_top_role.position})!\n\n"
                f"**Lösung:** Verschiebe die Bot-Rolle in den Server-Einstellungen ÜBER die Guild-Rolle.\n"
                f"Discord erlaubt Bots nur, Rollen zu vergeben, die UNTER ihrer eigenen Rolle sind.",
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
            # Re-run analysis to get current ranking
            role_scanner = RoleScanner(
                guild,
                exclusion_role_ids=self.config.exclusion_roles,
                exclusion_user_ids=self.config.exclusion_users
            )
            activity_tracker = ActivityTracker(
                guild,
                excluded_channels=self.config.excluded_channels,
                excluded_channel_names=self.config.excluded_channel_names,
                cache=self.cache,
                message_store=getattr(self.bot, 'message_store', None)
            )
            scorer = Scorer(
                weight_days=self.config.scoring_weights["days_in_server"],
                weight_messages=self.config.scoring_weights["message_count"],
                weight_voice=self.config.scoring_weights.get("voice_activity", 0.2),
                min_messages=self.config.min_messages
            )

            # Get members and count messages
            members, excluded_members = await role_scanner.get_members_with_role(ranking_role)

            if not members:
                await interaction.followup.send(
                    "❌ No members found to rank!",
                    ephemeral=True
                )
                return

            message_counts, _ = await activity_tracker.count_messages_for_users(members)
            
            # Get voice stats
            voice_totals = await self.bot.message_store.get_guild_voice_totals(
                guild.id,
                days=self.config.max_days_lookback
            )

            scores = scorer.calculate_scores(members, message_counts, voice_counts=voice_totals)
            ranked_users = Ranker.rank_users(scores)

            # Filter by score cutoff if provided
            if score_cutoff is not None:
                ranked_users = [
                    (rank, score) for rank, score in ranked_users
                    if score.final_score >= score_cutoff
                ]

            # Limit to count
            selected_users = ranked_users[:count]

            if not selected_users:
                await interaction.followup.send(
                    "❌ No users match the criteria!",
                    ephemeral=True
                )
                return

            # Check spot availability
            # Count ALL members with exclusion roles (not just those with ranking role)
            spots_already_filled = role_scanner.count_all_excluded_members()
            spots_available = self.config.max_guild_spots - spots_already_filled

            if len(selected_users) > spots_available:
                await interaction.followup.send(
                    f"⚠️ **Warning**: You're trying to assign {len(selected_users)} spots, "
                    f"but only {spots_available} are available!\n\n"
                    f"Total spots: {self.config.max_guild_spots}\n"
                    f"Already filled: {spots_already_filled}\n"
                    f"Available: {spots_available}\n\n"
                    f"Please reduce the count or use `/cache-clear` to update reserved spots.",
                    ephemeral=True
                )
                return

            # Create preview embed
            preview_embed = discord.Embed(
                title="⚠️ Confirm Guild Role Assignment",
                description=(
                    f"You are about to assign **@{guild_role.name}** to the following {len(selected_users)} users:\n\n"
                    f"**Score cutoff:** {score_cutoff if score_cutoff else 'None (Top ' + str(count) + ')'}\n"
                    f"**Spots remaining after:** {spots_available - len(selected_users)}/{self.config.max_guild_spots}"
                ),
                color=discord.Color.orange()
            )

            preview_list = []
            for rank, score in selected_users[:10]:  # Show first 10
                preview_list.append(
                    f"`#{rank:02d}` **{score.display_name}** - Score: {score.final_score}"
                )

            preview_embed.add_field(
                name=f"Selected Users (showing {min(10, len(selected_users))} of {len(selected_users)})",
                value="\n".join(preview_list),
                inline=False
            )

            if len(selected_users) > 10:
                preview_embed.set_footer(text=f"+ {len(selected_users) - 10} more users...")

            # Create confirmation view
            view = ConfirmView(self, selected_users, guild_role, interaction.user)

            await interaction.followup.send(
                embed=preview_embed,
                view=view,
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error in assign-guild-role command: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    async def execute_assignment(
        self,
        interaction: discord.Interaction,
        selected_users: list,
        guild_role: discord.Role
    ):
        """Execute the actual role assignment."""
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.errors.NotFound:
            logger.warning(f"Interaction expired - bot may have been reconnecting")
            return
        except Exception as e:
            logger.error(f"Error during defer: {e}", exc_info=True)
            return

        success_count = 0
        fail_count = 0
        failed_users = []

        for rank, score in selected_users:
            try:
                member = interaction.guild.get_member(score.user_id)
                if member:
                    await member.add_roles(guild_role, reason="Guild selection via GuildScout")
                    success_count += 1
                    logger.info(f"Assigned @{guild_role.name} to {member.name}")
                else:
                    fail_count += 1
                    failed_users.append(score.display_name)
            except Exception as e:
                fail_count += 1
                failed_users.append(f"{score.display_name} (Error: {str(e)})")
                logger.error(f"Failed to assign role to {score.display_name}: {e}")

        # Send result
        result_embed = discord.Embed(
            title="✅ Guild Role Assignment Complete",
            description=(
                f"Successfully assigned **@{guild_role.name}** to {success_count} users!"
            ),
            color=discord.Color.green()
        )

        result_embed.add_field(
            name="Results",
            value=(
                f"✅ Success: {success_count}\n"
                f"❌ Failed: {fail_count}"
            ),
            inline=False
        )

        if failed_users:
            result_embed.add_field(
                name="Failed Users",
                value="\n".join(failed_users[:10]),  # Show first 10
                inline=False
            )

        await interaction.followup.send(embed=result_embed, ephemeral=True)

        # Refresh ranking overview with new counts
        await refresh_welcome_message(self.config, interaction.guild, force=True)


class ConfirmView(discord.ui.View):
    """Confirmation view for role assignment."""

    def __init__(self, cog, selected_users, guild_role, requester):
        super().__init__(timeout=60)
        self.cog = cog
        self.selected_users = selected_users
        self.guild_role = guild_role
        self.requester = requester

    @discord.ui.button(label="✅ Confirm & Assign Roles", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Verify requester
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message(
                "❌ Only the person who initiated this can confirm!",
                ephemeral=True
            )
            return

        # Disable buttons
        for item in self.children:
            item.disabled = True

        await interaction.message.edit(view=self)

        # Execute assignment
        await self.cog.execute_assignment(interaction, self.selected_users, self.guild_role)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Verify requester
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message(
                "❌ Only the person who initiated this can cancel!",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "❌ Role assignment cancelled.",
            ephemeral=True
        )

        # Disable buttons
        for item in self.children:
            item.disabled = True

        await interaction.message.edit(view=self)


async def setup(bot: commands.Bot, config: Config, cache: MessageCache):
    """
    Setup function for the assign guild role command.

    Args:
        bot: Discord bot instance
        config: Configuration object
        cache: MessageCache instance
    """
    await bot.add_cog(AssignGuildRoleCommand(bot, config, cache))
