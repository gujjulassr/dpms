-- =============================================================
-- DPMS — Consolidated schema (all entity IDs are SERIAL integers)
-- =============================================================

-- ─── patients ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS patients (
    patient_id              SERIAL PRIMARY KEY,
    full_name               VARCHAR(100) NOT NULL,
    email                   VARCHAR(150) UNIQUE NOT NULL,
    phone                   VARCHAR(15) UNIQUE NOT NULL,
    date_of_birth           DATE,
    cancellation_count      INTEGER DEFAULT 0,
    late_cancellation_count INTEGER DEFAULT 0,
    no_show_count           INTEGER DEFAULT 0,
    risk_score              NUMERIC(4,2) DEFAULT 0.0,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ─── doctors ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS doctors (
    doctor_id               SERIAL PRIMARY KEY,
    full_name               VARCHAR(100) NOT NULL,
    specialization          VARCHAR(100) NOT NULL,
    email                   VARCHAR(150) UNIQUE NOT NULL,
    phone                   VARCHAR(15) UNIQUE NOT NULL,
    slot_duration_mins      INTEGER DEFAULT 15,
    max_patients_per_day    INTEGER DEFAULT 40,
    is_active               BOOLEAN DEFAULT TRUE,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ─── staff ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS staff (
    staff_id                SERIAL PRIMARY KEY,
    full_name               VARCHAR(100) NOT NULL,
    email                   VARCHAR(150) UNIQUE NOT NULL,
    phone                   VARCHAR(15) UNIQUE NOT NULL,
    role                    VARCHAR(20) NOT NULL CHECK(role IN ('RECEPTIONIST','DOCTOR','ADMIN')),
    is_active               BOOLEAN DEFAULT TRUE,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ─── users (auth) ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    user_id         SERIAL PRIMARY KEY,
    username        VARCHAR(50) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(20) NOT NULL CHECK(role IN ('ADMIN','RECEPTIONIST','DOCTOR','PATIENT')),
    display_name    VARCHAR(100) NOT NULL,
    staff_id        INTEGER REFERENCES staff(staff_id)      ON DELETE SET NULL,
    patient_id      INTEGER REFERENCES patients(patient_id)  ON DELETE SET NULL,
    doctor_id       INTEGER REFERENCES doctors(doctor_id)    ON DELETE SET NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    email           VARCHAR(150),
    auth_provider   VARCHAR(20) NOT NULL DEFAULT 'LOCAL'
                        CHECK(auth_provider IN ('LOCAL','GOOGLE')),
    google_sub      VARCHAR(100),
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_users_username   ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role       ON users(role);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub
    ON users(google_sub) WHERE google_sub IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_email
    ON users(email) WHERE email IS NOT NULL;

-- ─── sessions ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sessions (
    session_id      SERIAL PRIMARY KEY,
    doctor_id       INTEGER NOT NULL REFERENCES doctors(doctor_id),
    session_date    DATE NOT NULL,
    session_name    VARCHAR(20) NOT NULL CHECK(session_name IN ('MORNING','AFTERNOON')),
    start_time      TIME NOT NULL,
    end_time        TIME NOT NULL,
    status          VARCHAR(20) DEFAULT 'OPEN' CHECK(status IN ('OPEN','FULL','CLOSED')),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(doctor_id, session_date, session_name)
);

-- ─── appointments ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS appointments (
    appointment_id      SERIAL PRIMARY KEY,
    session_id          INTEGER NOT NULL REFERENCES sessions(session_id),
    patient_id          INTEGER NOT NULL REFERENCES patients(patient_id)  ON DELETE CASCADE,
    doctor_id           INTEGER NOT NULL REFERENCES doctors(doctor_id),
    appointment_date    DATE    NOT NULL,
    start_time          TIME    NOT NULL,
    end_time            TIME    NOT NULL,
    booked_at           TIMESTAMPTZ DEFAULT NOW(),
    status              VARCHAR(20) DEFAULT 'CONFIRMED'
                            CHECK(status IN ('CONFIRMED','CANCELLED','COMPLETED','NO_SHOW')),
    reminder_24hr_sent  BOOLEAN DEFAULT FALSE,
    reminder_2hr_sent   BOOLEAN DEFAULT FALSE,
    review_sent         BOOLEAN NOT NULL DEFAULT FALSE,
    confirmed_at        TIMESTAMPTZ,
    cancelled_at        TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_appt_no_double_book
    ON appointments (doctor_id, appointment_date, start_time)
    WHERE status = 'CONFIRMED';
CREATE INDEX IF NOT EXISTS idx_appt_session_status
    ON appointments (session_id, status);
CREATE INDEX IF NOT EXISTS idx_appt_doctor_date_status
    ON appointments (doctor_id, appointment_date, status);
CREATE INDEX IF NOT EXISTS idx_appointments_patient_status
    ON appointments(patient_id, status);

-- ─── waitlist ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS waitlist (
    waitlist_id             SERIAL PRIMARY KEY,
    patient_id              INTEGER NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    doctor_id               INTEGER NOT NULL REFERENCES doctors(doctor_id),
    session_id              INTEGER NOT NULL REFERENCES sessions(session_id),
    waitlist_date           DATE,
    priority                INTEGER NOT NULL DEFAULT 2 CHECK(priority IN (1, 2)),
    is_emergency            BOOLEAN DEFAULT FALSE,
    emergency_declared_by   INTEGER REFERENCES staff(staff_id) ON DELETE SET NULL,
    emergency_reason        TEXT,
    emergency_verified_at   TIMESTAMPTZ,
    status                  VARCHAR(20) DEFAULT 'WAITING'
                                CHECK(status IN ('WAITING','NOTIFIED','CONFIRMED','EXPIRED','CANCELLED')),
    joined_at               TIMESTAMPTZ DEFAULT NOW(),
    notified_at             TIMESTAMPTZ,
    response_deadline       TIMESTAMPTZ,
    responded_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_waitlist_session_status ON waitlist(session_id, status);
CREATE INDEX IF NOT EXISTS idx_waitlist_patient        ON waitlist(patient_id);

-- ─── cancellation_log ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cancellation_log (
    log_id                  SERIAL PRIMARY KEY,
    appointment_id          INTEGER NOT NULL REFERENCES appointments(appointment_id) ON DELETE CASCADE,
    patient_id              INTEGER NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    processed_by            INTEGER REFERENCES staff(staff_id) ON DELETE SET NULL,
    is_late_cancellation    BOOLEAN DEFAULT FALSE,
    reason                  TEXT,
    cancelled_by            VARCHAR(20) NOT NULL DEFAULT 'PATIENT'
                                CHECK(cancelled_by IN ('PATIENT','RECEPTIONIST','DOCTOR','ADMIN','SYSTEM','STAFF')),
    cancelled_at            TIMESTAMPTZ DEFAULT NOW()
);

-- ─── notification_log ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notification_log (
    log_id              SERIAL PRIMARY KEY,
    patient_id          INTEGER NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    appointment_id      INTEGER REFERENCES appointments(appointment_id) ON DELETE CASCADE,
    waitlist_id         INTEGER REFERENCES waitlist(waitlist_id) ON DELETE CASCADE,
    notification_type   VARCHAR(30) NOT NULL
                            CHECK(notification_type IN (
                                'BOOKING_CONFIRM','CANCELLATION','WAITLIST_NOTIFY',
                                'REMINDER_24HR','REMINDER_2HR','REVIEW_REQUEST',
                                'WAITLIST_EXPIRED'
                            )),
    channel             VARCHAR(20) DEFAULT 'EMAIL',
    sent_at             TIMESTAMPTZ DEFAULT NOW(),
    responded_at        TIMESTAMPTZ,
    response            VARCHAR(20),
    is_expired          BOOLEAN DEFAULT FALSE,
    response_status     VARCHAR(20) DEFAULT 'SENT'
                            CHECK(response_status IN ('SENT','DELIVERED','FAILED','BOUNCED'))
);
CREATE INDEX IF NOT EXISTS idx_notification_patient ON notification_log(patient_id);

-- ─── doctor_ratings ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS doctor_ratings (
    rating_id       SERIAL PRIMARY KEY,
    appointment_id  INTEGER NOT NULL REFERENCES appointments(appointment_id) ON DELETE CASCADE,
    patient_id      INTEGER NOT NULL REFERENCES patients(patient_id)         ON DELETE CASCADE,
    doctor_id       INTEGER NOT NULL REFERENCES doctors(doctor_id)           ON DELETE CASCADE,
    stars           SMALLINT NOT NULL CHECK (stars BETWEEN 1 AND 5),
    comment         TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (appointment_id)
);
CREATE INDEX IF NOT EXISTS idx_ratings_doctor  ON doctor_ratings(doctor_id);
CREATE INDEX IF NOT EXISTS idx_ratings_patient ON doctor_ratings(patient_id);
