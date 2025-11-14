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
            self._config = yaml.safe_load(f)

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
    def scoring_weights(self) -> Dict[str, float]:
        """Get scoring weights."""
        return {
            "days_in_server": self.get("scoring.weights.days_in_server", 0.4),
            "message_count": self.get("scoring.weights.message_count", 0.6),
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
    def cache_ttl(self) -> int:
        """Get cache TTL in seconds."""
        return self.get("analytics.cache_ttl", 3600)

    @property
    def excluded_channels(self) -> list:
        """Get list of excluded channel IDs."""
        return self.get("analytics.excluded_channels", [])

    @property
    def excluded_channel_names(self) -> list:
        """Get list of excluded channel name patterns."""
        return self.get("analytics.excluded_channel_names", ["nsfw", "bot-spam"])

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
