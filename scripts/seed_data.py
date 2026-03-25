"""
DPAM — Comprehensive Seed Script
=================================
Covers every table, every status variant, and enough variation
for meaningful analytics queries.

Data overview:
  Doctors       : 6  (5 active, 1 inactive) — 4 specializations
  Staff         : 4  (1 ADMIN, 2 RECEPTIONIST, 1 DOCTOR-staff)
  Patients      : 20 (mix of demographics, risk levels)
  Sessions      : ~60 (30 days × 2 sessions × up to 6 doctors, sampled)
  Slots         : auto-generated per session (~10-12 per session)
  Appointments  : ~120 (CONFIRMED, CANCELLED, COMPLETED, NO_SHOW)
  Cancellations : ~25 (mix of early / late, patient / staff)
  Waitlist      : ~15 (WAITING, CONFIRMED, EXPIRED, CANCELLED, NOTIFIED)
  Notifications : ~50 (all types and channels)

Date range: past 30 days → today → next 14 days
"""

import os
import sys
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path
from uuid import uuid4

# ── path setup so imports resolve ────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from sqlalchemy import create_engine, text
from app.database.config.settings import DATABASE_URL

engine = create_engine(DATABASE_URL)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def run(conn, sql, params=None):
    return conn.execute(text(sql), params or {})

def fetchone(conn, sql, params=None):
    return run(conn, sql, params).mappings().first()

def fetchall(conn, sql, params=None):
    return run(conn, sql, params).mappings().all()

TODAY = date.today()

def days_ago(n): return TODAY - timedelta(days=n)
def days_from_now(n): return TODAY + timedelta(days=n)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 0 — Wipe existing seed data (safe re-run)
# ─────────────────────────────────────────────────────────────────────────────
def clear_all(conn):
    print("  Clearing existing data...")
    tables = [
        "notification_log", "cancellation_log", "waitlist",
        "appointments", "slots", "sessions",
        "patients", "staff", "doctors",
    ]
    for t in tables:
        conn.execute(text(f"DELETE FROM {t}"))
    print("  ✓ Cleared")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Doctors (6)
# ─────────────────────────────────────────────────────────────────────────────
DOCTORS_DATA = [
    # name, specialization, email, phone, slot_mins, max_per_day, is_active
    ("Dr. Arun Mehta",      "Cardiology",       "arun.mehta@clinic.com",     "9100000001", 15, 40, True),
    ("Dr. Priya Sharma",    "Neurology",        "priya.sharma@clinic.com",   "9100000002", 20, 24, True),
    ("Dr. Ravi Kumar",      "Orthopedics",      "ravi.kumar@clinic.com",     "9100000003", 30, 16, True),
    ("Dr. Sunita Joshi",    "General Medicine", "sunita.joshi@clinic.com",   "9100000004", 15, 40, True),
    ("Dr. Kiran Patel",     "Dermatology",      "kiran.patel@clinic.com",    "9100000005", 15, 40, True),
    ("Dr. Mohan Rao",       "Cardiology",       "mohan.rao@clinic.com",      "9100000006", 15, 40, False),  # inactive
]

def seed_doctors(conn):
    print("  Seeding doctors...")
    ids = []
    for (name, spec, email, phone, slot_mins, max_pd, active) in DOCTORS_DATA:
        row = fetchone(conn,
            """INSERT INTO doctors
               (full_name, specialization, email, phone, slot_duration_mins, max_patients_per_day, is_active)
               VALUES (:name,:spec,:email,:phone,:slot_mins,:max_pd,:active)
               RETURNING doctor_id""",
            dict(name=name, spec=spec, email=email, phone=phone,
                 slot_mins=slot_mins, max_pd=max_pd, active=active))
        ids.append(str(row["doctor_id"]))
    print(f"  ✓ {len(ids)} doctors")
    return ids   # [arun, priya, ravi, sunita, kiran, mohan(inactive)]


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Staff (4)
# ─────────────────────────────────────────────────────────────────────────────
STAFF_DATA = [
    ("Admin Raj",        "admin.raj@clinic.com",    "9200000001", "ADMIN"),
    ("Receptionist Anu", "anu.recep@clinic.com",    "9200000002", "RECEPTIONIST"),
    ("Receptionist Dev", "dev.recep@clinic.com",    "9200000003", "RECEPTIONIST"),
    ("Staff Dr. Nita",   "nita.staff@clinic.com",   "9200000004", "DOCTOR"),
]

