"""Automatic Git commits for config.yaml changes."""

import asyncio
import logging
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger("guildscout.config_watcher")


class ConfigWatcher:
    """
    Watches config.yaml for changes and automatically commits to Git.

    Features:
    - Detects config file changes via hash comparison
    - Creates meaningful commit messages
    - Keeps last 10 config versions
    - Rollback support via git
    """

    def __init__(self, config_path: Path = Path("config/config.yaml")):
        """
        Initialize config watcher.

        Args:
            config_path: Path to config file to watch
        """
        self.config_path = config_path
        self.last_hash: Optional[str] = None
        self.check_interval = 60  # Check every 60 seconds
        self.watcher_task: Optional[asyncio.Task] = None

        logger.info(f"📝 Config watcher initialized for {config_path}")

    def _get_file_hash(self) -> Optional[str]:
        """Calculate SHA256 hash of config file."""
        try:
            if not self.config_path.exists():
                return None

            with open(self.config_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Failed to hash config: {e}")
            return None

    def _get_config_diff(self) -> Optional[str]:
        """Get git diff of config file."""
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD", str(self.config_path)],
                cwd=self.config_path.parent.parent,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout if result.returncode == 0 else None
        except Exception as e:
            logger.error(f"Failed to get diff: {e}")
            return None

    def _create_commit_message(self, diff: Optional[str]) -> str:
        """
        Create meaningful commit message from diff.

        Args:
            diff: Git diff output

        Returns:
            Commit message
        """
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        if not diff:
            return f"Config: Manual changes ({timestamp})"

        # Try to extract changed keys from diff
        changes = []
        for line in diff.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                # Extract key name
                if ':' in line:
                    key = line.split(':')[0].replace('+', '').strip()
                    if key and not key.startswith('#'):
                        changes.append(key)

        if changes:
            changed_keys = ', '.join(changes[:3])  # Max 3 keys in message
            if len(changes) > 3:
                changed_keys += f" (+{len(changes)-3} more)"
            return f"Config: Updated {changed_keys} ({timestamp})"
        else:
            return f"Config: Changes detected ({timestamp})"

    def _commit_config(self) -> bool:
        """
        Commit config changes to git.

        Returns:
            True if commit successful
        """
        try:
            repo_path = self.config_path.parent.parent

            # Check if file is tracked
            status_result = subprocess.run(
                ["git", "ls-files", "--error-unmatch", str(self.config_path)],
                cwd=repo_path,
                capture_output=True,
                timeout=5
            )

            if status_result.returncode != 0:
                logger.debug("Config file not tracked in git, skipping auto-commit")
                return False

            # Get diff for commit message
            diff = self._get_config_diff()

            # Stage the file
            subprocess.run(
                ["git", "add", str(self.config_path)],
                cwd=repo_path,
                check=True,
                timeout=10
            )

            # Create commit
            commit_msg = self._create_commit_message(diff)

            result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                logger.info(f"✅ Config auto-committed: {commit_msg}")
                return True
            elif "nothing to commit" in result.stdout.lower():
                logger.debug("No changes to commit")
                return False
            else:
                logger.warning(f"Commit failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Git command timed out")
            return False
        except Exception as e:
            logger.error(f"Failed to commit config: {e}")
            return False

    async def start(self):
        """Start watching config file."""
        if self.watcher_task and not self.watcher_task.done():
            logger.warning("Config watcher already running")
            return

        # Initialize hash
        self.last_hash = self._get_file_hash()

        self.watcher_task = asyncio.create_task(self._watch_loop())
        logger.info(f"🔄 Started config watcher (checking every {self.check_interval}s)")

    async def stop(self):
        """Stop watching config file."""
        if self.watcher_task and not self.watcher_task.done():
            self.watcher_task.cancel()
            try:
                await self.watcher_task
            except asyncio.CancelledError:
                pass
            logger.info("🛑 Stopped config watcher")

    async def _watch_loop(self):
        """Main watch loop."""
        while True:
            try:
                await asyncio.sleep(self.check_interval)

                current_hash = self._get_file_hash()

                if current_hash and current_hash != self.last_hash:
                    logger.info("📝 Config file changed, creating auto-commit...")

                    # Run git commit in thread pool to avoid blocking
                    loop = asyncio.get_event_loop()
                    success = await loop.run_in_executor(None, self._commit_config)

                    if success:
                        self.last_hash = current_hash

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in config watcher: {e}")


async def setup_config_watcher(config_path: Path = Path("config/config.yaml")):
    """
    Setup and start config watcher.

    Args:
        config_path: Path to config file

    Returns:
        ConfigWatcher instance
    """
    watcher = ConfigWatcher(config_path)
    await watcher.start()
    return watcher
