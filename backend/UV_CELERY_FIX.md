# UV + Celery Integration Fix

## Problem

Celery worker was not processing tasks even though it appeared to be running. The root cause was a **package management mismatch**:

- **Backend runs with**: `uv run python main.py` (uv manages dependencies)
- **Celery was running with**: Direct Python from conda environment
- **Result**: Celery couldn't see packages installed by `uv` (they're in a separate virtual environment)

## Symptoms

1. ✅ Celery worker appeared to be running
2. ✅ Redis was working
3. ✅ Tasks were in the queue
4. ❌ Tasks were NOT being consumed
5. ❌ Worker showed "empty" when inspecting active tasks

## Root Cause

When you use `uv`, it creates an isolated virtual environment. Running `celery` directly uses your system/conda Python, which doesn't have access to the packages installed via `uv`.

```bash
# This doesn't work:
celery -A app.celery_app worker

# This works:
uv run celery -A app.celery_app worker
```

## Solution

Updated all Celery management scripts to use `uv run`:

### Files Modified

1. **[celery_worker.sh](celery_worker.sh)**
   - Changed: `celery -A app.celery_app worker`
   - To: `uv run celery -A app.celery_app worker`

2. **[celery_flower.sh](celery_flower.sh)**
   - Changed: `celery -A app.celery_app flower`
   - To: `uv run celery -A app.celery_app flower`

3. **[celery_debug.sh](celery_debug.sh)**
   - All `celery -A app.celery_app inspect` commands
   - Changed to: `uv run celery -A app.celery_app inspect`

4. **[start_celery_worker.sh](start_celery_worker.sh)**
   - Legacy script also updated

5. **[start_flower.sh](start_flower.sh)**
   - Legacy script also updated

### Additional Fixes

#### Task Routing Issue

Found a secondary issue with task routing:

**Problem**: Task routing pattern was `"app.tasks.agent_tasks.*"` but actual task name was `"agent_tasks.process_agent_response"` (no `app.` prefix)

**Fixed in [app/celery_app.py](app/celery_app.py:43-46)**:
```python
# Before
task_routes={
    "app.tasks.agent_tasks.*": {"queue": "agent_processing"},
}

# After
task_routes={
    "agent_tasks.*": {"queue": "agent_processing"},
}
```

#### Queue Subscription

**Problem**: Worker wasn't listening to the default "celery" queue where tasks were being sent

**Fixed in [celery_worker.sh](celery_worker.sh:56)**:
```bash
# Before
--queues=agent_processing,github_operations

# After
--queues=agent_processing,github_operations,celery
```

## Verification

After fixes, verify everything works:

```bash
# Start services
./celery_manage.sh start

# Check status
./celery_debug.sh check

# Should show:
# ✅ Redis is running
# ✅ Worker is running (PID: xxxxx)
# ✅ Flower is running
# ✅ Worker shows as online (1 node online)

# Test task processing
./celery_debug.sh active  # Should show tasks when running
```

## Why UV?

If your project uses `uv` for package management:

**Pros:**
- ✅ Faster package installation
- ✅ Better dependency resolution
- ✅ Consistent environments
- ✅ Works with pyproject.toml

**Cons:**
- ⚠️  Must use `uv run` for all Python commands
- ⚠️  Separate virtual environment from system Python

## Alternative Solutions

If you don't want to use `uv run` with Celery:

### Option 1: Install packages globally
```bash
pip install celery redis flower
# Then use celery directly without uv run
```

### Option 2: Activate UV's virtual environment
```bash
# Find UV's venv
uv venv --show

# Activate it
source $(uv venv --show)/bin/activate

# Then run celery normally
celery -A app.celery_app worker
```

### Option 3: Use UV for everything (Recommended)
```bash
# Always prefix with uv run
uv run celery -A app.celery_app worker
uv run python script.py
uv run uvicorn app.main:app
```

## Testing

To verify Celery can see your packages:

```bash
# Test import
uv run python -c "from app.celery_app import celery_app; print('OK')"

# Should print: OK

# If it fails, packages aren't visible to uv's environment
```

## Current Status

✅ **All scripts updated to use `uv run`**
✅ **Task routing fixed**
✅ **Queue subscription fixed**
✅ **Worker successfully processing tasks**
✅ **Flower dashboard accessible at http://localhost:5555**

## Quick Reference

```bash
# Start everything
./celery_manage.sh start

# Stop everything
./celery_manage.sh stop

# Check status
./celery_debug.sh check

# View logs
tail -f logs/celery_worker.log

# Access Flower
open http://localhost:5555
```

## For Production

In production, ensure your deployment uses `uv run` consistently:

```ini
# systemd service file
[Service]
ExecStart=/path/to/backend/celery_worker.sh start

# Or directly:
ExecStart=/usr/local/bin/uv run celery -A app.celery_app worker ...
```

## Summary

The key insight: **When using `uv` for package management, ALL Python commands must be prefixed with `uv run`** to access the correct virtual environment with all dependencies.

This applies to:
- ✅ Running the backend: `uv run python main.py`
- ✅ Running Celery: `uv run celery -A app.celery_app worker`
- ✅ Running Flower: `uv run celery -A app.celery_app flower`
- ✅ Running scripts: `uv run python script.py`