def seed_staff(conn):
    print("  Seeding staff...")
    ids = []
    for (name, email, phone, role) in STAFF_DATA:
        row = fetchone(conn,
            """INSERT INTO staff (full_name, email, phone, role)
               VALUES (:name,:email,:phone,:role) RETURNING staff_id""",
            dict(name=name, email=email, phone=phone, role=role))
        ids.append(str(row["staff_id"]))
    print(f"  ✓ {len(ids)} staff")
    return ids   # [admin, recep1, recep2, doctor-staff]


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Patients (20)
# ─────────────────────────────────────────────────────────────────────────────
PATIENTS_DATA = [
    # name, email, phone, dob, cancel_count, late_cancel, noshow, risk
    ("Amit Verma",      "amit.verma@mail.com",      "8000000001", "1985-03-12", 0, 0, 0, 0.00),
    ("Neha Singh",      "neha.singh@mail.com",      "8000000002", "1992-07-04", 1, 0, 0, 0.10),
    ("Rahul Gupta",     "rahul.gupta@mail.com",     "8000000003", "1978-11-20", 3, 1, 1, 0.45),
    ("Pooja Patel",     "pooja.patel@mail.com",     "8000000004", "2000-01-15", 0, 0, 0, 0.00),
    ("Suresh Nair",     "suresh.nair@mail.com",     "8000000005", "1965-09-30", 2, 0, 0, 0.20),
    ("Kavya Reddy",     "kavya.reddy@mail.com",     "8000000006", "1990-05-22", 0, 0, 1, 0.15),
    ("Arjun Bose",      "arjun.bose@mail.com",      "8000000007", "1983-12-08", 1, 1, 0, 0.30),
    ("Divya Iyer",      "divya.iyer@mail.com",      "8000000008", "1995-04-17", 0, 0, 0, 0.00),
    ("Manoj Sharma",    "manoj.sharma@mail.com",    "8000000009", "1970-08-25", 4, 2, 2, 0.75),
    ("Pritha Das",      "pritha.das@mail.com",      "8000000010", "1988-02-14", 0, 0, 0, 0.00),
    ("Vikram Jain",     "vikram.jain@mail.com",     "8000000011", "1975-06-03", 1, 0, 1, 0.25),
    ("Anita Pillai",    "anita.pillai@mail.com",    "8000000012", "1993-10-11", 0, 0, 0, 0.00),
    ("Sanjay Khanna",   "sanjay.khanna@mail.com",   "8000000013", "1960-03-28", 3, 3, 0, 0.60),
    ("Ritu Agarwal",    "ritu.agarwal@mail.com",    "8000000014", "1998-09-16", 0, 0, 0, 0.00),
    ("Dinesh Tiwari",   "dinesh.tiwari@mail.com",   "8000000015", "1955-12-01", 2, 1, 0, 0.35),
    ("Shalini Menon",   "shalini.menon@mail.com",   "8000000016", "1987-07-19", 0, 0, 0, 0.00),
    ("Karan Malhotra",  "karan.malhotra@mail.com",  "8000000017", "2002-04-05", 1, 0, 0, 0.10),
    ("Radha Krishnan",  "radha.krishnan@mail.com",  "8000000018", "1972-11-14", 0, 0, 2, 0.20),
    ("Tushar Wagh",     "tushar.wagh@mail.com",     "8000000019", "1980-01-30", 5, 3, 1, 0.90),
    ("Meera Chatterjee","meera.chat@mail.com",      "8000000020", "1969-08-07", 0, 0, 0, 0.00),
]

def seed_patients(conn):
    print("  Seeding patients...")
    ids = []
    for (name, email, phone, dob, cc, lc, ns, risk) in PATIENTS_DATA:
        row = fetchone(conn,
            """INSERT INTO patients
               (full_name, email, phone, date_of_birth,
                cancellation_count, late_cancellation_count, no_show_count, risk_score)
               VALUES (:name,:email,:phone,:dob,:cc,:lc,:ns,:risk)
               RETURNING patient_id""",
            dict(name=name, email=email, phone=phone, dob=dob,
                 cc=cc, lc=lc, ns=ns, risk=risk))
        ids.append(str(row["patient_id"]))
    print(f"  ✓ {len(ids)} patients")
    return ids


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Sessions + Slots
# ─────────────────────────────────────────────────────────────────────────────
# Sessions per doctor per day (only active doctors = first 5)
# Range: 30 days ago → 14 days from now
# Not every doctor works every day → realistic gaps

