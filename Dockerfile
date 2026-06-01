# Multi-stage build: Frontend + Backend in single container
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY package*.json .
RUN npm ci

COPY . /app
WORKDIR /app
RUN npm run build

# Backend stage
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files
COPY . .

# Copy built frontend from builder stage
COPY --from=frontend-build /app/dist ./public

# Create non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Start API server (serves built frontend + API)
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
