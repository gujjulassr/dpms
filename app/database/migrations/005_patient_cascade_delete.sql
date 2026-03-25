-- Migration 005: Add ON DELETE CASCADE to all patient_id foreign keys
-- This lets DELETE FROM patients cascade automatically to all child tables,
-- so no manual cleanup of appointments/waitlist/etc. is needed.

-- appointments
ALTER TABLE appointments
    DROP CONSTRAINT IF EXISTS appointments_patient_id_fkey,
    ADD  CONSTRAINT appointments_patient_id_fkey
         FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE;

-- waitlist
ALTER TABLE waitlist
    DROP CONSTRAINT IF EXISTS waitlist_patient_id_fkey,
    ADD  CONSTRAINT waitlist_patient_id_fkey
         FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE;

-- cancellation_log
ALTER TABLE cancellation_log
    DROP CONSTRAINT IF EXISTS cancellation_log_patient_id_fkey,
    ADD  CONSTRAINT cancellation_log_patient_id_fkey
         FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE;

-- notification_log
ALTER TABLE notification_log
    DROP CONSTRAINT IF EXISTS notification_log_patient_id_fkey,
    ADD  CONSTRAINT notification_log_patient_id_fkey
         FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE;

-- users table already has ON DELETE SET NULL (correct — keeps the user row but nulls patient_id)