SESSION_CONFIG = {
    "MORNING":   (time(9,  0), time(13, 0)),
    "AFTERNOON": (time(14, 0), time(18, 0)),
}

LUNCH_START = time(13, 0)
LUNCH_END   = time(13, 30)

# Which days each doctor works (0=Mon ... 6=Sun)
DOCTOR_WORKDAYS = [
    {0,1,2,3,4},       # arun  — Mon-Fri
    {0,1,2,3,4},       # priya — Mon-Fri
    {0,1,3,4},         # ravi  — Mon,Tue,Thu,Fri
    {0,1,2,3,4,5},     # sunita— Mon-Sat
    {1,3,5},           # kiran — Tue,Thu,Sat
]

def generate_slots_for_session(conn, doctor_id, session_id, session_date, start_t, end_t, slot_mins):
    """Mirrors the app's _generate_slots logic."""
    slots = []
    current = datetime.combine(session_date, start_t)
    end_dt  = datetime.combine(session_date, end_t)
    lunch_start_dt = datetime.combine(session_date, LUNCH_START)
    lunch_end_dt   = datetime.combine(session_date, LUNCH_END)
    step = timedelta(minutes=slot_mins)

    while current + step <= end_dt:
        slot_end = current + step
        overlaps = current < lunch_end_dt and slot_end > lunch_start_dt
        status = "BLOCKED" if overlaps else "AVAILABLE"

        row = fetchone(conn,
            """INSERT INTO slots (doctor_id, session_id, slot_date, start_time, end_time, status)
               VALUES (:did,:sid,:sdate,:st,:et,:status) RETURNING slot_id, start_time, status""",
            dict(did=doctor_id, sid=session_id, sdate=session_date,
                 st=current.time(), et=slot_end.time(), status=status))
        slots.append(dict(row))
        current = slot_end
    return slots


def seed_sessions_and_slots(conn, doctor_ids):
    """Returns: {doctor_id: [{session_id, session_date, session_name, slots:[...]}]}"""
    print("  Seeding sessions & slots...")
    active_doctors = doctor_ids[:5]   # skip inactive mohan
    date_range = [TODAY - timedelta(days=d) for d in range(30, -1, -1)] + \
                 [TODAY + timedelta(days=d) for d in range(1, 15)]

    # {doctor_id: [session_records]}
    sessions_map = {d: [] for d in active_doctors}

    total_sessions = 0
    total_slots = 0

    for i, doctor_id in enumerate(active_doctors):
        workdays = DOCTOR_WORKDAYS[i]
        doctor_row = fetchone(conn, "SELECT slot_duration_mins FROM doctors WHERE doctor_id=:id",
                              {"id": doctor_id})
        slot_mins = doctor_row["slot_duration_mins"]

        for d in date_range:
            if d.weekday() not in workdays:
                continue
            for sname, (st, et) in SESSION_CONFIG.items():
                # Check not already existing
                existing = fetchone(conn,
                    "SELECT session_id FROM sessions WHERE doctor_id=:did AND session_date=:sd AND session_name=:sn",
                    dict(did=doctor_id, sd=d, sn=sname))
                if existing:
                    continue

                sess_row = fetchone(conn,
                    """INSERT INTO sessions (doctor_id, session_date, session_name, start_time, end_time, status)
                       VALUES (:did,:sd,:sn,:st,:et,'OPEN') RETURNING session_id""",
                    dict(did=doctor_id, sd=d, sn=sname, st=st, et=et))
                session_id = sess_row["session_id"]
                slots = generate_slots_for_session(conn, doctor_id, session_id, d, st, et, slot_mins)
                sessions_map[doctor_id].append({
                    "session_id": session_id,
                    "session_date": d,
                    "session_name": sname,
                    "slots": slots,
                })
                total_sessions += 1
                total_slots += len(slots)

    print(f"  ✓ {total_sessions} sessions, {total_slots} slots")
    return sessions_map


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — Appointments (rich mix of statuses)
# ─────────────────────────────────────────────────────────────────────────────

