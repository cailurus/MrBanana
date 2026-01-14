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
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
# ffmpeg: required for video processing
# curl: for healthchecks or debugging
# Chromium dependencies: required for patchright/playwright browser
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    # Chromium dependencies
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
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy project files for pip install
COPY pyproject.toml README.md ./
COPY mr_banana/ mr_banana/
COPY api/ api/

# Install Python dependencies using pyproject.toml
RUN pip install --no-cache-dir .

# Install Patchright browser (Chromium)
# Note: You might need to install additional system dependencies for Chromium
# if the slim image doesn't have them.
RUN patchright install chromium

# Copy built frontend assets from Stage 1
COPY --from=frontend-builder /app/web/dist /app/static

# Create necessary directories
RUN mkdir -p /app/downloads /app/data /app/logs

# Create non-root user for security
RUN useradd -m -u 1000 mrbanana && \
    chown -R mrbanana:mrbanana /app
USER mrbanana

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Run the application
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
