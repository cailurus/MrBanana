from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import subprocess
import platform
import os

router = APIRouter()

class PlayerOpenRequest(BaseModel):
    file_path: str

@router.post("/api/player/open")
async def open_with_system_player(request: PlayerOpenRequest):
    file_path = request.file_path
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    system = platform.system()
    try:
        if system == "Darwin":  # macOS
            subprocess.Popen(["open", file_path])
        elif system == "Windows":
            subprocess.Popen(["start", "", file_path], shell=True)
        else:  # Linux
            subprocess.Popen(["xdg-open", file_path])
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
