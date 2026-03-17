# Phase 2 Migration Notes

**Migration File:** `add_phase2_tables.sql`
**Date:** January 6, 2026
**Phase:** Test-Aware Agent (Phase 2)

---

## Overview

This migration adds support for automatic test generation and coverage tracking in Phase 2 of the Agent-Native Testing Strategy.

### What's Added

1. **Test Policy Configuration** - workspace-level test policies
2. **AgentTestGeneration Table** - tracks test generation attempts
3. **CoverageSnapshot Table** - stores coverage over time
4. **Indexes** - for efficient queries
5. **Triggers** - for timestamp management

---

## Changes Summary

| Change Type | Details |
|-------------|---------|
| **Workspace Extensions** | 2 new columns (test_policy_enabled, test_policy_config) |
| **New Tables** | 2 tables (agent_test_generations, coverage_snapshots) |
| **New Indexes** | 9 indexes across new tables |
| **New Triggers** | 1 trigger for timestamp updates |
| **Relationships** | 6 new foreign key relationships |

---

## Detailed Changes

### 1. Workspace Table Extensions

**Columns Added:**
```sql
test_policy_enabled BOOLEAN DEFAULT TRUE NOT NULL
test_policy_config JSON DEFAULT '{...}'
```

**Purpose:**
- `test_policy_enabled`: Enable/disable automatic test generation
- `test_policy_config`: JSON configuration for test policies

**Default Policy:**
```json
{
  "require_tests_for_features": true,
  "require_tests_for_bug_fixes": true,
  "minimum_coverage_percent": 80.0,
  "allow_coverage_decrease": false,
  "max_coverage_decrease_percent": 0.0,
  "require_edge_case_tests": true,
  "require_integration_tests": false,
  "test_quality_threshold": 70.0,
  "auto_generate_tests": true,
  "test_frameworks": {
    "backend": "pytest",
    "frontend": "jest"
  }
}
```

### 2. agent_test_generations Table

**Purpose:** Track automatic test generation attempts by the agent

**Columns:** 24 columns tracking:
- Generation context (trigger type, source files)
- Status tracking (pending → generating → validating → completed/failed)
- Quality metrics (tests generated, quality score, coverage delta)
- Validation results
- Resource usage (tokens, duration)
- Error handling (retry logic)

**Key Fields:**
- `trigger_type`: 'feature', 'bug_fix', or 'manual'
- `status`: Current generation status
- `test_quality_score`: 0-100 quality score
- `coverage_delta`: Change in coverage percentage

**Indexes:**
- `idx_agent_test_gen_workspace_id`
- `idx_agent_test_gen_agent_job_id`
- `idx_agent_test_gen_status`
- `idx_agent_test_gen_created_at`
- `idx_agent_test_gen_workspace_created`

### 3. coverage_snapshots Table

**Purpose:** Track test coverage over time for trend analysis

**Columns:** 17 columns tracking:
- Line coverage (covered, total, percentage)
- Branch coverage (covered, total, percentage)
- File-level coverage breakdown
- Uncovered code locations
- Context (commit, branch, PR)

**Key Fields:**
- `coverage_percent`: Overall coverage percentage
- `file_coverage`: JSON with per-file coverage
- `uncovered_lines`: JSON with line numbers lacking coverage
- `commit_sha`: Git commit associated with snapshot

**Indexes:**
- `idx_coverage_snapshot_workspace_id`
- `idx_coverage_snapshot_created_at`
- `idx_coverage_snapshot_workspace_created`
- `idx_coverage_snapshot_ci_run_id`

---

## Relationships

### New Foreign Keys

```
agent_test_generations
├── workspace_id → workspaces.id (CASCADE)
├── agent_job_id → agent_jobs.id (SET NULL)
└── ci_run_id → ci_runs.id (SET NULL)

coverage_snapshots
├── workspace_id → workspaces.id (CASCADE)
├── ci_run_id → ci_runs.id (SET NULL)
└── agent_test_generation_id → agent_test_generations.id (SET NULL)
```

### Model Relationships (Python)

**Workspace:**
```python
agent_test_generations = relationship("AgentTestGeneration", back_populates="workspace", cascade="all, delete-orphan")
coverage_snapshots = relationship("CoverageSnapshot", back_populates="workspace", cascade="all, delete-orphan")
```

