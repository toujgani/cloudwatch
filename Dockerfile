# ═══════════════════════════════════════════════════════════════════════════════
# Cloud AI Monitor — Production Multi-Stage Build
# Single container: FastAPI serves API + static React build
# Optimized for OpenShift (non-root, small image, layer caching)
# ═══════════════════════════════════════════════════════════════════════════════

# ── Stage 1: Build React Frontend ─────────────────────────────────────────────
FROM node:18-alpine AS frontend-build
WORKDIR /build

# Install dependencies first (layer cache)
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --production=false

# Copy source and build
COPY frontend/ .
RUN npm run build


# ── Stage 2: Python Production Image ─────────────────────────────────────────
FROM python:3.11-slim AS production

# Security: non-root user for OpenShift compatibility
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Install Python dependencies (layer cache)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY app.py ./app.py

# Copy built frontend into static folder
COPY --from=frontend-build /build/dist ./static/

# Create writable directories
RUN mkdir -p /app/logs /app/branding && \
    chown -R appuser:appuser /app && \
    chmod 775 /app/logs /app/branding

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/health')" || exit 1

# Expose port (OpenShift convention: 8080)
EXPOSE 8080

# Production server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--access-log", "--log-level", "info"]
