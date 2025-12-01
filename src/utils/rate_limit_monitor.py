"""Discord API Rate Limit Monitor."""

import logging
import time
from collections import deque
from typing import Optional
import discord

logger = logging.getLogger("guildscout.rate_limits")


class RateLimitMonitor:
    """
    Monitors Discord API rate limits to provide early warnings.

    Tracks:
    - Requests per second
    - Rate limit hits (429 responses)
    - Global rate limits
    - Per-route rate limits
    """

    def __init__(self):
        """Initialize rate limit monitor."""
        # Track requests in last 60 seconds
        self.request_timestamps: deque = deque(maxlen=10000)

        # Rate limit hits
        self.rate_limit_hits = 0
        self.global_rate_limits = 0
        self.last_rate_limit_time: Optional[float] = None

        # Warning thresholds
        self.warning_requests_per_second = 40  # Discord global limit is 50/s
        self.critical_requests_per_second = 45

        logger.info("📊 Rate limit monitor initialized")

    def track_request(self):
        """Track an API request."""
        self.request_timestamps.append(time.time())

        # Check if we're approaching limits
        rps = self.get_requests_per_second()

        if rps >= self.critical_requests_per_second:
            logger.error(
                f"🚨 CRITICAL: High request rate! {rps:.1f} req/s "
                f"(limit: 50 req/s)"
            )
        elif rps >= self.warning_requests_per_second:
            logger.warning(
                f"⚠️ WARNING: Approaching rate limit! {rps:.1f} req/s "
                f"(limit: 50 req/s)"
            )

    def track_rate_limit(self, is_global: bool = False, retry_after: Optional[float] = None):
        """
        Track a rate limit hit (429 response).

        Args:
            is_global: Whether this was a global rate limit
            retry_after: Retry-After header value in seconds
        """
        self.rate_limit_hits += 1
        self.last_rate_limit_time = time.time()

        if is_global:
            self.global_rate_limits += 1
            logger.error(
                f"🚫 GLOBAL RATE LIMIT HIT! "
                f"Retry after: {retry_after:.1f}s"
            )
        else:
            logger.warning(
                f"⚠️ Route rate limit hit. "
                f"Retry after: {retry_after:.1f}s if provided, "
                f"Total hits: {self.rate_limit_hits}"
            )

    def get_requests_per_second(self, window_seconds: int = 10) -> float:
        """
        Calculate requests per second in the last N seconds.

        Args:
            window_seconds: Time window to calculate over

        Returns:
            Requests per second
        """
        if not self.request_timestamps:
            return 0.0

        now = time.time()
        cutoff = now - window_seconds

        # Count requests in window
        recent_requests = sum(1 for ts in self.request_timestamps if ts >= cutoff)

        return recent_requests / window_seconds

    def get_stats(self) -> dict:
        """
        Get current rate limit statistics.

        Returns:
            Dictionary with stats
        """
        rps = self.get_requests_per_second()

        return {
            "requests_per_second": round(rps, 2),
            "total_rate_limit_hits": self.rate_limit_hits,
            "global_rate_limits": self.global_rate_limits,
            "last_rate_limit": (
                f"{time.time() - self.last_rate_limit_time:.0f}s ago"
                if self.last_rate_limit_time
                else "Never"
            ),
            "status": (
                "🚨 CRITICAL" if rps >= self.critical_requests_per_second
                else "⚠️ WARNING" if rps >= self.warning_requests_per_second
                else "✅ OK"
            )
        }

    def log_stats(self):
        """Log current statistics."""
        stats = self.get_stats()
        logger.info(
            f"📊 Rate Limit Stats: "
            f"{stats['requests_per_second']} req/s, "
            f"{stats['total_rate_limit_hits']} hits, "
            f"Status: {stats['status']}"
        )


# Global instance
_monitor: Optional[RateLimitMonitor] = None


def get_monitor() -> RateLimitMonitor:
    """Get or create the global rate limit monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = RateLimitMonitor()
    return _monitor
