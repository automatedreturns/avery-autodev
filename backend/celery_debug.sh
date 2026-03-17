#!/bin/bash

# Celery Debug Helper Script
# Provides quick commands for debugging and monitoring Celery

set -e

cd "$(dirname "$0")"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if Redis is running
check_redis() {
    print_header "Redis Connection"
    if redis-cli ping > /dev/null 2>&1; then
        print_success "Redis is running and responding"
        echo -n "  Connected clients: "
        redis-cli client list | wc -l
        echo -n "  Used memory: "
        redis-cli info memory | grep used_memory_human | cut -d: -f2
    else
        print_error "Redis is not responding"
        echo "  Try: brew services start redis"
    fi
    echo ""
}

# Check Celery worker status
check_worker() {
    print_header "Celery Worker Status"

    if [ -f "./pids/celery_worker.pid" ]; then
        PID=$(cat ./pids/celery_worker.pid)
        if ps -p "$PID" > /dev/null 2>&1; then
            print_success "Worker is running (PID: $PID)"
            ps -p "$PID" -o pid,etime,pcpu,pmem,comm
        else
            print_error "Worker not running (stale PID file)"
        fi
    else
        print_error "Worker not running (no PID file)"
    fi
    echo ""
}

# Check Flower status
check_flower() {
    print_header "Flower Dashboard Status"

    if [ -f "./pids/celery_flower.pid" ]; then
        PID=$(cat ./pids/celery_flower.pid)
        if ps -p "$PID" > /dev/null 2>&1; then
            print_success "Flower is running (PID: $PID)"
            print_success "Dashboard: http://localhost:5555"
        else
            print_error "Flower not running (stale PID file)"
        fi
    else
        print_error "Flower not running (no PID file)"
    fi
    echo ""
}

# Inspect active tasks
inspect_active() {
    print_header "Active Tasks"
    uv run celery -A app.celery_app inspect active 2>/dev/null || print_warning "No workers available or no active tasks"
    echo ""
}

# Inspect reserved tasks
inspect_reserved() {
    print_header "Reserved Tasks (Queued)"
    uv run celery -A app.celery_app inspect reserved 2>/dev/null || print_warning "No workers available or no reserved tasks"
    echo ""
}

# Show worker statistics
worker_stats() {
    print_header "Worker Statistics"
    uv run celery -A app.celery_app inspect stats 2>/dev/null || print_warning "No workers available"
    echo ""
}

# Show registered tasks
registered_tasks() {
    print_header "Registered Tasks"
    uv run celery -A app.celery_app inspect registered 2>/dev/null || print_warning "No workers available"
    echo ""
}

# View recent logs
view_logs() {
    print_header "Recent Worker Logs (last 20 lines)"
    if [ -f "./logs/celery_worker.log" ]; then
        tail -n 20 ./logs/celery_worker.log
    else
        print_warning "No log file found"
    fi
    echo ""

    print_header "Recent Flower Logs (last 20 lines)"
    if [ -f "./logs/celery_flower.log" ]; then
        tail -n 20 ./logs/celery_flower.log
    else
        print_warning "No log file found"
    fi
    echo ""
}

# Monitor logs in real-time
tail_logs() {
    print_header "Tailing Logs (Ctrl+C to exit)"
    tail -f ./logs/celery_worker.log ./logs/celery_flower.log 2>/dev/null
}

# Purge all tasks from queue
purge_queue() {
    print_header "Purge All Queued Tasks"
    read -p "Are you sure you want to purge ALL tasks from the queue? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        uv run celery -A app.celery_app purge -f
        print_success "Queue purged"
    else
        print_warning "Purge cancelled"
    fi
    echo ""
}

# Show queue length
queue_length() {
    print_header "Queue Length"
    # This requires redis-cli
    if command -v redis-cli > /dev/null; then
        echo -n "agent_processing queue: "
        redis-cli llen celery || echo "0"
        echo -n "github_operations queue: "
        redis-cli llen github_operations || echo "0"
    else
        print_warning "redis-cli not found"
    fi
    echo ""
}

# Full system check
system_check() {
    check_redis
    check_worker
    check_flower
    queue_length
    inspect_active
}

# Show help
show_help() {
    echo "Celery Debug Helper"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  check          - Full system health check"
    echo "  redis          - Check Redis connection"
    echo "  worker         - Check worker status"
    echo "  flower         - Check Flower status"
    echo "  active         - Show active tasks"
    echo "  reserved       - Show reserved (queued) tasks"
    echo "  stats          - Show worker statistics"
    echo "  tasks          - Show registered tasks"
    echo "  logs           - View recent logs"
    echo "  tail           - Tail logs in real-time"
    echo "  queue          - Show queue lengths"
    echo "  purge          - Purge all tasks from queue"
    echo ""
    echo "Examples:"
    echo "  $0 check       # Full system check"
    echo "  $0 active      # Show currently running tasks"
    echo "  $0 tail        # Watch logs in real-time"
}

# Main command handling
case "${1:-check}" in
    check)
        system_check
        ;;
    redis)
        check_redis
        ;;
    worker)
        check_worker
        ;;
    flower)
        check_flower
        ;;
    active)
        inspect_active
        ;;
    reserved)
        inspect_reserved
        ;;
    stats)
        worker_stats
        ;;
    tasks)
        registered_tasks
        ;;
    logs)
        view_logs
        ;;
    tail)
        tail_logs
        ;;
    queue)
        queue_length
        ;;
    purge)
        purge_queue
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "Unknown command: $1"
        echo "Run '$0 help' for usage information"
        exit 1
        ;;
esac
