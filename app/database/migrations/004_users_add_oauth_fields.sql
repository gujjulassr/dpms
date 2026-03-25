-- Migration 004: Add OAuth fields to users table
-- auth_provider: LOCAL (username+password) | GOOGLE
-- google_sub:    Google's unique user ID (subject claim in ID token)
-- email:         user email — used for auto-matching patients on first Google login

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS email         VARCHAR(150),
    ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(20) NOT NULL DEFAULT 'LOCAL'
        CHECK(auth_provider IN ('LOCAL','GOOGLE')),
    ADD COLUMN IF NOT EXISTS google_sub    VARCHAR(100);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub
    ON users(google_sub) WHERE google_sub IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_users_email
    ON users(email) WHERE email IS NOT NULL;
