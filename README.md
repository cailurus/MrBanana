# Mr. Banana

Download from Jable.tv and scrape local videos (generate NFO/artwork) with CLI or Web UI. Backend: FastAPI. Frontend: React/Vite.

## Features

- Concurrent HLS download with Cloudflare bypass
- Automatic segment merge (FFmpeg)
- Web UI for batch download & history
- Local scraper: scan folders, fetch metadata by code, write `*.nfo` + artwork

## Project layout

```
MrBanana/
├── api/          # FastAPI backend
├── mr_banana/    # Core library (CLI, downloader, scraper, utils)
├── web/          # React/Vite frontend source
├── static/       # Deployed frontend (built)
├── data/         # Local DB (ignored)
├── logs/         # Logs (ignored)
└── scripts/, tests/, Dockerfile, Makefile, pyproject.toml
```

## Quick start

```bash
git clone https://github.com/cailurus/MrBanana.git
cd MrBanana
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make py-install
make web-install
```

### Run (live dev)

```bash
make dev  # starts FastAPI on 8000 + Vite on 5173 with HMR
```
- Frontend: http://localhost:5173
- Backend:  http://127.0.0.1:8000

### Build & serve (single port)

```bash
make fe     # build frontend and copy to ./static
make serve  # FastAPI serves ./static on 8000
```

`make fe` vs `make dev`: `fe` builds static assets for production/serve; `dev` runs both servers with hot reload and no static copy.

### Docker

```bash
make docker-build IMAGE=yourname/mr-banana TAG=latest
make docker-run   IMAGE=yourname/mr-banana TAG=latest
```

## CLI usage

```bash
python -m mr_banana.cli --url <VIDEO_URL> --output_dir <OUT_DIR>
```
Common flags:
- `--url` (required): Jable.tv video URL
- `--output_dir`: output folder
- `--format`: filename format, supports `{id}` and `{title}`
- `-v/--verbose`: verbose logging

## Requirements

- Python 3.10+
- FFmpeg (merge segments)
- patchright + Chromium (Cloudflare bypass; `patchright install chromium` on first run)

## Environment variables

| Name | Description | Default |
|------|-------------|---------|
| `LOG_LEVEL` | Log level | `INFO` |
| `MR_BANANA_LOG_LEVEL` | Overrides log level | `INFO` |
| `ALLOWED_BROWSE_ROOTS` | Comma-separated paths for remote directory browsing | `/data` |

## Docker volume mounts

When running in Docker, map your host directories into the container. The syntax is `host_path:container_path`.

### Persistent storage

The container uses two main directories:

| Container path | Description | Recommended host path |
|----------------|-------------|----------------------|
| `/config` | Config file, database, logs (persisted) | `/volume/mrbanana/config` |
| `/data` | Media files (videos, downloads) | `/volume/data` |

**Important**: Mount `/config` to preserve your settings, subscription database, and logs across container updates.

### Example: Recommended setup

```bash
docker run -d \
  --name mr-banana \
  -p 8000:8000 \
  -v /volume/mrbanana/config:/config \
  -v /volume/data:/data \
  -e ALLOWED_BROWSE_ROOTS="/data" \
  cailurus/mr-banana:latest
```

| Host path | Container path | Description |
|-----------|----------------|-------------|
| `/volume/mrbanana/config` | `/config` | Config, database, logs |
| `/volume/data` | `/data` | Your media directory |

Contents saved in `/config`:
- `config.json` - Application settings
- `mr_banana_subscription.db` - Subscription database
- `logs/` - Application logs

The `ALLOWED_BROWSE_ROOTS` environment variable controls which directories users can browse via the web UI when accessing remotely.

## Browser Userscript

Install the userscript to add quick buttons on JavDB and Jable websites:

### Installation

1. Install [Tampermonkey](https://www.tampermonkey.net/) (Chrome/Firefox/Edge/Safari)
2. **Important**: Enable user scripts in Tampermonkey settings:
   - Click Tampermonkey icon → Dashboard → Settings tab
   - Find "Security" section → Enable "Allow User Scripts"
3. Click to install: [mrbanana-helper.user.js](https://raw.githubusercontent.com/cailurus/MrBanana/main/userscripts/mrbanana-helper.user.js)
4. Configure your Mr. Banana server address (click Tampermonkey icon → ⚙️ Mr. Banana 设置)

### Features

- **JavDB**: Adds "Subscribe to Mr. Banana" button on video detail pages
- **Jable**: Adds "Download to Mr. Banana" button on video pages

## License

[MIT License](LICENSE)