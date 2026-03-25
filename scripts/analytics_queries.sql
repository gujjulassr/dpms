-- =====================================================================
-- DPAM — Analytics & Reporting Queries
-- Run against: psql -U postgres -d dpam
-- =====================================================================


-- ─────────────────────────────────────────────────────────────────
-- SECTION 1: ROW COUNTS (Sanity check after seed)
-- ─────────────────────────────────────────────────────────────────

SELECT 'doctors'          AS tbl, COUNT(*) FROM doctors
UNION ALL
SELECT 'staff',                    COUNT(*) FROM staff
UNION ALL
SELECT 'patients',                 COUNT(*) FROM patients
UNION ALL
SELECT 'sessions',                 COUNT(*) FROM sessions
UNION ALL
SELECT 'slots',                    COUNT(*) FROM slots
UNION ALL
SELECT 'appointments',             COUNT(*) FROM appointments
UNION ALL
SELECT 'waitlist',                 COUNT(*) FROM waitlist
UNION ALL
SELECT 'cancellation_log',         COUNT(*) FROM cancellation_log
UNION ALL
SELECT 'notification_log',         COUNT(*) FROM notification_log
ORDER BY tbl;


-- ─────────────────────────────────────────────────────────────────
-- SECTION 2: APPOINTMENT BREAKDOWN
-- ─────────────────────────────────────────────────────────────────

-- 2a. Appointments by status
SELECT status,
       COUNT(*)                          AS total,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
FROM   appointments
GROUP  BY status
ORDER  BY total DESC;


-- 2b. Appointments per doctor (all time)
SELECT d.full_name,
       d.specialization,
       COUNT(a.appointment_id)           AS total,
       SUM(CASE WHEN a.status='CONFIRMED'  THEN 1 ELSE 0 END) AS confirmed,
       SUM(CASE WHEN a.status='COMPLETED'  THEN 1 ELSE 0 END) AS completed,
       SUM(CASE WHEN a.status='CANCELLED'  THEN 1 ELSE 0 END) AS cancelled,
       SUM(CASE WHEN a.status='NO_SHOW'    THEN 1 ELSE 0 END) AS no_show
FROM   doctors d
LEFT   JOIN appointments a ON a.doctor_id = d.doctor_id
GROUP  BY d.doctor_id, d.full_name, d.specialization
ORDER  BY total DESC;


-- 2c. Appointments per patient (top 10 most active)
SELECT p.full_name,
       p.risk_score,
       COUNT(a.appointment_id)           AS total_bookings,
       SUM(CASE WHEN a.status='CANCELLED' THEN 1 ELSE 0 END) AS cancellations,
       SUM(CASE WHEN a.status='NO_SHOW'   THEN 1 ELSE 0 END) AS no_shows
FROM   patients p
LEFT   JOIN appointments a ON a.patient_id = p.patient_id
GROUP  BY p.patient_id, p.full_name, p.risk_score
ORDER  BY total_bookings DESC
LIMIT  10;


-- 2d. Daily appointment count (last 30 days + next 14 days)
SELECT sl.slot_date,
       TO_CHAR(sl.slot_date, 'Dy')       AS day_of_week,
       COUNT(a.appointment_id)           AS appointments,
       SUM(CASE WHEN a.status='CONFIRMED'  THEN 1 ELSE 0 END) AS confirmed,
       SUM(CASE WHEN a.status='COMPLETED'  THEN 1 ELSE 0 END) AS completed,
       SUM(CASE WHEN a.status='CANCELLED'  THEN 1 ELSE 0 END) AS cancelled,
       SUM(CASE WHEN a.status='NO_SHOW'    THEN 1 ELSE 0 END) AS no_show
FROM   slots sl
JOIN   appointments a ON a.slot_id = sl.slot_id
WHERE  sl.slot_date BETWEEN CURRENT_DATE - INTERVAL '30 days'
                        AND CURRENT_DATE + INTERVAL '14 days'
