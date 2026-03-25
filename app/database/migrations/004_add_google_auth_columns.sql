-- Migration 004: Extend users table for Google login and email-based identity

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS email VARCHAR(255);

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(20) NOT NULL DEFAULT 'LOCAL'
    CHECK (auth_provider IN ('LOCAL', 'GOOGLE', 'BOTH'));

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS google_sub VARCHAR(255);

UPDATE users AS u
SET email = s.email
FROM staff AS s
WHERE u.staff_id = s.staff_id
  AND u.email IS NULL;

UPDATE users AS u
SET email = d.email
FROM doctors AS d
WHERE u.doctor_id = d.doctor_id
  AND u.email IS NULL;

UPDATE users AS u
SET email = p.email
FROM patients AS p
WHERE u.patient_id = p.patient_id
  AND u.email IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub_unique
    ON users(google_sub)
    WHERE google_sub IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique
    ON users(LOWER(email))
    WHERE email IS NOT NULL;
