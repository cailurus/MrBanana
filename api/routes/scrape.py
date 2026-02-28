from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.async_utils import run_sync
from api.dependencies import get_scrape_manager
from api.schemas import ScrapeConfigRequest, ScrapeStartRequest
from api.scrape_manager import ScrapeManager
from api.constants import DEFAULT_JOBS_LIMIT, DEFAULT_ITEMS_LIMIT
from api.security import validate_path_no_traversal, validate_directory_exists

router = APIRouter()


@router.get("/api/scrape/config")
async def get_scrape_config(manager: ScrapeManager = Depends(get_scrape_manager)):
    return manager.get_config()


@router.post("/api/scrape/config")
async def set_scrape_config(request: ScrapeConfigRequest, manager: ScrapeManager = Depends(get_scrape_manager)):
    updates = request.model_dump(exclude_unset=True)
    return manager.set_config(**updates)


@router.get("/api/scrape/jobs")
async def list_scrape_jobs(limit: int = Query(DEFAULT_JOBS_LIMIT, ge=1, le=200), manager: ScrapeManager = Depends(get_scrape_manager)):
    return manager.list_jobs(limit=limit)


@router.get("/api/scrape/history")
async def list_scrape_history(
    limit_jobs: int = Query(DEFAULT_JOBS_LIMIT, ge=1, le=200),
    limit_items_per_job: int = Query(DEFAULT_ITEMS_LIMIT, ge=1, le=1000),
    manager: ScrapeManager = Depends(get_scrape_manager),
):
    return manager.list_history_items(limit_jobs=limit_jobs, limit_items_per_job=limit_items_per_job)


@router.get("/api/scrape/items/{job_id}")
async def list_scrape_items(job_id: int, limit: int = Query(DEFAULT_ITEMS_LIMIT, ge=1, le=1000), manager: ScrapeManager = Depends(get_scrape_manager)):
    return manager.list_items(job_id=job_id, limit=limit)


@router.post("/api/scrape/start")
async def start_scrape_job(request: ScrapeStartRequest, manager: ScrapeManager = Depends(get_scrape_manager)):
    directory = str(request.directory).strip()
    validate_path_no_traversal(directory)
    validate_directory_exists(directory)

    # Manual trigger always ignores min_age_sec
    result = await run_sync(manager.start_job, directory, ignore_min_age=True)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message") or "failed")
    return result


@router.get("/api/scrape/logs/{job_id}")
async def get_scrape_logs(job_id: int, offset: int = 0, manager: ScrapeManager = Depends(get_scrape_manager)):
    return manager.read_log(job_id=job_id, offset=offset)


@router.get("/api/scrape/logs/{job_id}/item")
async def get_scrape_item_logs(job_id: int, filename: str, manager: ScrapeManager = Depends(get_scrape_manager)):
    return manager.read_item_log(job_id=job_id, filename=filename)


@router.delete("/api/scrape/logs/{job_id}")
async def delete_scrape_logs(job_id: int, manager: ScrapeManager = Depends(get_scrape_manager)):
    manager.delete_job_logs(job_id)
    return {"status": "success", "job_id": job_id}


@router.post("/api/scrape/logs/cleanup")
async def cleanup_scrape_logs(manager: ScrapeManager = Depends(get_scrape_manager)):
    return manager.cleanup_logs()


@router.post("/api/scrape/history/clear")
async def clear_scrape_history(manager: ScrapeManager = Depends(get_scrape_manager)):
    res = manager.clear_history()
    if res.get("status") == "error":
        raise HTTPException(status_code=409, detail=res.get("message") or "failed")
    return res


@router.get("/api/scrape/pending_count")
async def get_scrape_pending_count(ignore_min_age: bool = True, manager: ScrapeManager = Depends(get_scrape_manager)):
    return await run_sync(manager.pending_count, ignore_min_age=bool(ignore_min_age))
