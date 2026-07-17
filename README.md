# Mr. Banana

<p align="center">
  <img src="https://raw.githubusercontent.com/cailurus/MrBanana/main/web/public/favicon.svg" alt="Mr. Banana Logo" width="120" height="120">
</p>

<p align="center">
  <strong>Jable.tv Video Downloader & JAV Library Manager with Web UI</strong>
</p>

<p align="center">
  <a href="https://github.com/cailurus/MrBanana/releases"><img src="https://img.shields.io/github/v/release/cailurus/MrBanana?style=flat-square&color=blue" alt="GitHub Release"></a>
  <a href="https://github.com/cailurus/MrBanana/blob/main/LICENSE"><img src="https://img.shields.io/github/license/cailurus/MrBanana?style=flat-square" alt="License"></a>
  <a href="https://hub.docker.com/r/cailurus/mr-banana"><img src="https://img.shields.io/docker/pulls/cailurus/mr-banana?style=flat-square&logo=docker&logoColor=white" alt="Docker Pulls"></a>
  <a href="#quick-start-windows"><img src="https://img.shields.io/badge/Windows-PS%20Script-0078D6?style=flat-square&logo=powershell&logoColor=white" alt="Windows"></a>
  <a href="https://github.com/cailurus/MrBanana/stargazers"><img src="https://img.shields.io/github/stars/cailurus/MrBanana?style=flat-square&color=yellow" alt="GitHub Stars"></a>
</p>

<p align="center">
  <a href="./README_CN.md">中文文档</a>
</p>

---

## Features

- **⚡ High-Speed Download** — Concurrent HLS download from Jable.tv, auto bypass Cloudflare via cookie injection (no browser needed), FFmpeg segment merge
- **📚 Batch Download** — Submit a jable.tv list page URL (favorites / watch-later) and enqueue all videos at once
- **🏷️ Metadata Scraping** — Scan local folders, fetch metadata from JavDB, JavBus, DMM, JavTrailers, ThePornDB; generate Kodi-compatible NFO and artwork
- **🖥️ Web UI** — React-based interface with download queue, scraping, subscription management, and media library browser
- **🔔 Subscription Tracking** — Monitor magnet link updates on JavDB with Telegram notifications
- **📡 Userscripts** — Tampermonkey extensions for one-click download/subscribe on JavDB and Jable
- **⏸️ Pause & Resume** — Cancel mid-download and resume later without re-downloading completed segments
- **🔐 Cloudflare Bypass** — Auto-extract cookies from your logged-in Chrome session; skip Chromium on subsequent downloads

## Quick Start (Windows)

```powershell
.\run.ps1
```

1. Auto-launches Chrome with CDP debugging for cookie extraction
2. Opens jable.tv login page — log in and press any key
3. Automatically extracts cookies → saves to config → starts server
4. Open http://127.0.0.1:8000

No manual `.venv` activation needed.

## Docker (Recommended)

```bash
docker run -d \
  --name mr-banana \
  -p 8000:8000 \
  -v /your/config:/config \
  -v /your/media:/data \
  -e ALLOWED_BROWSE_ROOTS="/data" \
  cailurus/mr-banana:latest
```

Open http://localhost:8000

> **Note:** The Docker image uses Patchright (Chromium) for initial Cloudflare bypass. After adding your jable.tv cookie in Web UI → Download Settings, downloads will use the fast cookie-direct mode.

### Docker Compose

```yaml
services:
  mr-banana:
    image: cailurus/mr-banana:latest
    container_name: mr-banana
    ports:
      - "8000:8000"
    volumes:
      - /your/config:/config
      - /your/media:/data
    environment:
      - ALLOWED_BROWSE_ROOTS=/data
    restart: unless-stopped
```

### Volume Mounts

| Container Path | Description | Example Host Path |
|----------------|-------------|-------------------|
| `/config` | Config, database, logs (persisted) | `/volume/mrbanana/config` |
| `/data` | Media files (videos, downloads) | `/volume/data` |

`/config` contains: `config.json`, `mr_banana_subscription.db`, `logs/`

## Architecture

```
Frontend (React / Vite)
    ↓  REST /api/* + WebSocket /ws
API Layer (FastAPI)
    ↓
Managers (Download / Scrape / Subscription)
    ↓
Core Library
    ├── Downloader → JableExtractor → HLS (curl_cffi or Patchright)
    ├── Scraper → Crawlers (JavDB, JavBus, DMM, ...) → NFO Writer
    └── Utils (config, history, network, browser, translate)
```

## Local Development

### Prerequisites

- Python 3.10+
- Node.js 18+
- FFmpeg
- (optional) Chrome for CDP cookie extraction

### Setup

```bash
git clone https://github.com/cailurus/MrBanana.git
cd MrBanana
python -m venv .venv && .venv\Scripts\activate  # Windows
pip install -r requirements.txt
cd web && npm install && cd ..
```

### Development

```bash
make dev           # FastAPI :8000 + Vite :5173 with hot reload
# or
python run.ps1     # Single window: builds frontend + starts FastAPI
```

### Production Build

```bash
make fe            # Build frontend → ./static
make serve         # FastAPI serves ./static on :8000
```

## CLI Usage

```bash
python -m mr_banana.cli --url <VIDEO_URL> --output_dir <OUT_DIR>
```

| Flag | Description |
|------|-------------|
| `--url` | Jable.tv video URL (required) |
| `--output_dir` | Output folder |
| `--format` | Filename format — supports `{id}` and `{title}` |
| `-v` | Verbose logging |

## API Endpoints (New)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/download/batch` | Enqueue all videos from a jable.tv list page |
| `GET` | `/api/download/batch/preview` | Preview videos on a jable.tv list page |
| `GET` | `/api/jable/lists` | Fetch your liked and watch-later lists (CDP pagination) |
| `POST` | `/api/jable/login` | Login via CDP cookie extraction or manual browser |

## Browser Userscript

1. Install [Tampermonkey](https://www.tampermonkey.net/)
2. Click to install: [mrbanana-helper.user.js](https://raw.githubusercontent.com/cailurus/MrBanana/main/userscripts/mrbanana-helper.user.js)
3. Configure your Mr. Banana server address in Tampermonkey settings

**Supported sites:**
- **JavDB** — "Subscribe to Mr. Banana" button on detail pages
- **Jable** — "Download to Mr. Banana" button on video pages

## Cookie Management

Mr. Banana can extract Cloudflare bypass cookies from your existing Chrome login session:

```bash
# Method 1: Auto-extract via CDP (requires Chrome running on port 9222)
python scripts/mcp_cdp_cookie_server.py

# Method 2: Browser console
# Open jable.tv → F12 → Console → paste scripts/extract_jable_cookie.js → Enter
```

Paste the cookie string into **Web UI → Download Settings → Jable Cookie**. Subsequent downloads will use the fast cookie-direct mode (no browser launch).

## Environment Variables

| Name | Description | Default |
|------|-------------|---------|
| `LOG_LEVEL` | Log level | `INFO` |
| `MR_BANANA_LOG_LEVEL` | Override log level | `INFO` |
| `MR_BANANA_CONFIG_DIR` | Config directory | `/config` (Docker) |
| `ALLOWED_BROWSE_ROOTS` | Directories browsable in Web UI | `/data` |
| `CORS_ORIGINS` | CORS allowed origins | `*` |

## License

[MIT License](LICENSE)