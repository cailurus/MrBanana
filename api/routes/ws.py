from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from api.dependencies import get_download_manager
from api.manager import DownloadManager

router = APIRouter()


def _stable_stringify(tasks: dict[str, dict[str, Any]]) -> str:
    """Create a stable JSON string for comparison."""
    return json.dumps(tasks, sort_keys=True, default=str)


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    manager: DownloadManager = Depends(get_download_manager),
) -> None:
    """WebSocket endpoint for real-time task updates.

    Optimization: Only sends updates when task state actually changes,
    reducing unnecessary network traffic and client re-renders.
    """
    await manager.connect(websocket)
    last_state: str = ""

    try:
        while True:
            tasks_snapshot = manager.get_active_tasks_snapshot()

            if tasks_snapshot:
                current_state = _stable_stringify(tasks_snapshot)

                # Only send update if state has changed
                if current_state != last_state:
                    await websocket.send_json({
                        "type": "update",
                        "tasks": list(tasks_snapshot.values()),
                    })
                    last_state = current_state
            else:
                # No active tasks - send ping and reset state tracking
                if last_state:
                    # State changed from having tasks to empty
                    await websocket.send_json({
                        "type": "update",
                        "tasks": [],
                    })
                    last_state = ""
                else:
                    # Keep connection alive with periodic ping
                    await websocket.send_json({"type": "ping"})

            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
