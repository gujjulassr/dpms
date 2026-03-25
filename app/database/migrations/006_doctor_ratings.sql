-- =============================================================
-- Migration 006 — Doctor ratings + appointment completion tracking
-- =============================================================

-- Add review_sent & completed_at columns to appointments (if not already there)
ALTER TABLE appointments
    ADD COLUMN IF NOT EXISTS review_sent  BOOLEAN   NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;

-- Doctor ratings: one rating per appointment, by the patient who had it
CREATE TABLE IF NOT EXISTS doctor_ratings (
    rating_id      UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    appointment_id UUID         NOT NULL REFERENCES appointments(appointment_id) ON DELETE CASCADE,
    patient_id     UUID         NOT NULL REFERENCES patients(patient_id)         ON DELETE CASCADE,
    doctor_id      UUID         NOT NULL REFERENCES doctors(doctor_id)           ON DELETE CASCADE,
    stars          SMALLINT     NOT NULL CHECK (stars BETWEEN 1 AND 5),
    comment        TEXT,
    created_at     TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE (appointment_id)   -- one rating per appointment
);

CREATE INDEX IF NOT EXISTS idx_ratings_doctor ON doctor_ratings(doctor_id);
CREATE INDEX IF NOT EXISTS idx_ratings_patient ON doctor_ratings(patient_id);