**AgentJob:**
```python
agent_test_generations = relationship("AgentTestGeneration", back_populates="agent_job", cascade="all, delete-orphan")
```

**CIRun:**
```python
agent_test_generation = relationship("AgentTestGeneration", back_populates="ci_run", uselist=False)
coverage_snapshot = relationship("CoverageSnapshot", back_populates="ci_run", uselist=False)
```

---

## Running the Migration

### Prerequisites

1. **Backup Database:**
```bash
cp backend/avery.db backend/avery.db.backup-$(date +%Y%m%d)
```

2. **Verify Current Schema:**
```bash
sqlite3 backend/avery.db ".schema workspaces" | grep test_policy
# Should return nothing if Phase 2 not applied yet
```

### Apply Migration

```bash
cd backend
sqlite3 avery.db < migrations/add_phase2_tables.sql
```

### Verify Migration

**1. Check new columns:**
```bash
sqlite3 avery.db "PRAGMA table_info(workspaces);" | grep test_policy
```

**2. Check new tables:**
```bash
sqlite3 avery.db "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('agent_test_generations', 'coverage_snapshots');"
```

**3. Check indexes:**
```bash
sqlite3 avery.db "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name IN ('agent_test_generations', 'coverage_snapshots');"
```

**4. Check trigger:**
```bash
sqlite3 avery.db "SELECT name FROM sqlite_master WHERE type='trigger' AND name='update_agent_test_gen_timestamp';"
```

### Test in Python

```python
from app.database import SessionLocal
from app.models import Workspace, AgentTestGeneration, CoverageSnapshot

db = SessionLocal()

# Test workspace policy
workspace = db.query(Workspace).first()
print(f"Test policy enabled: {workspace.test_policy_enabled}")
print(f"Test policy config: {workspace.test_policy_config}")

# Test relationships
print(f"Workspace has {len(workspace.agent_test_generations)} test generations")
print(f"Workspace has {len(workspace.coverage_snapshots)} coverage snapshots")

db.close()
```

---

## Rollback

### Using Rollback Script

```bash
cd backend
sqlite3 avery.db < migrations/rollback_phase2_tables.sql
```

**Note:** The rollback script does NOT remove the workspace columns due to SQLite limitations. See script for manual instructions if needed.

### Manual Rollback

If you need to completely revert including workspace columns:

```bash
# 1. Backup database
cp backend/avery.db backend/avery.db.before-rollback

# 2. Run rollback script
sqlite3 avery.db < migrations/rollback_phase2_tables.sql

# 3. Manually handle workspace columns if needed
# (See rollback_phase2_tables.sql for detailed instructions)
```

---

## Post-Migration Steps

### 1. Restart Backend

```bash
cd backend
./restart.sh
```

### 2. Verify Models Load

```bash
cd backend
python -c "from app.models import AgentTestGeneration, CoverageSnapshot; print('Models loaded successfully')"
```

### 3. Test API Access

```bash
curl http://localhost:8000/api/v1/test-generation/workspaces/1/policy \
  -H "Authorization: Bearer $USER_TOKEN"
```

### 4. Check Logs

```bash
tail -f logs/backend.log | grep -i "phase 2\|test_generation\|coverage"
```

---

## Migration Impact

### Database Size

Estimated size increase:
- Empty tables: ~50 KB
- Per test generation record: ~2 KB
- Per coverage snapshot: ~5 KB (depends on file count)

**Example:** 1000 test generations + 1000 coverage snapshots ≈ 7 MB

### Performance

- All queries use indexes
- Foreign keys properly indexed
- No significant performance impact expected
- Coverage snapshots table will grow fastest

### Monitoring Recommendations

```sql
-- Monitor table sizes
SELECT
    name,
    (SELECT COUNT(*) FROM sqlite_master WHERE tbl_name=name) as table_count,
    pgsize as size_bytes
FROM dbstat
WHERE name IN ('agent_test_generations', 'coverage_snapshots');

-- Monitor growth rate
SELECT
    DATE(created_at) as date,
    COUNT(*) as generations_count
FROM agent_test_generations
GROUP BY DATE(created_at)
ORDER BY date DESC
LIMIT 30;
```