GROUP  BY sl.slot_date
ORDER  BY sl.slot_date;


-- ─────────────────────────────────────────────────────────────────
-- SECTION 3: BUSIEST DOCTOR
-- ─────────────────────────────────────────────────────────────────

-- 3a. Busiest doctor by confirmed + completed bookings
SELECT d.full_name,
       d.specialization,
       COUNT(a.appointment_id)  AS active_bookings
FROM   doctors d
JOIN   appointments a ON a.doctor_id = d.doctor_id
WHERE  a.status IN ('CONFIRMED','COMPLETED')
GROUP  BY d.doctor_id, d.full_name, d.specialization
ORDER  BY active_bookings DESC
LIMIT  5;


-- 3b. Busiest doctor THIS WEEK
SELECT d.full_name,
       COUNT(a.appointment_id)  AS bookings_this_week
FROM   doctors d
JOIN   appointments a ON a.doctor_id = d.doctor_id
JOIN   slots        sl ON sl.slot_id = a.slot_id
WHERE  sl.slot_date BETWEEN DATE_TRUNC('week', CURRENT_DATE)
                        AND DATE_TRUNC('week', CURRENT_DATE) + INTERVAL '6 days'
  AND  a.status IN ('CONFIRMED','COMPLETED')
GROUP  BY d.doctor_id, d.full_name
ORDER  BY bookings_this_week DESC;


-- ─────────────────────────────────────────────────────────────────
-- SECTION 4: PEAK BOOKING HOURS
-- ─────────────────────────────────────────────────────────────────

-- 4a. Which start_time slots are most booked (peak hours)?
SELECT sl.start_time,
       COUNT(a.appointment_id)  AS bookings
FROM   slots sl
JOIN   appointments a ON a.slot_id = sl.slot_id
WHERE  a.status IN ('CONFIRMED','COMPLETED','NO_SHOW')
GROUP  BY sl.start_time
ORDER  BY bookings DESC
LIMIT  10;


-- 4b. MORNING vs AFTERNOON — which session type gets more bookings?
SELECT se.session_name,
       COUNT(a.appointment_id)                              AS total_bookings,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1)  AS pct
FROM   sessions se
JOIN   slots    sl ON sl.session_id = se.session_id
JOIN   appointments a ON a.slot_id = sl.slot_id
WHERE  a.status IN ('CONFIRMED','COMPLETED','NO_SHOW')
GROUP  BY se.session_name;


-- 4c. Bookings by day of week
SELECT TO_CHAR(sl.slot_date, 'Day')       AS day_name,
       EXTRACT(DOW FROM sl.slot_date)     AS dow_num,
       COUNT(a.appointment_id)            AS bookings
FROM   slots sl
JOIN   appointments a ON a.slot_id = sl.slot_id
WHERE  a.status IN ('CONFIRMED','COMPLETED','NO_SHOW')
GROUP  BY day_name, dow_num
ORDER  BY dow_num;


-- ─────────────────────────────────────────────────────────────────
-- SECTION 5: CANCELLATION ANALYSIS
-- ─────────────────────────────────────────────────────────────────

