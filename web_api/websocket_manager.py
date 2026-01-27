"""WebSocket manager for real-time updates in GuildScout Dashboard."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("guildscout.websocket")


class EventType(str, Enum):
    """WebSocket event types."""

    # Raid events
    RAID_CREATED = "raid:created"
    RAID_UPDATED = "raid:updated"
    RAID_SIGNUP = "raid:signup"
    RAID_CLOSED = "raid:closed"
    RAID_LOCKED = "raid:locked"
    RAID_UNLOCKED = "raid:unlocked"

    # Activity events
    ACTIVITY_NEW = "activity:new"

    # System events
    SYSTEM_STATUS = "system:status"
    SYSTEM_HEALTH = "system:health"

    # Connection events
    CONNECTED = "connection:established"
    PING = "ping"
    PONG = "pong"


@dataclass
class WebSocketEvent:
    """A WebSocket event to broadcast."""

    type: EventType
    guild_id: int
    data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_json(self) -> str:
        """Serialize event to JSON.

        Note: guild_id is sent as string to avoid JavaScript BigInt issues.
        JavaScript cannot safely handle integers > 2^53-1.
        """
        return json.dumps({
            "type": self.type.value,
            "guild_id": str(self.guild_id),  # String for JavaScript BigInt safety
            "data": self.data,
            "timestamp": self.timestamp,
        })


@dataclass
class Connection:
    """A WebSocket connection with metadata."""

    websocket: WebSocket
    user_id: int
    guild_ids: Set[int] = field(default_factory=set)
    connected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class WebSocketManager:
    """Manages WebSocket connections and broadcasts events."""

    def __init__(self):
        """Initialize the WebSocket manager."""
        # Active connections: connection_id -> Connection
        self._connections: Dict[str, Connection] = {}
        # Guild subscriptions: guild_id -> set of connection_ids
        self._guild_subscriptions: Dict[int, Set[str]] = {}
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        # Event queue for buffering
        self._event_queue: asyncio.Queue[WebSocketEvent] = asyncio.Queue()
        # Background task for processing events
        self._broadcast_task: Optional[asyncio.Task] = None

    async def connect(
        self,
        websocket: WebSocket,
        user_id: int,
        guild_ids: List[int]
    ) -> str:
        """Accept a new WebSocket connection.

        Args:
            websocket: The WebSocket connection
            user_id: The user's Discord ID
            guild_ids: List of guild IDs the user has access to

        Returns:
            Connection ID
        """
        await websocket.accept()

        connection_id = f"{user_id}_{id(websocket)}"

        async with self._lock:
            # Create connection
            connection = Connection(
                websocket=websocket,
                user_id=user_id,
                guild_ids=set(guild_ids),
            )
            self._connections[connection_id] = connection

            # Subscribe to guilds
            for guild_id in guild_ids:
                if guild_id not in self._guild_subscriptions:
                    self._guild_subscriptions[guild_id] = set()
                self._guild_subscriptions[guild_id].add(connection_id)

        logger.info(
            f"WebSocket connected: user={user_id}, guilds={guild_ids}, "
            f"total_connections={len(self._connections)}"
        )

        # Send connection confirmation
        await self._send_to_connection(
            connection_id,
            WebSocketEvent(
                type=EventType.CONNECTED,
                guild_id=0,
                data={
                    "connection_id": connection_id,
                    "subscribed_guilds": guild_ids,
                }
            )
        )

        return connection_id

    async def disconnect(self, connection_id: str) -> None:
        """Remove a WebSocket connection.

        Args:
            connection_id: The connection to remove
        """
        async with self._lock:
            if connection_id not in self._connections:
                return

            connection = self._connections[connection_id]

            # Remove from guild subscriptions
            for guild_id in connection.guild_ids:
                if guild_id in self._guild_subscriptions:
                    self._guild_subscriptions[guild_id].discard(connection_id)
                    if not self._guild_subscriptions[guild_id]:
                        del self._guild_subscriptions[guild_id]

            # Remove connection
            del self._connections[connection_id]

        logger.info(
            f"WebSocket disconnected: connection={connection_id}, "
            f"remaining={len(self._connections)}"
        )

    async def broadcast_to_guild(self, event: WebSocketEvent) -> int:
        """Broadcast an event to all connections subscribed to a guild.

        Args:
            event: The event to broadcast

        Returns:
            Number of connections that received the event
        """
        sent_count = 0

        async with self._lock:
            connection_ids = self._guild_subscriptions.get(event.guild_id, set()).copy()

        for connection_id in connection_ids:
            if await self._send_to_connection(connection_id, event):
                sent_count += 1

        if sent_count > 0:
            logger.debug(
                f"Broadcast {event.type.value} to guild {event.guild_id}: "
                f"{sent_count} connections"
            )

        return sent_count

    async def broadcast_to_user(self, user_id: int, event: WebSocketEvent) -> bool:
        """Send an event to a specific user's connections.

        Args:
            user_id: Target user ID
            event: The event to send

        Returns:
            True if sent to at least one connection
        """
        sent = False

        async with self._lock:
            for conn_id, conn in self._connections.items():
                if conn.user_id == user_id:
                    if await self._send_to_connection(conn_id, event):
                        sent = True

        return sent

    async def _send_to_connection(
        self,
        connection_id: str,
        event: WebSocketEvent
    ) -> bool:
        """Send an event to a specific connection.

        Args:
            connection_id: Target connection ID
            event: The event to send

        Returns:
            True if sent successfully
        """
        async with self._lock:
            connection = self._connections.get(connection_id)
            if not connection:
                return False

        try:
            await connection.websocket.send_text(event.to_json())
            return True
        except Exception as e:
            logger.warning(f"Failed to send to {connection_id}: {e}")
            # Schedule disconnect
            asyncio.create_task(self.disconnect(connection_id))
            return False

    async def handle_message(
        self,
        connection_id: str,
        message: str
    ) -> Optional[WebSocketEvent]:
        """Handle an incoming WebSocket message.

        Args:
            connection_id: The connection that sent the message
            message: The raw message text

        Returns:
            Response event if any
        """
        try:
            data = json.loads(message)
            msg_type = data.get("type", "")

            # Handle ping/pong
            if msg_type == "ping":
                return WebSocketEvent(
                    type=EventType.PONG,
                    guild_id=0,
                    data={"timestamp": datetime.now(timezone.utc).isoformat()}
                )

            # Handle subscription updates
            if msg_type == "subscribe":
                guild_id = data.get("guild_id")
                if guild_id:
                    async with self._lock:
                        if connection_id in self._connections:
                            self._connections[connection_id].guild_ids.add(guild_id)
                            if guild_id not in self._guild_subscriptions:
                                self._guild_subscriptions[guild_id] = set()
                            self._guild_subscriptions[guild_id].add(connection_id)
                    logger.info(f"Connection {connection_id} subscribed to guild {guild_id}")

            if msg_type == "unsubscribe":
                guild_id = data.get("guild_id")
                if guild_id:
                    async with self._lock:
                        if connection_id in self._connections:
                            self._connections[connection_id].guild_ids.discard(guild_id)
                        if guild_id in self._guild_subscriptions:
                            self._guild_subscriptions[guild_id].discard(connection_id)

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from {connection_id}: {message[:100]}")
        except Exception as e:
            logger.error(f"Error handling message from {connection_id}: {e}")

        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics.

        Returns:
            Dictionary with stats
        """
        return {
            "total_connections": len(self._connections),
            "guilds_with_connections": len(self._guild_subscriptions),
            "connections_per_guild": {
                str(gid): len(conns)
                for gid, conns in self._guild_subscriptions.items()
            },
        }