---

## Troubleshooting

### Issue: Migration Fails

**Symptom:** Error during migration

**Solutions:**
1. Check SQLite version: `sqlite3 --version` (need 3.24+)
2. Check database integrity: `sqlite3 avery.db "PRAGMA integrity_check;"`
3. Check permissions: `ls -la backend/avery.db`
4. Review error message for specific SQL issue

### Issue: Workspace Policy Not Showing

**Symptom:** `workspace.test_policy_config` is NULL

**Solution:**
```sql
-- Set default policy for existing workspaces
UPDATE workspaces
SET test_policy_config = '{"require_tests_for_features":true,"require_tests_for_bug_fixes":true,"minimum_coverage_percent":80.0,"allow_coverage_decrease":false,"max_coverage_decrease_percent":0.0,"require_edge_case_tests":true,"require_integration_tests":false,"test_quality_threshold":70.0,"auto_generate_tests":true,"test_frameworks":{"backend":"pytest","frontend":"jest"}}'
WHERE test_policy_config IS NULL;
```

### Issue: Relationship Errors

**Symptom:** AttributeError when accessing relationships

**Solutions:**
1. Verify models imported: Check `backend/app/models/__init__.py`
2. Restart Python: `pkill -f "python.*backend"`
3. Clear pycache: `find backend -type d -name __pycache__ -exec rm -rf {} +`

### Issue: Foreign Key Constraint Failed

**Symptom:** Cannot insert into agent_test_generations

**Solution:**
```sql
-- Enable foreign keys (should be enabled)
PRAGMA foreign_keys = ON;

-- Check foreign keys are valid
PRAGMA foreign_key_check(agent_test_generations);
```

---

## Testing the Migration

### Unit Tests

Create `backend/tests/test_phase2_models.py`:
```python
def test_agent_test_generation_creation(db_session):
    """Test creating an agent test generation record."""
    workspace = create_test_workspace(db_session)

    gen = AgentTestGeneration(
        workspace_id=workspace.id,
        trigger_type="feature",
        source_files=["app/services/foo.py"],
        status="pending"
    )
    db_session.add(gen)
    db_session.commit()

    assert gen.id is not None
    assert gen.status == "pending"

def test_coverage_snapshot_creation(db_session):
    """Test creating a coverage snapshot."""
    workspace = create_test_workspace(db_session)

    snapshot = CoverageSnapshot(
        workspace_id=workspace.id,
        lines_covered=900,
        lines_total=1000,
        coverage_percent=90.0,
        commit_sha="abc123def456",
        branch_name="feature-xyz"
    )
    db_session.add(snapshot)
    db_session.commit()

    assert snapshot.id is not None
    assert snapshot.get_coverage_grade() == "A"
```

### Integration Tests

```bash
# Create test generation
curl -X POST http://localhost:8000/api/v1/test-generation/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": 1,
    "files": ["app/services/test.py"],
    "generation_type": "unit"
  }'

# Verify in database
sqlite3 backend/avery.db "SELECT * FROM agent_test_generations ORDER BY created_at DESC LIMIT 1;"
```

---

## Future Migrations

Phase 2 is designed to be extended in future phases:

### Phase 3 (Confidence Scoring)
- Will add `confidence_scores` table
- May extend `agent_test_generations` with confidence metrics

### Phase 4 (Shadow CI)
- Will add `shadow_ci_runs` table
- May extend `coverage_snapshots` with additional metrics

### Phase 5 (Enterprise)
- Will add audit logging
- May extend policies with governance rules

---

## Summary

✅ **Migration adds:**
- 2 columns to workspaces
- 2 new tables (41 columns total)
- 9 indexes
- 1 trigger
- 6 foreign key relationships

✅ **Ready for:**
- Automatic test generation
- Test quality validation
- Coverage tracking
- Policy enforcement
- Trend analysis

🔄 **Rollback available:** `rollback_phase2_tables.sql`

---

**Migration Status:** ✅ Complete
**Phase 2 Database Schema:** ✅ Ready
**Next Step:** Implement Phase 2 services and APIs
