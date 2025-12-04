"""Track verification statistics for dashboard display."""

import json
import logging
from datetime import datetime, timedelta
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

    def mark_running(self, guild_id: int, is_running: bool, label: str = "Verifikation"):
        """Mark a verification as currently running or finished."""
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
        if is_running:
            stats["current_run"] = {
                "start_time": datetime.utcnow().isoformat(),
                "label": label
            }
        else:
            stats.pop("current_run", None)
        
        self._save()

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
        
        # Clear running flag if it exists
        stats.pop("current_run", None)

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
        if not stats:
            return "Keine Verifikationen durchgeführt"
            
        # Check if currently running
        running_text = ""
        current_run = stats.get("current_run")
        if current_run:
            try:
                start_time = datetime.fromisoformat(current_run["start_time"])
                # If older than 30 mins, assume stale/crashed and ignore
                if datetime.utcnow() - start_time < timedelta(minutes=30):
                    label = current_run.get("label", "Verifikation")
                    running_text = f"\n🔄 **{label} läuft...** <t:{int(start_time.timestamp())}:R>"
            except Exception:
                pass

        if stats["total_runs"] == 0 and not running_text:
            return "Keine Verifikationen durchgeführt"

        total_runs = stats.get("total_runs", 0)
        if total_runs > 0:
            success_rate = (stats.get("successful_runs", 0) / total_runs) * 100
            
            last_run = ""
            if stats.get("last_run_timestamp"):
                try:
                    dt = datetime.fromisoformat(stats["last_run_timestamp"])
                    timestamp_int = int(dt.timestamp())
                    status = "✅" if stats["last_run_passed"] else "⚠️"
                    accuracy = stats["last_run_accuracy"]
                    last_run = f"\n**Letzte Prüfung:** {status} {accuracy:.1f}% Accuracy <t:{timestamp_int}:R>"
                except:
                    pass

            return (
                f"**Verifikationen:** {total_runs} durchgeführt\n"
                f"**Erfolgsrate:** {success_rate:.1f}% ({stats.get('successful_runs', 0)}/{total_runs})\n"
                f"**Gesamt-Abweichungen:** {stats.get('total_mismatches', 0)}"
                f"{last_run}"
                f"{running_text}"
            )
        else:
             return f"Noch keine Ergebnisse vorhanden.{running_text}"