def pick_available_slots(sessions_map, doctor_id, n, date_filter=None):
    """Pick n AVAILABLE slots for a doctor (optionally filtered by date range)."""
    result = []
    for sess in sessions_map.get(doctor_id, []):
        if date_filter and not date_filter(sess["session_date"]):
            continue
        for sl in sess["slots"]:
            if sl["status"] == "AVAILABLE":
                result.append((sess["session_id"], sess["session_date"],
                                sess["session_name"], sl["slot_id"], sl["start_time"]))
    random.shuffle(result)
    return result[:n]


def book_slot(conn, slot_id, patient_id, doctor_id, status="CONFIRMED",
              booked_at=None, cancelled_at=None, confirmed_at=None,
              r24=False, r2=False):
    appt_row = fetchone(conn,
        """INSERT INTO appointments
           (slot_id, patient_id, doctor_id, status,
            reminder_24hr_sent, reminder_2hr_sent,
            confirmed_at, cancelled_at, booked_at)
           VALUES (:sid,:pid,:did,:status,:r24,:r2,:cat2,:cat,:bat)
           RETURNING appointment_id""",
        dict(sid=slot_id, pid=patient_id, did=doctor_id, status=status,
             r24=r24, r2=r2,
             cat2=confirmed_at,
             cat=cancelled_at,
             bat=booked_at or datetime.utcnow()))
    return str(appt_row["appointment_id"])


def mark_slot(conn, slot_id, status):
    conn.execute(text("UPDATE slots SET status=:s WHERE slot_id=:id"),
                 {"s": status, "id": slot_id})


