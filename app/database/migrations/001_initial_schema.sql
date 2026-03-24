-- =============================================================
-- DPAM - Doctor Patient Appointment Management
-- Migration : 001_initial_schema.sql
-- Database  : dpam
-- Run       : psql -U postgres -d dpam -f 001_initial_schema.sql
-- =============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================
-- TABLE: patients
-- =============================================================
CREATE TABLE IF NOT EXISTS patients (
    patient_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name               VARCHAR(100) NOT NULL,
    email                   VARCHAR(150) UNIQUE NOT NULL,
    phone                   VARCHAR(15) UNIQUE NOT NULL,
    date_of_birth           DATE,
    cancellation_count      INTEGER DEFAULT 0,
    late_cancellation_count INTEGER DEFAULT 0,
    no_show_count           INTEGER DEFAULT 0,
    risk_score              NUMERIC(4,2) DEFAULT 0.0,
    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW()
);

-- =============================================================
-- TABLE: doctors
-- =============================================================
CREATE TABLE IF NOT EXISTS doctors (
    doctor_id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name               VARCHAR(100) NOT NULL,
    specialization          VARCHAR(100) NOT NULL,
    email                   VARCHAR(150) UNIQUE NOT NULL,
    phone                   VARCHAR(15) UNIQUE NOT NULL,
    slot_duration_mins      INTEGER DEFAULT 15,
    max_patients_per_day    INTEGER DEFAULT 40,
    is_active               BOOLEAN DEFAULT TRUE,
    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW()
);

-- =============================================================
-- TABLE: staff
-- role: RECEPTIONIST | DOCTOR | ADMIN
-- Only staff can verify emergencies — patients cannot self-declare
-- =============================================================
CREATE TABLE IF NOT EXISTS staff (
    staff_id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name               VARCHAR(100) NOT NULL,
    email                   VARCHAR(150) UNIQUE NOT NULL,
    phone                   VARCHAR(15) UNIQUE NOT NULL,
    role                    VARCHAR(20) NOT NULL CHECK(role IN ('RECEPTIONIST', 'DOCTOR', 'ADMIN')),
    is_active               BOOLEAN DEFAULT TRUE,
    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW()
);

-- =============================================================
-- TABLE: sessions
-- Morning / Afternoon per doctor per day
-- Lunch 1pm-1:30pm is auto-blocked at slot generation
-- status: OPEN | FULL | CLOSED
-- =============================================================
CREATE TABLE IF NOT EXISTS sessions (
    session_id              SERIAL PRIMARY KEY,
    doctor_id               UUID NOT NULL REFERENCES doctors(doctor_id),
    session_date            DATE NOT NULL,
    session_name            VARCHAR(20) NOT NULL CHECK(session_name IN ('MORNING', 'AFTERNOON')),
    start_time              TIME NOT NULL,
    end_time                TIME NOT NULL,
    status                  VARCHAR(20) DEFAULT 'OPEN' CHECK(status IN ('OPEN', 'FULL', 'CLOSED')),
    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW(),
    UNIQUE(doctor_id, session_date, session_name)
);

-- =============================================================
-- TABLE: slots
-- Auto-generated time slots inside a session
-- version: optimistic locking for race condition handling
--          when 2 patients book same slot → whoever updates
--          version first wins → other gets next available slot
-- status: AVAILABLE | BOOKED | BLOCKED | CANCELLED
-- BLOCKED = lunch break (1:00pm - 1:30pm)
-- =============================================================
CREATE TABLE IF NOT EXISTS slots (
    slot_id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    doctor_id               UUID NOT NULL REFERENCES doctors(doctor_id),
    session_id              INTEGER NOT NULL REFERENCES sessions(session_id),
    slot_date               DATE NOT NULL,
    start_time              TIME NOT NULL,
    end_time                TIME NOT NULL,
    status                  VARCHAR(20) DEFAULT 'AVAILABLE' CHECK(status IN ('AVAILABLE', 'BOOKED', 'BLOCKED', 'CANCELLED')),
    version                 INTEGER DEFAULT 1,
    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW()
);

-- =============================================================
-- TABLE: appointments
-- Confirmed bookings — slot_id is UNIQUE (no double booking)
-- status: CONFIRMED | CANCELLED | COMPLETED | NO_SHOW
-- =============================================================
CREATE TABLE IF NOT EXISTS appointments (
    appointment_id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slot_id                 UUID UNIQUE NOT NULL REFERENCES slots(slot_id),
    patient_id              UUID NOT NULL REFERENCES patients(patient_id),
    doctor_id               UUID NOT NULL REFERENCES doctors(doctor_id),
    booked_at               TIMESTAMP DEFAULT NOW(),
    status                  VARCHAR(20) DEFAULT 'CONFIRMED' CHECK(status IN ('CONFIRMED', 'CANCELLED', 'COMPLETED', 'NO_SHOW')),
    reminder_24hr_sent      BOOLEAN DEFAULT FALSE,
    reminder_2hr_sent       BOOLEAN DEFAULT FALSE,
    confirmed_at            TIMESTAMP,
    cancelled_at            TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT NOW()
);

