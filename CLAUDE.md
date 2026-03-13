# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mr. Banana is a full-stack video download and metadata scraping tool for jable.tv and local video libraries. It consists of three layers: a React frontend, a FastAPI backend, and a core Python library.

## Common Commands

```bash
# Development (runs both API on :8000 and Vite on :5173 with hot reload)
make dev

# Run only backend or frontend
make api-dev
make web-dev

# Build frontend to ./static and serve
make fe
make serve

# Install dependencies
make py-install          # Python deps from requirements.txt
make web-install         # Node deps

# Testing
pytest tests/            # Run all tests
pytest tests/test_api.py # Run a single test file

# Docker
make docker-build IMAGE=yourname/mr-banana TAG=latest
make docker-run IMAGE=yourname/mr-banana TAG=latest
```

## Architecture

```
Frontend (React/Vite :5173)
    ↓ REST /api/* + WebSocket /ws
API Routes (FastAPI :8000)
    ↓
Managers (DownloadManager, ScrapeManager)
    ↓
Core Library (mr_banana/)
    ├→ MovieDownloader → JableExtractor → HLSDownloader
    ├→ ScrapeRunner → Crawlers (javdb, javbus, dmm, etc.)
    └→ Utils (config, history, network, browser)
```

**Data flow:** User action in web UI → FastAPI endpoint → Manager creates task and broadcasts status via WebSocket → Core library executes work → Progress updates stream back to frontend in real-time.

### Backend (`api/`)

- `api/main.py` — FastAPI app factory, CORS, static file serving, lifespan
- `api/routes/` — 10 routers: download, library, scrape, search, subscription, system, player, ws, version, player_open
- `api/manager.py` — DownloadManager: task orchestration, WebSocket broadcast, history
- `api/scrape_manager.py` — ScrapeManager: scraping orchestration
- `api/scheduler.py` — APScheduler for recurring tasks
- `api/security.py` — Path validation, directory access control

### Core Library (`mr_banana/`)

- `mr_banana/cli.py` — CLI entry point (`python -m mr_banana.cli`)
- `mr_banana/downloader.py` — MovieDownloader (extraction + HLS download orchestration)
- `mr_banana/extractors/jable.py` — Video info parsing, m3u8 URL extraction
- `mr_banana/scraper/runner.py` — Scraper orchestrator; `crawlers/` has pluggable crawler classes; `writers/nfo.py` generates NFO files; `merger.py` merges results from multiple crawlers
- `mr_banana/utils/` — hls.py (segment download with resumption), network.py (HTTP + browser automation via patchright), browser.py (Patchright/Playwright management), config.py (JSON config), history.py (SQLite), subscription.py, logger.py, translate.py, telegram.py

### Frontend (`web/`)

- `web/src/App.jsx` — Main app with 5 tabs
- `web/src/stores/` — Zustand stores: downloadStore, scrapeStore, subscriptionStore, playerStore, uiStore
- `web/src/components/` — UI components organized by feature
- `web/src/i18n.js` — Internationalization (multiple languages)

## Tech Stack

- **Backend:** Python 3.10+, FastAPI, Uvicorn, Patchright (browser automation), curl-cffi, httpx, BeautifulSoup4, SQLite, Pydantic 2.0+
- **Frontend:** React 18, Vite 5, Zustand 5, Tailwind CSS 3, Axios
- **Infrastructure:** Docker (multi-stage, Python 3.11 slim), GitHub Actions CI
- **Testing:** Pytest, pytest-asyncio
- **External deps:** FFmpeg (segment merging), Chromium (via Patchright)

## Key Environment Variables

- `MR_BANANA_CONFIG_DIR` — Config directory (default: /config in Docker, project dir locally)
- `ALLOWED_BROWSE_ROOTS` — Comma-separated paths for remote browsing (default: /data)
- `LOG_LEVEL` / `MR_BANANA_LOG_LEVEL` — Logging level
- `CORS_ORIGINS` — CORS allowed origins (default: *)
