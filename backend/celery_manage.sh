#!/bin/bash

# Celery Management Script - Control both Worker and Flower
# Usage:
#   ./celery_manage.sh start   - Start both worker and Flower
#   ./celery_manage.sh stop    - Stop both worker and Flower
#   ./celery_manage.sh restart - Restart both worker and Flower
#   ./celery_manage.sh status  - Check status of both

set -e

# Navigate to the backend directory
cd "$(dirname "$0")"

WORKER_SCRIPT="./celery_worker.sh"
FLOWER_SCRIPT="./celery_flower.sh"

# Ensure scripts are executable
chmod +x "$WORKER_SCRIPT" 2>/dev/null || true
chmod +x "$FLOWER_SCRIPT" 2>/dev/null || true

# Function to start all services
start_all() {
    echo "🚀 Starting Celery services..."
    echo ""

    # Start worker
    if [ -f "$WORKER_SCRIPT" ]; then
        bash "$WORKER_SCRIPT" start
    else
        echo "❌ Worker script not found: $WORKER_SCRIPT"
        exit 1
    fi

    echo ""

    # Start Flower
    if [ -f "$FLOWER_SCRIPT" ]; then
        bash "$FLOWER_SCRIPT" start
    else
        echo "❌ Flower script not found: $FLOWER_SCRIPT"
        exit 1
    fi

    echo ""
    echo "✅ All Celery services started successfully!"
    echo ""
    echo "📊 Monitor tasks at: http://localhost:5555"
}

# Function to stop all services
stop_all() {
    echo "🛑 Stopping Celery services..."
    echo ""

    # Stop Flower first (lighter service)
    if [ -f "$FLOWER_SCRIPT" ]; then
        bash "$FLOWER_SCRIPT" stop || true
    fi

    echo ""

    # Stop worker (may take longer due to active tasks)
    if [ -f "$WORKER_SCRIPT" ]; then
        bash "$WORKER_SCRIPT" stop || true
    fi

    echo ""
    echo "✅ All Celery services stopped"
}

# Function to restart all services
restart_all() {
    echo "🔄 Restarting Celery services..."
    echo ""

    stop_all
    sleep 2
    start_all
}

# Function to check status of all services
status_all() {
    echo "📊 Celery Services Status"
    echo "========================"
    echo ""

    echo "Worker Status:"
    echo "-------------"
    bash "$WORKER_SCRIPT" status || true

    echo ""
    echo "Flower Status:"
    echo "-------------"
    bash "$FLOWER_SCRIPT" status || true
}

# Main command handling
case "${1:-}" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        restart_all
        ;;
    status)
        status_all
        ;;
    worker)
        # Pass through to worker script
        shift
        bash "$WORKER_SCRIPT" "$@"
        ;;
    flower)
        # Pass through to flower script
        shift
        bash "$FLOWER_SCRIPT" "$@"
        ;;
    *)
        echo "Celery Management Script - Control Worker and Flower"
        echo ""
        echo "Usage: $0 {start|stop|restart|status|worker|flower} [args]"
        echo ""
        echo "Commands:"
        echo "  start          - Start both worker and Flower"
        echo "  stop           - Stop both worker and Flower"
        echo "  restart        - Restart both worker and Flower"
        echo "  status         - Check status of both services"
        echo "  worker <cmd>   - Pass command to worker (e.g., ./celery_manage.sh worker restart)"
        echo "  flower <cmd>   - Pass command to Flower (e.g., ./celery_manage.sh flower stop)"
        echo ""
        echo "Examples:"
        echo "  $0 start                 # Start all services"
        echo "  $0 status                # Check status of all services"
        echo "  $0 worker restart        # Restart only the worker"
        echo "  $0 flower stop           # Stop only Flower"
        exit 1
        ;;
esac
