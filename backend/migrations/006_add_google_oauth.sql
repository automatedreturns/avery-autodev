-- Add Google OAuth columns to users table
-- SQLite doesn't support ADD COLUMN with UNIQUE constraint directly
-- So we add without constraint and create a unique index separately
ALTER TABLE users ADD COLUMN google_id VARCHAR(255);
ALTER TABLE users ADD COLUMN google_email VARCHAR(255);
ALTER TABLE users ADD COLUMN google_picture VARCHAR(500);

-- Create unique index for google_id for faster lookups and uniqueness constraint
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id_unique ON users(google_id) WHERE google_id IS NOT NULL;

-- Make hashed_password nullable for OAuth users
-- SQLite doesn't support ALTER COLUMN, so we need to handle this in application logic
-- The application will allow NULL hashed_password for OAuth-only users
