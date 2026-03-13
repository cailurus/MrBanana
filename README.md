# Mr. Banana

<p align="center">
  <img src="https://raw.githubusercontent.com/cailurus/MrBanana/main/web/public/favicon.svg" alt="Mr. Banana Logo" width="120" height="120">
</p>

<p align="center">
  <strong>Download from Jable.tv & scrape local video libraries with a Web UI</strong>
</p>

<p align="center">
  <a href="https://github.com/cailurus/MrBanana/releases"><img src="https://img.shields.io/github/v/release/cailurus/MrBanana?style=flat-square&color=blue" alt="GitHub Release"></a>
  <a href="https://github.com/cailurus/MrBanana/blob/main/LICENSE"><img src="https://img.shields.io/github/license/cailurus/MrBanana?style=flat-square" alt="License"></a>
  <a href="https://hub.docker.com/r/cailurus/mr-banana"><img src="https://img.shields.io/docker/pulls/cailurus/mr-banana?style=flat-square&logo=docker&logoColor=white" alt="Docker Pulls"></a>
  <a href="https://hub.docker.com/r/cailurus/mr-banana"><img src="https://img.shields.io/docker/image-size/cailurus/mr-banana/latest?style=flat-square&logo=docker&logoColor=white&label=image%20size" alt="Docker Image Size"></a>
  <a href="https://github.com/cailurus/MrBanana/stargazers"><img src="https://img.shields.io/github/stars/cailurus/MrBanana?style=flat-square&color=yellow" alt="GitHub Stars"></a>
</p>

<p align="center">
  <a href="https://raw.githubusercontent.com/cailurus/MrBanana/main/userscripts/mrbanana-helper.user.js"><img src="https://img.shields.io/badge/Tampermonkey-Install%20Script-00485B?style=flat-square&logo=tampermonkey&logoColor=white" alt="Install Userscript"></a>
  <a href="#docker-recommended"><img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker Ready"></a>
  <a href="#local-development"><img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+"></a>
</p>

<p align="center">
  <a href="./README_CN.md">中文文档</a>
</p>

---

## Features

- **Video Download** — Concurrent HLS download from Jable.tv with Cloudflare bypass, automatic segment merge via FFmpeg
- **Metadata Scraping** — Scan local folders, fetch metadata from multiple sources (JavDB, JavBus, DMM, JavTrailers, ThePornDB), generate Kodi-compatible NFO files and artwork
- **Web UI** — React-based interface for batch download, scraping, subscription management, and library browsing
- **Subscription Tracking** — Monitor magnet link updates on JavDB with optional Telegram notifications
- **CLI** — Command-line interface for scripted downloads
- **Browser Userscripts** — Tampermonkey extensions for one-click download/subscribe on JavDB and Jable

## Architecture

```
Frontend (React / Vite)
    ↓  REST /api/* + WebSocket /ws
API Layer (FastAPI)
    ↓
Managers (Download / Scrape / Subscription)
    ↓
Core Library
    ├── Downloader → JableExtractor → HLS
    ├── Scraper → Crawlers (JavDB, JavBus, DMM, ...) → NFO Writer
    └── Utils (config, history, network, browser, translate)
```

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

Open http://localhost:8000 in your browser.

### Volume Mounts

| Container Path | Description | Example Host Path |
|----------------|-------------|-------------------|
| `/config` | Config, database, logs (persisted across updates) | `/volume/mrbanana/config` |
| `/data` | Media files (videos, downloads) | `/volume/data` |

Files stored in `/config`:
- `config.json` — Application settings
- `mr_banana_subscription.db` — Subscription database
- `logs/` — Application logs

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

## Local Development

### Prerequisites

- Python 3.10+
- Node.js 18+
- FFmpeg
- patchright + Chromium (`patchright install chromium` on first run)

### Setup

```bash
git clone https://github.com/cailurus/MrBanana.git
cd MrBanana
python3 -m venv .venv && source .venv/bin/activate
make py-install    # Install Python dependencies
make web-install   # Install Node dependencies
```

### Development

```bash
make dev           # FastAPI :8000 + Vite :5173 with hot reload
make test          # Run tests
make test-quick    # Run tests (quiet output)
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

## Browser Userscript

1. Install [Tampermonkey](https://www.tampermonkey.net/)
2. Click to install: [mrbanana-helper.user.js](https://raw.githubusercontent.com/cailurus/MrBanana/main/userscripts/mrbanana-helper.user.js)
3. Configure your Mr. Banana server address in Tampermonkey settings

**Supported sites:**
- **JavDB** — "Subscribe to Mr. Banana" button on detail pages
- **Jable** — "Download to Mr. Banana" button on video pages

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
