# Migration Notes for Phase 1 CI Integration

## Changes Made

### 1. New Table: `ci_runs`
**File:** `add_ci_runs_table.sql`

Created new table to track GitHub Actions CI runs with:
- Foreign keys to `workspaces` and `agent_jobs`
- CI status and results tracking
- Self-fix attempt tracking
- Quality metrics (tests, coverage, errors)
- Comprehensive indexes for performance

### 2. Model Relationships (No Schema Changes Required)

The following changes were made to SQLAlchemy models but **do not require database migration** as they only define relationships in Python code, not database schema:

#### backend/app/models/workspace.py
```python
# Added relationship (line 46):
ci_runs = relationship("CIRun", back_populates="workspace", cascade="all, delete-orphan")
```

This creates a one-to-many relationship where:
- One workspace can have many CI runs
- When workspace is deleted, all its CI runs are deleted (cascade)
- No database column needed (foreign key is in `ci_runs` table)

#### backend/app/models/agent_job.py
```python
# Added relationship (line 60):
ci_runs = relationship("CIRun", back_populates="agent_job", cascade="all, delete-orphan")
```

This creates a one-to-many relationship where:
- One agent job can have many CI runs
- When agent job is deleted, all its CI runs are deleted (cascade)
- No database column needed (foreign key is in `ci_runs` table)

### 3. Why No Migration Needed for Relationships?

SQLAlchemy relationships are **ORM-level constructs** that:
1. Do not modify database schema
2. Only affect how Python code queries data
3. Use existing foreign keys in related tables

The foreign keys are defined in the `ci_runs` table:
```sql
-- Foreign keys in ci_runs table
FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
FOREIGN KEY (agent_job_id) REFERENCES agent_jobs(id) ON DELETE CASCADE
```

These foreign keys establish the database relationships. The Python `relationship()` definitions just make it easier to query:

```python
# Without relationship:
ci_runs = db.query(CIRun).filter(CIRun.workspace_id == workspace.id).all()

# With relationship:
ci_runs = workspace.ci_runs  # Much cleaner!
```

---

## Migration Checklist

### ✅ Already Applied (No Action Needed)
- [x] `workspace.py` - Added `ci_runs` relationship
- [x] `agent_job.py` - Added `ci_runs` relationship
- [x] `__init__.py` - Imported `CIRun` and `AgentJob` models

### 🔄 Needs to be Run
- [ ] Run SQL migration: `sqlite3 avery.db < migrations/add_ci_runs_table.sql`

---

## How to Verify Migration

### 1. Check Table Exists
```bash
sqlite3 backend/avery.db "SELECT name FROM sqlite_master WHERE type='table' AND name='ci_runs';"
```
Expected output: `ci_runs`

### 2. Check Schema
```bash
sqlite3 backend/avery.db ".schema ci_runs"
```
Should show full table definition with all columns and foreign keys.

### 3. Check Indexes
```bash
sqlite3 backend/avery.db "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='ci_runs';"
```
Should show multiple indexes (workspace_id, pr_number, run_id, etc.).

### 4. Test Relationships in Python
```python
from app.database import SessionLocal
from app.models.workspace import Workspace
from app.models.ci_run import CIRun

db = SessionLocal()

# Test workspace -> ci_runs relationship
workspace = db.query(Workspace).first()
print(f"Workspace {workspace.id} has {len(workspace.ci_runs)} CI runs")

# Test ci_run -> workspace relationship
ci_run = db.query(CIRun).first()
if ci_run:
    print(f"CI run {ci_run.id} belongs to workspace: {ci_run.workspace.name}")

db.close()
```

---

## Rollback (if needed)

To rollback the migration:

```sql
-- Drop indexes
DROP INDEX IF EXISTS idx_ci_runs_workspace_id;
DROP INDEX IF EXISTS idx_ci_runs_agent_job_id;
DROP INDEX IF EXISTS idx_ci_runs_pr_number;
DROP INDEX IF EXISTS idx_ci_runs_run_id;
DROP INDEX IF EXISTS idx_ci_runs_status;
DROP INDEX IF EXISTS idx_ci_runs_conclusion;
DROP INDEX IF EXISTS idx_ci_runs_workspace_pr;
DROP INDEX IF EXISTS idx_ci_runs_created_at;

-- Drop trigger
DROP TRIGGER IF EXISTS update_ci_runs_timestamp;

-- Drop table
DROP TABLE IF EXISTS ci_runs;
```

Then revert the relationship changes in `workspace.py` and `agent_job.py` by removing the `ci_runs = relationship(...)` lines.

---

## Future Migrations

### Phase 2 (Test-Aware Agent)
Will add:
- Workspace test policy fields (no migration needed if using JSON column)
- Possibly new tables for test quality metrics

### Phase 3 (Confidence Scoring)
Will add:
- `confidence_scores` table
- `pr_rules` table for custom rules

### Phase 4 (Shadow CI)
Will add:
- `shadow_ci_runs` table
- Additional metrics columns

---

## Alternative: Using Alembic (Recommended for Production)

If you want to use proper migration management:

### 1. Install Alembic
```bash
pip install alembic
```

### 2. Initialize Alembic
```bash
cd backend
alembic init alembic
```

### 3. Configure Alembic
Edit `alembic.ini`:
```ini
sqlalchemy.url = sqlite:///./avery.db
```

Edit `alembic/env.py`:
```python
from app.database import Base
from app.models import *  # Import all models
target_metadata = Base.metadata
```

### 4. Generate Migration
```bash
alembic revision --autogenerate -m "Add ci_runs table"
```

### 5. Review and Apply
```bash
# Review the generated migration file in alembic/versions/
# Then apply it:
alembic upgrade head
```

### 6. Future Migrations
```bash
# Make model changes, then:
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

This gives you:
- Version control for schema changes
- Automatic detection of model changes
- Easy rollback: `alembic downgrade -1`
- Better team collaboration

---

## Summary

✅ **Relationships added to models:** workspace.py, agent_job.py (no migration needed)
✅ **SQL migration created:** add_ci_runs_table.sql
🔄 **Action required:** Run the SQL migration
💡 **Recommendation:** Consider using Alembic for future migrations
