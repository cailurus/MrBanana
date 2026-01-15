# Stage 1: Build Frontend
FROM node:18-alpine AS frontend-builder

WORKDIR /app/web

# Copy package files
COPY web/package.json web/package-lock.json* ./

# Install dependencies (need devDependencies for build)
RUN npm ci

# Copy source code
COPY web/ ./

# Build frontend
RUN npm run build && npm cache clean --force

# Stage 2: Runtime
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Reduce patchright browser size
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

WORKDIR /app

# Install system dependencies in single layer
# ffmpeg: required for video processing
# curl: for healthchecks
# Chromium dependencies: required for patchright/playwright browser
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    # Chromium dependencies (minimal set)
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* \
    && apt-get clean \
    && apt-get autoremove -y

# Copy requirements first for better cache
COPY requirements.txt ./

# Install Python dependencies using requirements.txt (faster than pyproject.toml)
RUN pip install --no-cache-dir -r requirements.txt \
    && rm -rf ~/.cache/pip

# Install Patchright browser (Chromium only, minimal)
RUN patchright install chromium --with-deps \
    && rm -rf /root/.cache

# Copy project files
COPY pyproject.toml README.md ./
COPY mr_banana/ mr_banana/
COPY api/ api/

# Install the package itself (without deps, already installed)
RUN pip install --no-cache-dir --no-deps -e .

# Copy built frontend assets from Stage 1
COPY --from=frontend-builder /app/web/dist /app/static

# Create necessary directories and non-root user in single layer
RUN mkdir -p /app/downloads /app/data /app/logs \
    && useradd -m -u 1000 mrbanana \
    && chown -R mrbanana:mrbanana /app

USER mrbanana

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Run the application
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