def seed_appointments(conn, doctor_ids, patient_ids, sessions_map, staff_ids):
    print("  Seeding appointments...")
    active_docs = doctor_ids[:5]
    appt_records = []   # for cancellation log later

    # Helper: past date filter
    past   = lambda d: d < TODAY
    future = lambda d: d > TODAY
    today_ = lambda d: d == TODAY

    # ── A. COMPLETED appointments (past, 3-4 per doctor) ─────────────────────
    for did in active_docs:
        slots = pick_available_slots(sessions_map, did, 6, past)
        patients = random.sample(patient_ids, min(6, len(patient_ids)))
        for (sess_id, sdate, sname, slot_id, st), pid in zip(slots, patients):
            booked_dt = datetime.combine(sdate, time(8, 0)) - timedelta(days=1)
            appt_id = book_slot(conn, slot_id, pid, did,
                                status="COMPLETED",
                                booked_at=booked_dt,
                                confirmed_at=booked_dt,
                                r24=True, r2=True)
            mark_slot(conn, slot_id, "BOOKED")
            appt_records.append(dict(appt_id=appt_id, slot_id=slot_id, pid=pid,
                                     did=did, sdate=sdate, st=st,
                                     status="COMPLETED", sess_id=sess_id))

    # ── B. CONFIRMED upcoming (today + future) ────────────────────────────────
    for did in active_docs:
        slots = pick_available_slots(sessions_map, did, 8,
                                     lambda d: d >= TODAY)
        patients = random.sample(patient_ids, min(8, len(patient_ids)))
        for (sess_id, sdate, sname, slot_id, st), pid in zip(slots, patients):
            booked_dt = datetime.utcnow() - timedelta(hours=random.randint(1, 72))
            appt_id = book_slot(conn, slot_id, pid, did,
                                status="CONFIRMED",
                                booked_at=booked_dt,
                                confirmed_at=booked_dt,
                                r24=(sdate < TODAY + timedelta(days=1)))
            mark_slot(conn, slot_id, "BOOKED")
            appt_records.append(dict(appt_id=appt_id, slot_id=slot_id, pid=pid,
                                     did=did, sdate=sdate, st=st,
                                     status="CONFIRMED", sess_id=sess_id))

    # ── C. CANCELLED past appointments (early cancellations — valid) ──────────
    cancel_early_records = []
    for did in active_docs[:3]:
        slots = pick_available_slots(sessions_map, did, 4, past)
        patients = random.sample(patient_ids, min(4, len(patient_ids)))
        for (sess_id, sdate, sname, slot_id, st), pid in zip(slots, patients):
            booked_dt = datetime.combine(sdate, time(8,0)) - timedelta(days=2)
            cancel_dt = datetime.combine(sdate, time(8,0)) - timedelta(hours=6)
            appt_id = book_slot(conn, slot_id, pid, did,
                                status="CANCELLED",
                                booked_at=booked_dt,
                                confirmed_at=booked_dt,
                                cancelled_at=cancel_dt)
            # slot stays AVAILABLE after cancel
            appt_records.append(dict(appt_id=appt_id, slot_id=slot_id, pid=pid,
                                     did=did, sdate=sdate, st=st,
                                     status="CANCELLED", late=False, sess_id=sess_id))
            cancel_early_records.append(appt_records[-1])

    # ── D. CANCELLED — LATE cancellations (within 2hrs) ──────────────────────
    cancel_late_records = []
    for did in active_docs[2:5]:
        slots = pick_available_slots(sessions_map, did, 3, past)
        patients = random.sample(patient_ids, min(3, len(patient_ids)))
        for (sess_id, sdate, sname, slot_id, st), pid in zip(slots, patients):
            raw_st = str(st)
            parts = raw_st.split(":")
            slot_time_val = time(int(parts[0]), int(parts[1]))
            slot_dt = datetime.combine(sdate, slot_time_val)
            cancel_dt = slot_dt - timedelta(minutes=45)   # 45 mins before = LATE
            booked_dt = slot_dt - timedelta(days=1)
            appt_id = book_slot(conn, slot_id, pid, did,
                                status="CANCELLED",
                                booked_at=booked_dt,
                                confirmed_at=booked_dt,
                                cancelled_at=cancel_dt)
            appt_records.append(dict(appt_id=appt_id, slot_id=slot_id, pid=pid,
                                     did=did, sdate=sdate, st=st,
                                     status="CANCELLED", late=True, sess_id=sess_id))
            cancel_late_records.append(appt_records[-1])

    # ── E. NO_SHOW past appointments ──────────────────────────────────────────
    for did in active_docs[1:4]:
        slots = pick_available_slots(sessions_map, did, 3, past)
        patients = random.sample(patient_ids, min(3, len(patient_ids)))
        for (sess_id, sdate, sname, slot_id, st), pid in zip(slots, patients):
            booked_dt = datetime.combine(sdate, time(8,0)) - timedelta(days=1)
            appt_id = book_slot(conn, slot_id, pid, did,
                                status="NO_SHOW",
                                booked_at=booked_dt,
                                confirmed_at=booked_dt,
                                r24=True, r2=True)
            mark_slot(conn, slot_id, "BOOKED")
            appt_records.append(dict(appt_id=appt_id, slot_id=slot_id, pid=pid,
                                     did=did, sdate=sdate, st=st,
                                     status="NO_SHOW", sess_id=sess_id))

    print(f"  ✓ {len(appt_records)} appointments")
    return appt_records, cancel_early_records, cancel_late_records


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — Cancellation Logs
# ─────────────────────────────────────────────────────────────────────────────

CANCEL_REASONS = [
    "Patient requested cancellation due to travel",
    "Emergency at home",
    "Feeling better, no longer required",
    "Doctor unavailable — rescheduled by staff",
    "Transportation issue",
    "Work conflict",
    None,
]

def seed_cancellation_logs(conn, cancel_early, cancel_late, staff_ids):
    print("  Seeding cancellation logs...")
    count = 0

    for rec in cancel_early:
        by = random.choice(["PATIENT", "STAFF"])
        conn.execute(text(
            """INSERT INTO cancellation_log
               (appointment_id, patient_id, processed_by, cancelled_at,
                is_late_cancellation, reason, cancelled_by)
               VALUES (:aid,:pid,:proc,:cat,:late,:reason,:by)"""),
            dict(aid=rec["appt_id"], pid=rec["pid"],
                 proc=staff_ids[1] if by == "STAFF" else None,
                 cat=datetime.utcnow() - timedelta(days=random.randint(1,20)),
                 late=False,
                 reason=random.choice(CANCEL_REASONS),
                 by=by))
        count += 1

    for rec in cancel_late:
        conn.execute(text(
            """INSERT INTO cancellation_log
               (appointment_id, patient_id, processed_by, cancelled_at,
                is_late_cancellation, reason, cancelled_by)
               VALUES (:aid,:pid,:proc,:cat,:late,:reason,:by)"""),
            dict(aid=rec["appt_id"], pid=rec["pid"],
                 proc=staff_ids[2],
                 cat=datetime.utcnow() - timedelta(days=random.randint(1,10)),
                 late=True,
                 reason=random.choice(CANCEL_REASONS),
                 by="PATIENT"))
        count += 1

    print(f"  ✓ {count} cancellation log entries")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 7 — Waitlist (all status variants)
