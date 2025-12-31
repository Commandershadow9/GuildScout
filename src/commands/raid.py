"""Raid scheduling commands."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
import csv
import io
from typing import Dict, Optional
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from src.database.raid_store import RaidStore
from src.utils.config import Config
from src.utils.raid_utils import (
    ROLE_BENCH,
    ROLE_CANCEL,
    ROLE_DPS,
    ROLE_HEALER,
    ROLE_TANK,
    ROLE_EMOJIS,
    build_raid_embed,
    parse_raid_datetime,
)


logger = logging.getLogger("guildscout.commands.raid")

DEFAULT_COUNTS = {
    ROLE_TANK: 2,
    ROLE_HEALER: 2,
    ROLE_DPS: 6,
    ROLE_BENCH: 0,
}

SLOT_TEMPLATES = [
    ("Standard", {ROLE_TANK: 2, ROLE_HEALER: 2, ROLE_DPS: 6, ROLE_BENCH: 0}),
    ("Klein", {ROLE_TANK: 1, ROLE_HEALER: 1, ROLE_DPS: 3, ROLE_BENCH: 0}),
    ("Gross", {ROLE_TANK: 3, ROLE_HEALER: 3, ROLE_DPS: 9, ROLE_BENCH: 2}),
]

MAX_SLOT_OPTION = 20
DATE_RANGE_DAYS = 25
DATE_PAGE_STEP_DAYS = 7
MAX_DATE_OFFSET_DAYS = 365


def build_raid_info_embed() -> discord.Embed:
    """Return the raid info/start embed."""
    embed = discord.Embed(
        title="🗡️ Raid-Guide (Where Winds Meet)",
        description=(
            "Hier findest du die komplette Anleitung fuer Raids.\n"
            "Rollen: Tank, Healer, DPS + Reserve."
        ),
        color=discord.Color.green(),
    )
    embed.add_field(
        name="Raid erstellen (Ersteller/Admin)",
        value=(
            "1) Button 'Raid erstellen' klicken\n"
            "2) Titel + Beschreibung eingeben\n"
            "3) Datum/Uhrzeit ueber Dropdowns waehlen (Woche blaettern)\n"
            "4) Slots setzen oder Vorlage nutzen\n"
            "5) 'Raid posten' klicken"
        ),
        inline=False,
    )
    embed.add_field(
        name="Anmelden im Raid-Post",
        value=(
            "Reagiere mit: 🛡️ Tank, 💉 Healer, ⚔️ DPS, 🪑 Reserve\n"
            "❌ = Abmelden. Pro Person nur eine Rolle.\n"
            "Wenn Rolle voll ist, wirst du auf Reserve gesetzt (falls frei)."
        ),
        inline=False,
    )
    embed.add_field(
        name="Verwalten (Ersteller/Admin/Lead)",
        value=(
            "Buttons im Raid-Post: ✏️ Bearbeiten, 🔒 Sperren/Oeffnen,\n"
            "✅ Abschliessen, 🛑 Absagen, 📄 Export.\n"
            "Sperren = nur Reserve. Auto-Close zur Startzeit."
        ),
        inline=False,
    )
    embed.add_field(
        name="Teilnehmerrolle & Reminder",
        value=(
            "Beim Anmelden bekommst du die Teilnehmerrolle (falls gesetzt).\n"
            "Sie wird beim Verlassen oder nach Raid-Ende entfernt.\n"
            "Erinnerungen kommen z.B. 24h/1h vor Start."
        ),
        inline=False,
    )
    embed.add_field(
        name="Befehle",
        value=(
            "/raid-create – Raid erstellen (Alternative zum Button)\n"
            "/raid-list – kommende Raids anzeigen\n"
            "Admin: /raid-setup, /raid-set-channel, /raid-info-setup,\n"
            "/raid-add-creator-role, /raid-remove-creator-role,\n"
            "/raid-set-participant-role"
        ),
        inline=False,
    )
    return embed


class RoleCountSelect(discord.ui.Select):
    """Dropdown for selecting role counts."""

    def __init__(self, label: str, role_key: str, current_value: int, row: int):
        self.label_text = label
        options = [
            discord.SelectOption(label=str(value), value=str(value))
            for value in range(MAX_SLOT_OPTION + 1)
        ]
        super().__init__(
            placeholder=f"{label}: {current_value}",
            min_values=1,
            max_values=1,
            options=options,
            row=row,
        )
        self.role_key = role_key

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, RaidSlotsView):
            return
        selected = int(self.values[0])
        view.counts[self.role_key] = selected
        self.placeholder = f"{self.label_text}: {selected}"
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class RaidDateSelect(discord.ui.Select):
    """Dropdown for selecting the raid date."""

    def __init__(self, view: "RaidScheduleView"):
        options = view.build_date_options()
        super().__init__(
            placeholder=f"Datum: {view.date_value}",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, RaidScheduleView):
            return

        previous_date = view.date_value
        view.date_value = self.values[0]
        if not view.update_start_ts():
            view.date_value = previous_date
            view.update_select_defaults()
            await interaction.response.edit_message(embed=view.build_embed(), view=view)
            await interaction.followup.send(
                "❌ Startzeit liegt in der Vergangenheit.",
                ephemeral=True,
            )
            return

        view.update_select_defaults()
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class RaidHourSelect(discord.ui.Select):
    """Dropdown for selecting the raid hour."""

    def __init__(self, view: "RaidScheduleView"):
        options = [
            discord.SelectOption(
                label=f"{hour:02d}",
                value=str(hour),
                default=(hour == view.hour_value),
            )
            for hour in range(0, 24)
        ]

        super().__init__(
            placeholder=f"Stunde: {view.hour_value:02d}",
            min_values=1,
            max_values=1,
            options=options,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, RaidScheduleView):
            return

        previous_hour = view.hour_value
        view.hour_value = int(self.values[0])
        view.time_value = f"{view.hour_value:02d}:{view.minute_value:02d}"
        if not view.update_start_ts():
            view.hour_value = previous_hour
            view.time_value = f"{view.hour_value:02d}:{view.minute_value:02d}"
            view.update_select_defaults()
            await interaction.response.edit_message(embed=view.build_embed(), view=view)
            await interaction.followup.send(
                "❌ Startzeit liegt in der Vergangenheit.",
                ephemeral=True,
            )
            return

        view.update_select_defaults()
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class RaidMinuteSelect(discord.ui.Select):
    """Dropdown for selecting the raid minutes."""

    def __init__(self, view: "RaidScheduleView"):
        options = [
            discord.SelectOption(
                label=minute,
                value=minute,
                default=(int(minute) == view.minute_value),
            )
            for minute in ("00", "30")
        ]

        super().__init__(
            placeholder=f"Minute: {view.minute_value:02d}",
            min_values=1,
            max_values=1,
            options=options,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, RaidScheduleView):
            return

        previous_minute = view.minute_value
        view.minute_value = int(self.values[0])
        view.time_value = f"{view.hour_value:02d}:{view.minute_value:02d}"
        if not view.update_start_ts():
            view.minute_value = previous_minute
            view.time_value = f"{view.hour_value:02d}:{view.minute_value:02d}"
            view.update_select_defaults()
            await interaction.response.edit_message(embed=view.build_embed(), view=view)
            await interaction.followup.send(
                "❌ Startzeit liegt in der Vergangenheit.",
                ephemeral=True,
            )
            return

        view.update_select_defaults()
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class RaidScheduleView(discord.ui.View):
    """Pick date/time before choosing slot counts."""

    def __init__(
        self,
        bot: commands.Bot,
        config: Config,
        raid_store: RaidStore,
        requester_id: int,
        title: str,
        description: Optional[str],
        start_ts: int,
        timezone_name: str,
        date_value: str,
        time_value: str,
        counts: Optional[Dict[str, int]] = None,
        template_index: int = 0,
    ):
        super().__init__(timeout=600)
        self.bot = bot
        self.config = config
        self.raid_store = raid_store
        self.requester_id = requester_id
        self.title = title
        self.description = description
        self.start_ts = start_ts
        self.timezone_name = timezone_name
        self.date_value = date_value
        self.time_value = time_value
        self.template_index = template_index
        self.hour_value = 0
        self.minute_value = 0
        try:
            hour_str, minute_str = self.time_value.split(":", 1)
            self.hour_value = int(hour_str)
            self.minute_value = int(minute_str)
        except (ValueError, AttributeError):
            self.hour_value = 0
            self.minute_value = 0
        self.counts = counts or DEFAULT_COUNTS.copy()
        self.message: Optional[discord.Message] = None

        self.date_range_days = DATE_RANGE_DAYS
        self.date_offset_days = 0
        self.max_date_offset_days = MAX_DATE_OFFSET_DAYS
        self._sync_date_offset_with_selection()

        self.add_item(RaidDateSelect(self))
        self.add_item(RaidHourSelect(self))
        self.add_item(RaidMinuteSelect(self))

    def get_timezone(self) -> timezone:
        """Return the configured timezone for this raid."""
        try:
            return ZoneInfo(self.timezone_name)
        except Exception:
            return timezone.utc

    def update_start_ts(self) -> bool:
        """Update start timestamp from current date/time values."""
        try:
            dt = parse_raid_datetime(self.date_value, self.time_value, self.timezone_name)
        except ValueError:
            return False

        if int(dt.timestamp()) <= int(datetime.now(timezone.utc).timestamp()):
            return False

        self.start_ts = int(dt.timestamp())
        return True

    def _get_today(self):
        tz = self.get_timezone()
        return datetime.now(tz).date()

    def _parse_date_value(self) -> Optional[datetime]:
        try:
            return datetime.strptime(self.date_value, "%d.%m.%Y")
        except (ValueError, TypeError):
            return None

    def _sync_date_offset_with_selection(self) -> None:
        parsed = self._parse_date_value()
        if not parsed:
            self.date_offset_days = 0
            return

        today = self._get_today()
        diff = (parsed.date() - today).days
        if diff <= 0:
            self.date_offset_days = 0
            return

        diff = min(diff, self.max_date_offset_days)
        if diff <= self.date_range_days - 1:
            self.date_offset_days = 0
            return

        self.date_offset_days = max(0, diff - (self.date_range_days - 1))

    def build_date_options(self) -> list:
        today = self._get_today()
        start_date = today + timedelta(days=self.date_offset_days)
        weekday_labels = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        options = []
        selected_in_range = False

        for offset in range(self.date_range_days):
            date_obj = start_date + timedelta(days=offset)
            date_value = date_obj.strftime("%d.%m.%Y")
            label = f"{weekday_labels[date_obj.weekday()]} {date_value}"
            if date_value == self.date_value:
                selected_in_range = True
            options.append(
                discord.SelectOption(
                    label=label,
                    value=date_value,
                    default=(date_value == self.date_value),
                )
            )

        if not selected_in_range and options:
            self.date_value = options[0].value
            self.update_start_ts()
            for option in options:
                option.default = option.value == self.date_value

        return options

    def refresh_date_options(self) -> None:
        for item in self.children:
            if isinstance(item, RaidDateSelect):
                item.options = self.build_date_options()
                item.placeholder = f"Datum: {self.date_value}"

    def update_select_defaults(self) -> None:
        """Update select placeholders/defaults after changes."""
        for item in self.children:
            if isinstance(item, RaidDateSelect):
                item.placeholder = f"Datum: {self.date_value}"
                for option in item.options:
                    option.default = option.value == self.date_value
            elif isinstance(item, RaidHourSelect):
                item.placeholder = f"Stunde: {self.hour_value:02d}"
                for option in item.options:
                    option.default = option.value == str(self.hour_value)
            elif isinstance(item, RaidMinuteSelect):
                item.placeholder = f"Minute: {self.minute_value:02d}"
                for option in item.options:
                    option.default = option.value == f"{self.minute_value:02d}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "❌ Nur der Ersteller kann diesen Entwurf bearbeiten.",
                ephemeral=True,
            )
            return False
        return True

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"📝 Raid Entwurf: {self.title}",
            description=self.description or None,
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Startzeit",
            value=f"<t:{self.start_ts}:F>\n<t:{self.start_ts}:R>",
            inline=False,
        )
        embed.add_field(
            name="Slots",
            value="Im nächsten Schritt auswählen.",
            inline=False,
        )
        embed.set_footer(text="Datum/Uhrzeit wählen, dann 'Weiter' klicken.")
        return embed

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="➡️ Weiter", style=discord.ButtonStyle.green, row=4)
    async def continue_to_slots(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        if self.start_ts <= int(datetime.now(timezone.utc).timestamp()):
            await interaction.response.send_message(
                "❌ Startzeit liegt in der Vergangenheit.",
                ephemeral=True,
            )
            return

        next_view = RaidSlotsView(
            bot=self.bot,
            config=self.config,
            raid_store=self.raid_store,
            requester_id=self.requester_id,
            title=self.title,
            description=self.description,
            start_ts=self.start_ts,
            timezone_name=self.timezone_name,
            date_value=self.date_value,
            time_value=self.time_value,
            counts=self.counts,
            template_index=self.template_index,
        )
        await interaction.response.edit_message(
            embed=next_view.build_embed(),
            view=next_view,
        )
        next_view.message = interaction.message
        self.stop()

    @discord.ui.button(label="◀️ Woche zurück", style=discord.ButtonStyle.secondary, row=3)
    async def prev_week(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if self.date_offset_days <= 0:
            await interaction.response.send_message(
                "ℹ️ Du bist bereits am Anfang.",
                ephemeral=True,
            )
            return

        self.date_offset_days = max(0, self.date_offset_days - DATE_PAGE_STEP_DAYS)
        self.refresh_date_options()
        self.update_select_defaults()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="▶️ Woche weiter", style=discord.ButtonStyle.secondary, row=3)
    async def next_week(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if self.date_offset_days >= self.max_date_offset_days:
            await interaction.response.send_message(
                "ℹ️ Weiter geht aktuell nicht.",
                ephemeral=True,
            )
            return

        self.date_offset_days = min(
            self.max_date_offset_days, self.date_offset_days + DATE_PAGE_STEP_DAYS
        )
        self.refresh_date_options()
        self.update_select_defaults()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="✏️ Titel/Beschreibung", style=discord.ButtonStyle.secondary, row=3)
    async def edit_details(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(RaidEditModal(self))

    @discord.ui.button(label="❌ Abbrechen", style=discord.ButtonStyle.red, row=4)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for item in self.children:
            item.disabled = True
        self.stop()
        await interaction.response.edit_message(
            content="❌ Raid-Erstellung abgebrochen.",
            embed=None,
            view=self,
        )


class RaidSlotsView(discord.ui.View):
    """Select slot counts and post the raid."""

    def __init__(
        self,
        bot: commands.Bot,
        config: Config,
        raid_store: RaidStore,
        requester_id: int,
        title: str,
        description: Optional[str],
        start_ts: int,
        timezone_name: str,
        date_value: str,
        time_value: str,
        counts: Optional[Dict[str, int]] = None,
        template_index: int = 0,
    ):
        super().__init__(timeout=600)
        self.bot = bot
        self.config = config
        self.raid_store = raid_store
        self.requester_id = requester_id
        self.title = title
        self.description = description
        self.start_ts = start_ts
        self.timezone_name = timezone_name
        self.date_value = date_value
        self.time_value = time_value
        self.counts = counts or DEFAULT_COUNTS.copy()
        self.template_index = template_index
        self.message: Optional[discord.Message] = None

        self.add_item(RoleCountSelect("Tanks", ROLE_TANK, self.counts[ROLE_TANK], row=0))
        self.add_item(RoleCountSelect("Healer", ROLE_HEALER, self.counts[ROLE_HEALER], row=1))
        self.add_item(RoleCountSelect("DPS", ROLE_DPS, self.counts[ROLE_DPS], row=2))
        self.add_item(RoleCountSelect("Reserve", ROLE_BENCH, self.counts[ROLE_BENCH], row=3))

    def _get_template_label(self) -> str:
        for idx, (name, template) in enumerate(SLOT_TEMPLATES):
            if all(self.counts.get(role) == template.get(role) for role in DEFAULT_COUNTS):
                self.template_index = idx
                return name
        return "Custom"

    def _apply_template(self) -> str:
        name, template = SLOT_TEMPLATES[self.template_index]
        for role_key, value in template.items():
            self.counts[role_key] = value
        return name

    def _sync_select_placeholders(self) -> None:
        for item in self.children:
            if isinstance(item, RoleCountSelect):
                current = self.counts.get(item.role_key, 0)
                item.placeholder = f"{item.label_text}: {current}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "❌ Nur der Ersteller kann diesen Entwurf bearbeiten.",
                ephemeral=True,
            )
            return False
        return True

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"📝 Raid Entwurf: {self.title}",
            description=self.description or None,
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Startzeit",
            value=f"<t:{self.start_ts}:F>\n<t:{self.start_ts}:R>",
            inline=False,
        )
        embed.add_field(name="Tanks", value=str(self.counts[ROLE_TANK]), inline=True)
        embed.add_field(name="Healer", value=str(self.counts[ROLE_HEALER]), inline=True)
        embed.add_field(name="DPS", value=str(self.counts[ROLE_DPS]), inline=True)
        embed.add_field(name="Reserve", value=str(self.counts[ROLE_BENCH]), inline=True)
        template_label = self._get_template_label()
        embed.set_footer(
            text=f"Vorlage: {template_label} · Slots einstellen, dann 'Raid posten' klicken."
        )
        return embed

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="⬅️ Zurück", style=discord.ButtonStyle.secondary, row=4)
    async def back(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        back_view = RaidScheduleView(
            bot=self.bot,
            config=self.config,
            raid_store=self.raid_store,
            requester_id=self.requester_id,
            title=self.title,
            description=self.description,
            start_ts=self.start_ts,
            timezone_name=self.timezone_name,
            date_value=self.date_value,
            time_value=self.time_value,
            counts=self.counts,
            template_index=self.template_index,
        )
        await interaction.response.edit_message(
            embed=back_view.build_embed(),
            view=back_view,
        )
        back_view.message = interaction.message
        self.stop()

    @discord.ui.button(label="✏️ Titel/Beschreibung", style=discord.ButtonStyle.secondary, row=4)
    async def edit_details(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(RaidEditModal(self))

    @discord.ui.button(label="🧩 Vorlage wechseln", style=discord.ButtonStyle.secondary, row=4)
    async def cycle_template(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.template_index = (self.template_index + 1) % len(SLOT_TEMPLATES)
        self._apply_template()
        self._sync_select_placeholders()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="✅ Raid posten", style=discord.ButtonStyle.green, row=4)
    async def post_raid(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not self.config.raid_post_channel_id:
            await interaction.response.send_message(
                "❌ Kein Raid-Channel gesetzt. Nutze `/raid-setup` oder `/raid-set-channel`.",
                ephemeral=True,
            )
            return

        if self.start_ts <= int(datetime.now(timezone.utc).timestamp()):
            await interaction.response.send_message(
                "❌ Startzeit liegt in der Vergangenheit.",
                ephemeral=True,
            )
            return

        if self.counts[ROLE_TANK] + self.counts[ROLE_HEALER] + self.counts[ROLE_DPS] == 0:
            await interaction.response.send_message(
                "❌ Bitte mindestens einen Slot für Tank/Healer/DPS setzen.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("❌ Guild nicht gefunden.", ephemeral=True)
            return

        post_channel = guild.get_channel(self.config.raid_post_channel_id)
        if not isinstance(post_channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ Raid-Channel nicht gefunden. Bitte neu konfigurieren.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        raid_id = await self.raid_store.create_raid(
            guild_id=guild.id,
            channel_id=post_channel.id,
            creator_id=interaction.user.id,
            title=self.title,
            description=self.description,
            start_time=self.start_ts,
            tanks_needed=self.counts[ROLE_TANK],
            healers_needed=self.counts[ROLE_HEALER],
            dps_needed=self.counts[ROLE_DPS],
            bench_needed=self.counts[ROLE_BENCH],
        )

        raid = await self.raid_store.get_raid(raid_id)
        if not raid:
            await interaction.response.send_message(
                "❌ Raid konnte nicht gespeichert werden.",
                ephemeral=True,
            )
            return

        embed = build_raid_embed(raid, {}, self.config.raid_timezone)
        manage_view = RaidManageView(self.config, self.raid_store)
        raid_message = await post_channel.send(embed=embed, view=manage_view)
        await self.raid_store.set_message_id(raid_id, raid_message.id)

        for emoji, count in [
            (ROLE_EMOJIS[ROLE_TANK], self.counts[ROLE_TANK]),
            (ROLE_EMOJIS[ROLE_HEALER], self.counts[ROLE_HEALER]),
            (ROLE_EMOJIS[ROLE_DPS], self.counts[ROLE_DPS]),
            (ROLE_EMOJIS[ROLE_BENCH], self.counts[ROLE_BENCH]),
        ]:
            if count > 0:
                try:
                    await raid_message.add_reaction(emoji)
                except Exception:
                    logger.warning("Failed to add reaction %s", emoji, exc_info=True)

        try:
            await raid_message.add_reaction(ROLE_EMOJIS[ROLE_CANCEL])
        except Exception:
            logger.warning("Failed to add cancel reaction", exc_info=True)

        for item in self.children:
            item.disabled = True
        self.stop()

        success_embed = discord.Embed(
            title="✅ Raid erstellt",
            description=f"Raid wurde gepostet: {raid_message.jump_url}",
            color=discord.Color.green(),
        )
        try:
            await interaction.edit_original_response(embed=success_embed, view=self)
        except Exception:
            await interaction.followup.send(embed=success_embed, ephemeral=True)

    @discord.ui.button(label="❌ Abbrechen", style=discord.ButtonStyle.red, row=4)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for item in self.children:
            item.disabled = True
        self.stop()
        await interaction.response.edit_message(
            content="❌ Raid-Erstellung abgebrochen.",
            embed=None,
            view=self,
        )


class RaidCreateModal(discord.ui.Modal):
    """Modal for raid basics."""

    def __init__(self, cog: "RaidCommand"):
        super().__init__(title="Raid erstellen")
        self.cog = cog

        self.title_input = discord.ui.TextInput(
            label="Titel",
            placeholder="z.B. WWM Gildenraid",
            max_length=80,
        )
        self.desc_input = discord.ui.TextInput(
            label="Beschreibung (optional)",
            placeholder="Kurzbeschreibung oder Hinweis",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=400,
        )

        self.add_item(self.title_input)
        self.add_item(self.desc_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            tz = ZoneInfo(self.cog.config.raid_timezone)
        except Exception:
            tz = timezone.utc

        now_local = datetime.now(tz)
        if now_local.minute < 30:
            hour = now_local.hour
            minute_bucket = 30
            date_base = now_local
        else:
            hour = now_local.hour + 1
            minute_bucket = 0
            date_base = now_local

        if hour >= 24:
            hour = 0
            date_base = date_base + timedelta(days=1)

        date_value = date_base.strftime("%d.%m.%Y")
        time_value = f"{hour:02d}:{minute_bucket:02d}"

        try:
            dt = parse_raid_datetime(date_value, time_value, self.cog.config.raid_timezone)
        except ValueError as exc:
            await interaction.response.send_message(
                f"❌ {exc}",
                ephemeral=True,
            )
            return

        start_ts = int(dt.timestamp())

        view = RaidScheduleView(
            bot=self.cog.bot,
            config=self.cog.config,
            raid_store=self.cog.raid_store,
            requester_id=interaction.user.id,
            title=self.title_input.value,
            description=self.desc_input.value,
            start_ts=start_ts,
            timezone_name=self.cog.config.raid_timezone,
            date_value=date_value,
            time_value=time_value,
        )

        await interaction.response.send_message(
            embed=view.build_embed(),
            view=view,
            ephemeral=True,
        )
        view.message = await interaction.original_response()


class RaidEditModal(discord.ui.Modal):
    """Modal to edit raid title and description."""

    def __init__(self, view_ref):
        super().__init__(title="Raid bearbeiten")
        self.view_ref = view_ref

        self.title_input = discord.ui.TextInput(
            label="Titel",
            placeholder="z.B. WWM Gildenraid",
            default=view_ref.title,
            max_length=80,
        )
        self.desc_input = discord.ui.TextInput(
            label="Beschreibung (optional)",
            placeholder="Kurzbeschreibung oder Hinweis",
            required=False,
            default=view_ref.description or "",
            style=discord.TextStyle.paragraph,
            max_length=400,
        )

        self.add_item(self.title_input)
        self.add_item(self.desc_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.view_ref.title = self.title_input.value
        description = self.desc_input.value.strip()
        self.view_ref.description = description or None

        if self.view_ref.message:
            try:
                await self.view_ref.message.edit(
                    embed=self.view_ref.build_embed(),
                    view=self.view_ref,
                )
            except Exception as exc:
                logger.warning("Failed to update raid draft message: %s", exc)

        await interaction.response.send_message(
            "✅ Raid-Entwurf aktualisiert.",
            ephemeral=True,
        )


class RaidPostEditModal(discord.ui.Modal):
    """Modal to edit a posted raid."""

    def __init__(self, view_ref, raid):
        super().__init__(title="Raid bearbeiten")
        self.view_ref = view_ref
        self.raid = raid

        try:
            tz = ZoneInfo(self.view_ref.config.raid_timezone)
        except Exception:
            tz = timezone.utc

        local_dt = datetime.fromtimestamp(raid.start_time, tz)
        date_value = local_dt.strftime("%d.%m.%Y")
        time_value = local_dt.strftime("%H:%M")

        self.title_input = discord.ui.TextInput(
            label="Titel",
            placeholder="z.B. WWM Gildenraid",
            default=raid.title,
            max_length=80,
        )
        self.desc_input = discord.ui.TextInput(
            label="Beschreibung (optional)",
            placeholder="Kurzbeschreibung oder Hinweis",
            required=False,
            default=raid.description or "",
            style=discord.TextStyle.paragraph,
            max_length=400,
        )
        self.date_input = discord.ui.TextInput(
            label="Datum (DD.MM.YYYY)",
            placeholder="10.02.2025",
            default=date_value,
            max_length=10,
        )
        self.time_input = discord.ui.TextInput(
            label="Uhrzeit (HH:MM)",
            placeholder="20:00",
            default=time_value,
            max_length=5,
        )

        self.add_item(self.title_input)
        self.add_item(self.desc_input)
        self.add_item(self.date_input)
        self.add_item(self.time_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        title = self.title_input.value.strip()
        description = self.desc_input.value.strip() or None

        try:
            dt = parse_raid_datetime(
                self.date_input.value,
                self.time_input.value,
                self.view_ref.config.raid_timezone,
            )
        except ValueError as exc:
            await interaction.response.send_message(
                f"❌ {exc}",
                ephemeral=True,
            )
            return

        start_ts = int(dt.timestamp())
        if start_ts <= int(datetime.now(timezone.utc).timestamp()):
            await interaction.response.send_message(
                "❌ Startzeit liegt in der Vergangenheit.",
                ephemeral=True,
            )
            return

        await self.view_ref.raid_store.update_raid_details(
            self.raid.id,
            title=title,
            description=description,
            start_time=start_ts,
        )

        updated = await self.view_ref.raid_store.get_raid(self.raid.id)
        if not updated or not interaction.message:
            await interaction.response.send_message(
                "✅ Raid aktualisiert.",
                ephemeral=True,
            )
            return

        signups = await self.view_ref.raid_store.get_signups_by_role(self.raid.id)
        embed = build_raid_embed(updated, signups, self.view_ref.config.raid_timezone)
        await interaction.message.edit(embed=embed, view=self.view_ref)

        await interaction.response.send_message(
            "✅ Raid aktualisiert.",
            ephemeral=True,
        )


class RaidStartView(discord.ui.View):
    """Persistent view for starting raid creation."""

    def __init__(self, cog: "RaidCommand"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="🗡️ Raid erstellen",
        style=discord.ButtonStyle.green,
        custom_id="guildscout_raid_start_v1",
    )
    async def start_raid(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ Dieser Button funktioniert nur im Server.",
                ephemeral=True,
            )
            return

        if not self.cog._has_creator_permission(interaction):
            await interaction.response.send_message(
                "❌ Keine Berechtigung für Raid-Erstellung.",
                ephemeral=True,
            )
            return

        allowed_channels = {
            self.cog.config.raid_manage_channel_id,
            self.cog.config.raid_info_channel_id,
        }
        allowed_channels = {cid for cid in allowed_channels if cid}
        if allowed_channels and interaction.channel_id not in allowed_channels:
            manage_channel = interaction.guild.get_channel(
                self.cog.config.raid_manage_channel_id
            )
            channel_hint = manage_channel.mention if manage_channel else "den Raid-Channel"
            await interaction.response.send_message(
                f"❌ Bitte nutze {channel_hint} für die Raid-Erstellung.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(RaidCreateModal(self.cog))


class RaidManageView(discord.ui.View):
    """Persistent view for managing posted raids."""

    def __init__(self, config: Config, raid_store: RaidStore):
        super().__init__(timeout=None)
        self.config = config
        self.raid_store = raid_store

    def _has_admin_permission(self, interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        if interaction.user.id in self.config.admin_users:
            return True
        if hasattr(interaction.user, "roles"):
            user_role_ids = [role.id for role in interaction.user.roles]
            return any(role_id in user_role_ids for role_id in self.config.admin_roles)
        return False

    def _has_creator_role(self, interaction: discord.Interaction) -> bool:
        if hasattr(interaction.user, "roles"):
            user_role_ids = [role.id for role in interaction.user.roles]
            return any(role_id in user_role_ids for role_id in self.config.raid_creator_roles)
        return False

    def _can_manage(self, interaction: discord.Interaction, raid) -> bool:
        return (
            self._has_admin_permission(interaction)
            or self._has_creator_role(interaction)
            or interaction.user.id == raid.creator_id
        )

    async def _get_raid_from_interaction(
        self, interaction: discord.Interaction
    ) -> Optional[object]:
        if not interaction.message:
            await interaction.response.send_message(
                "❌ Raid-Message nicht gefunden.",
                ephemeral=True,
            )
            return None
        raid = await self.raid_store.get_raid_by_message_id(interaction.message.id)
        if not raid:
            await interaction.response.send_message(
                "❌ Raid nicht gefunden.",
                ephemeral=True,
            )
            return None
        return raid

    async def _remove_participant_roles(self, interaction: discord.Interaction, raid_id: int) -> None:
        guild = interaction.guild
        if not guild:
            return
        role_id = self.config.raid_participant_role_id
        if not role_id:
            fallback = discord.utils.get(guild.roles, name="Raid Teilnehmer")
            if fallback:
                self.config.set_raid_participant_role_id(fallback.id)
                role_id = fallback.id
            else:
                return
        role = guild.get_role(role_id)
        if not role:
            return
        signups = await self.raid_store.list_signups(raid_id)
        for entry in signups:
            user_id = entry.get("user_id")
            if not user_id:
                continue
            member = guild.get_member(int(user_id))
            if not member:
                try:
                    member = await guild.fetch_member(int(user_id))
                except Exception:
                    continue
            if role not in member.roles:
                continue
            active_count = await self.raid_store.count_user_active_signups(
                guild.id, member.id
            )
            if active_count == 0:
                try:
                    await member.remove_roles(role, reason="Raid ended")
                except Exception:
                    logger.warning("Failed to remove raid participant role", exc_info=True)

    @discord.ui.button(
        label="✏️ Bearbeiten",
        style=discord.ButtonStyle.secondary,
        custom_id="guildscout_raid_edit_v1",
        row=0,
    )
    async def edit(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        raid = await self._get_raid_from_interaction(interaction)
        if not raid:
            return

        if not self._can_manage(interaction, raid):
            await interaction.response.send_message(
                "❌ Keine Berechtigung zum Bearbeiten.",
                ephemeral=True,
            )
            return
        if raid.status in ("closed", "cancelled"):
            await interaction.response.send_message(
                "❌ Geschlossene/abgesagte Raids koennen nicht bearbeitet werden.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(RaidPostEditModal(self, raid))

    @discord.ui.button(
        label="🔒 Sperren/Oeffnen",
        style=discord.ButtonStyle.secondary,
        custom_id="guildscout_raid_lock_v1",
        row=0,
    )
    async def toggle_lock(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        raid = await self._get_raid_from_interaction(interaction)
        if not raid:
            return

        if not self._can_manage(interaction, raid):
            await interaction.response.send_message(
                "❌ Keine Berechtigung zum Sperren.",
                ephemeral=True,
            )
            return
        if raid.status in ("closed", "cancelled"):
            await interaction.response.send_message(
                "❌ Abgeschlossene/abgesagte Raids koennen nicht gesperrt werden.",
                ephemeral=True,
            )
            return

        new_status = "locked" if raid.status == "open" else "open"
        await self.raid_store.update_status(raid.id, new_status)
        updated = await self.raid_store.get_raid(raid.id)
        if updated and interaction.message:
            signups = await self.raid_store.get_signups_by_role(raid.id)
            embed = build_raid_embed(updated, signups, self.config.raid_timezone)
            await interaction.message.edit(embed=embed, view=self)

        await interaction.response.send_message(
            "✅ Raid wurde gesperrt." if new_status == "locked" else "✅ Raid ist wieder offen.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="✅ Abschliessen",
        style=discord.ButtonStyle.danger,
        custom_id="guildscout_raid_close_v1",
        row=0,
    )
    async def close(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        raid = await self._get_raid_from_interaction(interaction)
        if not raid:
            return

        if not self._can_manage(interaction, raid):
            await interaction.response.send_message(
                "❌ Keine Berechtigung zum Schließen.",
                ephemeral=True,
            )
            return
        if raid.status in ("closed", "cancelled"):
            await interaction.response.send_message(
                "❌ Raid ist bereits abgeschlossen/abgesagt.",
                ephemeral=True,
            )
            return

        await self.raid_store.close_raid(raid.id)
        updated = await self.raid_store.get_raid(raid.id)
        if updated:
            signups = await self.raid_store.get_signups_by_role(raid.id)
            embed = build_raid_embed(updated, signups, self.config.raid_timezone)
            await interaction.message.edit(embed=embed, view=self)
            try:
                await interaction.message.clear_reactions()
            except Exception:
                pass
            await self._remove_participant_roles(interaction, raid.id)

        await interaction.response.send_message(
            "✅ Raid geschlossen.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="📄 Export",
        style=discord.ButtonStyle.secondary,
        custom_id="guildscout_raid_export_v1",
        row=1,
    )
    async def export(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        raid = await self._get_raid_from_interaction(interaction)
        if not raid:
            return

        if not self._can_manage(interaction, raid):
            await interaction.response.send_message(
                "❌ Keine Berechtigung fuer Export.",
                ephemeral=True,
            )
            return

        signups = await self.raid_store.list_signups(raid.id)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["user_id", "display_name", "role", "preferred_role", "joined_at"])

        guild = interaction.guild
        for entry in signups:
            user_id = int(entry["user_id"])
            role = entry["role"]
            preferred_role = entry.get("preferred_role") or ""
            joined_at = entry.get("joined_at") or 0
            display_name = str(user_id)
            if guild:
                member = guild.get_member(user_id)
                if member:
                    display_name = member.display_name
            joined_iso = datetime.fromtimestamp(joined_at, timezone.utc).isoformat()
            writer.writerow([user_id, display_name, role, preferred_role, joined_iso])

        filename = f"raid_{raid.id}_signups.csv"
        data = io.BytesIO(output.getvalue().encode("utf-8"))
        await interaction.response.send_message(
            content="✅ Export erstellt.",
            file=discord.File(data, filename=filename),
            ephemeral=True,
        )

    @discord.ui.button(
        label="🛑 Absagen",
        style=discord.ButtonStyle.danger,
        custom_id="guildscout_raid_cancel_v1",
        row=1,
    )
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        raid = await self._get_raid_from_interaction(interaction)
        if not raid:
            return

        if not self._can_manage(interaction, raid):
            await interaction.response.send_message(
                "❌ Keine Berechtigung zum Absagen.",
                ephemeral=True,
            )
            return
        if raid.status == "cancelled":
            await interaction.response.send_message(
                "ℹ️ Raid ist bereits abgesagt.",
                ephemeral=True,
            )
            return
        if raid.status == "closed":
            await interaction.response.send_message(
                "❌ Abgeschlossene Raids koennen nicht abgesagt werden.",
                ephemeral=True,
            )
            return

        await self.raid_store.update_status(raid.id, "cancelled")
        updated = await self.raid_store.get_raid(raid.id)
        if updated and interaction.message:
            signups = await self.raid_store.get_signups_by_role(raid.id)
            embed = build_raid_embed(updated, signups, self.config.raid_timezone)
            await interaction.message.edit(embed=embed, view=self)
            try:
                await interaction.message.clear_reactions()
            except Exception:
                pass
            await self._remove_participant_roles(interaction, raid.id)

        await interaction.response.send_message(
            "🛑 Raid wurde abgesagt.",
            ephemeral=True,
        )


class RaidCommand(commands.Cog):
    """Cog for raid scheduling and configuration."""

    def __init__(self, bot: commands.Bot, config: Config, raid_store: RaidStore):
        self.bot = bot
        self.config = config
        self.raid_store = raid_store
        if self.config.raid_info_channel_id:
            self.bot.loop.create_task(self._refresh_info_on_start())

    async def _ensure_participant_role(
        self, guild: discord.Guild
    ) -> Optional[discord.Role]:
        role_id = self.config.raid_participant_role_id
        if role_id:
            role = guild.get_role(role_id)
            if role:
                return role
        role = discord.utils.get(guild.roles, name="Raid Teilnehmer")
        if role:
            self.config.set_raid_participant_role_id(role.id)
            return role
        try:
            role = await guild.create_role(
                name="Raid Teilnehmer",
                mentionable=True,
                reason="Raid setup",
            )
        except Exception:
            logger.warning("Failed to create raid participant role", exc_info=True)
            return None
        self.config.set_raid_participant_role_id(role.id)
        return role

    async def _refresh_info_on_start(self) -> None:
        await self.bot.wait_until_ready()
        if not self.config.raid_info_channel_id:
            return
        guild = self.bot.get_guild(self.config.guild_id)
        if not guild:
            return
        await self._ensure_participant_role(guild)
        channel = guild.get_channel(self.config.raid_info_channel_id)
        if not isinstance(channel, discord.TextChannel):
            try:
                channel = await guild.fetch_channel(self.config.raid_info_channel_id)
            except Exception:
                return
        if not isinstance(channel, discord.TextChannel):
            return
        await self._upsert_raid_info_message(channel)

    def _has_admin_permission(self, interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        if interaction.user.id in self.config.admin_users:
            return True
        if hasattr(interaction.user, "roles"):
            user_role_ids = [role.id for role in interaction.user.roles]
            return any(role_id in user_role_ids for role_id in self.config.admin_roles)
        return False

    def _has_creator_permission(self, interaction: discord.Interaction) -> bool:
        if self._has_admin_permission(interaction):
            return True
        if hasattr(interaction.user, "roles"):
            user_role_ids = [role.id for role in interaction.user.roles]
            return any(role_id in user_role_ids for role_id in self.config.raid_creator_roles)
        return False

    async def _upsert_raid_info_message(
        self, channel: discord.TextChannel
    ) -> Optional[discord.Message]:
        embed = build_raid_info_embed()
        view = RaidStartView(self)

        message_id = self.config.raid_info_message_id
        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(embed=embed, view=view)
                return message
            except discord.NotFound:
                self.config.set_raid_info_message_id(None)
            except Exception as exc:
                logger.warning("Failed to update raid info message: %s", exc)

        message = await channel.send(embed=embed, view=view)
        self.config.set_raid_info_message_id(message.id)
        return message

    @app_commands.command(name="raid-create", description="[Raid] Raid erstellen")
    async def raid_create(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ Dieser Command funktioniert nur im Server.",
                ephemeral=True,
            )
            return

        if not self.config.raid_enabled:
            await interaction.response.send_message(
                "❌ Raid-System ist deaktiviert.",
                ephemeral=True,
            )
            return

        if not self._has_creator_permission(interaction):
            await interaction.response.send_message(
                "❌ Keine Berechtigung für Raid-Erstellung.",
                ephemeral=True,
            )
            return

        if self.config.raid_manage_channel_id and (
            interaction.channel_id != self.config.raid_manage_channel_id
        ):
            channel = interaction.guild.get_channel(self.config.raid_manage_channel_id)
            channel_hint = channel.mention if channel else "den Raid-Channel"
            await interaction.response.send_message(
                f"❌ Bitte nutze {channel_hint} für die Raid-Erstellung.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(RaidCreateModal(self))

    @app_commands.command(name="raid-list", description="[Raid] Kommende Raids anzeigen")
    async def raid_list(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ Dieser Command funktioniert nur im Server.",
                ephemeral=True,
            )
            return

        if not self.config.raid_enabled:
            await interaction.response.send_message(
                "❌ Raid-System ist deaktiviert.",
                ephemeral=True,
            )
            return

        now_ts = int(datetime.now(timezone.utc).timestamp())
        raids = await self.raid_store.list_upcoming_raids(now_ts, limit=10)
        if not raids:
            await interaction.response.send_message(
                "ℹ️ Keine kommenden Raids gefunden.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🗓️ Kommende Raids",
            color=discord.Color.blurple(),
        )

        for raid in raids:
            signups = await self.raid_store.get_signups_by_role(raid.id)
            tank_count = len(signups.get(ROLE_TANK, []))
            healer_count = len(signups.get(ROLE_HEALER, []))
            dps_count = len(signups.get(ROLE_DPS, []))
            bench_count = len(signups.get(ROLE_BENCH, []))
            status_label = "Offen" if raid.status == "open" else "Gesperrt"

            jump_url = "—"
            if raid.message_id:
                jump_url = (
                    f"https://discord.com/channels/{raid.guild_id}/"
                    f"{raid.channel_id}/{raid.message_id}"
                )

            value = (
                f"Start: <t:{raid.start_time}:F> (<t:{raid.start_time}:R>)\n"
                f"Status: {status_label}\n"
                f"Tanks: {tank_count}/{raid.tanks_needed} · "
                f"Healer: {healer_count}/{raid.healers_needed} · "
                f"DPS: {dps_count}/{raid.dps_needed}\n"
                f"Reserve: {bench_count}/{raid.bench_needed}\n"
                f"Link: {jump_url}"
            )
            embed.add_field(name=raid.title, value=value, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="raid-setup",
        description="[Admin] Erstellt Raid-Channels und speichert die IDs",
    )
    async def raid_setup(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ Dieser Command funktioniert nur im Server.",
                ephemeral=True,
            )
            return

        if not self._has_admin_permission(interaction):
            await interaction.response.send_message(
                "❌ Nur Admins können das Setup ausführen.",
                ephemeral=True,
            )
            return

        try:
            await interaction.response.defer(ephemeral=True)
        except discord.errors.NotFound:
            return
        except Exception as exc:
            logger.error("Error during raid-setup defer: %s", exc, exc_info=True)
            return

        guild = interaction.guild
        if not guild:
            await interaction.followup.send("❌ Guild nicht gefunden.", ephemeral=True)
            return

        category = discord.utils.get(guild.categories, name="Raids")
        if not category:
            try:
                category = await guild.create_category("Raids", reason="Raid setup")
            except Exception as exc:
                logger.error("Failed to create raid category: %s", exc, exc_info=True)
                await interaction.followup.send(
                    "❌ Kategorie konnte nicht erstellt werden.",
                    ephemeral=True,
                )
                return

        post_channel = discord.utils.get(category.channels, name="raid-ankuendigungen")
        if not post_channel:
            try:
                post_channel = await guild.create_text_channel(
                    "raid-ankuendigungen",
                    category=category,
                    reason="Raid setup",
                )
            except Exception as exc:
                logger.error("Failed to create raid post channel: %s", exc, exc_info=True)
                await interaction.followup.send(
                    "❌ Raid-Channel konnte nicht erstellt werden.",
                    ephemeral=True,
                )
                return

        manage_channel = discord.utils.get(category.channels, name="raid-planung")
        if not manage_channel:
            try:
                manage_channel = await guild.create_text_channel(
                    "raid-planung",
                    category=category,
                    reason="Raid setup",
                )
            except Exception as exc:
                logger.error("Failed to create raid manage channel: %s", exc, exc_info=True)
                await interaction.followup.send(
                    "❌ Raid-Planungs-Channel konnte nicht erstellt werden.",
                    ephemeral=True,
                )
                return

        info_channel = discord.utils.get(category.channels, name="raid-info")
        if not info_channel:
            try:
                info_channel = await guild.create_text_channel(
                    "raid-info",
                    category=category,
                    reason="Raid setup",
                    topic="🗡️ Infos und Anleitung für Raid-Anmeldungen",
                )
            except Exception as exc:
                logger.error("Failed to create raid info channel: %s", exc, exc_info=True)
                await interaction.followup.send(
                    "❌ Raid-Info-Channel konnte nicht erstellt werden.",
                    ephemeral=True,
                )
                return

        participant_role = await self._ensure_participant_role(guild)

        self.config.set_raid_post_channel_id(post_channel.id)
        self.config.set_raid_manage_channel_id(manage_channel.id)
        self.config.set_raid_info_channel_id(info_channel.id)
        if participant_role:
            self.config.set_raid_participant_role_id(participant_role.id)

        await self._upsert_raid_info_message(info_channel)

        embed = discord.Embed(
            title="✅ Raid-Setup abgeschlossen",
            description="Channels wurden erstellt und gespeichert.",
            color=discord.Color.green(),
        )
        embed.add_field(name="Raid-Posts", value=post_channel.mention, inline=False)
        embed.add_field(name="Raid-Planung", value=manage_channel.mention, inline=False)
        embed.add_field(name="Raid-Info", value=info_channel.mention, inline=False)
        if participant_role:
            embed.add_field(
                name="Teilnehmerrolle",
                value=participant_role.mention,
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="raid-set-channel",
        description="[Admin] Setzt die Raid-Channels",
    )
    @app_commands.describe(
        post_channel="Channel für Raid-Ankündigungen",
        manage_channel="Optionaler Channel für Raid-Erstellung",
        info_channel="Optionaler Channel für Raid-Info",
    )
    async def raid_set_channel(
        self,
        interaction: discord.Interaction,
        post_channel: Optional[discord.TextChannel] = None,
        manage_channel: Optional[discord.TextChannel] = None,
        info_channel: Optional[discord.TextChannel] = None,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ Dieser Command funktioniert nur im Server.",
                ephemeral=True,
            )
            return

        if not self._has_admin_permission(interaction):
            await interaction.response.send_message(
                "❌ Nur Admins können Channels setzen.",
                ephemeral=True,
            )
            return

        if not post_channel and not manage_channel and not info_channel:
            await interaction.response.send_message(
                "❌ Bitte mindestens einen Channel angeben.",
                ephemeral=True,
            )
            return

        if post_channel:
            self.config.set_raid_post_channel_id(post_channel.id)
        if manage_channel:
            self.config.set_raid_manage_channel_id(manage_channel.id)
        if info_channel:
            self.config.set_raid_info_channel_id(info_channel.id)
            await self._upsert_raid_info_message(info_channel)

        embed = discord.Embed(
            title="✅ Raid-Channels aktualisiert",
            color=discord.Color.green(),
        )
        if post_channel:
            embed.add_field(name="Raid-Posts", value=post_channel.mention, inline=False)
        if manage_channel:
            embed.add_field(name="Raid-Planung", value=manage_channel.mention, inline=False)
        if info_channel:
            embed.add_field(name="Raid-Info", value=info_channel.mention, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="raid-info-setup",
        description="[Admin] Erstellt/aktualisiert den Raid-Info-Post",
    )
    async def raid_info_setup(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ Dieser Command funktioniert nur im Server.",
                ephemeral=True,
            )
            return

        if not self._has_admin_permission(interaction):
            await interaction.response.send_message(
                "❌ Nur Admins können das Setup ausführen.",
                ephemeral=True,
            )
            return

        try:
            await interaction.response.defer(ephemeral=True)
        except discord.errors.NotFound:
            return
        except Exception as exc:
            logger.error("Error during raid-info-setup defer: %s", exc, exc_info=True)
            return

        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Raids")
        if not category:
            try:
                category = await guild.create_category("Raids", reason="Raid info setup")
            except Exception as exc:
                logger.error("Failed to create raid category: %s", exc, exc_info=True)
                await interaction.followup.send(
                    "❌ Kategorie konnte nicht erstellt werden.",
                    ephemeral=True,
                )
                return

        info_channel = discord.utils.get(category.channels, name="raid-info")
        if not info_channel:
            info_channel = await guild.create_text_channel(
                "raid-info",
                category=category,
                reason="Raid info setup",
                topic="🗡️ Infos und Anleitung für Raid-Anmeldungen",
            )

        self.config.set_raid_info_channel_id(info_channel.id)
        await self._upsert_raid_info_message(info_channel)

        embed = discord.Embed(
            title="✅ Raid-Info aktualisiert",
            color=discord.Color.green(),
        )
        embed.add_field(name="Raid-Info", value=info_channel.mention, inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="raid-add-creator-role",
        description="[Admin] Rolle zur Raid-Erstellung hinzufügen",
    )
    async def raid_add_creator_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ Dieser Command funktioniert nur im Server.",
                ephemeral=True,
            )
            return

        if not self._has_admin_permission(interaction):
            await interaction.response.send_message(
                "❌ Nur Admins können Rollen hinzufügen.",
                ephemeral=True,
            )
            return

        self.config.add_raid_creator_role(role.id)
        await interaction.response.send_message(
            f"✅ Rolle {role.mention} hinzugefügt.",
            ephemeral=True,
        )

    @app_commands.command(
        name="raid-remove-creator-role",
        description="[Admin] Rolle von Raid-Erstellung entfernen",
    )
    async def raid_remove_creator_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ Dieser Command funktioniert nur im Server.",
                ephemeral=True,
            )
            return

        if not self._has_admin_permission(interaction):
            await interaction.response.send_message(
                "❌ Nur Admins können Rollen entfernen.",
                ephemeral=True,
            )
            return

        self.config.remove_raid_creator_role(role.id)
        await interaction.response.send_message(
            f"✅ Rolle {role.mention} entfernt.",
            ephemeral=True,
        )

    @app_commands.command(
        name="raid-set-participant-role",
        description="[Admin] Setzt die Raid-Teilnehmerrolle",
    )
    async def raid_set_participant_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ Dieser Command funktioniert nur im Server.",
                ephemeral=True,
            )
            return

        if not self._has_admin_permission(interaction):
            await interaction.response.send_message(
                "❌ Nur Admins koennen die Teilnehmerrolle setzen.",
                ephemeral=True,
            )
            return

        self.config.set_raid_participant_role_id(role.id)
        await interaction.response.send_message(
            f"✅ Teilnehmerrolle gesetzt: {role.mention}",
            ephemeral=True,
        )


async def setup(bot: commands.Bot, config: Config, raid_store: RaidStore) -> None:
    """Setup function for raid commands."""
    cog = RaidCommand(bot, config, raid_store)
    await bot.add_cog(cog)
    bot.add_view(RaidStartView(cog))
    bot.add_view(RaidManageView(config, raid_store))
    logger.info("RaidCommand cog loaded")
