# Multi-stage build for production
FROM golang:1.21-alpine AS go-builder

WORKDIR /app/go-engine
COPY go-engine/ .
RUN go mod download
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o migration-engine ./cmd/migration-engine

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    openssh-client \
    rsync \
    mysql-client \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd --create-home --shell /bin/bash app

WORKDIR /app

# Copy Python requirements and install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy Go binary from builder stage
COPY --from=go-builder /app/go-engine/migration-engine /usr/local/bin/

# Copy application code
COPY migration_assistant/ ./migration_assistant/
COPY docs/ ./docs/
COPY scripts/ ./scripts/

# Set proper permissions
RUN chown -R app:app /app
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Default command
CMD ["python", "-m", "migration_assistant.api.main"]