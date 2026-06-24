# ============================================================
# B6 Core Business Service Dockerfile
# Version: 1.3.1 - FIXED for Docker Compose
# ============================================================

# Stage 1: Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install packages - CÀI ĐẶT DIRECTLY VÀO SITE-PACKAGES CHUẨN
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime stage
FROM python:3.11-slim

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --gid 1001 appuser

WORKDIR /app

# Copy installed packages từ builder vào hệ thống Python
COPY --from=builder --chown=appuser:appgroup /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder --chown=appuser:appgroup /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup .env.example .env

# Create data directory for audit/quota storage
RUN mkdir -p /app/data && chown -R appuser:appgroup /app/data

# Set PYTHONPATH
ENV PYTHONPATH=/app:$PYTHONPATH

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application - SỬ DỤNG UVICORN TRỰC TIẾP
CMD ["uvicorn", "src.core_service.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--log-level", "info"]