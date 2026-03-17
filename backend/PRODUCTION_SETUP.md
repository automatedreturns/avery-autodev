# Production PostgreSQL Setup

This guide covers setting up the application with PostgreSQL for production.

## Prerequisites

1. PostgreSQL server installed and running
2. Database created
3. Database user with appropriate permissions

## Environment Configuration

Set the following environment variables in your production environment:

```bash
# Database
DATABASE_URL="postgresql://username:password@host:5432/database_name"

# Security
SECRET_KEY="your-secret-key-here"
SESSION_SECRET_KEY="your-session-secret-here"

# CORS - Add your production domain
BACKEND_CORS_ORIGINS='["https://your-frontend-domain.com"]'

# Google OAuth
GOOGLE_CLIENT_ID="your-google-client-id"
GOOGLE_CLIENT_SECRET="your-google-client-secret"
GOOGLE_REDIRECT_URI="https://your-backend-domain.com/api/v1/auth/google/callback"

# Frontend URL
FRONTEND_URL="https://your-frontend-domain.com"

# SMTP for Magic Links
SMTP_HOST="smtp.office365.com"
SMTP_PORT=587
SMTP_USER="your-email@domain.com"
SMTP_PASSWORD="your-email-password"
SMTP_FROM_EMAIL="your-email@domain.com"
SMTP_FROM_NAME="Your App Name"
SMTP_USE_TLS=true
MAGIC_LINK_EXPIRE_MINUTES=15

# Optional
ANTHROPIC_API_KEY="your-anthropic-api-key"
REPOS_BASE_PATH="/app/repos"
```

## Database Setup

### 1. Create PostgreSQL Database

```sql
CREATE DATABASE avery_production;
CREATE USER avery_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE avery_production TO avery_user;
```

### 2. Install PostgreSQL Python Driver

The project should already have `psycopg2-binary` in requirements. If not:

```bash
pip install psycopg2-binary
```

Or add to `pyproject.toml`:

```toml
[tool.poetry.dependencies]
psycopg2-binary = "^2.9.9"
```

### 3. Run Migrations

With `DATABASE_URL` set to your PostgreSQL connection string:

```bash
cd backend

# Check current migration status
alembic current

# Apply all migrations
alembic upgrade head
```

## Deployment Checklist

- [ ] PostgreSQL server is running and accessible
- [ ] Database and user created
- [ ] All environment variables set
- [ ] `psycopg2-binary` installed
- [ ] Migrations applied (`alembic upgrade head`)
- [ ] Application can connect to database
- [ ] SMTP credentials tested
- [ ] Google OAuth credentials configured
- [ ] CORS origins include frontend domain

## Migration Workflow for Production

### Option 1: Manual Migration

Before deploying new code that requires schema changes:

```bash
# SSH into production server
ssh production-server

# Navigate to app directory
cd /path/to/app/backend

# Pull latest code
git pull

# Run migrations
alembic upgrade head

# Restart application
systemctl restart avery-backend
```

### Option 2: Automated Migration (Recommended)

Include migrations in your deployment process:

```bash
#!/bin/bash
# deploy.sh

cd backend

# Run migrations
alembic upgrade head

# Restart application
systemctl restart avery-backend
```

### Option 3: Separate Migration Job

For zero-downtime deployments, run migrations as a separate job before deploying new code:

```bash
# migration-job.sh
cd backend
alembic upgrade head
```

## Connecting to Production Database

### From Application

The application automatically uses `DATABASE_URL` from environment variables.

### For Manual Queries

```bash
# Using psql
psql "$DATABASE_URL"

# Or with individual parameters
psql -h host -U username -d database_name
```

### Check Migration Status

```bash
cd backend
alembic current
alembic history
```

## Troubleshooting

### Connection Refused

- Check PostgreSQL is running: `systemctl status postgresql`
- Verify firewall rules allow connections on port 5432
- Check `pg_hba.conf` for authentication settings

### Permission Denied

- Ensure database user has appropriate privileges
- Grant connect permission: `GRANT CONNECT ON DATABASE dbname TO username;`
- Grant schema usage: `GRANT USAGE ON SCHEMA public TO username;`

### Migration Errors

If migrations fail:

1. Check current migration status: `alembic current`
2. Review migration history: `alembic history`
3. Check database logs for errors
4. If database is corrupted, restore from backup

### Rolling Back Migrations

If you need to rollback:

```bash
# Downgrade one version
alembic downgrade -1

# Downgrade to specific version
alembic downgrade <revision>
```

## Performance Tuning

For production PostgreSQL:

1. **Connection Pooling**: Consider using PgBouncer
2. **Indexes**: Monitor slow queries and add indexes as needed
3. **Backup**: Set up regular backups using `pg_dump`
4. **Monitoring**: Use tools like pg_stat_statements

## Security Best Practices

1. Use strong passwords for database users
2. Limit database user permissions to only what's needed
3. Use SSL/TLS for database connections
4. Keep PostgreSQL updated with security patches
5. Regular backups and test restore procedures
6. Use environment variables for secrets, never commit them

## Example Production DATABASE_URL Formats

```bash
# Standard connection
DATABASE_URL="postgresql://user:pass@localhost:5432/dbname"

# With SSL
DATABASE_URL="postgresql://user:pass@localhost:5432/dbname?sslmode=require"

# With connection pooling (if using PgBouncer)
DATABASE_URL="postgresql://user:pass@pgbouncer-host:6432/dbname"

# Cloud providers
# AWS RDS
DATABASE_URL="postgresql://user:pass@instance.region.rds.amazonaws.com:5432/dbname"

# Google Cloud SQL
DATABASE_URL="postgresql://user:pass@/dbname?host=/cloudsql/project:region:instance"

# Heroku (automatically provided)
DATABASE_URL="postgres://user:pass@host:5432/dbname"
```

---

For development setup with SQLite, see [MIGRATIONS.md](MIGRATIONS.md)
