SHELL := /bin/bash

# ------------------------------
# Mr. Banana Makefile
#
# Goal: Common entrypoints for local dev, build, and Docker.
# This file only wires commands; business logic lives under api/ and mr_banana/.
# ------------------------------

# 可覆盖的命令（如：make api-dev PYTHON=python）
PYTHON ?= python3
PIP ?= pip3
NPM ?= npm

# 本地开发端口（前后端分离：Vite 5173 -> 代理到 FastAPI 8000）
API_HOST ?= 127.0.0.1
API_PORT ?= 8000
WEB_PORT ?= 5173

# Docker 镜像/容器设置（可通过 make docker-build IMAGE=xxx TAG=yyy 覆盖）
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
# 安装 Python 依赖（本项目不以 PyPI 包发布为目标；直接用 requirements.txt）
py-install:
	$(PYTHON) -m pip install -r requirements.txt

.PHONY: web-install
# 安装前端依赖（Node 工具链：npm install）
web-install:
	cd web && $(NPM) install

.PHONY: api-dev
# 启动 FastAPI 开发服务（热重载）；前端会通过 Vite proxy 访问 /api 与 /ws
api-dev: py-install
	$(PYTHON) -m uvicorn api.main:app --reload --host $(API_HOST) --port $(API_PORT)

.PHONY: web-dev
# 启动 Vite 开发服务器（默认端口 5173，可通过 WEB_PORT 覆盖）
web-dev:
	cd web && $(NPM) run dev -- --port $(WEB_PORT)

.PHONY: dev
# 并行启动后端与前端（-j2 并发执行两个 target）
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
# 单端口运行：FastAPI 托管 ./static（适合本地快速体验或简单部署）
serve: py-install web-to-static
	$(PYTHON) -m uvicorn api.main:app --host $(API_HOST) --port $(API_PORT)

.PHONY: docker-build
# 构建 Docker 镜像（Dockerfile 会先构建前端，再安装 Python 包）
docker-build:
	docker build -t $(IMAGE):$(TAG) .

.PHONY: docker-stop
# 停止并删除同名容器（忽略不存在的情况）
docker-stop:
	@docker rm -f $(CONTAINER_NAME) >/dev/null 2>&1 || true

.PHONY: docker-run
# 运行容器：
# - 端口映射：$(DOCKER_PORT) -> 容器内 8000
# - 挂载：downloads 目录与历史 DB（mr_banana_history.db）用于持久化
docker-run: docker-stop
	docker run -d \
		--name $(CONTAINER_NAME) \
		-p $(DOCKER_PORT):8000 \
		-v $(PWD)/downloads:/app/downloads \
			-v $(PWD)/mr_banana_history.db:/app/mr_banana_history.db \
		$(IMAGE):$(TAG)

.PHONY: docker-logs
# 跟随容器日志（Ctrl+C 退出，不会停止容器）
docker-logs:
	docker logs -f $(CONTAINER_NAME)

.PHONY: docker-push
# 推送镜像到远端仓库（确保 IMAGE 指向你的 registry/repo，并已 docker login）
docker-push:
	docker push $(IMAGE):$(TAG)