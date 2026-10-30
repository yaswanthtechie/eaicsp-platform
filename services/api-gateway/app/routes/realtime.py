"""
WebSocket route for Live Dashboard Analytics KPIs feed (R15-M3).

Path:
    WS /api/v1/analytics/kpis/real-time
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.realtime.auth import ws_auth_service
from app.services.realtime.connection_manager import connection_manager

logger = logging.getLogger("api_gateway.realtime.route")

router = APIRouter(
    tags=["Realtime Analytics"],
)


@router.websocket("/api/v1/analytics/kpis/real-time")
async def realtime_kpis_websocket(websocket: WebSocket) -> None:
    """
    Realtime WebSocket streaming endpoint for Live Dashboard KPI and operational events.

    Handshake:
    - Supports query parameter token (?token=<JWT>)
    - Supports WebSocket subprotocol header (Sec-WebSocket-Protocol: bearer, <JWT>)
    - Enforces Platform /verify authentication with a 2-second timeout.
    - Rejects unauthorized roles with close code 4403.
    - Rejects missing/invalid tokens with close code 4401.
    - Fails closed with 1013 if Platform is unreachable.

    Heartbeats:
    - Handles transport-level WebSocket Ping/Pong frames.
    - Handles application-level JSON ping:
      Client sends {"type": "ping"}; Server replies {"type": "pong", "timestamp": "..."}
    """
    # 1. Authenticate & Authorize
    is_auth, close_code, close_reason, user_data, subprotocol = await ws_auth_service.authenticate(websocket)
    if not is_auth:
        logger.info(
            "Closing unauthorized WebSocket handshake (code=%s, reason=%s)",
            close_code,
            close_reason,
        )

        await websocket.accept(subprotocol=subprotocol)

        await websocket.close(
            code=close_code or 4401,
            reason=close_reason or "Unauthorized",
        )
        return

    # 2. Accept connection
    if subprotocol:
        await websocket.accept(subprotocol=subprotocol)
    else:
        await websocket.accept()

    await connection_manager.connect(websocket)

    # 3. Connection listen loop (heartbeats and keep-alives)
    try:
        while True:
            text = await websocket.receive_text()
            if not text:
                continue

            try:
                msg = json.loads(text)
                if isinstance(msg, dict) and msg.get("type") == "ping":
                    pong_payload = {
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    await websocket.send_text(json.dumps(pong_payload))
            except json.JSONDecodeError:
                # Client sent non-JSON text; ignore gracefully
                pass

    except WebSocketDisconnect:
        await connection_manager.disconnect(websocket)
    except Exception as exc:
        logger.debug("WebSocket connection terminated with exception: %s", exc)
        await connection_manager.disconnect(websocket)
