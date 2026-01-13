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
| `ALLOWED_BROWSE_ROOTS` | Comma-separated paths for remote directory browsing | `/app/downloads,/downloads,/media,/data` |

## Docker volume mounts

When running in Docker, you can map local directories into the container:

```bash
docker run -d \
  -p 8000:8000 \
  -v /your/local/downloads:/app/downloads \
  -v /your/local/media:/media \
  -e ALLOWED_BROWSE_ROOTS="/app/downloads,/media" \
  yourname/mr-banana:latest
```

The `ALLOWED_BROWSE_ROOTS` environment variable controls which directories users can browse via the web UI when accessing remotely.

## License

[MIT License](LICENSE)