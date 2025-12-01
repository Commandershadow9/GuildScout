"""Track verification statistics for dashboard display."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("guildscout.verification_stats")


class VerificationStats:
    """Simple file-based storage for verification statistics."""

    def __init__(self, data_dir: str = "data"):
        self.data_file = Path(data_dir) / "verification_stats.json"
        self.data_file.parent.mkdir(exist_ok=True)
        self._stats: Dict[int, Dict[str, Any]] = self._load()

    def _load(self) -> Dict[int, Dict[str, Any]]:
        """Load stats from file."""
        if not self.data_file.exists():
            return {}
        try:
            with open(self.data_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load verification stats: {e}")
            return {}

    def _save(self):
        """Save stats to file."""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self._stats, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save verification stats: {e}")

    def record_verification(
        self,
        guild_id: int,
        passed: bool,
        accuracy: float,
        sample_size: int,
        mismatches: int = 0
    ):
        """Record a verification result."""
        guild_id_str = str(guild_id)

        if guild_id_str not in self._stats:
            self._stats[guild_id_str] = {
                "total_runs": 0,
                "successful_runs": 0,
                "total_mismatches": 0,
                "last_run_timestamp": None,
                "last_run_passed": None,
                "last_run_accuracy": None
            }

        stats = self._stats[guild_id_str]
        stats["total_runs"] += 1
        if passed:
            stats["successful_runs"] += 1
        stats["total_mismatches"] += mismatches
        stats["last_run_timestamp"] = datetime.utcnow().isoformat()
        stats["last_run_passed"] = passed
        stats["last_run_accuracy"] = accuracy

        self._save()
        logger.info(f"Recorded verification for guild {guild_id}: passed={passed}, accuracy={accuracy:.1f}%")

    def get_stats(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get verification stats for a guild."""
        # Reload from file to ensure fresh data (multiple instances may exist)
        self._stats = self._load()
        return self._stats.get(str(guild_id))

    def get_summary(self, guild_id: int) -> str:
        """Get a formatted summary for display."""
        stats = self.get_stats(guild_id)
        if not stats or stats["total_runs"] == 0:
            return "Keine Verifikationen durchgeführt"

        success_rate = (stats["successful_runs"] / stats["total_runs"]) * 100

        last_run = ""
        if stats["last_run_timestamp"]:
            try:
                dt = datetime.fromisoformat(stats["last_run_timestamp"])
                timestamp_int = int(dt.timestamp())
                status = "✅" if stats["last_run_passed"] else "⚠️"
                accuracy = stats["last_run_accuracy"]
                last_run = f"\n**Letzte Prüfung:** {status} {accuracy:.1f}% Accuracy <t:{timestamp_int}:R>"
            except:
                pass

        return (
            f"**Verifikationen:** {stats['total_runs']} durchgeführt\n"
            f"**Erfolgsrate:** {success_rate:.1f}% ({stats['successful_runs']}/{stats['total_runs']})\n"
            f"**Gesamt-Abweichungen:** {stats['total_mismatches']}"
            f"{last_run}"
        )
