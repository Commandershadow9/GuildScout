"""ShadowOps Notification System with Health Check and Retry Queue."""

import aiohttp
import asyncio
import logging
import json
import hmac
import hashlib
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
from collections import deque

logger = logging.getLogger("guildscout.shadowops_notifier")


class ShadowOpsNotifier:
    """
    Sends notifications to ShadowOps Bot with retry capability.

    Features:
    - Health check before sending (ping /health endpoint)
    - Retry queue for failed alerts
    - Periodic retry attempts
    - Persistent queue (survives bot restarts)
    """

    def __init__(self, webhook_url: str, enabled: bool = True, webhook_secret: str = ""):
        """
        Initialize ShadowOps notifier.

        Args:
            webhook_url: URL of ShadowOps webhook endpoint
            enabled: Whether notifications are enabled
            webhook_secret: Shared secret for HMAC signature verification
        """
        self.webhook_url = webhook_url
        self.health_url = webhook_url.replace('/guildscout-alerts', '/health')
        self.enabled = enabled
        self.webhook_secret = webhook_secret
        self.session: Optional[aiohttp.ClientSession] = None

        # Retry queue: stores failed alerts
        self.retry_queue: deque = deque(maxlen=100)  # Max 100 pending alerts
        self.queue_file = Path("data/shadowops_queue.json")

        # Load persisted queue
        self._load_queue()

        # Retry task (runs every 5 minutes)
        self.retry_task: Optional[asyncio.Task] = None

        # Health check tracking (for health monitor)
        self.last_health_check: Optional[datetime] = None

        logger.info(f"📡 ShadowOps Notifier initialized (enabled: {enabled})")

    async def start_retry_task(self):
        """Start the periodic retry task."""
        if not self.retry_task or self.retry_task.done():
            self.retry_task = asyncio.create_task(self._retry_loop())
            logger.info("🔄 Started ShadowOps retry task (5 minute interval)")

    async def stop_retry_task(self):
        """Stop the retry task."""
        if self.retry_task and not self.retry_task.done():
            self.retry_task.cancel()
            try:
                await self.retry_task
            except asyncio.CancelledError:
                pass
            logger.info("🛑 Stopped ShadowOps retry task")

    async def _retry_loop(self):
        """Periodically retry failed alerts."""
        while True:
            try:
                await asyncio.sleep(300)  # 5 minutes
                await self._process_retry_queue()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in retry loop: {e}")

    async def _process_retry_queue(self):
        """Process all alerts in retry queue."""
        if not self.retry_queue:
            return

        logger.info(f"🔄 Processing retry queue ({len(self.retry_queue)} alerts pending)")

        # Check if ShadowOps is healthy first
        if not await self._check_health():
            logger.warning("⚠️ ShadowOps still unhealthy, skipping retry")
            return

        # Process queue (oldest first)
        processed = 0
        failed = []

        while self.retry_queue:
            alert = self.retry_queue.popleft()
            success = await self._send_alert_direct(alert)

            if success:
                processed += 1
            else:
                failed.append(alert)

        # Re-add failed alerts
        self.retry_queue.extend(failed)
        self._save_queue()

        if processed > 0:
            logger.info(f"✅ Processed {processed} queued alerts, {len(failed)} still pending")

    def _load_queue(self):
        """Load persisted queue from disk."""
        try:
            if self.queue_file.exists():
                with open(self.queue_file, 'r') as f:
                    data = json.load(f)
                    self.retry_queue = deque(data, maxlen=100)
                    if self.retry_queue:
                        logger.info(f"📥 Loaded {len(self.retry_queue)} alerts from persistent queue")
        except Exception as e:
            logger.error(f"Failed to load queue: {e}")

    def _save_queue(self):
        """Persist queue to disk."""
        try:
            self.queue_file.parent.mkdir(exist_ok=True)
            with open(self.queue_file, 'w') as f:
                json.dump(list(self.retry_queue), f)
        except Exception as e:
            logger.error(f"Failed to save queue: {e}")

    async def _ensure_session(self):
        """Ensure aiohttp session exists."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Close aiohttp session and save queue."""
        await self.stop_retry_task()
        self._save_queue()
        if self.session and not self.session.closed:
            await self.session.close()

    async def _check_health(self) -> bool:
        """
        Check if ShadowOps webhook is healthy.

        Returns:
            True if health endpoint responds OK
        """
        try:
            await self._ensure_session()

            async with self.session.get(
                self.health_url,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                is_healthy = response.status == 200
                if is_healthy:
                    self.last_health_check = datetime.utcnow()
                else:
                    logger.debug(f"Health check failed: {response.status}")
                return is_healthy

        except Exception as e:
            logger.debug(f"Health check error: {e}")
            return False

    def _generate_signature(self, payload: str) -> str:
        """
        Generate HMAC-SHA256 signature for webhook payload.

        Args:
            payload: JSON payload as string

        Returns:
            Hex-encoded HMAC signature
        """
        if not self.webhook_secret:
            return ""

        signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        )
        return signature.hexdigest()

    async def _send_alert_direct(self, payload: Dict) -> bool:
        """
        Send alert directly without health check or queuing.

        Args:
            payload: Alert payload

        Returns:
            True if sent successfully
        """
        try:
            await self._ensure_session()

            # Generate signature if secret is configured
            payload_str = json.dumps(payload, separators=(',', ':'), sort_keys=True)
            signature = self._generate_signature(payload_str)

            headers = {}
            if signature:
                headers['X-Webhook-Signature'] = f"sha256={signature}"

            async with self.session.post(
                self.webhook_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    logger.info(f"✅ Alert sent: {payload.get('title', 'Unknown')}")
                    return True
                else:
                    logger.warning(f"⚠️ Webhook returned {response.status}")
                    return False

        except asyncio.TimeoutError:
            logger.warning(f"⏱️ Timeout sending alert")
            return False
        except Exception as e:
            logger.error(f"❌ Error sending alert: {e}")
            return False

    async def send_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        description: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Send alert to ShadowOps with health check and retry capability.

        Args:
            alert_type: Type of alert (verification, error, health, etc.)
            severity: low, medium, high, critical
            title: Alert title
            description: Detailed description
            metadata: Additional data

        Returns:
            True if notification sent or queued successfully
        """
        if not self.enabled:
            logger.debug("ShadowOps notifications disabled")
            return False

        payload = {
            "source": "guildscout",
            "alert_type": alert_type,
            "severity": severity,
            "title": title,
            "description": description,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }

        # Check health first
        is_healthy = await self._check_health()

        if is_healthy:
            # Try to send
            success = await self._send_alert_direct(payload)
            if success:
                return True
            # Failed even though health check passed - queue it
            logger.warning(f"📥 Health OK but send failed, queuing: {title}")
            self.retry_queue.append(payload)
            self._save_queue()
            return True
        else:
            # ShadowOps is down, queue immediately
            logger.warning(f"📥 ShadowOps unhealthy, queuing alert: {title}")
            self.retry_queue.append(payload)
            self._save_queue()
            return True

    async def send_verification_result(
        self,
        passed: bool,
        accuracy: float,
        total_users: int,
        mismatches: int,
        healed: int,
        verification_type: str = "daily"
    ):
        """Send verification result to ShadowOps."""
        severity = "low" if passed and accuracy >= 95 else "medium" if passed else "high"

        title = f"{'✅' if passed else '⚠️'} {verification_type.title()} Verification: {accuracy:.1f}%"

        description = (
            f"**Accuracy:** {accuracy:.1f}%\n"
            f"**Users validated:** {total_users}\n"
            f"**Mismatches:** {mismatches}\n"
            f"**Healed:** {healed}\n"
            f"**Status:** {'PASSED' if passed else 'FAILED'}"
        )

        metadata = {
            "passed": passed,
            "accuracy": accuracy,
            "total_users": total_users,
            "mismatches": mismatches,
            "healed": healed,
            "verification_type": verification_type
        }

        await self.send_alert(
            alert_type="verification",
            severity=severity,
            title=title,
            description=description,
            metadata=metadata
        )

    async def send_error(self, error_type: str, error_message: str, traceback: Optional[str] = None):
        """Send critical error notification."""
        description = f"**Error:** {error_message}"
        if traceback:
            description += f"\n\n```\n{traceback[:500]}\n```"

        await self.send_alert(
            alert_type="error",
            severity="critical",
            title=f"🚨 GuildScout Error: {error_type}",
            description=description,
            metadata={"error_type": error_type, "error_message": error_message}
        )

    async def send_health_status(self, is_healthy: bool, details: Dict):
        """Send health status change notification."""
        severity = "low" if is_healthy else "critical"
        title = f"{'💚' if is_healthy else '❤️'} GuildScout Health: {'Healthy' if is_healthy else 'Unhealthy'}"

        description = "\n".join([f"**{k}:** {v}" for k, v in details.items()])

        await self.send_alert(
            alert_type="health",
            severity=severity,
            title=title,
            description=description,
            metadata=details
        )
