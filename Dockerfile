# Multi-stage build: Frontend builder
FROM node:20-alpine AS frontend-builder

WORKDIR /app

# Copy frontend dependencies and source
COPY package*.json ./
COPY src/ ./src/
COPY index.html vite.config.js eslint.config.js ./
COPY public/ ./public/

# Install and build
RUN npm ci
RUN npm run build

# Python backend runtime
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (curl for healthcheck, build tools for pip)
RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential && \
    rm -rf /var/lib/apt/lists/*

# Copy Python dependencies and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY *.py ./

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/dist ./dist

# Copy startup script and make executable
COPY start.sh ./
RUN chmod +x ./start.sh

# Create non-root user for security (optional)
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Ensure Python can import local modules regardless of execution cwd
ENV PYTHONPATH=/app

# Health check (use PORT env if provided)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD sh -c 'curl -f http://localhost:${PORT:-8000}/health || exit 1'

# Expose port
EXPOSE 8000

# Start API server (bind to $PORT if provided by the platform)
CMD sh -c "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"

