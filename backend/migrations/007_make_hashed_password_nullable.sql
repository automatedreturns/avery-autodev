-- Make hashed_password nullable for OAuth users
-- SQLite doesn't support ALTER COLUMN, so we need to recreate the table

-- Step 1: Create new table with nullable hashed_password
CREATE TABLE users_new (
    id INTEGER PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    username VARCHAR UNIQUE NOT NULL,
    hashed_password VARCHAR,  -- Now nullable
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    google_id VARCHAR(255),
    google_email VARCHAR(255),
    google_picture VARCHAR(500),
    github_token_encrypted VARCHAR,
    github_username VARCHAR
);

-- Step 2: Copy data from old table
INSERT INTO users_new (id, email, username, hashed_password, is_active, created_at, google_id, google_email, google_picture, github_token_encrypted, github_username)
SELECT id, email, username, hashed_password, is_active, created_at, google_id, google_email, google_picture, github_token_encrypted, github_username
FROM users;

-- Step 3: Drop old table
DROP TABLE users;

-- Step 4: Rename new table
ALTER TABLE users_new RENAME TO users;

-- Step 5: Recreate indexes
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id_unique ON users(google_id) WHERE google_id IS NOT NULL;
