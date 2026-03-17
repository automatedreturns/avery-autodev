#!/bin/bash

# Celery Worker Management Script
# Usage:
#   ./celery_worker.sh start   - Start the Celery worker
#   ./celery_worker.sh stop    - Stop the Celery worker
#   ./celery_worker.sh restart - Restart the Celery worker
#   ./celery_worker.sh status  - Check worker status

set -e

# Navigate to the backend directory
cd "$(dirname "$0")"

# Configuration
WORKER_NAME="${WORKER_NAME:-agent_worker}"
CONCURRENCY="${CONCURRENCY:-2}"
LOG_LEVEL="${LOG_LEVEL:-info}"
PID_FILE="./pids/celery_worker.pid"
LOG_FILE="./logs/celery_worker.log"
LOG_DIR="./logs"
PID_DIR="./pids"

# Create directories if they don't exist
mkdir -p "$LOG_DIR"
mkdir -p "$PID_DIR"

# Set environment
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Function to start the worker
start_worker() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "❌ Celery worker is already running (PID: $PID)"
            exit 1
        else
            echo "⚠️  Removing stale PID file"
            rm -f "$PID_FILE"
        fi
    fi

    echo "🚀 Starting Celery worker for Avery Agent Processing..."
    echo "   Worker Name: ${WORKER_NAME}"
    echo "   Concurrency: ${CONCURRENCY}"
    echo "   Log Level: ${LOG_LEVEL}"
    echo "   Log File: ${LOG_FILE}"
    echo ""

    # Start Celery worker in background with nohup
    nohup uv run celery -A app.celery_app worker \
        --loglevel="${LOG_LEVEL}" \
        --concurrency="${CONCURRENCY}" \
        --hostname="${WORKER_NAME}@%h" \
        --queues=agent_processing,github_operations,celery \
        --max-tasks-per-child=50 \
        --time-limit=7200 \
        --soft-time-limit=6600 \
        > "$LOG_FILE" 2>&1 &

    # Save PID
    WORKER_PID=$!
    echo $WORKER_PID > "$PID_FILE"

    # Wait a moment and verify it started
    sleep 3
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "✅ Celery worker started successfully (PID: $PID)"
            echo "   View logs: tail -f $LOG_FILE"
        else
            echo "❌ Failed to start Celery worker"
            rm -f "$PID_FILE"
            exit 1
        fi
    else
        echo "❌ PID file not created. Check logs: $LOG_FILE"
        exit 1
    fi
}

# Function to stop the worker
stop_worker() {
    if [ ! -f "$PID_FILE" ]; then
        echo "⚠️  PID file not found. Celery worker may not be running."
        # Try to find and kill any running workers
        pkill -f "celery.*app.celery_app worker" && echo "✅ Stopped running Celery worker process" || echo "❌ No running Celery worker found"
        exit 0
    fi

    PID=$(cat "$PID_FILE")

    if ps -p "$PID" > /dev/null 2>&1; then
        echo "🛑 Stopping Celery worker (PID: $PID)..."

        # Send TERM signal for graceful shutdown
        kill -TERM "$PID"

        # Wait up to 30 seconds for graceful shutdown
        for i in {1..30}; do
            if ! ps -p "$PID" > /dev/null 2>&1; then
                echo "✅ Celery worker stopped successfully"
                rm -f "$PID_FILE"
                exit 0
            fi
            sleep 1
        done

        # If still running, force kill
        echo "⚠️  Worker didn't stop gracefully, forcing shutdown..."
        kill -9 "$PID" 2>/dev/null || true
        rm -f "$PID_FILE"
        echo "✅ Celery worker force stopped"
    else
        echo "⚠️  Process not running. Removing stale PID file."
        rm -f "$PID_FILE"
    fi
}

# Function to check status
status_worker() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "✅ Celery worker is running (PID: $PID)"
            echo ""
            echo "Process details:"
            ps -p "$PID" -o pid,etime,pcpu,pmem,comm
            echo ""
            echo "Recent log entries:"
            tail -n 10 "$LOG_FILE" 2>/dev/null || echo "No log file found"
            exit 0
        else
            echo "❌ Celery worker is not running (stale PID file)"
            exit 1
        fi
    else
        echo "❌ Celery worker is not running"
        exit 1
    fi
}

# Function to restart
restart_worker() {
    echo "🔄 Restarting Celery worker..."
    stop_worker
    sleep 2
    start_worker
}

# Main command handling
case "${1:-}" in
    start)
        start_worker
        ;;
    stop)
        stop_worker
        ;;
    restart)
        restart_worker
        ;;
    status)
        status_worker
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the Celery worker"
        echo "  stop    - Stop the Celery worker"
        echo "  restart - Restart the Celery worker"
        echo "  status  - Check worker status"
        exit 1
        ;;
esac
