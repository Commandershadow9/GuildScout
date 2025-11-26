"""Track bot lifetime statistics across restarts."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("guildscout.bot_statistics")


class BotStatistics:
    """Track bot statistics with lifetime and session tracking."""

    def __init__(self, data_dir: str = "data"):
        self.data_file = Path(data_dir) / "bot_statistics.json"
        self.data_file.parent.mkdir(exist_ok=True)
        self._stats: Dict[str, Any] = self._load()
        self._session_start = datetime.utcnow()
        self._session_messages_tracked = 0

    def _load(self) -> Dict[str, Any]:
        """Load stats from file."""
        try:
            if not self.data_file.exists():
                data = {
                    "first_startup": datetime.utcnow().isoformat(),
                    "last_restart": datetime.utcnow().isoformat(),
                    "total_restarts": 1,  # First start is restart #1
                    "lifetime_messages_tracked": 0
                }
                # Save immediately to create file
                with open(self.data_file, 'w') as f:
                    json.dump(data, f, indent=2)
                return data

            with open(self.data_file, 'r') as f:
                data = json.load(f)
            
            # Increment restart counter and update timestamp
            data["total_restarts"] = data.get("total_restarts", 0) + 1
            data["last_restart"] = datetime.utcnow().isoformat()
            
            # Persist the increment immediately
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
                
            return data
        except Exception as e:
            logger.warning(f"Could not load bot statistics: {e}")
            return {
                "first_startup": datetime.utcnow().isoformat(),
                "last_restart": datetime.utcnow().isoformat(),
                "total_restarts": 0,
                "lifetime_messages_tracked": 0
            }

    def _save(self):
        """Save stats to file."""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self._stats, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save bot statistics: {e}")

    def track_message(self):
        """Track a message (both session and lifetime)."""
        self._session_messages_tracked += 1
        self._stats["lifetime_messages_tracked"] = self._stats.get("lifetime_messages_tracked", 0) + 1

        # Save every 100 messages to avoid too many writes
        if self._session_messages_tracked % 100 == 0:
            self._save()

    def get_session_stats(self) -> Dict[str, Any]:
        """Get stats for current session."""
        uptime = datetime.utcnow() - self._session_start
        uptime_minutes = int(uptime.total_seconds() // 60)
        uptime_hours = uptime_minutes // 60
        uptime_mins = uptime_minutes % 60

        return {
            "session_start": self._session_start,
            "session_messages_tracked": self._session_messages_tracked,
            "uptime_formatted": f"{uptime_hours}h {uptime_mins}m" if uptime_hours > 0 else f"{uptime_mins}m"
        }

    def get_lifetime_stats(self) -> Dict[str, Any]:
        """Get lifetime stats."""
        try:
            first_startup = datetime.fromisoformat(self._stats.get("first_startup", datetime.utcnow().isoformat()))
            last_restart = datetime.fromisoformat(self._stats.get("last_restart", datetime.utcnow().isoformat()))

            total_days = (datetime.utcnow() - first_startup).days

            return {
                "first_startup": first_startup,
                "last_restart": last_restart,
                "total_restarts": self._stats.get("total_restarts", 0),
                "lifetime_messages_tracked": self._stats.get("lifetime_messages_tracked", 0),
                "total_days_online": total_days
            }
        except Exception as e:
            logger.warning(f"Error getting lifetime stats: {e}")
            return {
                "first_startup": datetime.utcnow(),
                "last_restart": datetime.utcnow(),
                "total_restarts": 0,
                "lifetime_messages_tracked": 0,
                "total_days_online": 0
            }

    def get_dashboard_summary(self, total_db_messages: Optional[int] = None) -> str:
        """
        Get formatted summary for dashboard.
        
        Args:
            total_db_messages: Optional total message count from DB (more accurate)
        """
        session = self.get_session_stats()
        lifetime = self.get_lifetime_stats()

        last_restart_ts = int(lifetime["last_restart"].timestamp())
        
        # Use DB count if provided, otherwise internal counter
        total_messages = total_db_messages if total_db_messages is not None else lifetime['lifetime_messages_tracked']

        summary = (
            f"**📊 Seit Restart:** {session['session_messages_tracked']:,} Nachrichten ({session['uptime_formatted']} uptime)\n"
            f"**📈 Lifetime:** {total_messages:,} Nachrichten getrackt\n"
            f"**🔄 Letzter Restart:** <t:{last_restart_ts}:R> ({lifetime['total_restarts']} Restarts gesamt)"
        )

        return summary

    def save_on_shutdown(self):
        """Force save on shutdown."""
        self._save()
        logger.info("Bot statistics saved on shutdown")
