"""Raid scheduling commands."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from src.database.raid_store import RaidStore
from src.database.raid_template_store import RaidTemplateStore, DEFAULT_TEMPLATE_SPECS
from src.events.raid_events import BenchPreferenceView
from src.utils.config import Config
from src.utils.raid_utils import (
    GAME_LABELS,
    GAME_WWM,
    ROLE_BENCH,
    ROLE_CANCEL,
    ROLE_DPS,
    ROLE_HEALER,
    ROLE_LABELS,
    ROLE_TANK,
    ROLE_EMOJIS,
    MODE_GUILDWAR,
    MODE_LABELS,
    MODE_RAID,
    build_raid_embed,
    build_raid_log_embed,
    get_role_limit,
    parse_raid_datetime,
)


logger = logging.getLogger("guildscout.commands.raid")

DEFAULT_COUNTS = {
    ROLE_TANK: 2,
    ROLE_HEALER: 2,
    ROLE_DPS: 6,
    ROLE_BENCH: 0,
}

DEFAULT_TEMPLATE_PAYLOADS = [
    {
        "name": spec["name"],
        "counts": {
            ROLE_TANK: spec["tanks"],
            ROLE_HEALER: spec["healers"],
            ROLE_DPS: spec["dps"],
            ROLE_BENCH: spec["bench"],
        },
        "is_default": spec.get("is_default", False),
    }
    for spec in DEFAULT_TEMPLATE_SPECS
]

def _format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "a moment"
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts and secs:
        parts.append(f"{secs}s")
    return " ".join(parts)

ROLE_SIGNUP_ROLES = (ROLE_TANK, ROLE_HEALER, ROLE_DPS, ROLE_BENCH)
ROLE_EMOJI_TO_ROLE = {
    ROLE_EMOJIS[ROLE_TANK]: ROLE_TANK,
    ROLE_EMOJIS[ROLE_HEALER]: ROLE_HEALER,
    ROLE_EMOJIS[ROLE_DPS]: ROLE_DPS,
    ROLE_EMOJIS[ROLE_BENCH]: ROLE_BENCH,
    ROLE_EMOJIS[ROLE_CANCEL]: ROLE_CANCEL,
}


async def load_template_payloads(
    template_store: RaidTemplateStore, guild_id: int
) -> list[dict]:
    """Load template payloads for a guild with sane defaults."""
    if not template_store or not guild_id:
        return DEFAULT_TEMPLATE_PAYLOADS
    try:
        await template_store.ensure_default_templates(guild_id)
        templates = await template_store.list_templates(guild_id)
    except Exception:
        logger.warning("Failed to load raid templates", exc_info=True)
        return DEFAULT_TEMPLATE_PAYLOADS
    if not templates:
        return DEFAULT_TEMPLATE_PAYLOADS
    payloads = []
    for template in templates:
        payloads.append(
            {
                "name": template.name,
                "counts": {
                    ROLE_TANK: template.tanks,
                    ROLE_HEALER: template.healers,
                    ROLE_DPS: template.dps,
                    ROLE_BENCH: template.bench,
                },
                "is_default": template.is_default,
            }
        )
    return payloads

MAX_SLOT_OPTION = 20
DATE_RANGE_DAYS = 25
DATE_PAGE_STEP_DAYS = 7
MAX_DATE_OFFSET_DAYS = 365
STATS_TOP_LIMIT = 10


def get_default_date_time(timezone_name: str) -> tuple[str, str, int]:
    """Return default date/time values rounded to next half hour."""
    try:
        tz = ZoneInfo(timezone_name)
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
    dt = parse_raid_datetime(date_value, time_value, timezone_name)
    start_ts = int(dt.timestamp())
    return date_value, time_value, start_ts


def build_raid_info_embed() -> discord.Embed:
    """Return the raid info/start embed."""
    embed = discord.Embed(
        title="🗡️ Raid Guide (Where Winds Meet)",
        description=(
            "Everything you need to know about raids.\n"
            "Roles: Tank, Healer, DPS + Bench."
        ),
        color=discord.Color.green(),
    )
    embed.add_field(
        name="Create a raid (Creator/Admin)",
        value=(
            "1) Click 'Create raid'\n"
            "2) Enter title + description\n"
            "3) Select game + mode\n"
            "4) Pick date/time via dropdowns (page weeks)\n"
            "5) Set slots or use a template\n"
            "6) Click 'Post raid'\n"
            "Guildwar posts go to the guildwar channel."
        ),
        inline=False,
    )
    embed.add_field(
        name="Sign up in the raid post",
        value=(
            "React with: 🛡️ Tank, 💉 Healer, ⚔️ DPS, 🪑 Bench\n"
            "❌ = leave. One role per person.\n"
            "If a role is full, you are moved to bench (if available).\n"
            "On bench, react with a role to set your preference.\n"
            "Optional: ✅ check-in can be enabled before start.\n"
            "On leave you can optionally send a DM reason."
        ),
        inline=False,
    )
    embed.add_field(
        name="Web UI",
        value=(
            "Use the GuildScout Web UI to create raids, edit templates,\n"
            "and update settings without commands."
        ),
        inline=False,
    )
    embed.add_field(
        name="Manage (Creator/Admin/Lead)",
        value=(
            "Buttons in the raid post: ✏️ Edit, 🔒 Lock/Unlock,\n"
            "✅ Close, 🛑 Cancel, ⏭️ Follow-up, ⚙️ Slots, 🪑 Promote.\n"
            "Lock = bench only. Auto-close can be disabled\n"
            "or used as a safety close after X hours."
        ),
        inline=False,
    )
    embed.add_field(
        name="Raid archive & stats (optional)",
        value=(
            "Optional log channel: summary with roles, check-in,\n"
            "no-show and reasons. In the raid channel there is a\n"
            "participation leaderboard (all-time, top list). Admin: /raid-user-stats."
        ),
        inline=False,
    )
    embed.add_field(
        name="Participant role & reminders",
        value=(
            "On signup you get the participant role (if configured).\n"
            "It is removed on leave or after raid end.\n"
            "Reminders go out e.g. 24h/1h before start + DM 15 minutes before.\n"
            "If slots open up, the bot can ping the participant role."
        ),
        inline=False,
    )
    embed.add_field(
        name="Commands",
        value=(
            "/raid-create – create raid (button alternative)\n"
            "/raid-list – show upcoming raids\n"
            "Admin: /raid-setup, /raid-set-channel, /raid-info-setup,\n"
            "/raid-add-creator-role, /raid-remove-creator-role,\n"
            "/raid-set-participant-role, /raid-user-stats"
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
        if not view or not hasattr(view, "counts") or not hasattr(view, "build_embed"):
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
            placeholder=f"Date: {view.date_value}",
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
                "❌ Start time is in the past.",
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
            placeholder=f"Hour: {view.hour_value:02d}",
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
                "❌ Start time is in the past.",
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
                "❌ Start time is in the past.",
                ephemeral=True,
            )
            return

        view.update_select_defaults()
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class RaidGameSelect(discord.ui.Select):
    """Dropdown for selecting the game."""

    def __init__(self, view: "RaidGameModeView"):
        options = [
            discord.SelectOption(
                label=GAME_LABELS[GAME_WWM],
                value=GAME_WWM,
                default=(view.game == GAME_WWM),
            )
        ]
        super().__init__(
            placeholder=f"Game: {GAME_LABELS.get(view.game, view.game)}",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, RaidGameModeView):
            return
        view.game = self.values[0]
        view.update_select_defaults()
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class RaidModeSelect(discord.ui.Select):
    """Dropdown for selecting the game mode."""

    def __init__(self, view: "RaidGameModeView"):
        options = [
            discord.SelectOption(
                label=MODE_LABELS[MODE_RAID],
                value=MODE_RAID,
                default=(view.mode == MODE_RAID),
            ),
            discord.SelectOption(
                label=MODE_LABELS[MODE_GUILDWAR],
                value=MODE_GUILDWAR,
                default=(view.mode == MODE_GUILDWAR),
            ),
        ]
        super().__init__(
            placeholder=f"Mode: {MODE_LABELS.get(view.mode, view.mode)}",
            min_values=1,
            max_values=1,
            options=options,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, RaidGameModeView):
            return
        view.mode = self.values[0]
        view.update_select_defaults()
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class RaidGameModeView(discord.ui.View):
    """Pick game/mode before choosing date/time."""

    def __init__(
        self,
        bot: commands.Bot,
        config: Config,
        raid_store: RaidStore,
        template_store: RaidTemplateStore,
        guild_id: int,
        requester_id: int,
        title: str,
        description: Optional[str],
        game: str = GAME_WWM,
        mode: str = MODE_RAID,
    ):
        super().__init__(timeout=600)
        self.bot = bot
        self.config = config
        self.raid_store = raid_store
        self.template_store = template_store
        self.guild_id = guild_id
        self.requester_id = requester_id
        self.title = title
        self.description = description
        self.game = game
        self.mode = mode
        self.message: Optional[discord.Message] = None

        self.add_item(RaidGameSelect(self))
        self.add_item(RaidModeSelect(self))

    def update_select_defaults(self) -> None:
        for item in self.children:
            if isinstance(item, RaidGameSelect):
                item.placeholder = f"Game: {GAME_LABELS.get(self.game, self.game)}"
                for option in item.options:
                    option.default = option.value == self.game
            elif isinstance(item, RaidModeSelect):
                item.placeholder = f"Mode: {MODE_LABELS.get(self.mode, self.mode)}"
                for option in item.options:
                    option.default = option.value == self.mode

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "❌ Only the creator can edit this draft.",
                ephemeral=True,
            )
            return False
        return True

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"📝 Raid Draft: {self.title}",
            description=self.description or None,
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Game",
            value=GAME_LABELS.get(self.game, self.game),
            inline=True,
        )
        embed.add_field(
            name="Mode",
            value=MODE_LABELS.get(self.mode, self.mode),
            inline=True,
        )
        embed.set_footer(text="Select game/mode, then click 'Next'.")
        return embed

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.green, row=2)
    async def continue_to_schedule(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        try:
            date_value, time_value, start_ts = get_default_date_time(
                self.config.raid_timezone
            )
        except ValueError as exc:
            await interaction.response.send_message(
                f"❌ {exc}",
                ephemeral=True,
            )
            return

        view = RaidScheduleView(
            bot=self.bot,
            config=self.config,
            raid_store=self.raid_store,
            template_store=self.template_store,
            guild_id=self.guild_id,
            requester_id=self.requester_id,
            title=self.title,
            description=self.description,
            start_ts=start_ts,
            timezone_name=self.config.raid_timezone,
            date_value=date_value,
            time_value=time_value,
            game=self.game,
            mode=self.mode,
        )
        await interaction.response.edit_message(
            embed=view.build_embed(),
            view=view,
        )
        view.message = interaction.message
        self.stop()

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red, row=2)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for item in self.children:
            item.disabled = True
        self.stop()
        await interaction.response.edit_message(
            content="❌ Raid creation cancelled.",
            embed=None,
            view=self,
        )


class RaidScheduleView(discord.ui.View):
    """Pick date/time before choosing slot counts."""

    def __init__(
        self,
        bot: commands.Bot,
        config: Config,
        raid_store: RaidStore,
        template_store: RaidTemplateStore,
        guild_id: int,
        requester_id: int,
        title: str,
        description: Optional[str],
        start_ts: int,
        timezone_name: str,
        date_value: str,
        time_value: str,
        game: str = GAME_WWM,
        mode: str = MODE_RAID,
        counts: Optional[Dict[str, int]] = None,
        template_index: int = 0,
    ):
        super().__init__(timeout=600)
        self.bot = bot
        self.config = config
        self.raid_store = raid_store
        self.template_store = template_store
        self.guild_id = guild_id
        self.requester_id = requester_id
        self.title = title
        self.description = description
        self.start_ts = start_ts
        self.timezone_name = timezone_name
        self.date_value = date_value
        self.time_value = time_value
        self.game = game
        self.mode = mode
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
        weekday_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
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
                item.placeholder = f"Date: {self.date_value}"

    def update_select_defaults(self) -> None:
        """Update select placeholders/defaults after changes."""
        for item in self.children:
            if isinstance(item, RaidDateSelect):
                item.placeholder = f"Date: {self.date_value}"
                for option in item.options:
                    option.default = option.value == self.date_value
            elif isinstance(item, RaidHourSelect):
                item.placeholder = f"Hour: {self.hour_value:02d}"
                for option in item.options:
                    option.default = option.value == str(self.hour_value)
            elif isinstance(item, RaidMinuteSelect):
                item.placeholder = f"Minute: {self.minute_value:02d}"
                for option in item.options:
                    option.default = option.value == f"{self.minute_value:02d}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "❌ Only the creator can edit this draft.",
                ephemeral=True,
            )
            return False
        return True

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"📝 Raid Draft: {self.title}",
            description=self.description or None,
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Game",
            value=GAME_LABELS.get(self.game, self.game),
            inline=True,
        )
        embed.add_field(
            name="Mode",
            value=MODE_LABELS.get(self.mode, self.mode),
            inline=True,
        )
        embed.add_field(
            name="Start Time",
            value=f"<t:{self.start_ts}:F>\n<t:{self.start_ts}:R>",
            inline=False,
        )
        embed.add_field(
            name="Slots",
            value="Select in the next step.",
            inline=False,
        )
        embed.set_footer(text="Select date/time, then click 'Next'.")
        return embed

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.green, row=4)
    async def continue_to_slots(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        if self.start_ts <= int(datetime.now(timezone.utc).timestamp()):
            await interaction.response.send_message(
                "❌ Start time is in the past.",
                ephemeral=True,
            )
            return

        templates = await load_template_payloads(self.template_store, self.guild_id)

        next_view = RaidSlotsView(
            bot=self.bot,
            config=self.config,
            raid_store=self.raid_store,
            template_store=self.template_store,
            templates=templates,
            requester_id=self.requester_id,
            title=self.title,
            description=self.description,
            start_ts=self.start_ts,
            timezone_name=self.timezone_name,
            date_value=self.date_value,
            time_value=self.time_value,
            game=self.game,
            mode=self.mode,
            counts=self.counts,
            template_index=self.template_index,
        )
        await interaction.response.edit_message(
            embed=next_view.build_embed(),
            view=next_view,
        )
        next_view.message = interaction.message
        self.stop()

    @discord.ui.button(label="◀️ Previous week", style=discord.ButtonStyle.secondary, row=3)
    async def prev_week(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if self.date_offset_days <= 0:
            await interaction.response.send_message(
                "ℹ️ You are already at the first page.",
                ephemeral=True,
            )
            return

        self.date_offset_days = max(0, self.date_offset_days - DATE_PAGE_STEP_DAYS)
        self.refresh_date_options()
        self.update_select_defaults()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="▶️ Next week", style=discord.ButtonStyle.secondary, row=3)
    async def next_week(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if self.date_offset_days >= self.max_date_offset_days:
            await interaction.response.send_message(
                "ℹ️ Can't go further right now.",
                ephemeral=True,
            )
            return

        self.date_offset_days = min(
            self.max_date_offset_days, self.date_offset_days + DATE_PAGE_STEP_DAYS
        )
        self.refresh_date_options()
        self.update_select_defaults()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="✏️ Title/Description", style=discord.ButtonStyle.secondary, row=3)
    async def edit_details(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(RaidEditModal(self))

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red, row=4)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for item in self.children:
            item.disabled = True
        self.stop()
        await interaction.response.edit_message(
            content="❌ Raid creation cancelled.",
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
        template_store: RaidTemplateStore,
        templates: Optional[list[dict]],
        requester_id: int,
        title: str,
        description: Optional[str],
        start_ts: int,
        timezone_name: str,
        date_value: str,
        time_value: str,
        game: str = GAME_WWM,
        mode: str = MODE_RAID,
        counts: Optional[Dict[str, int]] = None,
        template_index: int = 0,
    ):
        super().__init__(timeout=600)
        self.bot = bot
        self.config = config
        self.raid_store = raid_store
        self.template_store = template_store
        self.requester_id = requester_id
        self.title = title
        self.description = description
        self.start_ts = start_ts
        self.timezone_name = timezone_name
        self.date_value = date_value
        self.time_value = time_value
        self.game = game
        self.mode = mode
        self.counts = counts or DEFAULT_COUNTS.copy()
        self.templates = templates or DEFAULT_TEMPLATE_PAYLOADS
        self.template_index = template_index
        self.message: Optional[discord.Message] = None

        self._normalize_template_index()

        self.add_item(RoleCountSelect("Tanks", ROLE_TANK, self.counts[ROLE_TANK], row=0))
        self.add_item(RoleCountSelect("Healer", ROLE_HEALER, self.counts[ROLE_HEALER], row=1))
        self.add_item(RoleCountSelect("DPS", ROLE_DPS, self.counts[ROLE_DPS], row=2))
        self.add_item(RoleCountSelect("Bench", ROLE_BENCH, self.counts[ROLE_BENCH], row=3))

    def _get_template_label(self) -> str:
        for idx, template in enumerate(self.templates):
            template_counts = template.get("counts", {})
            if all(
                self.counts.get(role) == template_counts.get(role)
                for role in DEFAULT_COUNTS
            ):
                self.template_index = idx
                return template.get("name", "Custom")
        return "Custom"

    def _apply_template(self) -> str:
        template = self.templates[self.template_index]
        for role_key, value in template.get("counts", {}).items():
            self.counts[role_key] = value
        return template.get("name", "Custom")

    def _normalize_template_index(self) -> None:
        if not self.templates:
            self.templates = DEFAULT_TEMPLATE_PAYLOADS
        if self.template_index < 0 or self.template_index >= len(self.templates):
            default_index = 0
            for idx, template in enumerate(self.templates):
                if template.get("is_default"):
                    default_index = idx
                    break
            self.template_index = default_index

    def _sync_select_placeholders(self) -> None:
        for item in self.children:
            if isinstance(item, RoleCountSelect):
                current = self.counts.get(item.role_key, 0)
                item.placeholder = f"{item.label_text}: {current}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "❌ Only the creator can edit this draft.",
                ephemeral=True,
            )
            return False
        return True

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"📝 Raid Draft: {self.title}",
            description=self.description or None,
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Game",
            value=GAME_LABELS.get(self.game, self.game),
            inline=True,
        )
        embed.add_field(
            name="Mode",
            value=MODE_LABELS.get(self.mode, self.mode),
            inline=True,
        )
        embed.add_field(
            name="Start Time",
            value=f"<t:{self.start_ts}:F>\n<t:{self.start_ts}:R>",
            inline=False,
        )
        embed.add_field(name="Tanks", value=str(self.counts[ROLE_TANK]), inline=True)
        embed.add_field(name="Healer", value=str(self.counts[ROLE_HEALER]), inline=True)
        embed.add_field(name="DPS", value=str(self.counts[ROLE_DPS]), inline=True)
        embed.add_field(name="Bench", value=str(self.counts[ROLE_BENCH]), inline=True)
        template_label = self._get_template_label()
        embed.set_footer(
            text=f"Template: {template_label} · Set slots, then click 'Post raid'."
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

    @discord.ui.button(label="⬅️ Back", style=discord.ButtonStyle.secondary, row=4)
    async def back(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        back_view = RaidScheduleView(
            bot=self.bot,
            config=self.config,
            raid_store=self.raid_store,
            template_store=self.template_store,
            guild_id=interaction.guild.id if interaction.guild else 0,
            requester_id=self.requester_id,
            title=self.title,
            description=self.description,
            start_ts=self.start_ts,
            timezone_name=self.timezone_name,
            date_value=self.date_value,
            time_value=self.time_value,
            game=self.game,
            mode=self.mode,
            counts=self.counts,
            template_index=self.template_index,
        )
        await interaction.response.edit_message(
            embed=back_view.build_embed(),
            view=back_view,
        )
        back_view.message = interaction.message
        self.stop()

    @discord.ui.button(label="✏️ Title/Description", style=discord.ButtonStyle.secondary, row=4)
    async def edit_details(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(RaidEditModal(self))

    @discord.ui.button(label="🧩 Switch template", style=discord.ButtonStyle.secondary, row=4)
    async def cycle_template(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not self.templates:
            self.templates = DEFAULT_TEMPLATE_PAYLOADS
        self.template_index = (self.template_index + 1) % len(self.templates)
        self._apply_template()
        self._sync_select_placeholders()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="✅ Post raid", style=discord.ButtonStyle.green, row=4)
    async def post_raid(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        post_channel_id = self.config.raid_post_channel_id
        if self.mode == MODE_GUILDWAR:
            post_channel_id = self.config.raid_guildwar_post_channel_id
            if not post_channel_id:
                await interaction.response.send_message(
                    "❌ No guildwar channel configured. Use `/raid-setup` or `/raid-set-channel`.",
                    ephemeral=True,
                )
                return
        if not post_channel_id:
            await interaction.response.send_message(
                "❌ No raid channel configured. Use `/raid-setup` or `/raid-set-channel`.",
                ephemeral=True,
            )
            return

        if self.start_ts <= int(datetime.now(timezone.utc).timestamp()):
            await interaction.response.send_message(
                "❌ Start time is in the past.",
                ephemeral=True,
            )
            return

        if self.counts[ROLE_TANK] + self.counts[ROLE_HEALER] + self.counts[ROLE_DPS] == 0:
            await interaction.response.send_message(
                "❌ Please set at least one slot for Tank/Healer/DPS.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("❌ Server not found.", ephemeral=True)
            return

        post_channel = guild.get_channel(post_channel_id)
        if not isinstance(post_channel, discord.TextChannel):
            missing_label = "Guildwar channel" if self.mode == MODE_GUILDWAR else "Raid channel"
            await interaction.response.send_message(
                f"❌ {missing_label} not found. Please reconfigure.",
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
            game=self.game,
            mode=self.mode,
            start_time=self.start_ts,
            tanks_needed=self.counts[ROLE_TANK],
            healers_needed=self.counts[ROLE_HEALER],
            dps_needed=self.counts[ROLE_DPS],
            bench_needed=self.counts[ROLE_BENCH],
        )

        raid = await self.raid_store.get_raid(raid_id)
        if not raid:
            await interaction.response.send_message(
                "❌ Raid could not be saved.",
                ephemeral=True,
            )
            return

        embed = build_raid_embed(raid, {}, self.config.raid_timezone, None, None)
        manage_view = RaidManageView(self.config, self.raid_store, self.template_store)
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
            title="✅ Raid created",
            description=f"Raid posted: {raid_message.jump_url}",
            color=discord.Color.green(),
        )
        try:
            await interaction.edit_original_response(embed=success_embed, view=self)
        except Exception:
            await interaction.followup.send(embed=success_embed, ephemeral=True)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red, row=4)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for item in self.children:
            item.disabled = True
        self.stop()
        await interaction.response.edit_message(
            content="❌ Raid creation cancelled.",
            embed=None,
            view=self,
        )


class RaidSlotEditView(discord.ui.View):
    """Edit slot counts for an existing raid."""

    def __init__(
        self,
        config: Config,
        raid_store: RaidStore,
        requester_id: int,
        raid_id: int,
        title: str,
        counts: Dict[str, int],
    ):
        super().__init__(timeout=600)
        self.config = config
        self.raid_store = raid_store
        self.requester_id = requester_id
        self.raid_id = raid_id
        self.title = title
        self.counts = counts
        self.message: Optional[discord.Message] = None

        self.add_item(RoleCountSelect("Tanks", ROLE_TANK, self.counts[ROLE_TANK], row=0))
        self.add_item(RoleCountSelect("Healer", ROLE_HEALER, self.counts[ROLE_HEALER], row=1))
        self.add_item(RoleCountSelect("DPS", ROLE_DPS, self.counts[ROLE_DPS], row=2))
        self.add_item(RoleCountSelect("Bench", ROLE_BENCH, self.counts[ROLE_BENCH], row=3))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "❌ Only the creator can edit this.",
                ephemeral=True,
            )
            return False
        return True

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"⚙️ Edit slots: {self.title}",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Tanks", value=str(self.counts[ROLE_TANK]), inline=True)
        embed.add_field(name="Healer", value=str(self.counts[ROLE_HEALER]), inline=True)
        embed.add_field(name="DPS", value=str(self.counts[ROLE_DPS]), inline=True)
        embed.add_field(name="Bench", value=str(self.counts[ROLE_BENCH]), inline=True)
        embed.set_footer(text="Adjust and save.")
        return embed

    async def _get_raid_message(self, guild: discord.Guild):
        raid = await self.raid_store.get_raid(self.raid_id)
        if not raid or not raid.message_id:
            return None, None
        channel = guild.get_channel(raid.channel_id)
        if not isinstance(channel, discord.TextChannel):
            try:
                channel = await guild.fetch_channel(raid.channel_id)
            except Exception:
                return raid, None
        try:
            message = await channel.fetch_message(raid.message_id)
        except Exception:
            return raid, None
        return raid, message

    async def _send_dm(self, member: Optional[discord.Member], message: str) -> None:
        if not member:
            return
        try:
            await member.send(message)
        except Exception:
            pass

    async def _promote_from_bench(
        self,
        raid,
        message: Optional[discord.Message],
        guild: discord.Guild,
    ) -> None:
        if raid.status != "open":
            return

        for role in (ROLE_TANK, ROLE_HEALER, ROLE_DPS):
            limit = get_role_limit(raid, role)
            if limit <= 0:
                continue

            while True:
                signups = await self.raid_store.get_signups_by_role(raid.id)
                current_count = len(signups.get(role, []))
                if current_count >= limit:
                    break

                bench_candidates = await self.raid_store.get_bench_queue(
                    raid.id, preferred_role=role
                )
                if not bench_candidates:
                    bench_candidates = await self.raid_store.get_bench_queue(raid.id)
                if not bench_candidates:
                    break

                user_id = bench_candidates[0]
                await self.raid_store.upsert_signup(raid.id, user_id, role)
                member = guild.get_member(user_id)
                if not member:
                    try:
                        member = await guild.fetch_member(user_id)
                    except Exception:
                        member = None
                if message and member:
                    try:
                        await message.remove_reaction(ROLE_EMOJIS[ROLE_BENCH], member)
                    except Exception:
                        pass
                await self._send_dm(
                    member,
                    f"✅ You were moved from bench to {role.upper()}.",
                )

    async def _maybe_ping_open_slots(
        self,
        raid,
        message: Optional[discord.Message],
        guild: discord.Guild,
    ) -> None:
        if not self.config.raid_open_slot_ping_enabled:
            return
        if raid.status != "open":
            return
        role_id = self.config.raid_participant_role_id
        if not role_id:
            return
        role = guild.get_role(role_id)
        if not role:
            return

        signups = await self.raid_store.get_signups_by_role(raid.id)
        open_tanks = max(raid.tanks_needed - len(signups.get(ROLE_TANK, [])), 0)
        open_healers = max(raid.healers_needed - len(signups.get(ROLE_HEALER, [])), 0)
        open_dps = max(raid.dps_needed - len(signups.get(ROLE_DPS, [])), 0)
        total_open = open_tanks + open_healers + open_dps
        if total_open <= 0:
            return

        cooldown = self.config.raid_open_slot_ping_minutes * 60
        now_ts = int(datetime.now(timezone.utc).timestamp())
        last_sent = await self.raid_store.get_alert_sent_at(raid.id, "open_slots")
        if last_sent and now_ts - last_sent < cooldown:
            return

        parts = []
        if open_tanks:
            parts.append(f"Tanks: {open_tanks}")
        if open_healers:
            parts.append(f"Healer: {open_healers}")
        if open_dps:
            parts.append(f"DPS: {open_dps}")
        slot_text = " | ".join(parts)
        content = f"{role.mention} Open slots for **{raid.title}**: {slot_text}"
        try:
            if message:
                await message.channel.send(content)
                await self.raid_store.mark_alert_sent(raid.id, "open_slots")
        except Exception:
            logger.warning("Failed to send open slot ping", exc_info=True)

    @discord.ui.button(label="✅ Speichern", style=discord.ButtonStyle.green, row=4)
    async def save(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if self.counts[ROLE_TANK] + self.counts[ROLE_HEALER] + self.counts[ROLE_DPS] == 0:
            await interaction.response.send_message(
                "❌ Please set at least one slot for Tank/Healer/DPS.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if not guild:
            await interaction.response.send_message(
                "❌ Server not found.",
                ephemeral=True,
            )
            return

        await self.raid_store.update_raid_slots(
            self.raid_id,
            self.counts[ROLE_TANK],
            self.counts[ROLE_HEALER],
            self.counts[ROLE_DPS],
            self.counts[ROLE_BENCH],
        )

        raid, raid_message = await self._get_raid_message(guild)
        if raid and raid_message:
            await self._maybe_ping_open_slots(raid, raid_message, guild)
            signups = await self.raid_store.get_signups_by_role(raid.id)
            bench_preferences = await self.raid_store.get_bench_preferences(raid.id)
            confirmed = await self.raid_store.get_confirmed_user_ids(raid.id)
            no_shows = await self.raid_store.get_no_show_user_ids(raid.id)
            embed = build_raid_embed(
                raid,
                signups,
                self.config.raid_timezone,
                confirmed,
                no_shows,
                bench_preferences=bench_preferences,
            )
            try:
                await raid_message.edit(embed=embed)
            except Exception:
                pass

        for item in self.children:
            item.disabled = True
        self.stop()

        await interaction.response.edit_message(
            embed=discord.Embed(
                title="✅ Slots updated",
                color=discord.Color.green(),
            ),
            view=self,
        )

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red, row=4)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for item in self.children:
            item.disabled = True
        self.stop()
        await interaction.response.edit_message(
            content="❌ Slot editing cancelled.",
            embed=None,
            view=self,
        )


class RaidCreateModal(discord.ui.Modal):
    """Modal for raid basics."""

    def __init__(self, cog: "RaidCommand"):
        super().__init__(title="Create raid")
        self.cog = cog

        self.title_input = discord.ui.TextInput(
            label="Title",
            placeholder="e.g. WWM guild raid",
            max_length=80,
        )
        self.desc_input = discord.ui.TextInput(
            label="Description (optional)",
            placeholder="Short description or note",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=400,
        )

        self.add_item(self.title_input)
        self.add_item(self.desc_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        view = RaidGameModeView(
            bot=self.cog.bot,
            config=self.cog.config,
            raid_store=self.cog.raid_store,
            template_store=self.cog.template_store,
            guild_id=interaction.guild.id if interaction.guild else 0,
            requester_id=interaction.user.id,
            title=self.title_input.value,
            description=self.desc_input.value,
            game=GAME_WWM,
            mode=MODE_RAID,
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
        super().__init__(title="Edit raid")
        self.view_ref = view_ref

        self.title_input = discord.ui.TextInput(
            label="Title",
            placeholder="e.g. WWM guild raid",
            default=view_ref.title,
            max_length=80,
        )
        self.desc_input = discord.ui.TextInput(
            label="Description (optional)",
            placeholder="Short description or note",
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
            "✅ Raid draft updated.",
            ephemeral=True,
        )


class RaidPostEditModal(discord.ui.Modal):
    """Modal to edit a posted raid."""

    def __init__(self, view_ref, raid):
        super().__init__(title="Edit raid")
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
            label="Title",
            placeholder="e.g. WWM guild raid",
            default=raid.title,
            max_length=80,
        )
        self.desc_input = discord.ui.TextInput(
            label="Description (optional)",
            placeholder="Short description or note",
            required=False,
            default=raid.description or "",
            style=discord.TextStyle.paragraph,
            max_length=400,
        )
        self.date_input = discord.ui.TextInput(
            label="Date (DD.MM.YYYY)",
            placeholder="10.02.2025",
            default=date_value,
            max_length=10,
        )
        self.time_input = discord.ui.TextInput(
            label="Time (HH:MM)",
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
                "❌ Start time is in the past.",
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
                "✅ Raid updated.",
                ephemeral=True,
            )
            return

        signups = await self.view_ref.raid_store.get_signups_by_role(self.raid.id)
        bench_preferences = await self.view_ref.raid_store.get_bench_preferences(
            self.raid.id
        )
        confirmed = await self.view_ref.raid_store.get_confirmed_user_ids(self.raid.id)
        no_shows = await self.view_ref.raid_store.get_no_show_user_ids(self.raid.id)
        embed = build_raid_embed(
            updated,
            signups,
            self.view_ref.config.raid_timezone,
            confirmed,
            no_shows,
            bench_preferences=bench_preferences,
        )
        await interaction.message.edit(embed=embed, view=self.view_ref)

        await interaction.response.send_message(
            "✅ Raid updated.",
            ephemeral=True,
        )


class RaidStartView(discord.ui.View):
    """Persistent view for starting raid creation."""

    def __init__(self, cog: "RaidCommand"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="🗡️ Create raid",
        style=discord.ButtonStyle.green,
        custom_id="guildscout_raid_start_v1",
    )
    async def start_raid(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This button only works in a server.",
                ephemeral=True,
            )
            return

        if not self.cog._has_creator_permission(interaction):
            await interaction.response.send_message(
                "❌ You do not have permission to create raids.",
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
            channel_hint = manage_channel.mention if manage_channel else "the raid channel"
            await interaction.response.send_message(
                f"❌ Please use {channel_hint} to create raids.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(RaidCreateModal(self.cog))


class BenchRoleSelect(discord.ui.Select):
    """Dropdown for selecting a role to promote into."""

    def __init__(self, view_ref: "BenchPromotionView"):
        options = [
            discord.SelectOption(label="Tank", value=ROLE_TANK),
            discord.SelectOption(label="Healer", value=ROLE_HEALER),
            discord.SelectOption(label="DPS", value=ROLE_DPS),
        ]
        super().__init__(placeholder="Select role", options=options, row=0)
        self.view_ref = view_ref

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view_ref.selected_role = self.values[0]
        await interaction.response.defer()


class BenchUserSelect(discord.ui.Select):
    """Dropdown for selecting a bench user."""

    def __init__(self, view_ref: "BenchPromotionView", options: list[discord.SelectOption]):
        super().__init__(placeholder="Select bench user", options=options, row=1)
        self.view_ref = view_ref

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view_ref.selected_user_id = int(self.values[0])
        await interaction.response.defer()


class BenchPromotionView(discord.ui.View):
    """Promote a bench signup into an open role."""

    def __init__(
        self,
        config: Config,
        raid_store: RaidStore,
        raid,
        raid_message: Optional[discord.Message],
        guild: discord.Guild,
        requester_id: int,
        bench_options: list[discord.SelectOption],
    ):
        super().__init__(timeout=300)
        self.config = config
        self.raid_store = raid_store
        self.raid = raid
        self.raid_message = raid_message
        self.guild = guild
        self.requester_id = requester_id
        self.selected_role: Optional[str] = None
        self.selected_user_id: Optional[int] = None
        self.add_item(BenchRoleSelect(self))
        self.add_item(BenchUserSelect(self, bench_options))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "❌ Only the requester can use this menu.",
                ephemeral=True,
            )
            return False
        return True

    def _get_participant_role(self) -> Optional[discord.Role]:
        role_id = self.config.raid_participant_role_id
        if not role_id:
            fallback = None
            for name in ("Raid Participants", "Raid Teilnehmer"):
                fallback = discord.utils.get(self.guild.roles, name=name)
                if fallback:
                    break
            if fallback:
                self.config.set_raid_participant_role_id(fallback.id)
            return fallback
        return self.guild.get_role(role_id)

    async def _ensure_participant_role(self, member: Optional[discord.Member]) -> None:
        if not member:
            return
        role = self._get_participant_role()
        if not role or role in member.roles:
            return
        try:
            await member.add_roles(role, reason="Raid signup promotion")
        except Exception:
            logger.warning("Failed to add raid participant role", exc_info=True)

    async def _get_member(self, user_id: int) -> Optional[discord.Member]:
        member = self.guild.get_member(user_id)
        if member:
            return member
        try:
            return await self.guild.fetch_member(user_id)
        except Exception:
            return None

    async def _send_dm(self, member: Optional[discord.Member], message: str) -> None:
        if not member:
            return
        try:
            await member.send(message)
        except Exception:
            pass

    @discord.ui.button(label="⬆️ Promote", style=discord.ButtonStyle.green, row=2)
    async def promote(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not self.selected_role or not self.selected_user_id:
            await interaction.response.send_message(
                "❌ Please select a role and a bench user.",
                ephemeral=True,
            )
            return

        raid = await self.raid_store.get_raid(self.raid.id)
        if not raid or raid.status != "open":
            await interaction.response.send_message(
                "❌ Raid is not open.",
                ephemeral=True,
            )
            return

        current_role = await self.raid_store.get_user_role(
            raid.id, self.selected_user_id
        )
        if current_role != ROLE_BENCH:
            await interaction.response.send_message(
                "❌ That user is no longer on bench.",
                ephemeral=True,
            )
            return

        signups = await self.raid_store.get_signups_by_role(raid.id)
        limit = get_role_limit(raid, self.selected_role)
        if limit <= 0:
            await interaction.response.send_message(
                "❌ No slots configured for that role.",
                ephemeral=True,
            )
            return
        current_count = len(signups.get(self.selected_role, []))
        if current_count >= limit:
            await interaction.response.send_message(
                "❌ No open slots for that role.",
                ephemeral=True,
            )
            return

        await self.raid_store.upsert_signup(raid.id, self.selected_user_id, self.selected_role)

        member = await self._get_member(self.selected_user_id)
        await self._ensure_participant_role(member)
        if self.raid_message and member:
            try:
                await self.raid_message.remove_reaction(ROLE_EMOJIS[ROLE_BENCH], member)
                await self.raid_message.remove_reaction(
                    ROLE_EMOJIS[self.selected_role], member
                )
            except Exception:
                pass
        await self._send_dm(
            member,
            (
                f"✅ You were moved from bench to {self.selected_role.upper()} "
                f"for **{self.raid.title}**.\n"
                f"Please contact the raid creator <@{self.raid.creator_id}> to confirm "
                "your spot (DM or voice is fine)."
            ),
        )

        if self.raid_message:
            updated_signups = await self.raid_store.get_signups_by_role(raid.id)
            bench_preferences = await self.raid_store.get_bench_preferences(raid.id)
            confirmed = await self.raid_store.get_confirmed_user_ids(raid.id)
            no_shows = await self.raid_store.get_no_show_user_ids(raid.id)
            embed = build_raid_embed(
                raid,
                updated_signups,
                self.config.raid_timezone,
                confirmed,
                no_shows,
                bench_preferences=bench_preferences,
            )
            try:
                await self.raid_message.edit(embed=embed)
            except Exception:
                pass

        for item in self.children:
            item.disabled = True
        self.stop()

        role_label = ROLE_LABELS.get(self.selected_role, self.selected_role.upper())
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="✅ Bench promotion complete",
                description=f"<@{self.selected_user_id}> -> {role_label}",
                color=discord.Color.green(),
            ),
            view=self,
        )

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red, row=2)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for item in self.children:
            item.disabled = True
        self.stop()
        await interaction.response.edit_message(
            content="❌ Bench promotion cancelled.",
            embed=None,
            view=self,
        )


class RaidRoleChoiceView(discord.ui.View):
    """Let a user pick a single role after multiple reactions."""

    def __init__(
        self,
        raid_cog: "RaidCommand",
        raid_id: int,
        guild_id: int,
        channel_id: int,
        message_id: int,
        user_id: int,
    ):
        super().__init__(timeout=600)
        self.raid_cog = raid_cog
        self.raid_id = raid_id
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.message_id = message_id
        self.user_id = user_id

    async def _handle_choice(
        self, interaction: discord.Interaction, requested_role: str
    ) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ This selection is not for you.",
                ephemeral=True,
            )
            return

        raid = await self.raid_cog.raid_store.get_raid(self.raid_id)
        if not raid or raid.status not in ("open", "locked"):
            await interaction.response.edit_message(
                content="❌ This raid is no longer open.",
                view=None,
            )
            self.stop()
            return

        guild = self.raid_cog.bot.get_guild(self.guild_id)
        if not guild:
            await interaction.response.edit_message(
                content="❌ Server not found.",
                view=None,
            )
            self.stop()
            return

        message = None
        channel = guild.get_channel(self.channel_id)
        if not isinstance(channel, discord.TextChannel):
            try:
                channel = await guild.fetch_channel(self.channel_id)
            except Exception:
                channel = None
        if isinstance(channel, discord.TextChannel):
            try:
                message = await channel.fetch_message(self.message_id)
            except Exception:
                message = None

        member = await self.raid_cog._get_member(guild, self.user_id)
        effective_role, note, _ = await self.raid_cog._apply_role_choice(
            raid, self.user_id, requested_role, member
        )

        if message and member:
            roles_to_remove = tuple(
                role for role in ROLE_SIGNUP_ROLES if role != effective_role
            )
            await self.raid_cog._remove_user_reactions(message, member, roles_to_remove)
        if message:
            await self.raid_cog._refresh_raid_message(raid.id, message)

        for item in self.children:
            item.disabled = True
        self.stop()

        if effective_role == ROLE_CANCEL:
            role_label = "No signup"
        else:
            role_label = ROLE_LABELS.get(effective_role, effective_role.upper())
        text = f"✅ Choice saved: {role_label}."
        if note:
            text = f"{text}\n{note}"
        await interaction.response.edit_message(
            content=text,
            view=self,
        )

    @discord.ui.button(label="Tank", style=discord.ButtonStyle.secondary, row=0)
    async def choose_tank(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        await self._handle_choice(interaction, ROLE_TANK)

    @discord.ui.button(label="Healer", style=discord.ButtonStyle.secondary, row=0)
    async def choose_healer(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        await self._handle_choice(interaction, ROLE_HEALER)

    @discord.ui.button(label="DPS", style=discord.ButtonStyle.secondary, row=0)
    async def choose_dps(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        await self._handle_choice(interaction, ROLE_DPS)

    @discord.ui.button(label="Bench", style=discord.ButtonStyle.secondary, row=0)
    async def choose_bench(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        await self._handle_choice(interaction, ROLE_BENCH)


class RaidManageView(discord.ui.View):
    """Persistent view for managing posted raids."""

    def __init__(self, config: Config, raid_store: RaidStore, template_store: RaidTemplateStore):
        super().__init__(timeout=None)
        self.config = config
        self.raid_store = raid_store
        self.template_store = template_store

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

    async def _refresh_history_embed(self, interaction: discord.Interaction) -> None:
        cog = interaction.client.get_cog("RaidCommand")
        if not cog or not hasattr(cog, "refresh_raid_history"):
            return
        try:
            await cog.refresh_raid_history(interaction.guild)
        except Exception:
            logger.warning("Failed to refresh raid history embed", exc_info=True)

    async def _get_raid_from_interaction(
        self, interaction: discord.Interaction
    ) -> Optional[object]:
        if not interaction.message:
            await interaction.response.send_message(
                "❌ Raid message not found.",
                ephemeral=True,
            )
            return None
        raid = await self.raid_store.get_raid_by_message_id(interaction.message.id)
        if not raid:
            await interaction.response.send_message(
                "❌ Raid not found.",
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
            fallback = None
            for name in ("Raid Participants", "Raid Teilnehmer"):
                fallback = discord.utils.get(guild.roles, name=name)
                if fallback:
                    break
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

    async def _cleanup_reminder_messages(
        self,
        channel: discord.TextChannel,
        raid_title: str,
        limit: int = 50,
    ) -> None:
        title_key = (raid_title or "").lower()
        async for message in channel.history(limit=limit):
            if not message.author or not message.author.bot:
                continue
            content = (message.content or "").lower()
            if "reminder" not in content and "erinnerung" not in content:
                continue
            if title_key and title_key not in content:
                continue
            try:
                await message.delete()
            except Exception:
                pass

    async def _cleanup_slot_pings(
        self,
        channel: discord.TextChannel,
        raid_title: str,
        limit: int = 50,
    ) -> None:
        title_key = (raid_title or "").lower()
        async for message in channel.history(limit=limit):
            if not message.author or not message.author.bot:
                continue
            content = (message.content or "").lower()
            if "open slots" not in content and "slots frei" not in content:
                continue
            if title_key and title_key not in content:
                continue
            try:
                await message.delete()
            except Exception:
                pass

    async def _cleanup_confirmation_message(
        self,
        channel: discord.TextChannel,
        raid_id: int,
    ) -> None:
        message_id = await self.raid_store.get_confirmation_message_id(raid_id)
        if not message_id:
            return
        try:
            message = await channel.fetch_message(message_id)
        except Exception:
            await self.raid_store.clear_confirmation_message(raid_id)
            return
        try:
            await message.delete()
        except Exception:
            pass
        await self.raid_store.clear_confirmation_message(raid_id)

    async def _send_raid_log(
        self,
        interaction: discord.Interaction,
        raid,
        status_label: str,
    ) -> None:
        channel_id = self.config.raid_log_channel_id
        if not channel_id:
            return
        guild = interaction.guild
        if not guild:
            return
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            try:
                channel = await guild.fetch_channel(channel_id)
            except Exception:
                return
        signups = await self.raid_store.get_signups_by_role(raid.id)
        confirmed = await self.raid_store.get_confirmed_user_ids(raid.id)
        no_shows = await self.raid_store.get_no_show_user_ids(raid.id)
        leave_reasons = await self.raid_store.list_leave_reasons(raid.id)
        embed = build_raid_log_embed(
            raid,
            signups,
            self.config.raid_timezone,
            confirmed,
            no_shows,
            leave_reasons,
            status_label=status_label,
        )
        try:
            await channel.send(embed=embed)
        except Exception:
            logger.warning("Failed to send raid log", exc_info=True)

    @discord.ui.button(
        label="✏️ Edit",
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
                "❌ You do not have permission to edit this raid.",
                ephemeral=True,
            )
            return
        if raid.status in ("closed", "cancelled"):
            await interaction.response.send_message(
                "❌ Closed/cancelled raids cannot be edited.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(RaidPostEditModal(self, raid))

    @discord.ui.button(
        label="🔒 Lock/Unlock",
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
                "❌ You do not have permission to lock/unlock.",
                ephemeral=True,
            )
            return
        if raid.status in ("closed", "cancelled"):
            await interaction.response.send_message(
                "❌ Closed/cancelled raids cannot be locked.",
                ephemeral=True,
            )
            return

        new_status = "locked" if raid.status == "open" else "open"
        await self.raid_store.update_status(raid.id, new_status)
        updated = await self.raid_store.get_raid(raid.id)
        if updated and interaction.message:
            signups = await self.raid_store.get_signups_by_role(raid.id)
            bench_preferences = await self.raid_store.get_bench_preferences(raid.id)
            confirmed = await self.raid_store.get_confirmed_user_ids(raid.id)
            no_shows = await self.raid_store.get_no_show_user_ids(raid.id)
            embed = build_raid_embed(
                updated,
                signups,
                self.config.raid_timezone,
                confirmed,
                no_shows,
                bench_preferences=bench_preferences,
            )
            await interaction.message.edit(embed=embed, view=self)

        await interaction.response.send_message(
            "✅ Raid locked." if new_status == "locked" else "✅ Raid is open again.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="⏭️ Follow-up",
        style=discord.ButtonStyle.secondary,
        custom_id="guildscout_raid_followup_v1",
        row=1,
    )
    async def followup(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        raid = await self._get_raid_from_interaction(interaction)
        if not raid:
            return

        if not self._can_manage(interaction, raid):
            await interaction.response.send_message(
                "❌ You do not have permission to create a follow-up raid.",
                ephemeral=True,
            )
            return

        try:
            date_value, time_value, start_ts = get_default_date_time(
                self.config.raid_timezone
            )
        except ValueError as exc:
            await interaction.response.send_message(
                f"❌ {exc}",
                ephemeral=True,
            )
            return

        counts = {
            ROLE_TANK: raid.tanks_needed,
            ROLE_HEALER: raid.healers_needed,
            ROLE_DPS: raid.dps_needed,
            ROLE_BENCH: raid.bench_needed,
        }

        view = RaidScheduleView(
            bot=interaction.client,
            config=self.config,
            raid_store=self.raid_store,
            template_store=self.template_store,
            guild_id=interaction.guild.id if interaction.guild else 0,
            requester_id=interaction.user.id,
            title=raid.title,
            description=raid.description,
            start_ts=start_ts,
            timezone_name=self.config.raid_timezone,
            date_value=date_value,
            time_value=time_value,
            game=raid.game,
            mode=raid.mode,
            counts=counts,
        )

        await interaction.response.send_message(
            embed=view.build_embed(),
            view=view,
            ephemeral=True,
        )
        view.message = await interaction.original_response()

    @discord.ui.button(
        label="⚙️ Slots",
        style=discord.ButtonStyle.secondary,
        custom_id="guildscout_raid_slots_v1",
        row=1,
    )
    async def edit_slots(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        raid = await self._get_raid_from_interaction(interaction)
        if not raid:
            return

        if not self._can_manage(interaction, raid):
            await interaction.response.send_message(
                "❌ You do not have permission to edit slots.",
                ephemeral=True,
            )
            return

        counts = {
            ROLE_TANK: raid.tanks_needed,
            ROLE_HEALER: raid.healers_needed,
            ROLE_DPS: raid.dps_needed,
            ROLE_BENCH: raid.bench_needed,
        }
        view = RaidSlotEditView(
            config=self.config,
            raid_store=self.raid_store,
            requester_id=interaction.user.id,
            raid_id=raid.id,
            title=raid.title,
            counts=counts,
        )
        await interaction.response.send_message(
            embed=view.build_embed(),
            view=view,
            ephemeral=True,
        )
        view.message = await interaction.original_response()

    @discord.ui.button(
        label="🪑 Promote",
        style=discord.ButtonStyle.secondary,
        custom_id="guildscout_raid_promote_v1",
        row=2,
    )
    async def promote_from_bench(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        raid = await self._get_raid_from_interaction(interaction)
        if not raid:
            return

        if not self._can_manage(interaction, raid):
            await interaction.response.send_message(
                "❌ You do not have permission to promote from bench.",
                ephemeral=True,
            )
            return
        if raid.status != "open":
            await interaction.response.send_message(
                "❌ Raid is not open.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if not guild:
            await interaction.response.send_message(
                "❌ Server not found.",
                ephemeral=True,
            )
            return

        signups = await self.raid_store.list_signups(raid.id)
        bench_entries = [entry for entry in signups if entry.get("role") == ROLE_BENCH]
        if not bench_entries:
            await interaction.response.send_message(
                "ℹ️ No bench signups available.",
                ephemeral=True,
            )
            return

        truncated = len(bench_entries) > 25
        bench_entries = bench_entries[:25]
        options: list[discord.SelectOption] = []
        for entry in bench_entries:
            user_id = entry.get("user_id")
            if not user_id:
                continue
            member = guild.get_member(int(user_id))
            label = member.display_name if member else f"User {user_id}"
            preferred_role = entry.get("preferred_role")
            preferred_label = ROLE_LABELS.get(preferred_role, "Any") if preferred_role else "Any"
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    value=str(user_id),
                    description=f"pref: {preferred_label}"[:100],
                )
            )
        if not options:
            await interaction.response.send_message(
                "ℹ️ No bench signups available.",
                ephemeral=True,
            )
            return

        view = BenchPromotionView(
            config=self.config,
            raid_store=self.raid_store,
            raid=raid,
            raid_message=interaction.message,
            guild=guild,
            requester_id=interaction.user.id,
            bench_options=options,
        )

        signups_by_role = await self.raid_store.get_signups_by_role(raid.id)
        open_tanks = max(raid.tanks_needed - len(signups_by_role.get(ROLE_TANK, [])), 0)
        open_healers = max(
            raid.healers_needed - len(signups_by_role.get(ROLE_HEALER, [])), 0
        )
        open_dps = max(raid.dps_needed - len(signups_by_role.get(ROLE_DPS, [])), 0)
        parts = []
        if open_tanks:
            parts.append(f"Tanks: {open_tanks}")
        if open_healers:
            parts.append(f"Healer: {open_healers}")
        if open_dps:
            parts.append(f"DPS: {open_dps}")
        slot_text = " | ".join(parts) if parts else "No open slots."
        description = "Select a role and a bench user to promote."
        if truncated:
            description += " Showing first 25 bench signups."

        embed = discord.Embed(
            title="🪑 Bench promotion",
            description=description,
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Open slots", value=slot_text, inline=False)

        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(
        label="✅ Close",
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
                "❌ You do not have permission to close this raid.",
                ephemeral=True,
            )
            return
        if raid.status in ("closed", "cancelled"):
            await interaction.response.send_message(
                "❌ Raid is already closed/cancelled.",
                ephemeral=True,
            )
            return

        await self.raid_store.close_raid(raid.id)
        await self.raid_store.archive_participation(raid.id, "closed")
        await self._send_raid_log(interaction, raid, "Closed")
        channel = interaction.channel
        if interaction.message:
            try:
                await interaction.message.delete()
            except Exception:
                updated = await self.raid_store.get_raid(raid.id)
                if updated:
                    signups = await self.raid_store.get_signups_by_role(raid.id)
                    bench_preferences = await self.raid_store.get_bench_preferences(
                        raid.id
                    )
                    confirmed = await self.raid_store.get_confirmed_user_ids(raid.id)
                    no_shows = await self.raid_store.get_no_show_user_ids(raid.id)
                    embed = build_raid_embed(
                        updated,
                        signups,
                        self.config.raid_timezone,
                        confirmed,
                        no_shows,
                        bench_preferences=bench_preferences,
                    )
                    await interaction.message.edit(embed=embed, view=self)
                    try:
                        await interaction.message.clear_reactions()
                    except Exception:
                        pass
        if isinstance(channel, discord.TextChannel):
            await self._cleanup_reminder_messages(channel, raid.title)
            await self._cleanup_slot_pings(channel, raid.title)
            await self._cleanup_confirmation_message(channel, raid.id)
        await self._remove_participant_roles(interaction, raid.id)
        await self._refresh_history_embed(interaction)

        await interaction.response.send_message(
            "✅ Raid closed.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="🛑 Cancel",
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
                "❌ You do not have permission to cancel this raid.",
                ephemeral=True,
            )
            return
        if raid.status == "cancelled":
            await interaction.response.send_message(
                "ℹ️ Raid is already cancelled.",
                ephemeral=True,
            )
            return
        if raid.status == "closed":
            await interaction.response.send_message(
                "❌ Closed raids cannot be cancelled.",
                ephemeral=True,
            )
            return

        await self.raid_store.update_status(raid.id, "cancelled")
        await self.raid_store.archive_participation(raid.id, "cancelled")
        await self._send_raid_log(interaction, raid, "Cancelled")
        channel = interaction.channel
        if interaction.message:
            try:
                await interaction.message.delete()
            except Exception:
                updated = await self.raid_store.get_raid(raid.id)
                if updated:
                    signups = await self.raid_store.get_signups_by_role(raid.id)
                    bench_preferences = await self.raid_store.get_bench_preferences(
                        raid.id
                    )
                    confirmed = await self.raid_store.get_confirmed_user_ids(raid.id)
                    no_shows = await self.raid_store.get_no_show_user_ids(raid.id)
                    embed = build_raid_embed(
                        updated,
                        signups,
                        self.config.raid_timezone,
                        confirmed,
                        no_shows,
                        bench_preferences=bench_preferences,
                    )
                    await interaction.message.edit(embed=embed, view=self)
                    try:
                        await interaction.message.clear_reactions()
                    except Exception:
                        pass
        if isinstance(channel, discord.TextChannel):
            await self._cleanup_reminder_messages(channel, raid.title)
            await self._cleanup_slot_pings(channel, raid.title)
            await self._cleanup_confirmation_message(channel, raid.id)
        await self._remove_participant_roles(interaction, raid.id)
        await self._refresh_history_embed(interaction)

        await interaction.response.send_message(
            "🛑 Raid cancelled.",
            ephemeral=True,
        )


class RaidCommand(commands.Cog):
    """Cog for raid scheduling and configuration."""

    def __init__(
        self,
        bot: commands.Bot,
        config: Config,
        raid_store: RaidStore,
        template_store: RaidTemplateStore,
    ):
        self.bot = bot
        self.config = config
        self.raid_store = raid_store
        self.template_store = template_store
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
        role = None
        for name in ("Raid Participants", "Raid Teilnehmer"):
            role = discord.utils.get(guild.roles, name=name)
            if role:
                break
        if role:
            self.config.set_raid_participant_role_id(role.id)
            return role
        try:
            role = await guild.create_role(
                name="Raid Participants",
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
        info_message = await self._upsert_raid_info_message(channel)
        await self._cleanup_raid_info_channel(
            channel,
            {message.id for message in (info_message,) if message is not None},
        )
        await self.refresh_raid_history(guild)

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

    async def _build_raid_history_embed(
        self, guild: discord.Guild
    ) -> discord.Embed:
        embed = discord.Embed(
            title="📊 Raid Participation (All-Time)",
            description="Top participation with role counts (auto-updated).",
            color=discord.Color.blurple(),
        )
        embed.timestamp = datetime.now(timezone.utc)

        leaderboard = await self.raid_store.get_participation_leaderboard(
            limit=STATS_TOP_LIMIT
        )
        if leaderboard:
            lines = []
            for index, entry in enumerate(leaderboard, start=1):
                user_id = entry.get("user_id")
                mention = f"<@{user_id}>"
                role_parts = []
                for role_key in (ROLE_TANK, ROLE_HEALER, ROLE_DPS, ROLE_BENCH):
                    count = entry.get(role_key, 0)
                    if count:
                        role_parts.append(f"{ROLE_EMOJIS[role_key]} {count}")
                roles_text = " ".join(role_parts) if role_parts else "no data"
                total = entry.get("total", 0)
                lines.append(f"{index}. {mention} — {total} ({roles_text})")
            value = "\n".join(lines)
        else:
            value = "No completed raids yet."

        embed.add_field(name="Top participants", value=value, inline=False)
        embed.set_footer(text="Admin: /raid-user-stats for details")
        return embed

    async def _upsert_raid_history_message(
        self, channel: discord.TextChannel, guild: discord.Guild
    ) -> Optional[discord.Message]:
        embed = await self._build_raid_history_embed(guild)

        message_id = self.config.raid_history_message_id
        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(embed=embed)
                return message
            except discord.NotFound:
                self.config.set_raid_history_message_id(None)
            except Exception as exc:
                logger.warning("Failed to update raid history message: %s", exc)

        message = await channel.send(embed=embed)
        self.config.set_raid_history_message_id(message.id)
        return message

    async def _cleanup_raid_info_channel(
        self, channel: discord.TextChannel, keep_ids: set[int]
    ) -> None:
        bot_user = getattr(self.bot, "user", None)
        if not bot_user:
            return
        try:
            async for message in channel.history(limit=50):
                if message.id in keep_ids:
                    continue
                if message.author.id != bot_user.id:
                    continue
                if not message.embeds:
                    continue
                title = message.embeds[0].title or ""
                if (
                    title.startswith("🗡️ Raid Guide")
                    or title.startswith("📚 Raid-Historie")
                    or title.startswith("📊 Raid Participation")
                ):
                    await message.delete()
        except Exception:
            logger.warning("Failed to clean raid info channel", exc_info=True)

    async def _get_member(
        self, guild: discord.Guild, user_id: int
    ) -> Optional[discord.Member]:
        member = guild.get_member(user_id)
        if member:
            return member
        try:
            return await guild.fetch_member(user_id)
        except Exception:
            return None

    async def _send_dm(self, member: Optional[discord.Member], message: str) -> None:
        if not member:
            return
        try:
            await member.send(message)
        except Exception:
            pass

    async def _delete_message_later(
        self, message: discord.Message, delay_seconds: int = 600
    ) -> None:
        await asyncio.sleep(delay_seconds)
        try:
            await message.delete()
        except Exception:
            pass

    async def _prompt_bench_preference(
        self,
        raid,
        member: Optional[discord.Member],
        message: Optional[discord.Message],
    ) -> None:
        if not member:
            return
        view = BenchPreferenceView(self.raid_store, raid.id, member.id)
        try:
            await member.send(
                (
                    f"ℹ️ You are on bench for **{raid.title}**.\n"
                    "Pick a preferred role (or Any) so leaders can choose you faster."
                ),
                view=view,
            )
            return
        except Exception:
            pass

        if not message:
            return
        try:
            prompt_view = BenchPreferenceView(self.raid_store, raid.id, member.id)
            prompt = await message.channel.send(
                (
                    f"{member.mention} I couldn't DM you.\n"
                    "Pick a bench preference below (or react with 🛡️/💉/⚔️ "
                    "on the raid post)."
                ),
                view=prompt_view,
            )
            self.bot.loop.create_task(self._delete_message_later(prompt))
        except Exception:
            pass

    def _get_participant_role_for_guild(
        self, guild: discord.Guild
    ) -> Optional[discord.Role]:
        role_id = self.config.raid_participant_role_id
        if not role_id:
            fallback = None
            for name in ("Raid Participants", "Raid Teilnehmer"):
                fallback = discord.utils.get(guild.roles, name=name)
                if fallback:
                    break
            if fallback:
                self.config.set_raid_participant_role_id(fallback.id)
            return fallback
        return guild.get_role(role_id)

    async def _ensure_participant_role_for_member(
        self, member: Optional[discord.Member]
    ) -> None:
        if not member:
            return
        role = self._get_participant_role_for_guild(member.guild)
        if not role or role in member.roles:
            return
        try:
            await member.add_roles(role, reason="Raid signup")
        except Exception:
            logger.warning("Failed to add raid participant role", exc_info=True)

    async def _remove_participant_role_for_member_if_unused(
        self,
        member: Optional[discord.Member],
    ) -> None:
        if not member:
            return
        role = self._get_participant_role_for_guild(member.guild)
        if not role or role not in member.roles:
            return
        active_count = await self.raid_store.count_user_active_signups(
            member.guild.id,
            member.id,
        )
        if active_count > 0:
            return
        try:
            await member.remove_roles(role, reason="Raid signup removed")
        except Exception:
            logger.warning("Failed to remove raid participant role", exc_info=True)

    async def _remove_user_reactions(
        self,
        message: discord.Message,
        member: Optional[discord.Member],
        roles: tuple[str, ...],
    ) -> None:
        if not member:
            return
        for role in roles:
            emoji = ROLE_EMOJIS.get(role)
            if not emoji:
                continue
            try:
                await message.remove_reaction(emoji, member)
            except Exception:
                pass

    async def _refresh_raid_message(
        self, raid_id: int, message: discord.Message
    ) -> None:
        raid = await self.raid_store.get_raid(raid_id)
        if not raid:
            return
        signups = await self.raid_store.get_signups_by_role(raid.id)
        bench_preferences = await self.raid_store.get_bench_preferences(raid.id)
        confirmation_message_id = await self.raid_store.get_confirmation_message_id(
            raid.id
        )
        confirmed = None
        no_shows = None
        if confirmation_message_id:
            confirmed = await self.raid_store.get_confirmed_user_ids(raid.id)
            no_shows = await self.raid_store.get_no_show_user_ids(raid.id)
        embed = build_raid_embed(
            raid,
            signups,
            self.config.raid_timezone,
            confirmed,
            no_shows,
            bench_preferences=bench_preferences,
        )
        try:
            await message.edit(embed=embed)
        except Exception:
            logger.warning("Failed to update raid message %s", raid_id, exc_info=True)

    async def _apply_role_choice(
        self,
        raid,
        user_id: int,
        requested_role: str,
        member: Optional[discord.Member],
    ) -> tuple[str, Optional[str], bool]:
        current_role = await self.raid_store.get_user_role(raid.id, user_id)
        signups = await self.raid_store.get_signups_by_role(raid.id)
        bench_limit = get_role_limit(raid, ROLE_BENCH)
        bench_count = len(signups.get(ROLE_BENCH, []))
        bench_available = bench_limit > 0 and (
            bench_count < bench_limit or current_role == ROLE_BENCH
        )

        note: Optional[str] = None
        changed = False

        if requested_role == ROLE_BENCH:
            if not bench_available and current_role != ROLE_BENCH:
                note = "❌ Bench is already full."
                return current_role or ROLE_CANCEL, note, False
            existing_preferred = None
            if current_role == ROLE_BENCH:
                existing_preferred = await self.raid_store.get_user_preferred_role(
                    raid.id, user_id
                )
            if current_role in (ROLE_TANK, ROLE_HEALER, ROLE_DPS):
                preferred_role = current_role
            else:
                preferred_role = existing_preferred
            if current_role == ROLE_BENCH:
                if preferred_role != existing_preferred:
                    await self.raid_store.set_preferred_role(
                        raid.id, user_id, preferred_role
                    )
                    changed = True
            else:
                await self.raid_store.upsert_signup_with_preference(
                    raid.id, user_id, ROLE_BENCH, preferred_role
                )
                await self._ensure_participant_role_for_member(member)
                changed = True
            return ROLE_BENCH, note, changed

        if current_role == requested_role:
            return current_role, None, False

        if raid.status == "locked":
            if not bench_available and current_role != ROLE_BENCH:
                note = "❌ Signups are locked and bench is full."
                return current_role or ROLE_CANCEL, note, False
            if current_role == ROLE_BENCH:
                existing_preferred = await self.raid_store.get_user_preferred_role(
                    raid.id, user_id
                )
                if requested_role != existing_preferred:
                    await self.raid_store.set_preferred_role(
                        raid.id, user_id, requested_role
                    )
                    changed = True
                note = "ℹ️ Signups locked: you remain on bench (preference saved)."
                return ROLE_BENCH, note, changed
            await self.raid_store.upsert_signup_with_preference(
                raid.id, user_id, ROLE_BENCH, requested_role
            )
            await self._ensure_participant_role_for_member(member)
            note = "ℹ️ Signups locked: you were moved to bench (preference saved)."
            return ROLE_BENCH, note, True

        limit = get_role_limit(raid, requested_role)
        current_count = len(signups.get(requested_role, []))
        if limit <= 0 or (current_count >= limit and current_role != requested_role):
            if not bench_available and current_role != ROLE_BENCH:
                note = "❌ That role is full and the bench is also full."
                return current_role or ROLE_CANCEL, note, False
            if current_role == ROLE_BENCH:
                existing_preferred = await self.raid_store.get_user_preferred_role(
                    raid.id, user_id
                )
                if requested_role != existing_preferred:
                    await self.raid_store.set_preferred_role(
                        raid.id, user_id, requested_role
                    )
                    changed = True
                note = "ℹ️ Role full: you remain on bench (preference saved)."
                return ROLE_BENCH, note, changed
            await self.raid_store.upsert_signup_with_preference(
                raid.id, user_id, ROLE_BENCH, requested_role
            )
            await self._ensure_participant_role_for_member(member)
            note = "ℹ️ Role full: you were moved to bench (preference saved)."
            return ROLE_BENCH, note, True

        await self.raid_store.upsert_signup(raid.id, user_id, requested_role)
        await self._ensure_participant_role_for_member(member)
        return requested_role, None, True

    async def _collect_reaction_users(
        self, message: discord.Message
    ) -> Dict[str, set[int]]:
        users_by_role: Dict[str, set[int]] = {
            role: set() for role in ROLE_EMOJI_TO_ROLE.values()
        }
        for reaction in message.reactions:
            role = ROLE_EMOJI_TO_ROLE.get(str(reaction.emoji))
            if not role:
                continue
            try:
                async for user in reaction.users(limit=None):
                    if user.bot:
                        continue
                    users_by_role[role].add(int(user.id))
            except Exception:
                continue
        return users_by_role

    async def _reconcile_raid_reactions(
        self,
        raid,
        message: discord.Message,
        guild: discord.Guild,
    ) -> None:
        users_by_role = await self._collect_reaction_users(message)
        cancel_users = users_by_role.get(ROLE_CANCEL, set())

        user_roles: Dict[int, set[str]] = {}
        for role in ROLE_SIGNUP_ROLES:
            for user_id in users_by_role.get(role, set()):
                user_roles.setdefault(user_id, set()).add(role)

        processed: set[int] = set()
        roles_to_clear = ROLE_SIGNUP_ROLES + (ROLE_CANCEL,)

        for user_id in cancel_users:
            processed.add(user_id)
            await self.raid_store.remove_signup(raid.id, user_id)
            member = await self._get_member(guild, user_id)
            if member:
                await self._remove_user_reactions(message, member, roles_to_clear)
                await self._remove_participant_role_for_member_if_unused(member)
                await self._send_dm(
                    member, f"✅ You left **{raid.title}**."
                )

        for user_id, roles in user_roles.items():
            if len(roles) <= 1 or user_id in processed:
                continue
            processed.add(user_id)
            member = await self._get_member(guild, user_id)
            if member:
                jump_url = message.jump_url
                view = RaidRoleChoiceView(
                    self,
                    raid.id,
                    raid.guild_id,
                    raid.channel_id,
                    raid.message_id,
                    user_id,
                )
                try:
                    await member.send(
                        (
                            f"⚠️ You reacted to multiple roles for **{raid.title}**.\n"
                            f"Please pick a single role below.\n{jump_url}"
                        ),
                        view=view,
                    )
                except Exception:
                    pass

        for user_id, roles in user_roles.items():
            if len(roles) != 1 or user_id in processed:
                continue
            requested_role = next(iter(roles))
            member = await self._get_member(guild, user_id)
            effective_role, note, _ = await self._apply_role_choice(
                raid, user_id, requested_role, member
            )
            if member and requested_role != effective_role:
                await self._remove_user_reactions(
                    message, member, (requested_role,)
                )
            if note:
                await self._send_dm(member, note)

        users_with_reactions = set(user_roles.keys())
        signups = await self.raid_store.list_signups(raid.id)
        for entry in signups:
            role = entry.get("role")
            user_id = entry.get("user_id")
            if not user_id or role not in (ROLE_TANK, ROLE_HEALER, ROLE_DPS):
                continue
            if int(user_id) in users_with_reactions:
                continue
            await self.raid_store.remove_signup(raid.id, int(user_id))
            member = await self._get_member(guild, int(user_id))
            await self._remove_participant_role_for_member_if_unused(member)

    async def refresh_raid_history(self, guild: Optional[discord.Guild] = None) -> None:
        """Refresh the raid stats embed if configured."""
        if not self.config.raid_post_channel_id:
            return
        if guild is None:
            guild = self.bot.get_guild(self.config.guild_id)
        if not guild:
            return
        channel = guild.get_channel(self.config.raid_post_channel_id)
        if not isinstance(channel, discord.TextChannel):
            try:
                channel = await guild.fetch_channel(self.config.raid_post_channel_id)
            except Exception:
                return
        if not isinstance(channel, discord.TextChannel):
            return
        await self._upsert_raid_history_message(channel, guild)

    async def refresh_active_raids(self, guild: Optional[discord.Guild] = None) -> int:
        """Refresh all open/locked raid embeds and views after startup."""
        if not self.config.raid_enabled:
            return 0
        if guild is None:
            guild = self.bot.get_guild(self.config.guild_id)
        if not guild:
            return 0

        now_ts = int(datetime.now(timezone.utc).timestamp())
        upcoming = await self.raid_store.list_active_raids(now_ts)
        ongoing = await self.raid_store.list_raids_to_close(now_ts)
        raid_map = {raid.id: raid for raid in upcoming}
        for raid in ongoing:
            raid_map[raid.id] = raid

        refreshed = 0
        for raid in raid_map.values():
            if not raid.message_id:
                continue

            channel = guild.get_channel(raid.channel_id)
            if not isinstance(channel, discord.TextChannel):
                try:
                    channel = await guild.fetch_channel(raid.channel_id)
                except Exception:
                    continue
            if not isinstance(channel, discord.TextChannel):
                continue

            try:
                message = await channel.fetch_message(raid.message_id)
            except Exception:
                continue

            try:
                await self._reconcile_raid_reactions(raid, message, guild)
            except Exception:
                logger.warning(
                    "Failed to reconcile raid reactions for %s",
                    raid.id,
                    exc_info=True,
                )

            signups = await self.raid_store.get_signups_by_role(raid.id)
            bench_preferences = await self.raid_store.get_bench_preferences(raid.id)
            signups_raw = await self.raid_store.list_signups(raid.id)
            bench_missing: list[int] = []
            for entry in signups_raw:
                if entry.get("role") != ROLE_BENCH:
                    continue
                if entry.get("preferred_role"):
                    continue
                user_id = entry.get("user_id")
                if user_id is None:
                    continue
                try:
                    bench_missing.append(int(user_id))
                except (TypeError, ValueError):
                    continue
            confirmation_message_id = await self.raid_store.get_confirmation_message_id(
                raid.id
            )
            confirmed = None
            no_shows = None
            if confirmation_message_id:
                confirmed = await self.raid_store.get_confirmed_user_ids(raid.id)
                no_shows = await self.raid_store.get_no_show_user_ids(raid.id)

            embed = build_raid_embed(
                raid,
                signups,
                self.config.raid_timezone,
                confirmed,
                no_shows,
                bench_preferences=bench_preferences,
            )
            view = RaidManageView(self.config, self.raid_store, self.template_store)
            try:
                await message.edit(embed=embed, view=view)
                refreshed += 1
            except Exception:
                continue

            for user_id in bench_missing:
                alert_key = f"bench_pref_prompt:{user_id}"
                last_prompt = await self.raid_store.get_alert_sent_at(
                    raid.id, alert_key
                )
                if last_prompt:
                    continue
                member = await self._get_member(guild, user_id)
                await self._prompt_bench_preference(raid, member, message)
                await self.raid_store.mark_alert_sent(raid.id, alert_key)

            try:
                offline_seconds = getattr(self.bot, "last_offline_seconds", None)
                offline_text = None
                if isinstance(offline_seconds, int) and offline_seconds >= 0:
                    offline_text = _format_duration(offline_seconds)
                last_notice = await self.raid_store.get_alert_sent_at(
                    raid.id, "restart_notice"
                )
                if not last_notice or now_ts - last_notice > 600:
                    if offline_text:
                        offline_line = f" for about {offline_text}"
                    else:
                        offline_line = ""
                    await channel.send(
                        (
                            "⚠️ The bot was offline"
                            f"{offline_line}. If you reacted or removed a reaction "
                            "during that time, please re-apply your reaction.\n"
                            f"{message.jump_url}"
                        )
                    )
                    await self.raid_store.mark_alert_sent(raid.id, "restart_notice")
            except Exception:
                pass

        return refreshed

    @app_commands.command(name="raid-create", description="[Raid] Create a raid")
    async def raid_create(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command only works in a server.",
                ephemeral=True,
            )
            return

        if not self.config.raid_enabled:
            await interaction.response.send_message(
                "❌ Raid system is disabled.",
                ephemeral=True,
            )
            return

        if not self._has_creator_permission(interaction):
            await interaction.response.send_message(
                "❌ You do not have permission to create raids.",
                ephemeral=True,
            )
            return

        if self.config.raid_manage_channel_id and (
            interaction.channel_id != self.config.raid_manage_channel_id
        ):
            channel = interaction.guild.get_channel(self.config.raid_manage_channel_id)
            channel_hint = channel.mention if channel else "the raid channel"
            await interaction.response.send_message(
                f"❌ Please use {channel_hint} to create raids.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(RaidCreateModal(self))

    @app_commands.command(name="raid-list", description="[Raid] List upcoming raids")
    async def raid_list(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command only works in a server.",
                ephemeral=True,
            )
            return

        if not self.config.raid_enabled:
            await interaction.response.send_message(
                "❌ Raid system is disabled.",
                ephemeral=True,
            )
            return

        now_ts = int(datetime.now(timezone.utc).timestamp())
        raids = await self.raid_store.list_upcoming_raids(now_ts, limit=10)
        if not raids:
            await interaction.response.send_message(
                "ℹ️ No upcoming raids found.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🗓️ Upcoming raids",
            color=discord.Color.blurple(),
        )

        for raid in raids:
            signups = await self.raid_store.get_signups_by_role(raid.id)
            tank_count = len(signups.get(ROLE_TANK, []))
            healer_count = len(signups.get(ROLE_HEALER, []))
            dps_count = len(signups.get(ROLE_DPS, []))
            bench_count = len(signups.get(ROLE_BENCH, []))
            status_label = "Open" if raid.status == "open" else "Locked"
            game_label = GAME_LABELS.get(raid.game, raid.game)
            mode_label = MODE_LABELS.get(raid.mode, raid.mode)

            jump_url = "—"
            if raid.message_id:
                jump_url = (
                    f"https://discord.com/channels/{raid.guild_id}/"
                    f"{raid.channel_id}/{raid.message_id}"
                )

            value = (
                f"Game: {game_label}\n"
                f"Mode: {mode_label}\n"
                f"Start: <t:{raid.start_time}:F> (<t:{raid.start_time}:R>)\n"
                f"Status: {status_label}\n"
                f"Tanks: {tank_count}/{raid.tanks_needed} · "
                f"Healer: {healer_count}/{raid.healers_needed} · "
                f"DPS: {dps_count}/{raid.dps_needed}\n"
                f"Bench: {bench_count}/{raid.bench_needed}\n"
                f"Link: {jump_url}"
            )
            embed.add_field(name=raid.title, value=value, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="raid-setup",
        description="[Admin] Create raid channels and store IDs",
    )
    async def raid_setup(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command only works in a server.",
                ephemeral=True,
            )
            return

        if not self._has_admin_permission(interaction):
            await interaction.response.send_message(
                "❌ Only admins can run setup.",
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
            await interaction.followup.send("❌ Server not found.", ephemeral=True)
            return

        category = discord.utils.get(guild.categories, name="Raids")
        if not category:
            try:
                category = await guild.create_category("Raids", reason="Raid setup")
            except Exception as exc:
                logger.error("Failed to create raid category: %s", exc, exc_info=True)
                await interaction.followup.send(
                    "❌ Category could not be created.",
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
                    "❌ Raid channel could not be created.",
                    ephemeral=True,
                )
                return

        guildwar_channel = discord.utils.get(
            category.channels, name="guildwar-ankuendigungen"
        )
        if not guildwar_channel:
            try:
                guildwar_channel = await guild.create_text_channel(
                    "guildwar-ankuendigungen",
                    category=category,
                    reason="Raid setup",
                )
            except Exception as exc:
                logger.error("Failed to create guildwar channel: %s", exc, exc_info=True)
                await interaction.followup.send(
                    "❌ Guildwar channel could not be created.",
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
                    "❌ Raid planning channel could not be created.",
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
                    topic="🗡️ Info and instructions for raid signups",
                )
            except Exception as exc:
                logger.error("Failed to create raid info channel: %s", exc, exc_info=True)
                await interaction.followup.send(
                    "❌ Raid info channel could not be created.",
                    ephemeral=True,
                )
                return

        participant_role = await self._ensure_participant_role(guild)

        self.config.set_raid_post_channel_id(post_channel.id)
        self.config.set_raid_guildwar_post_channel_id(guildwar_channel.id)
        self.config.set_raid_manage_channel_id(manage_channel.id)
        self.config.set_raid_info_channel_id(info_channel.id)
        if participant_role:
            self.config.set_raid_participant_role_id(participant_role.id)

        info_message = await self._upsert_raid_info_message(info_channel)
        await self._cleanup_raid_info_channel(
            info_channel,
            {message.id for message in (info_message,) if message is not None},
        )
        await self._upsert_raid_history_message(post_channel, guild)

        embed = discord.Embed(
            title="✅ Raid setup complete",
            description="Channels were created and saved.",
            color=discord.Color.green(),
        )
        embed.add_field(name="Raid Posts", value=post_channel.mention, inline=False)
        embed.add_field(name="Guildwar Posts", value=guildwar_channel.mention, inline=False)
        embed.add_field(name="Raid Planning", value=manage_channel.mention, inline=False)
        embed.add_field(name="Raid Info", value=info_channel.mention, inline=False)
        if participant_role:
            embed.add_field(
                name="Participant role",
                value=participant_role.mention,
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="raid-set-channel",
        description="[Admin] Set raid channels",
    )
    @app_commands.describe(
        post_channel="Channel for raid announcements",
        guildwar_channel="Channel for guildwar announcements",
        manage_channel="Optional channel for raid creation",
        info_channel="Optional channel for raid info",
        log_channel="Optional channel for raid logs",
    )
    async def raid_set_channel(
        self,
        interaction: discord.Interaction,
        post_channel: Optional[discord.TextChannel] = None,
        guildwar_channel: Optional[discord.TextChannel] = None,
        manage_channel: Optional[discord.TextChannel] = None,
        info_channel: Optional[discord.TextChannel] = None,
        log_channel: Optional[discord.TextChannel] = None,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command only works in a server.",
                ephemeral=True,
            )
            return
        guild = interaction.guild

        if not self._has_admin_permission(interaction):
            await interaction.response.send_message(
                "❌ Only admins can set channels.",
                ephemeral=True,
            )
            return

        if (
            not post_channel
            and not guildwar_channel
            and not manage_channel
            and not info_channel
            and not log_channel
        ):
            await interaction.response.send_message(
                "❌ Please provide at least one channel.",
                ephemeral=True,
            )
            return

        if post_channel:
            self.config.set_raid_post_channel_id(post_channel.id)
        if guildwar_channel:
            self.config.set_raid_guildwar_post_channel_id(guildwar_channel.id)
        if manage_channel:
            self.config.set_raid_manage_channel_id(manage_channel.id)
        if info_channel:
            self.config.set_raid_info_channel_id(info_channel.id)
            info_message = await self._upsert_raid_info_message(info_channel)
            await self._cleanup_raid_info_channel(
                info_channel,
                {message.id for message in (info_message,) if message is not None},
            )
        if log_channel:
            self.config.set_raid_log_channel_id(log_channel.id)

        await self.refresh_raid_history(guild)

        embed = discord.Embed(
            title="✅ Raid channels updated",
            color=discord.Color.green(),
        )
        if post_channel:
            embed.add_field(name="Raid Posts", value=post_channel.mention, inline=False)
        if guildwar_channel:
            embed.add_field(
                name="Guildwar Posts",
                value=guildwar_channel.mention,
                inline=False,
            )
        if manage_channel:
            embed.add_field(name="Raid Planning", value=manage_channel.mention, inline=False)
        if info_channel:
            embed.add_field(name="Raid Info", value=info_channel.mention, inline=False)
        if log_channel:
            embed.add_field(name="Raid Logs", value=log_channel.mention, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="raid-info-setup",
        description="[Admin] Create/update the raid info post",
    )
    async def raid_info_setup(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command only works in a server.",
                ephemeral=True,
            )
            return

        if not self._has_admin_permission(interaction):
            await interaction.response.send_message(
                "❌ Only admins can run setup.",
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
                    "❌ Category could not be created.",
                    ephemeral=True,
                )
                return

        info_channel = discord.utils.get(category.channels, name="raid-info")
        if not info_channel:
            info_channel = await guild.create_text_channel(
                "raid-info",
                category=category,
                reason="Raid info setup",
                topic="🗡️ Info and instructions for raid signups",
            )

        self.config.set_raid_info_channel_id(info_channel.id)
        info_message = await self._upsert_raid_info_message(info_channel)
        await self._cleanup_raid_info_channel(
            info_channel,
            {
                message.id
                for message in (info_message,)
                if message is not None
            },
        )
        await self.refresh_raid_history(guild)

        embed = discord.Embed(
            title="✅ Raid info updated",
            color=discord.Color.green(),
        )
        embed.add_field(name="Raid Info", value=info_channel.mention, inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="raid-add-creator-role",
        description="[Admin] Add a role that can create raids",
    )
    async def raid_add_creator_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command only works in a server.",
                ephemeral=True,
            )
            return

        if not self._has_admin_permission(interaction):
            await interaction.response.send_message(
                "❌ Only admins can add roles.",
                ephemeral=True,
            )
            return

        self.config.add_raid_creator_role(role.id)
        await interaction.response.send_message(
            f"✅ Role {role.mention} added.",
            ephemeral=True,
        )

    @app_commands.command(
        name="raid-remove-creator-role",
        description="[Admin] Remove a role from raid creators",
    )
    async def raid_remove_creator_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command only works in a server.",
                ephemeral=True,
            )
            return

        if not self._has_admin_permission(interaction):
            await interaction.response.send_message(
                "❌ Only admins can remove roles.",
                ephemeral=True,
            )
            return

        self.config.remove_raid_creator_role(role.id)
        await interaction.response.send_message(
            f"✅ Role {role.mention} removed.",
            ephemeral=True,
        )

    @app_commands.command(
        name="raid-user-stats",
        description="[Admin] Show raid participation stats for a user",
    )
    async def raid_user_stats(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command only works in a server.",
                ephemeral=True,
            )
            return

        if not self._has_admin_permission(interaction):
            await interaction.response.send_message(
                "❌ Only admins can view these stats.",
                ephemeral=True,
            )
            return

        summary = await self.raid_store.get_user_participation_summary(user.id)
        total = summary.pop("total", 0)
        tanks = summary.get(ROLE_TANK, 0)
        healers = summary.get(ROLE_HEALER, 0)
        dps = summary.get(ROLE_DPS, 0)
        bench = summary.get(ROLE_BENCH, 0)

        embed = discord.Embed(
            title="📊 Raid participation",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="User", value=user.mention, inline=False)
        embed.add_field(name="Total", value=str(total), inline=True)
        embed.add_field(name="Tanks", value=str(tanks), inline=True)
        embed.add_field(name="Healer", value=str(healers), inline=True)
        embed.add_field(name="DPS", value=str(dps), inline=True)
        embed.add_field(name="Bench", value=str(bench), inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="raid-set-participant-role",
        description="[Admin] Set the raid participant role",
    )
    async def raid_set_participant_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command only works in a server.",
                ephemeral=True,
            )
            return

        if not self._has_admin_permission(interaction):
            await interaction.response.send_message(
                "❌ Only admins can set the participant role.",
                ephemeral=True,
            )
            return

        self.config.set_raid_participant_role_id(role.id)
        await interaction.response.send_message(
            f"✅ Participant role set: {role.mention}",
            ephemeral=True,
        )


async def setup(bot: commands.Bot, config: Config, raid_store: RaidStore) -> None:
    """Setup function for raid commands."""
    template_store = RaidTemplateStore()
    await template_store.initialize()
    cog = RaidCommand(bot, config, raid_store, template_store)
    await bot.add_cog(cog)
    bot.add_view(RaidStartView(cog))
    bot.add_view(RaidManageView(config, raid_store, template_store))
    logger.info("RaidCommand cog loaded")