# Singleton instance
_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Get or create the WebSocket manager singleton.

    Returns:
        WebSocketManager instance
    """
    global _manager
    if _manager is None:
        _manager = WebSocketManager()
    return _manager


# Helper functions for common broadcasts

async def broadcast_raid_event(
    guild_id: int,
    event_type: EventType,
    raid_data: Dict[str, Any]
) -> int:
    """Broadcast a raid-related event.

    Args:
        guild_id: Target guild ID
        event_type: Type of raid event
        raid_data: Raid data to include

    Returns:
        Number of connections notified
    """
    manager = get_websocket_manager()
    event = WebSocketEvent(
        type=event_type,
        guild_id=guild_id,
        data=raid_data,
    )
    return await manager.broadcast_to_guild(event)


async def broadcast_activity(
    guild_id: int,
    activity_type: str,
    description: str,
    user_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> int:
    """Broadcast an activity event.

    Args:
        guild_id: Target guild ID
        activity_type: Type of activity (e.g., "raid_signup", "raid_created")
        description: Human-readable description
        user_name: User who triggered the activity
        metadata: Additional data

    Returns:
        Number of connections notified
    """
    manager = get_websocket_manager()
    event = WebSocketEvent(
        type=EventType.ACTIVITY_NEW,
        guild_id=guild_id,
        data={
            "activity_type": activity_type,
            "description": description,
            "user_name": user_name,
            "metadata": metadata or {},
        },
    )
    return await manager.broadcast_to_guild(event)
