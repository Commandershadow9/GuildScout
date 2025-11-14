"""Commands to manage the Discord log channel."""

import logging
from typing import Optional
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from ..utils import Config

logger = logging.getLogger("guildscout.commands.log_channel")


class LogChannelCommands(commands.Cog):
    """Cog providing admin commands for the log channel."""

    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config

    def _has_permission(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id in self.config.admin_users:
            return True

        if hasattr(interaction.user, "roles"):
            role_ids = [role.id for role in interaction.user.roles]
            for admin_role_id in self.config.admin_roles:
                if admin_role_id in role_ids:
                    return True
        return False

    @app_commands.command(
        name="setup-log-channel",
        description="[Admin] Create or assign the GuildScout log channel"
    )
    @app_commands.describe(
        channel="Existing text channel to use (leave empty to create a new one)"
    )
    async def setup_log_channel(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None
    ):
        if not self._has_permission(interaction):
            await interaction.response.send_message(
                "❌ Du darfst diesen Befehl nicht verwenden.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild

        try:
            created = False
            if channel:
                log_channel = channel
            else:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    guild.me: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        embed_links=True,
                        attach_files=True
                    )
                }
                for role_id in self.config.admin_roles:
                    role = guild.get_role(role_id)
                    if role:
                        overwrites[role] = discord.PermissionOverwrite(
                            read_messages=True,
                            send_messages=True
                        )
                log_channel = await guild.create_text_channel(
                    name="guildscout-logs",
                    topic="🧾 GuildScout Logs – Analysen und Systemereignisse",
                    overwrites=overwrites
                )
                created = True

            if not hasattr(self.bot, "log_channels"):
                self.bot.log_channels = {}
            self.bot.log_channels[guild.id] = log_channel.id
            self.config.set_log_channel_id(log_channel.id)

            await self._post_intro(log_channel)

            embed = discord.Embed(
                title="✅ Log-Channel konfiguriert",
                description=f"Logeinträge erscheinen jetzt in {log_channel.mention}",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(
                name="Channel",
                value=f"{log_channel.mention} — `#{log_channel.name}`",
                inline=False
            )
            embed.add_field(
                name="Status",
                value="📜 Analyse- und Systemlogs werden hier gepostet",
                inline=False
            )
            if created:
                embed.add_field(
                    name="Hinweis",
                    value="Der Channel ist nur für Admins sichtbar.",
                    inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(
                "Log channel configured by %s: #%s (%s)",
                interaction.user.name,
                log_channel.name,
                log_channel.id
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Mir fehlen Rechte, um den Kanal zu verwalten.",
                ephemeral=True
            )
        except Exception as exc:
            logger.error("Error configuring log channel: %s", exc, exc_info=True)
            await interaction.followup.send(
                f"❌ Fehler beim Einrichten: {exc}",
                ephemeral=True
            )

    @app_commands.command(
        name="log-channel-info",
        description="[Admin] Zeigt den aktuellen Log-Channel"
    )
    async def log_channel_info(self, interaction: discord.Interaction):
        if not self._has_permission(interaction):
            await interaction.response.send_message(
                "❌ Du darfst diesen Befehl nicht verwenden.",
                ephemeral=True
            )
            return

        guild = interaction.guild
        channel_id = self.config.log_channel_id
        if not channel_id:
            await interaction.response.send_message(
                "⚠️ Kein Log-Channel konfiguriert. Nutze `/setup-log-channel`.",
                ephemeral=True
            )
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message(
                "⚠️ Der hinterlegte Log-Channel existiert nicht mehr. Bitte neu setzen.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🧾 Log-Channel",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="Channel",
            value=f"{channel.mention}\n`#{channel.name}` (ID: {channel.id})",
            inline=False
        )
        perms = channel.permissions_for(guild.me)
        embed.add_field(
            name="Berechtigungen",
            value=(
                f"Senden: {'✅' if perms.send_messages else '❌'}\n"
                f"Embeds: {'✅' if perms.embed_links else '❌'}\n"
                f"Dateien: {'✅' if perms.attach_files else '❌'}"
            ),
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _post_intro(self, channel: discord.TextChannel) -> None:
        embed = discord.Embed(
            title="🧾 GuildScout Logs",
            description=(
                "Hier landen wichtige Ereignisse: Analyse-Starts, Abschlüsse und Fehler.") ,
            color=discord.Color.dark_gold(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="Beispiele",
            value=(
                "• Start/Ende einer `/analyze`-Auswertung\n"
                "• Fehlermeldungen oder Warnungen\n"
                "• Cache-Hinweise"
            ),
            inline=False
        )
        embed.set_footer(text="GuildScout – Monitoring")
        await channel.send(embed=embed)


async def setup(bot: commands.Bot, config: Config):
    await bot.add_cog(LogChannelCommands(bot, config))
    logger.info("LogChannelCommands loaded")
