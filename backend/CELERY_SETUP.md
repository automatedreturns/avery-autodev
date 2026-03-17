# Celery Setup Guide for Avery Agent Processing

This guide explains how to set up and run the Celery-based asynchronous task processing system for Avery's AI agent operations.

## Overview

The agent processing system now uses **Celery** with **Redis** as the message broker for:
- ✅ **Scalable execution**: Distribute agent tasks across multiple workers
- ✅ **Reliability**: Automatic retries on failure with exponential backoff
- ✅ **Observability**: Track job status, progress, and errors
- ✅ **Better resource management**: Time limits and task throttling
- ✅ **Monitoring**: Flower dashboard for real-time task monitoring

## Architecture

```
┌─────────────┐      ┌─────────────┐      ┌──────────────┐
│   FastAPI   │─────▶│    Redis    │─────▶│Celery Worker │
│   Server    │      │   (Broker)  │      │  (Agent)     │
└─────────────┘      └─────────────┘      └──────────────┘
       │                                           │
       │                                           │
       └──────────────▶ PostgreSQL ◀──────────────┘
                        (Database)
```

## Prerequisites

1. **Redis** (message broker)
2. **Python dependencies** (installed via pip)

## Installation

### 1. Install Redis

**macOS** (using Homebrew):
```bash
brew install redis
brew services start redis
```

**Ubuntu/Debian**:
```bash
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

**Docker**:
```bash
docker run -d -p 6379:6379 redis:latest
```

### 2. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt  # or use your preferred package manager

# Dependencies added:
# - celery[redis]>=5.4.0
# - redis>=5.0.0
# - flower>=2.0.0
```

### 3. Configure Environment Variables

Add to your `.env` file:

```bash
# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

For production with Redis password:
```bash
CELERY_BROKER_URL=redis://:password@redis-host:6379/0
CELERY_RESULT_BACKEND=redis://:password@redis-host:6379/0
```

### 4. Run Database Migrations

```bash
cd backend
alembic upgrade head
```

This creates the `agent_jobs` table for tracking Celery task execution.

## Running the System

### Development Mode

You need **2-3 terminal windows**:

**Terminal 1 - FastAPI Server**:
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - Celery Services** (Worker + Flower):
```bash
cd backend
./celery_manage.sh start
```

Then visit:
- API: http://localhost:8000
- Flower Dashboard: http://localhost:5555

**To stop services:**
```bash
./celery_manage.sh stop
```

**Alternative: Individual Control**

If you prefer to control services separately:

```bash
# Start worker only
./celery_worker.sh start

# Start Flower only
./celery_flower.sh start

# Check status
./celery_manage.sh status

# View logs
tail -f logs/celery_worker.log
```

See [CELERY_SCRIPTS.md](CELERY_SCRIPTS.md) for detailed script documentation.

### Production Mode

For production, use a process manager like **systemd** or **supervisord**.

#### Using systemd (Linux)

Create `/etc/systemd/system/celery-avery.service`:

```ini
[Unit]
Description=Celery Worker for Avery Agent Processing
After=network.target redis.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/path/to/avery-dev/backend
Environment="PATH=/path/to/venv/bin"
Environment="CELERY_BROKER_URL=redis://localhost:6379/0"
ExecStart=/path/to/avery-dev/backend/start_celery_worker.sh

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable celery-avery
sudo systemctl start celery-avery
sudo systemctl status celery-avery
```

#### Using Docker

See `docker-compose.yml` example:

```yaml
version: '3.8'

services:
  redis:
    image: redis:latest
    ports:
      - "6379:6379"

  celery_worker:
    build: ./backend
    command: celery -A app.celery_app worker --loglevel=info --concurrency=2
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    depends_on:
      - redis
    volumes:
      - ./backend:/app
```

## Configuration

### Worker Configuration

Edit `start_celery_worker.sh` to adjust:

```bash
# Number of concurrent tasks (adjust based on CPU/memory)
CONCURRENCY=2  # Default: 2

# Increase for more powerful servers
CONCURRENCY=4

# Use autoscaling for dynamic concurrency
celery -A app.celery_app worker --autoscale=10,2
```

### Task Time Limits

Configured in `app/celery_app.py`:
```python
task_time_limit=7200,        # 2 hours hard limit
task_soft_time_limit=6600,   # 1 hour 50 minutes soft limit
```

### Retry Configuration

Configured in `app/tasks/agent_tasks.py`:
```python
retry_kwargs = {
    'max_retries': 3,           # Maximum retry attempts
    'countdown': 60,            # Initial retry delay (seconds)
}
retry_backoff = True            # Exponential backoff (60s, 120s, 240s)
retry_jitter = True             # Add randomness to prevent thundering herd
```

## Monitoring

### Flower Dashboard

Access real-time monitoring at http://localhost:5555

Features:
- Active/completed/failed tasks
- Worker status and resource usage
- Task routing and queue status
- Task history and details
- Retry information

### API Endpoints

Check job status via API:

```bash
# Get latest job for a task
GET /api/v1/workspaces/{workspace_id}/tasks/{task_id}/jobs/latest

# List all jobs for a task
GET /api/v1/workspaces/{workspace_id}/tasks/{task_id}/jobs

# Get specific job details
GET /api/v1/workspaces/{workspace_id}/tasks/{task_id}/jobs/{job_id}

