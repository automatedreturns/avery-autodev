#!/bin/bash

# Flower Monitoring Dashboard Management Script
# Usage:
#   ./celery_flower.sh start   - Start Flower
#   ./celery_flower.sh stop    - Stop Flower
#   ./celery_flower.sh restart - Restart Flower
#   ./celery_flower.sh status  - Check Flower status

set -e

# Navigate to the backend directory
cd "$(dirname "$0")"

# Configuration
PORT="${FLOWER_PORT:-5555}"
BROKER_URL="${CELERY_BROKER_URL:-redis://localhost:6379/0}"
PID_FILE="./pids/celery_flower.pid"
LOG_FILE="./logs/celery_flower.log"
LOG_DIR="./logs"
PID_DIR="./pids"

# Create directories if they don't exist
mkdir -p "$LOG_DIR"
mkdir -p "$PID_DIR"

# Set environment
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Function to start Flower
start_flower() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "❌ Flower is already running (PID: $PID)"
            echo "   Dashboard: http://localhost:${PORT}"
            exit 1
        else
            echo "⚠️  Removing stale PID file"
            rm -f "$PID_FILE"
        fi
    fi

    echo "🌸 Starting Flower monitoring dashboard..."
    echo "   Port: ${PORT}"
    echo "   Broker: ${BROKER_URL}"
    echo "   Log File: ${LOG_FILE}"
    echo ""

    # Start Flower in background
    nohup uv run celery -A app.celery_app flower \
        --port="${PORT}" \
        --broker="${BROKER_URL}" \
        > "$LOG_FILE" 2>&1 &

    # Save PID
    echo $! > "$PID_FILE"

    # Wait a moment and verify it started
    sleep 2
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "✅ Flower started successfully (PID: $PID)"
            echo "   Dashboard URL: http://localhost:${PORT}"
            echo "   View logs: tail -f $LOG_FILE"
        else
            echo "❌ Failed to start Flower"
            rm -f "$PID_FILE"
            exit 1
        fi
    else
        echo "❌ PID file not created. Check logs: $LOG_FILE"
        exit 1
    fi
}

# Function to stop Flower
stop_flower() {
    if [ ! -f "$PID_FILE" ]; then
        echo "⚠️  PID file not found. Flower may not be running."
        # Try to find and kill any running Flower processes
        pkill -f "celery.*flower" && echo "✅ Stopped running Flower process" || echo "❌ No running Flower found"
        exit 0
    fi

    PID=$(cat "$PID_FILE")

    if ps -p "$PID" > /dev/null 2>&1; then
        echo "🛑 Stopping Flower (PID: $PID)..."

        # Send TERM signal for graceful shutdown
        kill -TERM "$PID"

        # Wait up to 10 seconds for graceful shutdown
        for i in {1..10}; do
            if ! ps -p "$PID" > /dev/null 2>&1; then
                echo "✅ Flower stopped successfully"
                rm -f "$PID_FILE"
                exit 0
            fi
            sleep 1
        done

        # If still running, force kill
        echo "⚠️  Flower didn't stop gracefully, forcing shutdown..."
        kill -9 "$PID" 2>/dev/null || true
        rm -f "$PID_FILE"
        echo "✅ Flower force stopped"
    else
        echo "⚠️  Process not running. Removing stale PID file."
        rm -f "$PID_FILE"
    fi
}

# Function to check status
status_flower() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "✅ Flower is running (PID: $PID)"
            echo "   Dashboard URL: http://localhost:${PORT}"
            echo ""
            echo "Process details:"
            ps -p "$PID" -o pid,etime,pcpu,pmem,comm
            echo ""
            echo "Recent log entries:"
            tail -n 10 "$LOG_FILE" 2>/dev/null || echo "No log file found"
            exit 0
        else
            echo "❌ Flower is not running (stale PID file)"
            exit 1
        fi
    else
        echo "❌ Flower is not running"
        exit 1
    fi
}

# Function to restart
restart_flower() {
    echo "🔄 Restarting Flower..."
    stop_flower
    sleep 2
    start_flower
}

# Main command handling
case "${1:-}" in
    start)
        start_flower
        ;;
    stop)
        stop_flower
        ;;
    restart)
        restart_flower
        ;;
    status)
        status_flower
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        echo ""
        echo "Commands:"
        echo "  start   - Start Flower monitoring dashboard"
        echo "  stop    - Stop Flower"
        echo "  restart - Restart Flower"
        echo "  status  - Check Flower status"
        exit 1
        ;;
esac
