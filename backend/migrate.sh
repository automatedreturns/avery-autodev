#!/usr/bin/env bash
# Database migration script using Alembic

set -e

cd "$(dirname "$0")"

echo "Running database migrations..."
echo "Database URL: ${DATABASE_URL:-sqlite:///./avery.db}"
echo ""

# Run migrations
alembic upgrade head

echo ""
echo "✓ Migrations completed successfully!"
