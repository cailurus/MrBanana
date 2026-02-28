SHELL := /bin/bash

# ------------------------------
# Mr. Banana Makefile
#
# Goal: Common entrypoints for local dev, build, and Docker.
# This file only wires commands; business logic lives under api/ and mr_banana/.
# ------------------------------

# Overridable commands (e.g., make api-dev PYTHON=python)
PYTHON ?= python3
PIP ?= pip3
NPM ?= npm

# Local dev ports (frontend/backend separated: Vite 5173 -> proxies to FastAPI 8000)
API_HOST ?= 127.0.0.1
API_PORT ?= 8000
WEB_PORT ?= 5173

# Docker image/container settings (override via: make docker-build IMAGE=xxx TAG=yyy)
IMAGE ?= mr-banana
TAG ?= latest
CONTAINER_NAME ?= mr-banana-app
DOCKER_PORT ?= 8000

.PHONY: help
# Print common commands (no execution)
help:
	@echo "Mr. Banana - Common commands"
	@echo ""
	@echo "Local dev (frontend + backend separated):"
	@echo "  make py-install        Install Python deps (requirements.txt)"
	@echo "  make web-install       Install frontend deps (web/)"
	@echo "  make api-dev           Start FastAPI (reload)  http://$(API_HOST):$(API_PORT)"
	@echo "  make web-dev           Start Vite dev server   http://localhost:$(WEB_PORT)"
	@echo "  make dev               Run api-dev and web-dev in parallel"
	@echo ""
	@echo "Single-port serve (FastAPI hosts built frontend):"
	@echo "  make fe                Build frontend and copy to ./static"
	@echo "  make serve             Start FastAPI hosting ./static  http://$(API_HOST):$(API_PORT)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build      Build image $(IMAGE):$(TAG)"
	@echo "  make docker-run        Run container and map port :$(DOCKER_PORT)"
	@echo "  make docker-stop       Stop/remove container $(CONTAINER_NAME)"
	@echo "  make docker-logs       Follow container logs"
	@echo "  make docker-push       Push image $(IMAGE):$(TAG)"

.PHONY: clean
# Clean Python/JS artifacts, static bundles, logs, caches, local DBs
clean:
	rm -rf dist/ build/ *.egg-info
	rm -rf static/ web/dist/
	rm -rf logs/*
	rm -f data/*.db data/*.db-shm data/*.db-wal
	rm -rf __pycache__ */__pycache__ .pytest_cache .ruff_cache .mypy_cache .vite

.PHONY: py-install
# Install Python dependencies (this project uses requirements.txt, not published to PyPI)
py-install:
	$(PYTHON) -m pip install -r requirements.txt

.PHONY: web-install
# Install frontend dependencies (Node toolchain: npm install)
web-install:
	cd web && $(NPM) install

.PHONY: api-dev
# Start FastAPI dev server (hot reload); frontend accesses /api and /ws via Vite proxy
api-dev: py-install
	$(PYTHON) -m uvicorn api.main:app --reload --host $(API_HOST) --port $(API_PORT)

.PHONY: web-dev
# Start Vite dev server (default port 5173, override via WEB_PORT)
web-dev:
	cd web && $(NPM) run dev -- --port $(WEB_PORT)

.PHONY: dev
# Run backend and frontend in parallel (-j2 runs two targets concurrently)
dev:
	$(MAKE) -j2 api-dev web-dev

.PHONY: web-build
# Build frontend into web/dist (for single-port serve or Docker)
web-build:
	cd web && $(NPM) run build

.PHONY: web-to-static
# Copy Vite build output to ./static for FastAPI to host (removes existing static/)
web-to-static: web-build
	rm -rf static
	cp -R web/dist static

.PHONY: fe
# Single command: build frontend and copy to ./static
fe: web-to-static

.PHONY: serve
# Single-port mode: FastAPI serves ./static (for quick local preview or simple deployment)
serve: py-install web-to-static
	$(PYTHON) -m uvicorn api.main:app --host $(API_HOST) --port $(API_PORT)

.PHONY: docker-build
# Build Docker image (Dockerfile builds frontend first, then installs Python packages)
docker-build:
	docker build -t $(IMAGE):$(TAG) .

.PHONY: docker-stop
# Stop and remove container with same name (ignores if not exists)
docker-stop:
	@docker rm -f $(CONTAINER_NAME) >/dev/null 2>&1 || true

.PHONY: docker-run
# Run container:
# - Port mapping: $(DOCKER_PORT) -> container port 8000
# - Mounts: /config for persistent config/DB/logs, /data for media files
docker-run: docker-stop
	docker run -d \
		--name $(CONTAINER_NAME) \
		-p $(DOCKER_PORT):8000 \
		-v $(PWD)/config:/config \
		-v $(PWD)/data:/data \
		$(IMAGE):$(TAG)

.PHONY: docker-logs
# Follow container logs (Ctrl+C to exit, won't stop container)
docker-logs:
	docker logs -f $(CONTAINER_NAME)

.PHONY: docker-push
# Push image to remote registry (ensure IMAGE points to your registry/repo and you're logged in)
docker-push:
	docker push $(IMAGE):$(TAG)

.PHONY: version
# Update version number in frontend, backend, and pyproject.toml
# Usage: make version V=0.2.5
version:
ifndef V
	@echo "Usage: make version V=0.2.5"
	@echo "Current version:"
	@grep "APP_VERSION" web/src/i18n.js | head -1
	@exit 1
endif
	@echo "Updating version to $(V)..."
	@sed -i '' "s/APP_VERSION = '[^']*'/APP_VERSION = '$(V)'/" web/src/i18n.js
	@sed -i '' 's/CURRENT_VERSION = "[^"]*"/CURRENT_VERSION = "$(V)"/' api/routes/version.py
	@sed -i '' 's/^version = "[^"]*"/version = "$(V)"/' pyproject.toml
	@echo "Updated:"
	@grep "APP_VERSION" web/src/i18n.js | head -1
	@grep "CURRENT_VERSION" api/routes/version.py | head -1
	@grep 'version =' pyproject.toml | head -1
	@echo ""
	@echo "Don't forget to:"
	@echo "  1. git commit -m 'chore: bump version to $(V)'"
	@echo "  2. git push origin main"
	@echo "  3. Create GitHub Release with tag v$(V)"