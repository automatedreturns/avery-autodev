#!/bin/bash

# Celery Worker Startup Script for Avery Agent Processing
# This script starts the Celery worker for processing agent tasks

set -e

# Navigate to the backend directory
cd "$(dirname "$0")"

# Set environment variables (optional - load from .env if needed)
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Worker configuration
WORKER_NAME="${WORKER_NAME:-agent_worker}"
CONCURRENCY="${CONCURRENCY:-2}"  # Number of concurrent tasks (adjust based on your server capacity)
LOG_LEVEL="${LOG_LEVEL:-info}"

echo "Starting Celery worker for Avery Agent Processing..."
echo "Worker Name: ${WORKER_NAME}"
echo "Concurrency: ${CONCURRENCY}"
echo "Log Level: ${LOG_LEVEL}"
echo ""

# Start Celery worker
celery -A app.celery_app worker \
  --loglevel="${LOG_LEVEL}" \
  --concurrency="${CONCURRENCY}" \
  --hostname="${WORKER_NAME}@%h" \
  --queues=agent_processing,github_operations \
  --max-tasks-per-child=50 \
  --time-limit=7200 \
  --soft-time-limit=6600 \
  > "../logs/celery_app.out" 2>&1 &

# Alternative: Start with autoscaling
# celery -A app.celery_app worker \
#   --loglevel="${LOG_LEVEL}" \
#   --autoscale=4,1 \
#   --hostname="${WORKER_NAME}@%h" \
#   --queues=agent_processing,github_operations
