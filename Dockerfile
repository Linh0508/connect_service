# ============================================================
# B6 Core Business Service Dockerfile
# Version: 1.3.0 - FIXED for Docker Compose
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

# Install packages to a specific location
RUN pip install --no-cache-dir -r requirements.txt --target /app/packages

# Stage 2: Runtime stage
FROM python:3.11-slim

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --gid 1001 appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder --chown=appuser:appgroup /app/packages /home/appuser/.local/lib/python3.11/site-packages

# Copy application code
COPY --chown=appuser:appgroup src/core_service/ ./src/core_service/
COPY --chown=appuser:appgroup .env.example .env

# Create data directory for audit/quota storage
RUN mkdir -p /app/data && chown -R appuser:appgroup /app/data

# Add Python user base to PATH
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/home/appuser/.local/lib/python3.11/site-packages:$PYTHONPATH

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "src.core_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
