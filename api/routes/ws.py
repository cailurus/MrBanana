from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.manager import manager

router = APIRouter()


def _stable_stringify(tasks: dict[str, dict[str, Any]]) -> str:
    """Create a stable JSON string for comparison."""
    return json.dumps(tasks, sort_keys=True, default=str)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time task updates.
    
    Optimization: Only sends updates when task state actually changes,
    reducing unnecessary network traffic and client re-renders.
    """
    await manager.connect(websocket)
    last_state: str = ""
    
    try:
        while True:
            if manager.active_tasks:
                current_state = _stable_stringify(manager.active_tasks)
                
                # Only send update if state has changed
                if current_state != last_state:
                    await websocket.send_json({
                        "type": "update",
                        "tasks": list(manager.active_tasks.values()),
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