-- 5a. Overall cancellation rate
SELECT
    COUNT(*)                                             AS total_appointments,
    SUM(CASE WHEN status='CANCELLED' THEN 1 ELSE 0 END)  AS cancelled,
    ROUND(SUM(CASE WHEN status='CANCELLED' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1)
                                                         AS cancellation_rate_pct
FROM appointments;


-- 5b. Late vs early cancellations
SELECT is_late_cancellation,
       cancelled_by,
       COUNT(*)  AS count
FROM   cancellation_log
GROUP  BY is_late_cancellation, cancelled_by
ORDER  BY is_late_cancellation DESC;


-- 5c. Patients with highest cancellation + no-show risk
SELECT p.full_name,
       p.cancellation_count,
       p.late_cancellation_count,
       p.no_show_count,
       p.risk_score,
       CASE
         WHEN p.risk_score >= 0.7 THEN 'HIGH RISK'
         WHEN p.risk_score >= 0.3 THEN 'MEDIUM RISK'
         ELSE 'LOW RISK'
       END AS risk_category
FROM   patients p
ORDER  BY p.risk_score DESC;


-- 5d. Cancellation trend by month
SELECT TO_CHAR(cl.cancelled_at, 'YYYY-MM')  AS month,
       COUNT(*)                              AS cancellations,
       SUM(CASE WHEN cl.is_late_cancellation THEN 1 ELSE 0 END) AS late
FROM   cancellation_log cl
GROUP  BY month
ORDER  BY month;


-- ─────────────────────────────────────────────────────────────────
-- SECTION 6: SLOT UTILISATION
-- ─────────────────────────────────────────────────────────────────

-- 6a. Overall slot utilisation rate
SELECT
    COUNT(*)                                                       AS total_slots,
    SUM(CASE WHEN status='BLOCKED'   THEN 1 ELSE 0 END)            AS blocked_lunch,
    SUM(CASE WHEN status='BOOKED'    THEN 1 ELSE 0 END)            AS booked,
    SUM(CASE WHEN status='AVAILABLE' THEN 1 ELSE 0 END)            AS available,
    SUM(CASE WHEN status='CANCELLED' THEN 1 ELSE 0 END)            AS cancelled,
    ROUND(
      SUM(CASE WHEN status='BOOKED' THEN 1 ELSE 0 END) * 100.0 /
      NULLIF(SUM(CASE WHEN status != 'BLOCKED' THEN 1 ELSE 0 END), 0),
    1)                                                             AS utilisation_pct
FROM slots;


-- 6b. Utilisation per doctor
SELECT d.full_name,
       COUNT(sl.slot_id)                                          AS total_slots,
       SUM(CASE WHEN sl.status='BOOKED'    THEN 1 ELSE 0 END)     AS booked,
       SUM(CASE WHEN sl.status='AVAILABLE' THEN 1 ELSE 0 END)     AS available,
       ROUND(
         SUM(CASE WHEN sl.status='BOOKED' THEN 1 ELSE 0 END) * 100.0 /
         NULLIF(SUM(CASE WHEN sl.status != 'BLOCKED' THEN 1 ELSE 0 END), 0),
       1)                                                         AS utilisation_pct
FROM   doctors d
JOIN   slots sl ON sl.doctor_id = d.doctor_id
GROUP  BY d.doctor_id, d.full_name
ORDER  BY utilisation_pct DESC NULLS LAST;


-- 6c. Slots utilisation by session (past only)
SELECT se.session_name,
       se.session_date,
       d.full_name  AS doctor,
       COUNT(sl.slot_id)                                                  AS total,
       SUM(CASE WHEN sl.status IN ('BOOKED') THEN 1 ELSE 0 END)           AS booked,
       SUM(CASE WHEN sl.status = 'AVAILABLE' THEN 1 ELSE 0 END)           AS available,
       ROUND(SUM(CASE WHEN sl.status='BOOKED' THEN 1 ELSE 0 END) * 100.0
             / NULLIF(SUM(CASE WHEN sl.status!='BLOCKED' THEN 1 ELSE 0 END),0), 1) AS util_pct
FROM   sessions se
JOIN   slots sl ON sl.session_id = se.session_id
JOIN   doctors d ON d.doctor_id = se.doctor_id
WHERE  se.session_date < CURRENT_DATE
GROUP  BY se.session_id, se.session_name, se.session_date, d.full_name
ORDER  BY se.session_date DESC, util_pct DESC
LIMIT  30;


-- ─────────────────────────────────────────────────────────────────
-- SECTION 7: WAITLIST ANALYTICS
-- ─────────────────────────────────────────────────────────────────

-- 7a. Waitlist by status
SELECT status,
       is_emergency,
       COUNT(*)  AS count
FROM   waitlist
GROUP  BY status, is_emergency
ORDER  BY status, is_emergency DESC;


-- 7b. Average wait time in queue (CONFIRMED entries — time from joining to confirmation)
SELECT d.full_name  AS doctor,
       ROUND(AVG(EXTRACT(EPOCH FROM (w.updated_at - w.joined_at)) / 3600), 2)
                    AS avg_wait_hours,
       COUNT(*)     AS confirmed_count
FROM   waitlist w
JOIN   doctors d ON d.doctor_id = w.doctor_id
WHERE  w.status = 'CONFIRMED'
GROUP  BY d.doctor_id, d.full_name
ORDER  BY avg_wait_hours;


-- 7c. Emergency vs normal waitlist requests
SELECT
    SUM(CASE WHEN is_emergency THEN 1 ELSE 0 END)  AS emergency_entries,
    SUM(CASE WHEN NOT is_emergency THEN 1 ELSE 0 END) AS normal_entries,
    COUNT(*)                                        AS total
FROM waitlist;


-- ─────────────────────────────────────────────────────────────────
-- SECTION 8: NOTIFICATION ANALYTICS
-- ─────────────────────────────────────────────────────────────────

-- 8a. Notifications by type and channel
SELECT notification_type,
       channel,
       COUNT(*)  AS sent,
       SUM(CASE WHEN response IS NOT NULL THEN 1 ELSE 0 END)  AS responded,
       SUM(CASE WHEN response='CONFIRMED'    THEN 1 ELSE 0 END) AS confirmed_resp,
       SUM(CASE WHEN response='CANCELLED'    THEN 1 ELSE 0 END) AS cancelled_resp,
       SUM(CASE WHEN response='NO_RESPONSE'  THEN 1 ELSE 0 END) AS no_response
FROM   notification_log
GROUP  BY notification_type, channel
ORDER  BY notification_type, sent DESC;


-- 8b. Response rate by channel
SELECT channel,
       COUNT(*)  AS total_sent,
       SUM(CASE WHEN response IN ('CONFIRMED','CANCELLED') THEN 1 ELSE 0 END) AS responded,
       ROUND(SUM(CASE WHEN response IN ('CONFIRMED','CANCELLED') THEN 1 ELSE 0 END)
             * 100.0 / COUNT(*), 1) AS response_rate_pct
FROM   notification_log
WHERE  notification_type IN ('REMINDER_24HR','REMINDER_2HR')
GROUP  BY channel;


-- ─────────────────────────────────────────────────────────────────
-- SECTION 9: DOCTOR WORKLOAD & SCHEDULE
-- ─────────────────────────────────────────────────────────────────

-- 9a. Doctor sessions this week
SELECT d.full_name,
       d.specialization,
       se.session_date,
       se.session_name,
       se.start_time,
       se.end_time,
       se.status,
       COUNT(sl.slot_id)                                              AS total_slots,
       SUM(CASE WHEN sl.status='BOOKED'    THEN 1 ELSE 0 END)         AS booked,
       SUM(CASE WHEN sl.status='AVAILABLE' THEN 1 ELSE 0 END)         AS available
FROM   sessions se
JOIN   doctors d  ON d.doctor_id = se.doctor_id
JOIN   slots   sl ON sl.session_id = se.session_id
WHERE  se.session_date BETWEEN DATE_TRUNC('week', CURRENT_DATE)
                           AND DATE_TRUNC('week', CURRENT_DATE) + INTERVAL '6 days'
GROUP  BY d.doctor_id, d.full_name, d.specialization,
          se.session_id, se.session_date, se.session_name, se.start_time, se.end_time, se.status
ORDER  BY se.session_date, d.full_name, se.session_name;


-- 9b. Specialization comparison
SELECT d.specialization,
       COUNT(DISTINCT d.doctor_id)           AS doctor_count,
       COUNT(a.appointment_id)               AS total_appointments,
       ROUND(AVG(CASE WHEN a.status IN ('CONFIRMED','COMPLETED')
                      THEN 1.0 ELSE 0 END) * 100, 1) AS booking_rate_pct
FROM   doctors d
LEFT   JOIN appointments a ON a.doctor_id = d.doctor_id
GROUP  BY d.specialization
ORDER  BY total_appointments DESC;


-- ─────────────────────────────────────────────────────────────────
-- SECTION 10: TODAY'S SNAPSHOT
-- ─────────────────────────────────────────────────────────────────

-- 10a. Today's confirmed appointments
SELECT d.full_name      AS doctor,
       p.full_name      AS patient,
       sl.start_time,
       sl.end_time,
       se.session_name,
       a.status,
       a.reminder_24hr_sent,
       a.reminder_2hr_sent
FROM   appointments a
JOIN   slots sl ON sl.slot_id   = a.slot_id
JOIN   sessions se ON se.session_id = sl.session_id
JOIN   doctors  d  ON d.doctor_id  = a.doctor_id
JOIN   patients p  ON p.patient_id = a.patient_id
WHERE  sl.slot_date = CURRENT_DATE
  AND  a.status IN ('CONFIRMED','NO_SHOW')
ORDER  BY sl.start_time;


-- 10b. Today's available slots (still free to book)
SELECT d.full_name  AS doctor,
       se.session_name,
       sl.start_time,
       sl.end_time
FROM   slots sl
JOIN   sessions se ON se.session_id = sl.session_id
JOIN   doctors  d  ON d.doctor_id   = sl.doctor_id
WHERE  sl.slot_date = CURRENT_DATE
  AND  sl.status = 'AVAILABLE'
ORDER  BY d.full_name, sl.start_time;


-- 10c. Today's no-shows (reminder sent but patient didn't come)
SELECT p.full_name  AS patient,
       d.full_name  AS doctor,
       sl.start_time,
       a.appointment_id
