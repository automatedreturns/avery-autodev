# Database Migrations

This project uses [Alembic](https://alembic.sqlalchemy.org/) for database migrations, which works with both SQLite (development) and PostgreSQL (production).

## Prerequisites

Alembic is already installed as part of the project dependencies.

## Configuration

- **alembic.ini**: Main Alembic configuration file
- **alembic/env.py**: Environment configuration that loads database URL from settings
- **alembic/versions/**: Contains all migration files

The database URL is automatically loaded from your `.env` file via the `DATABASE_URL` setting.

## Common Commands

### Check Current Migration Version

```bash
cd backend
alembic current
```

### View Migration History

```bash
alembic history
```

### Create a New Migration

After modifying models in `app/models/`, create a migration:

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "description_of_changes"

# Or create an empty migration to write manually
alembic revision -m "description_of_changes"
```

### Apply Migrations

```bash
# Upgrade to the latest version
alembic upgrade head

# Upgrade one version forward
alembic upgrade +1

# Downgrade one version back
alembic downgrade -1
```

## Database-Specific Considerations

### SQLite (Development)

- Used for local development
- Database file: `avery.db`
- Limited ALTER TABLE support (no column drops, limited column modifications)

### PostgreSQL (Production)

- Used for production deployment
- Full ALTER TABLE support
- Better performance and scalability

## Creating Migrations for Both Databases

When creating migrations, ensure they work with both SQLite and PostgreSQL:

1. **Avoid operations not supported by SQLite:**
   - Dropping columns (requires table recreation)
   - Renaming columns (requires table recreation)
   - Adding columns with constraints to existing tables (may require multiple steps)

2. **Use Alembic's batch operations for SQLite:**
   ```python
   from alembic import op
   import sqlalchemy as sa
   
   def upgrade():
       with op.batch_alter_table('table_name', schema=None) as batch_op:
           batch_op.add_column(sa.Column('new_column', sa.String(), nullable=True))
   ```

3. **Test migrations on both databases before deploying to production**

## Migration Workflow

1. **Make changes to models** in `app/models/`
2. **Generate migration:**
   ```bash
   alembic revision --autogenerate -m "add_user_profile_fields"
   ```
3. **Review the generated migration file** in `alembic/versions/`
4. **Test the migration:**
   ```bash
   # Apply it
   alembic upgrade head
   
   # If needed, rollback
   alembic downgrade -1
   ```
5. **Commit the migration file** to version control

## Initial Setup

The project already has a baseline migration (`initial_baseline`) that represents the current database schema including:

- Users table (with Google OAuth fields: `google_id`, `google_email`, `google_picture`)
- Magic Link tokens table
- Workspaces and workspace members
- Workspace tasks and agent messages
- Test suites, test cases, test runs, and test results
- Polling status and polling history

## Troubleshooting

### Migration out of sync

If your database is out of sync with migrations:

```bash
# Check current version
alembic current

# Check history
alembic history

# Stamp database with a specific version (dangerous!)
alembic stamp <revision>
```

### Starting fresh (development only)

```bash
# Delete the database
rm avery.db

# Run all migrations from scratch
alembic upgrade head
```

## Production Deployment

For production PostgreSQL databases:

1. Set `DATABASE_URL` in your environment:
   ```bash
   export DATABASE_URL="postgresql://user:password@localhost/dbname"
   ```

2. Run migrations:
   ```bash
   cd backend
   alembic upgrade head
   ```

3. Consider running migrations as part of your deployment process or as a separate migration job

## Deprecated: Manual SQL Migrations

The `migrations/` directory contains old manual SQL migration files that were used before Alembic. These are now deprecated and should not be used. All future migrations should be created using Alembic.

The old `run_migrations.py` script is also deprecated in favor of using `alembic` directly.
