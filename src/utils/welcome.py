"""Utilities to post and refresh the ranking channel welcome message."""

import logging
from datetime import datetime, timezone
from typing import Optional

import discord

from .config import Config

WELCOME_MESSAGE_VERSION = 3

logger = logging.getLogger("guildscout.welcome")


def build_welcome_embed(guild: discord.Guild, config: Config) -> discord.Embed:
    """Build the German welcome embed with usage instructions."""
    from ..analytics import RoleScanner

    role = guild.get_role(config.guild_role_id) if config.guild_role_id else None

    # Count ALL members with exclusion roles (guild role + leader role + etc.)
    scanner = RoleScanner(
        guild,
        exclusion_role_ids=config.exclusion_roles,
        exclusion_user_ids=config.exclusion_users
    )
    member_count = scanner.count_all_excluded_members()

    max_spots = config.max_guild_spots
    free_spots = max(max_spots - member_count, 0)

    embed = discord.Embed(
        title="📊 GuildScout Ranking-Kanal",
        description=(
            "Hier erscheinen automatisch alle Auswertungen von GuildScout.\n"
            "Die Bewertung kombiniert **40 %** Tage im Server und **60 %** Nachrichtenaktivität.\n"
            "Jede Analyse liefert ein Embed mit Scores plus eine CSV-Datei."
        ),
        color=discord.Color.blue(),
        timestamp=datetime.now(timezone.utc)
    )

    if role:
        embed.add_field(
            name="Aktuelle Belegung",
            value=(
                f"Rolle: {role.mention}\n"
                f"Mitglieder: **{member_count}** / {max_spots}\n"
                f"Freie Plätze: **{free_spots}**"
            ),
            inline=False
        )
    else:
        embed.add_field(
            name="Aktuelle Belegung",
            value="Keine Gildenrolle im Config-File hinterlegt (`guild_role_id`).",
            inline=False
        )

    embed.add_field(
        name="So funktioniert es",
        value=(
            "1. `/analyze role:@Rolle [days] [top_n]` – startet eine Auswertung.\n"
            "2. `/assign-guild-role ranking_role:@Rolle count:10` – vergibt die Gildenrolle an Top-Kandidaten.\n"
            "3. `/set-max-spots value:<Zahl>` – legt die verfügbaren Plätze fest.\n"
            "4. `/guild-status` – zeigt aktuelle Besetzung und Restplätze.\n"
            "5. `/my-score [role:@Rolle]` – Mitglieder prüfen ihren Score."
        ),
        inline=False
    )

    embed.add_field(
        name="Admin-Werkzeuge",
        value=(
            "• `/setup-ranking-channel` oder `/ranking-channel-info` – Kanal verwalten.\n"
            "• `/cache-stats` & `/cache-clear` – Cache prüfen oder leeren.\n"
            "• `/bot-info` – System- und Laufzeitinfos."
        ),
        inline=False
    )

    embed.add_field(
        name="Daten & Tracking",
        value=(
            "• `/import-status` – Import-Status, Mitglieder & Message-Counts.\n"
            "• `/import-messages [force]` – Historische Nachrichten einlesen.\n"
            "• `/message-store-stats` – Datenbankgröße & Coverage prüfen.\n"
            "• `/verify-message-counts [sample_size]` – Stichprobenkontrolle."
        ),
        inline=False
    )

    embed.set_footer(text="GuildScout – faire und transparente Auswahl")
    return embed


async def post_welcome_message(
    config: Config,
    channel: discord.TextChannel,
    *,
    previous_channel_id: Optional[int] = None,
    force: bool = False
) -> Optional[discord.Message]:
    """
    Delete the previous welcome message (if any) and post the latest version.

    Args:
        config: Bot configuration
        channel: Ranking channel where the message should appear
        previous_channel_id: Channel ID of the old welcome message (if different)
        force: Always repost, even if version already matches
    """
    # Avoid unnecessary reposts unless forced or version mismatch
    if (
        not force
        and config.ranking_channel_message_version == WELCOME_MESSAGE_VERSION
        and channel.id == config.ranking_channel_id
        and config.ranking_channel_message_id
    ):
        return None

    old_message_id = config.ranking_channel_message_id
    lookup_channel_id = previous_channel_id or config.ranking_channel_id

    if old_message_id and lookup_channel_id:
        target_channel = channel.guild.get_channel(lookup_channel_id)
        if target_channel:
            try:
                old_message = await target_channel.fetch_message(old_message_id)
                await old_message.delete()
                logger.info(
                    "Deleted previous welcome message %s in #%s",
                    old_message_id,
                    target_channel.name
                )
            except discord.NotFound:
                logger.info("Previous welcome message already removed.")
            except discord.Forbidden:
                logger.warning("Missing permissions to delete previous welcome message.")
            except Exception as exc:
                logger.error("Failed to delete previous welcome message: %s", exc, exc_info=True)

    embed = build_welcome_embed(channel.guild, config)
    message = await channel.send(embed=embed)
    config.set_ranking_channel_message_id(message.id)
    config.set_ranking_channel_message_version(WELCOME_MESSAGE_VERSION)
    logger.info("Posted welcome message %s in #%s", message.id, channel.name)

    # Pin the new welcome message and unpin old ones
    try:
        # Get all pinned messages
        pinned_messages = await channel.pins()

        # Unpin all old messages (except the one we just sent)
        for pinned_msg in pinned_messages:
            if pinned_msg.id != message.id:
                try:
                    await pinned_msg.unpin()
                    logger.info("Unpinned old message %s in #%s", pinned_msg.id, channel.name)
                except Exception as unpin_err:
                    logger.warning("Could not unpin message %s: %s", pinned_msg.id, unpin_err)

        # Pin the new welcome message
        await message.pin()
        logger.info("Pinned welcome message %s in #%s", message.id, channel.name)
    except discord.Forbidden:
        logger.warning("Missing permissions to pin/unpin messages in #%s", channel.name)
    except Exception as pin_err:
        logger.error("Failed to manage pins: %s", pin_err, exc_info=True)

    return message


async def refresh_welcome_message(
    config: Config,
    guild: discord.Guild,
    *,
    force: bool = False
) -> Optional[discord.Message]:
    """
    Refresh the ranking channel welcome message if possible.

    NOTE: This function is now a no-op. The combined dashboard in DashboardManager
    automatically handles welcome content updates. Keeping this function for
    backwards compatibility with existing code.
    """
    # Dashboard now handles all ranking channel content
    # No need to create/update separate welcome messages
    logger.info(f"Welcome refresh skipped - dashboard handles all content in {guild.name}")
    return None