# ─────────────────────────────────────────────────────────────────────────────

def seed_waitlist(conn, doctor_ids, patient_ids, sessions_map, staff_ids):
    print("  Seeding waitlist...")
    active_docs = doctor_ids[:5]
    count = 0

    # Find fully-booked sessions (sessions where most slots are BOOKED)
    # We'll just pick recent future sessions and use them for waitlist entries
    waitlist_entries = []

    for did in active_docs:
        future_sessions = [
            s for s in sessions_map.get(did, [])
            if s["session_date"] >= TODAY
        ]
        if not future_sessions:
            continue

        # Pick 2-3 sessions per doctor
        chosen = random.sample(future_sessions, min(3, len(future_sessions)))
        used_patients = set()

        for sess in chosen:
            sess_id = sess["session_id"]
            sess_date = sess["session_date"]

            # Pick patients not already used in this session
            avail_patients = [p for p in patient_ids if p not in used_patients]
            if not avail_patients:
                break

            # --- WAITING (normal priority) ---
            pid = random.choice(avail_patients)
            used_patients.add(pid)
            conn.execute(text(
                """INSERT INTO waitlist
                   (patient_id, doctor_id, session_id, waitlist_date, priority, is_emergency, status)
                   VALUES (:pid,:did,:sid,:wd,2,false,'WAITING')"""),
                dict(pid=pid, did=did, sid=sess_id, wd=sess_date))
            count += 1

            avail_patients = [p for p in avail_patients if p != pid]
            if not avail_patients:
                continue

            # --- WAITING (emergency priority — declared by staff) ---
            pid2 = random.choice(avail_patients)
            used_patients.add(pid2)
            conn.execute(text(
                """INSERT INTO waitlist
                   (patient_id, doctor_id, session_id, waitlist_date,
                    priority, is_emergency, emergency_declared_by,
                    emergency_reason, emergency_verified_at, status)
                   VALUES (:pid,:did,:sid,:wd,1,true,:edb,:reason,:eva,'WAITING')"""),
                dict(pid=pid2, did=did, sid=sess_id, wd=sess_date,
                     edb=staff_ids[1],
                     reason="Chest pain, needs urgent consultation",
                     eva=datetime.utcnow() - timedelta(hours=1)))
            count += 1

    # --- CONFIRMED waitlist entry (auto-allocated) ---
    if active_docs and patient_ids:
        did = active_docs[0]
        future_s = [s for s in sessions_map.get(did, []) if s["session_date"] >= TODAY]
        if future_s:
            sess = future_s[0]
            pid = patient_ids[5]   # Kavya
            conn.execute(text(
                """INSERT INTO waitlist
                   (patient_id, doctor_id, session_id, waitlist_date, priority,
                    is_emergency, status, notified_at, response_deadline)
                   VALUES (:pid,:did,:sid,:wd,2,false,'CONFIRMED',
                           NOW() - INTERVAL '10 minutes',
                           NOW() + INTERVAL '20 minutes')"""),
                dict(pid=pid, did=did, sid=sess["session_id"], wd=sess["session_date"]))
            count += 1

    # --- EXPIRED ---
    if len(active_docs) > 1 and len(patient_ids) > 7:
        did = active_docs[1]
        past_s = [s for s in sessions_map.get(did, []) if s["session_date"] < TODAY]
        if past_s:
            sess = past_s[0]
            pid = patient_ids[7]
            conn.execute(text(
                """INSERT INTO waitlist
                   (patient_id, doctor_id, session_id, waitlist_date, priority,
                    is_emergency, status, notified_at, response_deadline)
                   VALUES (:pid,:did,:sid,:wd,2,false,'EXPIRED',
                           NOW() - INTERVAL '2 hours',
                           NOW() - INTERVAL '1 hour 30 minutes')"""),
                dict(pid=pid, did=did, sid=sess["session_id"], wd=sess["session_date"]))
            count += 1

    # --- CANCELLED (patient left waitlist) ---
    if len(active_docs) > 2 and len(patient_ids) > 9:
        did = active_docs[2]
        any_s = [s for s in sessions_map.get(did, []) if s["session_date"] >= TODAY]
        if any_s:
            sess = any_s[0]
            pid = patient_ids[9]
            conn.execute(text(
                """INSERT INTO waitlist
                   (patient_id, doctor_id, session_id, waitlist_date, priority,
                    is_emergency, status)
                   VALUES (:pid,:did,:sid,:wd,2,false,'CANCELLED')"""),
                dict(pid=pid, did=did, sid=sess["session_id"], wd=sess["session_date"]))
            count += 1

    # --- NOTIFIED (waiting for patient response) ---
    if len(active_docs) > 3 and len(patient_ids) > 11:
        did = active_docs[3]
        any_s = [s for s in sessions_map.get(did, []) if s["session_date"] >= TODAY]
        if any_s:
            sess = any_s[0]
            pid = patient_ids[11]
            conn.execute(text(
                """INSERT INTO waitlist
                   (patient_id, doctor_id, session_id, waitlist_date, priority,
                    is_emergency, status, notified_at, response_deadline)
                   VALUES (:pid,:did,:sid,:wd,2,false,'NOTIFIED',
                           NOW() - INTERVAL '5 minutes',
                           NOW() + INTERVAL '25 minutes')"""),
                dict(pid=pid, did=did, sid=sess["session_id"], wd=sess["session_date"]))
            count += 1

    print(f"  ✓ {count} waitlist entries")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 8 — Notification Log (all types + channels)