# Get workspace job statistics
GET /api/v1/workspaces/{workspace_id}/jobs/stats?days=7
```

### Database Queries

Query job status directly:

```sql
-- Get running jobs
SELECT * FROM agent_jobs WHERE status = 'running';

-- Get failed jobs with errors
SELECT id, task_id, error_message, retry_count
FROM agent_jobs
WHERE status = 'failed'
ORDER BY created_at DESC;

-- Get average execution time
SELECT AVG(duration) as avg_duration_seconds
FROM agent_jobs
WHERE status = 'completed' AND duration IS NOT NULL;
```

## Troubleshooting

### Worker Not Starting

**Check Redis connection:**
```bash
redis-cli ping
# Should return: PONG
```

**Check logs:**
```bash
celery -A app.celery_app worker --loglevel=debug
```

### Tasks Not Processing

**Check worker is consuming from correct queue:**
```bash
celery -A app.celery_app inspect active_queues
```

**Check broker connection:**
```bash
celery -A app.celery_app inspect ping
```

### Memory Issues

**Restart workers periodically:**
```python
# In celery_app.py
worker_max_tasks_per_child=50  # Restart after 50 tasks
```

**Reduce concurrency:**
```bash
CONCURRENCY=1 ./start_celery_worker.sh
```

### Task Timeout

**Check task time limits:**
- Soft limit: 6600 seconds (110 minutes)
- Hard limit: 7200 seconds (120 minutes)

**Increase if needed** in `app/celery_app.py`:
```python
task_time_limit=10800,       # 3 hours
task_soft_time_limit=10200,  # 2 hours 50 minutes
```

## Scaling

### Horizontal Scaling

Run multiple workers on different machines:

**Machine 1:**
```bash
celery -A app.celery_app worker --hostname=worker1@%h
```

**Machine 2:**
```bash
celery -A app.celery_app worker --hostname=worker2@%h
```

All workers share the same Redis broker and will process tasks from the queue.

### Queue-Based Routing

Tasks are automatically routed to appropriate queues:
- `agent_processing`: AI agent tasks (heavy workload)
- `github_operations`: GitHub API operations (lighter workload)

You can run specialized workers:

```bash
# Worker for agent processing only
celery -A app.celery_app worker --queues=agent_processing --concurrency=2

# Worker for GitHub operations only
celery -A app.celery_app worker --queues=github_operations --concurrency=4
```

## Cleanup

### Remove Old Jobs

A cleanup task is available:

```python
from app.tasks.agent_tasks import cleanup_old_jobs_task

# Remove jobs older than 7 days
cleanup_old_jobs_task.delay(days_old=7)
```

Schedule this with **celery beat** (periodic tasks) or a **cron job**.

## Migration from Old System

The old system used:
- `BackgroundTasks` from FastAPI (limited, no retry)
- Daemon threads (unreliable, no tracking)

The new system automatically:
- ✅ Queues all agent tasks via Celery
- ✅ Tracks execution in `agent_jobs` table
- ✅ Provides retry on failure
- ✅ Allows horizontal scaling

**No changes needed** in the API client - endpoints remain the same.

## Performance Tips

1. **Adjust concurrency** based on your server:
   - 2 concurrent tasks per CPU core is a good starting point
   - Monitor with Flower and adjust as needed

2. **Use separate queues** for different workload types

3. **Monitor Redis memory** usage:
   ```bash
   redis-cli info memory
   ```

4. **Set up periodic cleanup** of old jobs

5. **Use Redis persistence** in production:
   ```bash
   # Use the production Redis config
   redis-server redis.conf.production

   # Or manually configure:
   # In redis.conf
   save 900 1
   save 300 10
   save 60 10000
   appendonly yes
   appendfsync everysec
   ```

## Redis vs RabbitMQ

### Why Redis Was Chosen

This implementation uses **Redis** as the message broker instead of RabbitMQ because:

1. **Simpler Setup**: Redis is a single service with minimal configuration
2. **Multi-Purpose**: Can also use for caching, sessions, rate limiting
3. **Sufficient Scale**: Handles thousands of tasks/hour easily
4. **Lower Resource Usage**: Lighter memory and CPU footprint
5. **Your Use Case**: Long-running agent tasks (minutes/hours), not high-throughput

### When to Consider RabbitMQ

Switch to RabbitMQ if you encounter:
- **High volume**: >1000 tasks/minute consistently
- **Complex routing**: Priority queues, topic-based routing
- **Strict guarantees**: Cannot afford any message loss
- **Memory constraints**: Messages don't fit in Redis RAM

### Migration Path

Switching is simple if needed:
```python
# In .env
CELERY_BROKER_URL=amqp://user:pass@localhost:5672//
```

Celery abstracts the broker, so your task code remains unchanged.

## Support

For issues or questions:
- Check Flower dashboard: http://localhost:5555
- View logs: `celery -A app.celery_app worker --loglevel=info`
- Check agent_jobs table for error details
- Review Celery documentation: https://docs.celeryq.dev/

## Summary

**Quick Start Checklist:**
- [ ] Install Redis
- [ ] Update dependencies (`pip install`)
- [ ] Add Celery environment variables to `.env`
- [ ] Run database migration (`alembic upgrade head`)
- [ ] Start Redis (`redis-server` or as service)
- [ ] Start Celery worker (`./start_celery_worker.sh`)
- [ ] Start FastAPI server (`uvicorn app.main:app`)
- [ ] (Optional) Start Flower (`./start_flower.sh`)

Your agent processing is now running on a scalable, reliable infrastructure! 🚀
