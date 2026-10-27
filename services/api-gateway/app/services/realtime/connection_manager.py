"""
WebSocket Connection Manager for Realtime Analytics KPI feed (R15-M3).

Manages active WebSocket client connections, safe fanout broadcasting of UTF-8 JSON
text frames, and automatic eviction of disconnected or failing sockets.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Set

from fastapi import WebSocket

logger = logging.getLogger("api_gateway.realtime.connection_manager")


class ConnectionManager:
    """
    Async-safe connection manager for multiple simultaneous WebSocket clients.
    """

    def __init__(self) -> None:
        self._active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Register a newly accepted WebSocket connection."""
        async with self._lock:
            self._active_connections.add(websocket)
            client_ip = getattr(websocket.client, "host", "unknown")
            logger.info(
                "WebSocket client connected: %s (total active: %d)",
                client_ip,
                len(self._active_connections),
            )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected WebSocket connection."""
        async with self._lock:
            self._active_connections.discard(websocket)
            client_ip = getattr(websocket.client, "host", "unknown")
            logger.info(
                "WebSocket client disconnected: %s (total active: %d)",
                client_ip,
                len(self._active_connections),
            )

    async def broadcast(self, message: str) -> int:
        """
        Broadcast a UTF-8 JSON text frame to all connected clients.

        Failed sends (e.g. client dropped TCP connection, socket closed) are safely
        caught and the broken sockets are evicted without impeding delivery to other clients.

        Returns:
            Number of clients successfully sent the message.
        """
        async with self._lock:
            connections = list(self._active_connections)

        if not connections:
            return 0

        failed_connections: list[WebSocket] = []
        successful_sends = 0

        for ws in connections:
            try:
                await ws.send_text(message)
                successful_sends += 1
            except Exception as exc:
                client_ip = getattr(ws.client, "host", "unknown")
                logger.warning(
                    "Failed to send text frame to client %s: %s; scheduling eviction",
                    client_ip,
                    exc,
                )
                failed_connections.append(ws)

        if failed_connections:
            async with self._lock:
                for ws in failed_connections:
                    self._active_connections.discard(ws)

        return successful_sends

    async def close_all(self, code: int = 1001, reason: str = "Server shutdown") -> None:
        """Gracefully close all active client connections during application shutdown."""
        async with self._lock:
            connections = list(self._active_connections)
            self._active_connections.clear()

        for ws in connections:
            try:
                await ws.close(code=code, reason=reason)
            except Exception as exc:
                logger.debug("Error closing websocket during shutdown: %s", exc)

    async def count(self) -> int:
        """Return number of currently active connections."""
        async with self._lock:
            return len(self._active_connections)


# Global singleton instance
connection_manager = ConnectionManager()
