-- Migration 002: Fix slot_id uniqueness on appointments
--
-- The original schema had `slot_id UNIQUE NOT NULL` which prevents
-- rebooking a slot after its appointment is cancelled (the cancelled row
-- still holds the unique key).
--
-- Replace it with a partial unique index that only enforces uniqueness
-- for non-cancelled appointments, which is the correct business rule.

-- Step 1: Drop the existing unique constraint on slot_id
ALTER TABLE appointments
    DROP CONSTRAINT IF EXISTS appointments_slot_id_key;

-- Step 2: Add a partial unique index — only one active (non-cancelled)
--         appointment is allowed per slot at any time.
CREATE UNIQUE INDEX IF NOT EXISTS uq_appointments_slot_active
    ON appointments(slot_id)
    WHERE status != 'CANCELLED';
