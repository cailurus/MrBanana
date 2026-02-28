from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_download_manager
from api.manager import DownloadManager
from api.schemas import (
    DownloadConfigRequest,
    DownloadRequest,
    ResumeRequest,
    TaskRequest,
)
from api.constants import (
    DEFAULT_HISTORY_LIMIT,
    MIN_DOWNLOAD_WORKERS,
    MAX_DOWNLOAD_WORKERS,
    VALID_RESOLUTIONS,
)
from api.security import validate_path_no_traversal, validate_directory_exists
from mr_banana.utils.config import load_config, save_config

router = APIRouter()


@router.get("/api/download/config")
async def get_download_config():
    cfg = load_config()
    return {
        "output_dir": cfg.output_dir or "",
        "max_download_workers": int(cfg.max_download_workers or 16),
        "filename_format": cfg.filename_format,
        "download_use_proxy": bool(cfg.download_use_proxy),
        "download_proxy_url": cfg.download_proxy_url or "",
        "download_resolution": cfg.download_resolution or "best",
        "download_scrape_after_default": bool(cfg.download_scrape_after_default),
    }


@router.post("/api/download/config")
async def save_download_config(request: DownloadConfigRequest):
    cfg = load_config()

    if request.output_dir is not None:
        output_dir = str(request.output_dir).strip()
        validate_path_no_traversal(output_dir)
        cfg.output_dir = output_dir
    if request.max_download_workers is not None:
        cfg.max_download_workers = max(
            MIN_DOWNLOAD_WORKERS,
            min(int(request.max_download_workers), MAX_DOWNLOAD_WORKERS)
        )
    if request.filename_format is not None:
        cfg.filename_format = str(request.filename_format) or "{id}"
    if request.download_use_proxy is not None:
        cfg.download_use_proxy = bool(request.download_use_proxy)
    if request.download_proxy_url is not None:
        cfg.download_proxy_url = str(request.download_proxy_url)
    if request.download_resolution is not None:
        res = str(request.download_resolution)
        if res not in VALID_RESOLUTIONS:
            raise HTTPException(status_code=400, detail="invalid download_resolution")
        cfg.download_resolution = res
    if request.download_scrape_after_default is not None:
        cfg.download_scrape_after_default = bool(request.download_scrape_after_default)

    save_config(cfg)
    return await get_download_config()


@router.post("/api/download")
async def start_download(
    request: DownloadRequest,
    manager: DownloadManager = Depends(get_download_manager),
):
    output_dir = str(request.output_dir).strip()
    if not output_dir:
        raise HTTPException(status_code=400, detail="output_dir is required")
    validate_path_no_traversal(output_dir)

    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create directory: {e}")

    result = manager.start_download(
        request.url,
        output_dir,
        scrape_after_download=bool(request.scrape_after_download),
    )
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.get("/api/history")
async def get_history(
    limit: int = Query(DEFAULT_HISTORY_LIMIT, ge=1, le=500),
    manager: DownloadManager = Depends(get_download_manager),
):
    history = manager.history_manager.get_history(limit)
    return [dict(row) for row in history]


@router.post("/api/resume")
async def resume_download(
    request: ResumeRequest,
    manager: DownloadManager = Depends(get_download_manager),
):
    output_dir = str(request.output_dir).strip()
    if not output_dir:
        raise HTTPException(status_code=400, detail="output_dir is required")
    validate_path_no_traversal(output_dir)

    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create directory: {e}")

    result = manager.resume_download(request.task_id, output_dir)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/api/pause")
async def pause_download(
    request: TaskRequest,
    manager: DownloadManager = Depends(get_download_manager),
):
    result = manager.pause_task(request.task_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/api/delete")
async def delete_task(
    request: TaskRequest,
    manager: DownloadManager = Depends(get_download_manager),
):
    result = manager.delete_task(request.task_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.get("/api/logs/{task_id}")
async def get_task_logs(
    task_id: int,
    offset: int = 0,
    manager: DownloadManager = Depends(get_download_manager),
):
    return manager.read_task_log(task_id=task_id, offset=offset)


@router.post("/api/download/logs/cleanup")
async def cleanup_download_logs(
    manager: DownloadManager = Depends(get_download_manager),
):
    return manager.cleanup_logs()


@router.post("/api/download/history/clear")
async def clear_download_history(
    manager: DownloadManager = Depends(get_download_manager),
):
    res = manager.clear_history()
    if res.get("status") == "error":
        raise HTTPException(status_code=409, detail=res.get("message") or "failed")
    return res
