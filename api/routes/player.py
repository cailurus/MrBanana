from __future__ import annotations

from fastapi import APIRouter

from api.schemas import PlayerConfigRequest
from mr_banana.utils.config import load_config, save_config

router = APIRouter()


@router.get("/api/player/config")
async def get_player_config():
    cfg = load_config()
    return {
        "player_root_dir": getattr(cfg, "player_root_dir", "") or "",
    }


@router.post("/api/player/config")
async def set_player_config(request: PlayerConfigRequest):
    cfg = load_config()
    if request.player_root_dir is not None:
        cfg.player_root_dir = str(request.player_root_dir)
    save_config(cfg)
    return await get_player_config()
