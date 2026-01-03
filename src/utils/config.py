"""Configuration loader for GuildScout Bot."""

import yaml
from pathlib import Path
from typing import Any, Dict, Optional


class Config:
    """Configuration manager for the GuildScout bot."""

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Initialize configuration from YAML file.

        Args:
            config_path: Path to the configuration file
        """
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}\n"
                f"Please copy config/config.example.yaml to config/config.yaml and configure it."
            )

        with open(self.config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f) or {}

    def save(self) -> None:
        """Persist configuration to disk."""
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self._config, f, sort_keys=False, allow_unicode=False)

    def reload(self) -> None:
        """Reload configuration from YAML file."""
        self.load()

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.

        Args:
            key: Configuration key (e.g., 'discord.token')
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

            if value is None:
                return default

        return value

    @property
    def discord_token(self) -> str:
        """Get Discord bot token."""
        token = self.get("discord.token")
        if not token or token == "YOUR_BOT_TOKEN_HERE":
            raise ValueError("Discord token not configured in config.yaml")
        return token

    @property
    def guild_id(self) -> int:
        """Get Discord guild ID."""
        guild_id = self.get("discord.guild_id")
        if not guild_id:
            raise ValueError("Guild ID not configured in config.yaml")
        return int(guild_id)

    @property
    def health_check_port(self) -> int:
        """Get the port for the health check server."""
        return self.get("health_check.port", 8765)

    @property
    def scoring_weights(self) -> Dict[str, float]:
        """Get scoring weights."""
        return {
            "days_in_server": self.get("scoring.weights.days_in_server", 0.1),
            "message_count": self.get("scoring.weights.message_count", 0.55),
            "voice_activity": self.get("scoring.weights.voice_activity", 0.35),
        }

    @property
    def min_messages(self) -> int:
        """Get minimum message count threshold."""
        return self.get("scoring.min_messages", 10)

    @property
    def max_days_lookback(self) -> int:
        """Get maximum days to look back (None = all time)."""
        return self.get("scoring.max_days_lookback")

    @property
    def cache_ttl(self):
        """Get cache TTL in seconds (None = never expires)."""
        return self.get("analytics.cache_ttl")

    @property
    def voice_tracking_enabled(self) -> bool:
        """Whether voice activity tracking is enabled."""
        return bool(self.get("voice_tracking.enabled", True))

    @property
    def voice_exclude_afk(self) -> bool:
        """Whether to exclude AFK channels from voice tracking."""
        return bool(self.get("voice_tracking.exclude_afk", True))

    @property
    def voice_min_seconds(self) -> int:
        """Minimum duration in seconds to count a voice session."""
        return int(self.get("voice_tracking.min_seconds", 10))

    @property
    def excluded_channels(self) -> list:
        """Get list of excluded channel IDs."""
        return self.get("analytics.excluded_channels", [])

    @property
    def excluded_channel_names(self) -> list:
        """Get list of excluded channel name patterns."""
        return self.get("analytics.excluded_channel_names", [])

    @property
    def admin_roles(self) -> list:
        """Get list of admin role IDs."""
        return self.get("permissions.admin_roles", [])

    @property
    def admin_users(self) -> list:
        """Get list of admin user IDs."""
        return self.get("permissions.admin_users", [])

    @property
    def max_users_per_embed(self) -> int:
        """Get maximum users to display in Discord embed."""
        return self.get("export.max_users_per_embed", 25)

    @property
    def csv_delimiter(self) -> str:
        """Get CSV delimiter."""
        return self.get("export.csv_delimiter", ",")

    @property
    def csv_encoding(self) -> str:
        """Get CSV encoding."""
        return self.get("export.csv_encoding", "utf-8-sig")

    @property
    def log_level(self) -> str:
        """Get logging level."""
        return self.get("logging.level", "INFO")

    @property
    def log_file(self) -> str:
        """Get log file path."""
        return self.get("logging.file", "logs/guildscout.log")

    @property
    def log_format(self) -> str:
        """Get log format string."""
        return self.get(
            "logging.format",
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    @property
    def alert_ping(self) -> Optional[str]:
        """Optional mention content to ping on errors (e.g., '@here' or '<@&role>')."""
        return self.get("logging.alert_ping")

    @property
    def dashboard_update_interval_seconds(self) -> int:
        """Interval for updating the dashboard embed in ranking channel."""
        interval = self.get("logging.dashboard_update_interval_seconds", 300)
        try:
            interval_int = int(interval)
        except (TypeError, ValueError):
            interval_int = 300
        return max(60, interval_int)  # Min 1 minute

    @property
    def dashboard_idle_gap_seconds(self) -> int:
        """Gap after which the dashboard should refresh immediately."""
        gap = self.get("logging.dashboard_idle_gap_seconds", 120)
        try:
            gap_int = int(gap)
        except (TypeError, ValueError):
            gap_int = 120
        return max(30, gap_int)  # Min 30 seconds

    @property
    def daily_verification_enabled(self) -> bool:
        """Whether daily scheduled verification is enabled."""
        return bool(self.get("verification.enable_daily", True))

    @property
    def daily_verification_sample_size(self) -> int:
        """Sample size for daily verification runs."""
        size = self.get("verification.daily_sample_size", 25)
        try:
            return max(1, int(size))
        except (TypeError, ValueError):
            return 25

    @property
    def daily_verification_hour(self) -> int:
        """UTC hour to run the daily verification."""
        hour = self.get("verification.daily_hour_utc", 3)
        try:
            return max(0, min(23, int(hour)))
        except (TypeError, ValueError):
            return 3

    @property
    def daily_verification_minute(self) -> int:
        """UTC minute to run the daily verification."""
        minute = self.get("verification.daily_minute", 0)
        try:
            return max(0, min(59, int(minute)))
        except (TypeError, ValueError):
            return 0

    @property
    def weekly_verification_enabled(self) -> bool:
        """Whether weekly verification runs are enabled."""
        return bool(self.get("verification.enable_weekly", True))

    @property
    def weekly_verification_sample_size(self) -> int:
        """Sample size for weekly verification runs."""
        size = self.get("verification.weekly_sample_size", 150)
        try:
            return max(1, int(size))
        except (TypeError, ValueError):
            return 150

    @property
    def weekly_verification_weekday(self) -> int:
        """Weekday for weekly verification (0=Monday)."""
        weekday = self.get("verification.weekly_weekday", 0)
        try:
            return max(0, min(6, int(weekday)))
        except (TypeError, ValueError):
            return 0

    @property
    def weekly_verification_hour(self) -> int:
        """UTC hour to run the weekly verification."""
        hour = self.get("verification.weekly_hour_utc", 4)
        try:
            return max(0, min(23, int(hour)))
        except (TypeError, ValueError):
            return 4

    @property
    def weekly_verification_minute(self) -> int:
        """UTC minute to run the weekly verification."""
        minute = self.get("verification.weekly_minute", 30)
        try:
            return max(0, min(59, int(minute)))
        except (TypeError, ValueError):
            return 30

    @property
    def sixhour_verification_enabled(self) -> bool:
        """Whether 6-hourly verification runs are enabled."""
        return bool(self.get("verification.enable_6h", False))

    @property
    def sixhour_verification_sample_size(self) -> int:
        """Sample size for 6-hourly verification runs."""
        size = self.get("verification.sixhour_sample_size", 30)
        try:
            return max(1, int(size))
        except (TypeError, ValueError):
            return 30

    @property
    def sixhour_verification_hours(self) -> list:
        """UTC hours to run the 6-hourly verification."""
        hours = self.get("verification.sixhour_hours_utc", [9, 15, 21])
        if not isinstance(hours, list):
            return [9, 15, 21]
        # Validate each hour is 0-23
        return [max(0, min(23, int(h))) for h in hours if isinstance(h, (int, str))]

    @property
    def shadowops_enabled(self) -> bool:
        """Whether ShadowOps integration is enabled."""
        return bool(self.get("shadowops.enabled", False))

    @property
    def shadowops_webhook_url(self) -> str:
        """ShadowOps webhook URL for alerts."""
        return self.get("shadowops.webhook_url", "http://localhost:9091/guildscout-alerts")

    @property
    def shadowops_webhook_secret(self) -> str:
        """Shared secret for webhook signature verification."""
        return self.get("shadowops.webhook_secret", "")

    @property
    def shadowops_notify_verification(self) -> bool:
        """Whether to notify ShadowOps on verification results."""
        return bool(self.get("shadowops.notify_on_verification", True))

    @property
    def shadowops_notify_errors(self) -> bool:
        """Whether to notify ShadowOps on critical errors."""
        return bool(self.get("shadowops.notify_on_errors", True))

    @property
    def discord_service_logs_enabled(self) -> bool:
        """Whether service lifecycle events should be logged to Discord."""
        return bool(self.get("logging.enable_discord_service_logs", True))

    @property
    def max_guild_spots(self) -> int:
        """Get maximum guild spots available."""
        return self.get("guild_management.max_spots", 50)

    @property
    def guild_role_id(self) -> Optional[int]:
        """Get guild role ID to assign."""
        role_id = self.get("guild_management.guild_role_id")
        return int(role_id) if role_id else None

    @property
    def exclusion_roles(self) -> list:
        """Get list of role IDs to exclude from ranking (already have spots)."""
        return self.get("guild_management.exclusion_roles", [])

    @property
    def exclusion_users(self) -> list:
        """Get list of user IDs to exclude from ranking (manual reservations)."""
        return self.get("guild_management.exclusion_users", [])

    @property
    def raid_enabled(self) -> bool:
        """Whether the raid feature is enabled."""
        return bool(self.get("raid_management.enabled", False))

    @property
    def raid_post_channel_id(self) -> Optional[int]:
        """Channel ID where raid announcements are posted."""
        channel_id = self.get("raid_management.post_channel_id")
        return int(channel_id) if channel_id else None

    def set_raid_post_channel_id(self, channel_id: Optional[int]) -> None:
        """Persist the raid announcement channel ID."""
        self._set_nested_value("raid_management.post_channel_id", channel_id)
        self.save()

    @property
    def raid_manage_channel_id(self) -> Optional[int]:
        """Optional channel ID where raid creation is allowed."""
        channel_id = self.get("raid_management.manage_channel_id")
        return int(channel_id) if channel_id else None

    def set_raid_manage_channel_id(self, channel_id: Optional[int]) -> None:
        """Persist the raid management channel ID."""
        self._set_nested_value("raid_management.manage_channel_id", channel_id)
        self.save()

    @property
    def raid_info_channel_id(self) -> Optional[int]:
        """Optional channel ID for raid info/start message."""
        channel_id = self.get("raid_management.info_channel_id")
        return int(channel_id) if channel_id else None

    def set_raid_info_channel_id(self, channel_id: Optional[int]) -> None:
        """Persist the raid info channel ID."""
        self._set_nested_value("raid_management.info_channel_id", channel_id)
        self.save()

    @property
    def raid_info_message_id(self) -> Optional[int]:
        """Stored message ID for the raid info/start embed."""
        message_id = self.get("raid_management.info_message_id")
        return int(message_id) if message_id else None

    def set_raid_info_message_id(self, message_id: Optional[int]) -> None:
        """Persist the raid info message ID."""
        self._set_nested_value("raid_management.info_message_id", message_id)
        self.save()

    @property
    def raid_creator_roles(self) -> list:
        """Role IDs allowed to create raids."""
        return self.get("raid_management.creator_roles", [])

    def add_raid_creator_role(self, role_id: int) -> None:
        """Add a role to the raid creator list."""
        roles = list(self.raid_creator_roles)
        if role_id not in roles:
            roles.append(role_id)
            self._set_nested_value("raid_management.creator_roles", roles)
            self.save()

    def remove_raid_creator_role(self, role_id: int) -> None:
        """Remove a role from the raid creator list."""
        roles = [rid for rid in self.raid_creator_roles if rid != role_id]
        self._set_nested_value("raid_management.creator_roles", roles)
        self.save()

    @property
    def raid_timezone(self) -> str:
        """Default timezone for raid scheduling."""
        return self.get("raid_management.timezone", "UTC")

    @property
    def raid_participant_role_id(self) -> Optional[int]:
        """Role ID to assign to raid participants."""
        role_id = self.get("raid_management.participant_role_id")
        return int(role_id) if role_id else None

    def set_raid_participant_role_id(self, role_id: Optional[int]) -> None:
        """Persist raid participant role ID."""
        self._set_nested_value("raid_management.participant_role_id", role_id)
        self.save()

    @property
    def raid_reminder_hours(self) -> list:
        """List of reminder offsets (hours before start)."""
        hours = self.get("raid_management.reminder_hours", [24, 1])
        if isinstance(hours, (int, float)):
            hours = [int(hours)]
        if not isinstance(hours, list):
            return [24, 1]
        parsed = []
        for value in hours:
            try:
                parsed.append(int(value))
            except (TypeError, ValueError):
                continue
        return sorted({hour for hour in parsed if hour > 0})

    @property
    def raid_dm_reminder_minutes(self) -> list:
        """List of DM reminder offsets (minutes before start)."""
        minutes = self.get("raid_management.dm_reminder_minutes", [15])
        if isinstance(minutes, (int, float)):
            minutes = [int(minutes)]
        if not isinstance(minutes, list):
            return [15]
        parsed = []
        for value in minutes:
            try:
                parsed.append(int(value))
            except (TypeError, ValueError):
                continue
        return sorted({minute for minute in parsed if minute > 0})

    @property
    def raid_auto_close_at_start(self) -> bool:
        """Whether raids auto-close at start time."""
        return bool(self.get("raid_management.auto_close_at_start", True))

    @property
    def dashboard_channel_id(self) -> Optional[int]:
        """Get dashboard channel ID (formerly ranking channel)."""
        # Try new key first, fallback to old key for backward compatibility
        channel_id = self.get("guild_management.dashboard_channel_id")
        if not channel_id:
            channel_id = self.get("guild_management.ranking_channel_id")
        return int(channel_id) if channel_id else None

    def set_dashboard_channel_id(self, channel_id: Optional[int]) -> None:
        """Update dashboard channel ID in config."""
        self._set_nested_value("guild_management.dashboard_channel_id", channel_id)
        self.save()

    @property
    def ranking_channel_id(self) -> Optional[int]:
        """Deprecated: Use dashboard_channel_id instead."""
        return self.dashboard_channel_id

    def set_ranking_channel_id(self, channel_id: Optional[int]) -> None:
        """Deprecated: Use set_dashboard_channel_id instead."""
        self.set_dashboard_channel_id(channel_id)

    @property
    def status_channel_id(self) -> Optional[int]:
        """Get status channel ID for errors and warnings."""
        channel_id = self.get("guild_management.status_channel_id")
        return int(channel_id) if channel_id else None

    def set_status_channel_id(self, channel_id: Optional[int]) -> None:
        """Update status channel ID in config."""
        self._set_nested_value("guild_management.status_channel_id", channel_id)
        self.save()

    @property
    def ranking_channel_message_id(self) -> Optional[int]:
        """Get stored welcome message ID."""
        message_id = self.get("guild_management.ranking_channel_message_id")
        return int(message_id) if message_id else None

    def set_ranking_channel_message_id(self, message_id: Optional[int]) -> None:
        """Update stored welcome message ID."""
        self._set_nested_value("guild_management.ranking_channel_message_id", message_id)
        self.save()

    @property
    def ranking_channel_message_version(self) -> int:
        """Get version of the welcome message text that was posted."""
        version = self.get("guild_management.ranking_channel_message_version", 0)
        try:
            return int(version)
        except (TypeError, ValueError):
            return 0

    def set_ranking_channel_message_version(self, version: int) -> None:
        """Persist welcome message version."""
        self._set_nested_value("guild_management.ranking_channel_message_version", int(version))
        self.save()

    def _set_nested_value(self, key: str, value: Any) -> None:
        """Helper to set nested configuration values."""
        keys = key.split(".")
        current = self._config

        for part in keys[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]

        if value is None:
            current.pop(keys[-1], None)
        else:
            current[keys[-1]] = value
