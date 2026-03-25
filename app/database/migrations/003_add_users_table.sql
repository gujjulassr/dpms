-- Migration 003: Add users table for authentication
-- Links each login account to a staff, patient, or doctor record

CREATE TABLE IF NOT EXISTS users (
    user_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username        VARCHAR(50) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(20) NOT NULL CHECK(role IN ('ADMIN','RECEPTIONIST','DOCTOR','PATIENT')),
    display_name    VARCHAR(100) NOT NULL,
    -- one of these will be set depending on role
    staff_id        UUID REFERENCES staff(staff_id)     ON DELETE SET NULL,
    patient_id      UUID REFERENCES patients(patient_id) ON DELETE SET NULL,
    doctor_id       UUID REFERENCES doctors(doctor_id)   ON DELETE SET NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    last_login_at   TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role     ON users(role);
