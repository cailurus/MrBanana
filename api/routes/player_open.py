from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import subprocess
import platform
import os

from api.security import get_all_media_roots, is_path_under_roots

router = APIRouter()

ALLOWED_VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"}


class PlayerOpenRequest(BaseModel):
    file_path: str


@router.post("/api/player/open")
async def open_with_system_player(request: PlayerOpenRequest):
    file_path = request.file_path
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    # Security: validate file extension is a known video type
    ext = Path(file_path).suffix.lower()
    if ext not in ALLOWED_VIDEO_EXTS:
        raise HTTPException(status_code=403, detail="File type not allowed")

    # Security: validate path is under configured media directories
    if not is_path_under_roots(file_path, get_all_media_roots()):
        raise HTTPException(status_code=403, detail="Path is not under allowed media directories")

    system = platform.system()
    try:
        if system == "Darwin":  # macOS
            subprocess.Popen(["open", file_path])
        elif system == "Windows":
            os.startfile(file_path)
        else:  # Linux
            subprocess.Popen(["xdg-open", file_path])
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
