# Celery Management Scripts

This directory contains scripts to manage Celery worker and Flower monitoring dashboard.

## Scripts Overview

### 1. **celery_manage.sh** (Recommended)
Master script to control both worker and Flower together.

```bash
# Start all services
./celery_manage.sh start

# Stop all services
./celery_manage.sh stop

# Restart all services
./celery_manage.sh restart

# Check status of all services
./celery_manage.sh status

# Control individual services
./celery_manage.sh worker start
./celery_manage.sh flower stop
```

### 2. **celery_worker.sh**
Control the Celery worker individually.

```bash
# Start worker
./celery_worker.sh start

# Stop worker
./celery_worker.sh stop

# Restart worker
./celery_worker.sh restart

# Check worker status
./celery_worker.sh status
```

### 3. **celery_flower.sh**
Control the Flower monitoring dashboard individually.

```bash
# Start Flower
./celery_flower.sh start

# Stop Flower
./celery_flower.sh stop

# Restart Flower
./celery_flower.sh restart

# Check Flower status
./celery_flower.sh status
```

## Features

All scripts provide:
- ✅ **PID file management** - Track process IDs
- ✅ **Graceful shutdown** - TERM signal with fallback to KILL
- ✅ **Status checking** - Verify if services are running
- ✅ **Log file management** - Separate logs for each service
- ✅ **Stale PID cleanup** - Automatic cleanup of stale PID files
- ✅ **Background execution** - Services run as daemons

## Directory Structure

Scripts create these directories automatically:

```
backend/
├── celery_manage.sh       # Master control script
├── celery_worker.sh       # Worker control script
├── celery_flower.sh       # Flower control script
├── logs/                  # Log files
│   ├── celery_worker.log
│   └── celery_flower.log
└── pids/                  # PID files
    ├── celery_worker.pid
    └── celery_flower.pid
```

## Quick Start

### Development Environment

```bash
# Start everything
./celery_manage.sh start

# Check status
./celery_manage.sh status

# View logs
tail -f logs/celery_worker.log
tail -f logs/celery_flower.log

# Access Flower dashboard
open http://localhost:5555

# Stop everything when done
./celery_manage.sh stop
```

### Production Environment

For production, use a process manager like **systemd** or **supervisord** (see below).

## Configuration

### Environment Variables

Set these in your `.env` file or export before running:

```bash
# Worker configuration
export WORKER_NAME=agent_worker
export CONCURRENCY=4
export LOG_LEVEL=info

# Flower configuration
export FLOWER_PORT=5555
export CELERY_BROKER_URL=redis://localhost:6379/0
```

### Worker Settings

Edit `celery_worker.sh` to adjust:
- `CONCURRENCY`: Number of concurrent tasks (default: 2)
- `WORKER_NAME`: Worker hostname (default: agent_worker)
- `LOG_LEVEL`: Logging verbosity (default: info)

### Flower Settings

Edit `celery_flower.sh` to adjust:
- `PORT`: Dashboard port (default: 5555)
- `BROKER_URL`: Redis connection string

## Common Operations

### Start Services on System Boot

Add to your crontab:

```bash
crontab -e

# Add this line:
@reboot cd /path/to/backend && ./celery_manage.sh start
```

### Monitor Logs in Real-Time

```bash
# Worker logs
tail -f logs/celery_worker.log

# Flower logs
tail -f logs/celery_flower.log

# Both logs together
tail -f logs/celery_*.log
```

### Graceful Worker Restart

```bash
# This waits for current tasks to complete
./celery_worker.sh stop
sleep 5
./celery_worker.sh start

# Or use restart (includes wait)
./celery_worker.sh restart
```

### Force Stop (Emergency)

If graceful shutdown fails:

```bash
# Kill worker
pkill -9 -f "celery.*worker"

# Kill Flower
pkill -9 -f "celery.*flower"

# Clean up PID files
rm -f pids/*.pid
```

## Systemd Integration (Linux Production)

Create `/etc/systemd/system/celery-worker.service`:

```ini
[Unit]
Description=Celery Worker for Avery
After=network.target redis.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/path/to/backend
ExecStart=/path/to/backend/celery_worker.sh start
ExecStop=/path/to/backend/celery_worker.sh stop
ExecReload=/path/to/backend/celery_worker.sh restart
PIDFile=/path/to/backend/pids/celery_worker.pid
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/celery-flower.service`:

```ini
[Unit]
Description=Celery Flower Dashboard
After=network.target celery-worker.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/path/to/backend
ExecStart=/path/to/backend/celery_flower.sh start
ExecStop=/path/to/backend/celery_flower.sh stop
PIDFile=/path/to/backend/pids/celery_flower.pid
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable celery-worker
sudo systemctl enable celery-flower
sudo systemctl start celery-worker
sudo systemctl start celery-flower

# Check status
sudo systemctl status celery-worker
sudo systemctl status celery-flower
```

## Supervisord Integration (Alternative)

Create `/etc/supervisor/conf.d/celery.conf`:

```ini
[program:celery-worker]
command=/path/to/backend/celery_worker.sh start
directory=/path/to/backend
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/path/to/backend/logs/celery_worker.log

[program:celery-flower]
command=/path/to/backend/celery_flower.sh start
directory=/path/to/backend
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/path/to/backend/logs/celery_flower.log
```

Start with supervisord:

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start celery-worker
sudo supervisorctl start celery-flower
```

## Troubleshooting

### Worker Won't Start

```bash
# Check Redis connection
redis-cli ping

# Check for port conflicts
lsof -i :6379

# Check logs
tail -n 50 logs/celery_worker.log

# Try starting in foreground for debugging
celery -A app.celery_app worker --loglevel=debug
```

### Stale PID Files

```bash
# Clean up manually
rm -f pids/*.pid

# Or let scripts auto-clean
./celery_manage.sh start  # Will detect and clean stale PIDs
```

### Worker Consumes Too Much Memory

```bash
# Reduce concurrency
export CONCURRENCY=1
./celery_worker.sh restart

# Or edit celery_worker.sh and change:
CONCURRENCY="${CONCURRENCY:-1}"
```

### Tasks Not Processing

```bash
# Check worker status
./celery_worker.sh status

# Check Flower dashboard
open http://localhost:5555

# Inspect Celery
celery -A app.celery_app inspect active
celery -A app.celery_app inspect reserved
celery -A app.celery_app inspect stats
```

## Log Rotation

To prevent log files from growing too large:

```bash
# Install logrotate config
sudo nano /etc/logrotate.d/celery

# Add:
/path/to/backend/logs/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    copytruncate
}
```

## Best Practices

1. **Always use celery_manage.sh** for starting/stopping in development
2. **Monitor logs** regularly during initial deployment
3. **Use systemd/supervisord** for production
4. **Set appropriate CONCURRENCY** based on server resources
5. **Enable Redis persistence** (see CELERY_SETUP.md)
6. **Check status** before restarting to avoid duplicate workers
7. **Use graceful shutdown** instead of force-kill when possible

## Quick Reference

```bash
# Most common commands
./celery_manage.sh start     # Start everything
./celery_manage.sh status    # Check status
./celery_manage.sh restart   # Restart everything
./celery_manage.sh stop      # Stop everything

# View logs
tail -f logs/celery_worker.log

# Access monitoring
open http://localhost:5555

# Debug mode (foreground)
celery -A app.celery_app worker --loglevel=debug
```

## Support

For issues:
1. Check logs: `tail -f logs/celery_worker.log`
2. Verify Redis: `redis-cli ping`
3. Check processes: `ps aux | grep celery`
4. Review Celery docs: https://docs.celeryq.dev/