FROM   appointments a
JOIN   slots    sl ON sl.slot_id   = a.slot_id
JOIN   patients p  ON p.patient_id = a.patient_id
JOIN   doctors  d  ON d.doctor_id  = a.doctor_id
WHERE  sl.slot_date = CURRENT_DATE
  AND  a.status = 'NO_SHOW';


-- ─────────────────────────────────────────────────────────────────
-- SECTION 11: FULL PATIENT HISTORY (parameterized — replace UUID)
-- ─────────────────────────────────────────────────────────────────

-- 11a. All appointments for a specific patient
-- Replace the email below with any patient from the patients table
SELECT a.appointment_id,
       d.full_name      AS doctor,
       d.specialization,
       sl.slot_date,
       sl.start_time,
       se.session_name,
       a.status,
       a.booked_at,
       a.cancelled_at
FROM   appointments a
JOIN   slots    sl ON sl.slot_id    = a.slot_id
JOIN   sessions se ON se.session_id = sl.session_id
JOIN   doctors  d  ON d.doctor_id   = a.doctor_id
JOIN   patients p  ON p.patient_id  = a.patient_id
WHERE  p.email = 'rahul.gupta@mail.com'   -- ← change to any patient email
ORDER  BY sl.slot_date DESC;


-- ─────────────────────────────────────────────────────────────────
-- SECTION 12: RISK PATIENTS UPCOMING (Flag before appointment)
-- ─────────────────────────────────────────────────────────────────

SELECT p.full_name,
       p.risk_score,
       p.cancellation_count,
       p.late_cancellation_count,
       p.no_show_count,
       d.full_name   AS doctor,
       sl.slot_date,
       sl.start_time,
       a.status
FROM   appointments a
JOIN   patients p  ON p.patient_id = a.patient_id
JOIN   slots    sl ON sl.slot_id   = a.slot_id
JOIN   doctors  d  ON d.doctor_id  = a.doctor_id
WHERE  sl.slot_date >= CURRENT_DATE
  AND  a.status = 'CONFIRMED'
  AND  p.risk_score >= 0.3
ORDER  BY p.risk_score DESC, sl.slot_date;
