#!/usr/bin/env python3
"""
Simple migration runner for SQLite database.
Runs all SQL migrations in the migrations/ directory in order.
"""

import sqlite3
import sys
from pathlib import Path

def run_migrations():
    """Run all SQL migration files in order."""
    # Get database path from DATABASE_URL or use default
    db_path = Path("avery.db")
    migrations_dir = Path("migrations")

    if not migrations_dir.exists():
        print(f"Error: Migrations directory not found: {migrations_dir}")
        sys.exit(1)

    # Get all SQL migration files sorted by name
    migration_files = sorted(migrations_dir.glob("*.sql"))

    if not migration_files:
        print("No migration files found.")
        return

    print(f"Found {len(migration_files)} migration(s)")
    print(f"Database: {db_path}")
    print("-" * 60)

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        for migration_file in migration_files:
            print(f"Running: {migration_file.name}...", end=" ")

            # Read migration SQL
            with open(migration_file, 'r') as f:
                sql = f.read()

            try:
                # Execute migration (handle multiple statements)
                cursor.executescript(sql)
                conn.commit()
                print("✓ Success")
            except sqlite3.Error as e:
                # Check if error is about already existing table/column
                error_msg = str(e).lower()
                if any(x in error_msg for x in ['already exists', 'duplicate column']):
                    print("⊘ Already applied")
                else:
                    print(f"✗ Failed: {e}")
                    # Continue with other migrations instead of failing

        print("-" * 60)
        print("Migrations completed!")

    finally:
        conn.close()

if __name__ == "__main__":
    run_migrations()
