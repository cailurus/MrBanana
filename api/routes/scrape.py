from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import ScrapeConfigRequest, ScrapeStartRequest
from api.scrape_manager import scrape_manager
from api.constants import DEFAULT_JOBS_LIMIT, DEFAULT_ITEMS_LIMIT
from api.security import validate_path_no_traversal, validate_directory_exists

router = APIRouter()


@router.get("/api/scrape/config")
async def get_scrape_config():
    return scrape_manager.get_config()


@router.post("/api/scrape/config")
async def set_scrape_config(request: ScrapeConfigRequest):
    updates = request.model_dump(exclude_unset=True)
    return scrape_manager.set_config(**updates)


@router.get("/api/scrape/jobs")
async def list_scrape_jobs(limit: int = DEFAULT_JOBS_LIMIT):
    return scrape_manager.list_jobs(limit=limit)


@router.get("/api/scrape/history")
async def list_scrape_history(limit_jobs: int = DEFAULT_JOBS_LIMIT, limit_items_per_job: int = DEFAULT_ITEMS_LIMIT):
    return scrape_manager.list_history_items(limit_jobs=limit_jobs, limit_items_per_job=limit_items_per_job)


@router.get("/api/scrape/items/{job_id}")
async def list_scrape_items(job_id: int, limit: int = DEFAULT_ITEMS_LIMIT):
    return scrape_manager.list_items(job_id=job_id, limit=limit)


@router.post("/api/scrape/start")
async def start_scrape_job(request: ScrapeStartRequest):
    directory = str(request.directory).strip()
    validate_path_no_traversal(directory)
    validate_directory_exists(directory)
    
    # Manual trigger always ignores min_age_sec
    result = scrape_manager.start_job(directory, ignore_min_age=True)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message") or "failed")
    return result


@router.get("/api/scrape/logs/{job_id}")
async def get_scrape_logs(job_id: int, offset: int = 0):
    return scrape_manager.read_log(job_id=job_id, offset=offset)


@router.get("/api/scrape/logs/{job_id}/item")
async def get_scrape_item_logs(job_id: int, filename: str):
    return scrape_manager.read_item_log(job_id=job_id, filename=filename)


@router.delete("/api/scrape/logs/{job_id}")
async def delete_scrape_logs(job_id: int):
    scrape_manager.delete_job_logs(job_id)
    return {"status": "success", "job_id": job_id}


@router.post("/api/scrape/logs/cleanup")
async def cleanup_scrape_logs():
    return scrape_manager.cleanup_logs()


@router.post("/api/scrape/history/clear")
async def clear_scrape_history():
    res = scrape_manager.clear_history()
    if res.get("status") == "error":
        raise HTTPException(status_code=409, detail=res.get("message") or "failed")
    return res


@router.get("/api/scrape/pending_count")
async def get_scrape_pending_count(ignore_min_age: bool = True):
    # Default aligns with manual start behavior (ignore min-age filtering).
    return scrape_manager.pending_count(ignore_min_age=bool(ignore_min_age))