# ─────────────────────────────────────────────────────────────────────────────

NOTIF_TYPES = [
    "REMINDER_24HR", "REMINDER_2HR", "WAITLIST_NOTIFY",
    "BOOKING_CONFIRM", "CANCELLATION", "WAITLIST_EXPIRED",
]
CHANNELS = ["WHATSAPP", "SMS", "EMAIL"]
RESPONSES = ["CONFIRMED", "CANCELLED", "NO_RESPONSE", None]

def seed_notifications(conn, appt_records, patient_ids):
    print("  Seeding notification logs...")
    count = 0

    # Booking confirmation for every CONFIRMED appointment
    confirmed_appts = [a for a in appt_records if a["status"] == "CONFIRMED"]
    for rec in confirmed_appts[:15]:
        conn.execute(text(
            """INSERT INTO notification_log
               (patient_id, appointment_id, notification_type, channel,
                sent_at, responded_at, response, is_expired)
               VALUES (:pid,:aid,:ntype,:ch,:sat,:rat,:resp,:exp)"""),
            dict(pid=rec["pid"], aid=rec["appt_id"],
                 ntype="BOOKING_CONFIRM",
                 ch=random.choice(CHANNELS),
                 sat=datetime.utcnow() - timedelta(hours=random.randint(1, 48)),
                 rat=None, resp=None, exp=False))
        count += 1

    # 24hr reminders for completed appointments
    completed_appts = [a for a in appt_records if a["status"] == "COMPLETED"]
    for rec in completed_appts:
        conn.execute(text(
            """INSERT INTO notification_log
               (patient_id, appointment_id, notification_type, channel,
                sent_at, responded_at, response, is_expired)
               VALUES (:pid,:aid,'REMINDER_24HR',:ch,:sat,:rat,:resp,false)"""),
            dict(pid=rec["pid"], aid=rec["appt_id"],
                 ch=random.choice(CHANNELS),
                 sat=datetime.combine(rec["sdate"], time(9,0)) - timedelta(days=1),
                 rat=datetime.combine(rec["sdate"], time(9,30)) - timedelta(days=1),
                 resp="CONFIRMED"))
        count += 1

    # 2hr reminders for completed + no-show
    noshow_appts = [a for a in appt_records if a["status"] == "NO_SHOW"]
    for rec in completed_appts[:8] + noshow_appts:
        parts = str(rec["st"]).split(":")
        slot_time_val = time(int(parts[0]), int(parts[1]))
        slot_dt = datetime.combine(rec["sdate"], slot_time_val)
        conn.execute(text(
            """INSERT INTO notification_log
               (patient_id, appointment_id, notification_type, channel,
                sent_at, responded_at, response, is_expired)
               VALUES (:pid,:aid,'REMINDER_2HR',:ch,:sat,:rat,:resp,false)"""),
            dict(pid=rec["pid"], aid=rec["appt_id"],
                 ch=random.choice(CHANNELS),
                 sat=slot_dt - timedelta(hours=2),
                 rat=slot_dt - timedelta(hours=1, minutes=45) if rec["status"]=="COMPLETED" else None,
                 resp="CONFIRMED" if rec["status"]=="COMPLETED" else "NO_RESPONSE"))
        count += 1

    # Cancellation notifications
    cancelled_appts = [a for a in appt_records if a["status"] == "CANCELLED"]
    for rec in cancelled_appts:
        conn.execute(text(
            """INSERT INTO notification_log
               (patient_id, appointment_id, notification_type, channel,
                sent_at, is_expired)
               VALUES (:pid,:aid,'CANCELLATION',:ch,NOW(),false)"""),
            dict(pid=rec["pid"], aid=rec["appt_id"],
                 ch=random.choice(CHANNELS)))
        count += 1

    # Waitlist notify (2 samples using random patients)
    for pid in random.sample(patient_ids, 3):
        conn.execute(text(
            """INSERT INTO notification_log
               (patient_id, notification_type, channel, sent_at,
                responded_at, response, is_expired)
               VALUES (:pid,'WAITLIST_NOTIFY',:ch,:sat,:rat,:resp,false)"""),
            dict(pid=pid,
                 ch=random.choice(CHANNELS),
                 sat=datetime.utcnow() - timedelta(minutes=random.randint(5,60)),
                 rat=datetime.utcnow() - timedelta(minutes=random.randint(1,4)),
                 resp=random.choice(["CONFIRMED","CANCELLED","NO_RESPONSE"])))
        count += 1

    # Waitlist expired
    for pid in random.sample(patient_ids, 2):
        conn.execute(text(
            """INSERT INTO notification_log
               (patient_id, notification_type, channel, sent_at,
                response, is_expired)
               VALUES (:pid,'WAITLIST_EXPIRED',:ch,:sat,'NO_RESPONSE',true)"""),
            dict(pid=pid,
                 ch=random.choice(CHANNELS),
                 sat=datetime.utcnow() - timedelta(hours=random.randint(2, 24))))
        count += 1

    print(f"  ✓ {count} notification log entries")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    random.seed(42)   # reproducible
    print("\n╔══════════════════════════════════════╗")
    print("║   DPAM — Comprehensive Seed Script   ║")
    print("╚══════════════════════════════════════╝\n")

    with engine.begin() as conn:
        clear_all(conn)
        print()

        print("[1/7] Doctors & Staff")
        doctor_ids = seed_doctors(conn)
        staff_ids  = seed_staff(conn)
        print()

        print("[2/7] Patients")
        patient_ids = seed_patients(conn)
        print()

        print("[3/7] Sessions & Slots")
        sessions_map = seed_sessions_and_slots(conn, doctor_ids)
        print()

        print("[4/7] Appointments")
        appt_records, cancel_early, cancel_late = seed_appointments(
            conn, doctor_ids, patient_ids, sessions_map, staff_ids)
        print()

        print("[5/7] Cancellation Logs")
        seed_cancellation_logs(conn, cancel_early, cancel_late, staff_ids)
        print()

        print("[6/7] Waitlist")
        seed_waitlist(conn, doctor_ids, patient_ids, sessions_map, staff_ids)
        print()

        print("[7/7] Notification Logs")
        seed_notifications(conn, appt_records, patient_ids)
        print()

    print("─" * 42)
    print("✅  Seed complete!\n")
    print("Quick counts (run these in psql):")
    print("  SELECT COUNT(*) FROM doctors;")
    print("  SELECT COUNT(*) FROM patients;")
    print("  SELECT COUNT(*) FROM sessions;")
    print("  SELECT COUNT(*) FROM slots;")
    print("  SELECT COUNT(*) FROM appointments;")
    print("  SELECT status, COUNT(*) FROM appointments GROUP BY status;")
    print("  SELECT COUNT(*) FROM waitlist;")
    print("  SELECT COUNT(*) FROM cancellation_log;")
    print("  SELECT COUNT(*) FROM notification_log;")
    print()


if __name__ == "__main__":
    main()