-- =============================================================
-- TABLE: waitlist
-- Session-level waitlist (not slot-level)
-- priority 1 = EMERGENCY (must be verified by staff)
-- priority 2 = NORMAL
-- emergency_declared_by FK to staff — patients CANNOT self-declare
-- response_deadline = notified_at + 30 mins, else moves to next
-- status: WAITING | NOTIFIED | CONFIRMED | EXPIRED | CANCELLED
-- =============================================================
CREATE TABLE IF NOT EXISTS waitlist (
    waitlist_id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id              UUID NOT NULL REFERENCES patients(patient_id),
    doctor_id               UUID NOT NULL REFERENCES doctors(doctor_id),
    session_id              INTEGER NOT NULL REFERENCES sessions(session_id),
    waitlist_date           DATE NOT NULL,
    priority                INTEGER DEFAULT 2 CHECK(priority IN (1, 2)),
    is_emergency            BOOLEAN DEFAULT FALSE,
    emergency_declared_by   UUID REFERENCES staff(staff_id),
    emergency_reason        TEXT,
    emergency_verified_at   TIMESTAMP,
    joined_at               TIMESTAMP DEFAULT NOW(),
    status                  VARCHAR(20) DEFAULT 'WAITING' CHECK(status IN ('WAITING', 'NOTIFIED', 'CONFIRMED', 'EXPIRED', 'CANCELLED')),
    notified_at             TIMESTAMP,
    response_deadline       TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT NOW()
);

-- =============================================================
-- TABLE: cancellation_log
-- Every cancellation tracked for risk score computation
-- is_late_cancellation: TRUE if cancelled within 2hrs of slot
-- cancelled_by: PATIENT | STAFF | SYSTEM
-- =============================================================
CREATE TABLE IF NOT EXISTS cancellation_log (
    log_id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    appointment_id          UUID NOT NULL REFERENCES appointments(appointment_id),
    patient_id              UUID NOT NULL REFERENCES patients(patient_id),
    processed_by            UUID REFERENCES staff(staff_id),
    cancelled_at            TIMESTAMP DEFAULT NOW(),
    is_late_cancellation    BOOLEAN DEFAULT FALSE,
    reason                  TEXT,
    cancelled_by            VARCHAR(20) DEFAULT 'PATIENT' CHECK(cancelled_by IN ('PATIENT', 'STAFF', 'SYSTEM'))
);

-- =============================================================
-- TABLE: notification_log
-- Every message sent to patients tracked here
-- type: REMINDER_24HR | REMINDER_2HR | WAITLIST_NOTIFY |
--       BOOKING_CONFIRM | CANCELLATION | WAITLIST_EXPIRED
-- channel: WHATSAPP | SMS | EMAIL
-- response: CONFIRMED | CANCELLED | NO_RESPONSE
-- =============================================================
CREATE TABLE IF NOT EXISTS notification_log (
    notification_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id              UUID NOT NULL REFERENCES patients(patient_id),
    appointment_id          UUID REFERENCES appointments(appointment_id),
    waitlist_id             UUID REFERENCES waitlist(waitlist_id),
    notification_type       VARCHAR(30) NOT NULL CHECK(notification_type IN (
                                'REMINDER_24HR', 'REMINDER_2HR',
                                'WAITLIST_NOTIFY', 'BOOKING_CONFIRM',
                                'CANCELLATION', 'WAITLIST_EXPIRED'
                            )),
    channel                 VARCHAR(20) DEFAULT 'WHATSAPP' CHECK(channel IN ('WHATSAPP', 'SMS', 'EMAIL')),
    sent_at                 TIMESTAMP DEFAULT NOW(),
    responded_at            TIMESTAMP,
    response                VARCHAR(20) CHECK(response IN ('CONFIRMED', 'CANCELLED', 'NO_RESPONSE')),
    is_expired              BOOLEAN DEFAULT FALSE
);

-- =============================================================
-- INDEXES
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_slots_doctor_date    ON slots(doctor_id, slot_date, status);
CREATE INDEX IF NOT EXISTS idx_slots_session        ON slots(session_id, status);
CREATE INDEX IF NOT EXISTS idx_appt_patient         ON appointments(patient_id, status);
CREATE INDEX IF NOT EXISTS idx_appt_doctor          ON appointments(doctor_id, status);
CREATE INDEX IF NOT EXISTS idx_waitlist_session     ON waitlist(session_id, priority, joined_at);
CREATE INDEX IF NOT EXISTS idx_waitlist_patient     ON waitlist(patient_id, status);
CREATE INDEX IF NOT EXISTS idx_notif_patient        ON notification_log(patient_id, sent_at);
CREATE INDEX IF NOT EXISTS idx_cancel_patient       ON cancellation_log(patient_id, cancelled_at);