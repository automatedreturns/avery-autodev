# Celery Quick Reference Card

## 🚀 Start/Stop Commands

```bash
# Start everything (worker + Flower)
./celery_manage.sh start

# Stop everything
./celery_manage.sh stop

# Restart everything
./celery_manage.sh restart

# Check status
./celery_manage.sh status
```

## 🔍 Debugging & Monitoring

```bash
# Full system check
./celery_debug.sh check

# Show active tasks
./celery_debug.sh active

# Show queued tasks
./celery_debug.sh reserved

# View logs
./celery_debug.sh logs

# Tail logs (live)
./celery_debug.sh tail

# Show worker stats
./celery_debug.sh stats
```

## 📊 Flower Dashboard

```bash
# Access at: http://localhost:5555
open http://localhost:5555

# Start Flower separately
./celery_flower.sh start

# Stop Flower
./celery_flower.sh stop
```

## 🔧 Individual Service Control

```bash
# Worker only
./celery_worker.sh start
./celery_worker.sh stop
./celery_worker.sh restart
./celery_worker.sh status

# Flower only
./celery_flower.sh start
./celery_flower.sh stop
./celery_flower.sh restart
./celery_flower.sh status
```

## 📝 Log Files

```bash
# View worker logs
tail -f logs/celery_worker.log

# View Flower logs
tail -f logs/celery_flower.log

# View both
tail -f logs/*.log
```

## 🐛 Common Issues

### Redis not running
```bash
# Check
redis-cli ping

# Start (macOS)
brew services start redis

# Start (Linux)
sudo systemctl start redis
```

### Worker stuck
```bash
# Graceful restart
./celery_worker.sh restart

# Force stop
pkill -9 -f "celery.*worker"
rm -f pids/celery_worker.pid
./celery_worker.sh start
```

### Clear task queue
```bash
# Purge all tasks
./celery_debug.sh purge

# Or manually
celery -A app.celery_app purge -f
```

## 📈 Performance Tuning

### Increase worker concurrency
```bash
# Set environment variable
export CONCURRENCY=4
./celery_worker.sh restart

# Or edit celery_worker.sh
```

### Enable autoscaling
```bash
# Edit celery_worker.sh, uncomment autoscale section
celery -A app.celery_app worker --autoscale=10,2
```

## 🔄 Queue Management

```bash
# Check queue length
./celery_debug.sh queue

# Inspect tasks
celery -A app.celery_app inspect active
celery -A app.celery_app inspect reserved
celery -A app.celery_app inspect registered
```

## 📊 Database Queries

```sql
-- Running jobs
SELECT * FROM agent_jobs WHERE status = 'running';

-- Failed jobs today
SELECT * FROM agent_jobs
WHERE status = 'failed'
AND created_at > CURRENT_DATE;

-- Average duration
SELECT AVG(duration) as avg_seconds
FROM agent_jobs
WHERE status = 'completed';
```

## 🚨 Emergency Stop

```bash
# Stop everything forcefully
pkill -9 -f celery
rm -f pids/*.pid

# Then start fresh
./celery_manage.sh start
```

## 📚 Full Documentation

- Setup Guide: [CELERY_SETUP.md](CELERY_SETUP.md)
- Script Details: [CELERY_SCRIPTS.md](CELERY_SCRIPTS.md)
- Implementation: [CELERY_IMPLEMENTATION_SUMMARY.md](../CELERY_IMPLEMENTATION_SUMMARY.md)

## 🔗 Useful Links

- Flower Dashboard: http://localhost:5555
- API Docs: http://localhost:8000/docs
- Celery Docs: https://docs.celeryq.dev/
