# Deprecated SQL Migrations

This directory contains old manual SQL migration files that were used before Alembic was implemented.

**These migrations are now deprecated and should not be used.**

## Migration to Alembic

The project now uses Alembic for database migrations, which provides:

- Database-agnostic migrations (works with SQLite and PostgreSQL)
- Automatic migration generation from model changes
- Version control and rollback capabilities
- Better handling of complex schema changes

## New Migration System

Please use Alembic for all new migrations:

```bash
cd backend

# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Or use the helper script
./migrate.sh
```

See `MIGRATIONS.md` in the backend directory for full documentation.

## Historical Reference

These SQL files represent the schema as it was before Alembic was introduced:

- `001_create_users.sql` - Initial users table
- `002_create_workspaces.sql` - Workspaces and members
- `003_create_workspace_tasks.sql` - Task tracking
- `004_add_agent_fields.sql` - Agent integration
- `005_add_test_generation_jobs.sql` - Test generation features
- `006_add_google_oauth.sql` - Google OAuth integration
- `007_add_magic_link.sql` - Magic link authentication
- `008_add_issue_polling.sql` - Automatic issue polling

All of these features are now tracked in the Alembic migration system starting from the `initial_baseline` migration.
