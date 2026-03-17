#!/bin/bash

# Flower Monitoring Dashboard Startup Script
# Flower provides a web UI for monitoring Celery tasks and workers

set -e

# Navigate to the backend directory
cd "$(dirname "$0")"

# Set environment variables
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Flower configuration
PORT="${FLOWER_PORT:-5555}"
BROKER_URL="${CELERY_BROKER_URL:-redis://localhost:6379/0}"

echo "Starting Flower monitoring dashboard..."
echo "Dashboard will be available at: http://localhost:${PORT}"
echo ""

# Start Flower
uv run celery -A app.celery_app flower \
  --port="${PORT}" \
  --broker="${BROKER_URL}"

# Access the dashboard at http://localhost:5555
