"""
Seed default user accounts for every role.
Run AFTER seed_data.py (needs staff, patients, and doctors to exist).

Works with both dataset sources:
  • scripts/seed_data.py         (clinic.com emails)
  • app/database/populate_database.py  (dpam.com emails)

Accounts created:
  Role          Username          Password
  ──────────────────────────────────────────
  ADMIN         admin             Admin@123
  RECEPTIONIST  receptionist      Recep@123
  RECEPTIONIST  receptionist2     Recep@123
  DOCTOR        doctor_arun       Doctor@123   (+ others found in DB)
  PATIENT       patient_amit      Patient@123  (+ others found in DB)

Patients log in via Google — these seed accounts are for testing only.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from sqlalchemy import create_engine, text
from app.database.config.settings import DATABASE_URL
from app.modules.auth.service import hash_password

engine = create_engine(DATABASE_URL)


def get_one(conn, sql, params=None):
    row = conn.execute(text(sql), params or {}).mappings().first()
    return dict(row) if row else None


def upsert_user(conn, username, password, role, display_name,
                email=None, staff_id=None, patient_id=None, doctor_id=None):
    existing = get_one(conn, "SELECT user_id FROM users WHERE username=:u", {"u": username})
    if existing:
        print(f"  ⚠  {username} already exists — skipping")
        return False

    conn.execute(text("""
        INSERT INTO users
            (username, password_hash, role, display_name,
             email, auth_provider, staff_id, patient_id, doctor_id)
        VALUES
            (:username, :ph, :role, :dn,
             :email, 'LOCAL', :sid, :pid, :did)
    """), dict(
        username=username,
        ph=hash_password(password),
        role=role,
        dn=display_name,
        email=email,
        sid=staff_id,
        pid=patient_id,
        did=doctor_id,
    ))
    print(f"  ✓  {role:<14}  {username:<20}  → {display_name}")
    return True


def by_email(conn, table, id_col, *emails):
    """Find a row in table whose email matches any of the given candidates."""
    for e in emails:
        row = get_one(conn, f"SELECT {id_col}, full_name, email FROM {table} WHERE email=:e", {"e": e})
        if row:
            return row
    return None


def main():
    print("\n╔══════════════════════════════════╗")
    print("║   DPAM — Seed User Accounts      ║")
    print("╚══════════════════════════════════╝\n")

    created = []

    with engine.begin() as conn:

        # ── Staff ─────────────────────────────────────────────────────
        admin_s  = by_email(conn, "staff", "staff_id",
                            "admin.raj@clinic.com", "anita.sharma@dpam.com")
        recep1_s = by_email(conn, "staff", "staff_id",
                            "anu.recep@clinic.com",  "ravi.kumar@dpam.com")
        recep2_s = by_email(conn, "staff", "staff_id",
                            "dev.recep@clinic.com",  "sonia.iyer@dpam.com")

        if admin_s and upsert_user(
                conn, "admin", "Admin@123", "ADMIN", admin_s["full_name"],
                email=admin_s["email"], staff_id=str(admin_s["staff_id"])):
            created.append(("ADMIN", "admin", "Admin@123"))

        if recep1_s and upsert_user(
                conn, "receptionist", "Recep@123", "RECEPTIONIST", recep1_s["full_name"],
                email=recep1_s["email"], staff_id=str(recep1_s["staff_id"])):
            created.append(("RECEPTIONIST", "receptionist", "Recep@123"))

        if recep2_s and upsert_user(
                conn, "receptionist2", "Recep@123", "RECEPTIONIST", recep2_s["full_name"],
                email=recep2_s["email"], staff_id=str(recep2_s["staff_id"])):
            created.append(("RECEPTIONIST", "receptionist2", "Recep@123"))

        # ── Doctors ───────────────────────────────────────────────────
        doctor_map = [
            ("doctor_arun",   "Dr. Arun Mehta",    "arun.mehta@clinic.com"),
            ("doctor_priya",  "Dr. Priya Sharma",  "priya.sharma@clinic.com"),
            ("doctor_ravi",   "Dr. Ravi Kumar",    "ravi.kumar@clinic.com"),
            ("doctor_sunita", "Dr. Sunita Joshi",  "sunita.joshi@clinic.com"),
            ("doctor_kiran",  "Dr. Kiran Patel",   "kiran.patel@clinic.com"),
            ("doctor_meera",  "Dr. Meera Rao",     "meera.rao@dpam.com"),
            ("doctor_arjun",  "Dr. Arjun Nair",    "arjun.nair@dpam.com"),
            ("doctor_kavya",  "Dr. Kavya Menon",   "kavya.menon@dpam.com"),
        ]
        for uname, display, email in doctor_map:
            doc = by_email(conn, "doctors", "doctor_id", email)
            if doc and upsert_user(
                    conn, uname, "Doctor@123", "DOCTOR", doc["full_name"],
                    email=doc["email"], doctor_id=str(doc["doctor_id"])):
                created.append(("DOCTOR", uname, "Doctor@123"))

        # ── Patients (seed accounts for testing — real patients use Google) ──
        patient_map = [
            ("patient_amit",   "Amit Verma",   "amit.verma@mail.com"),
            ("patient_neha",   "Neha Singh",   "neha.singh@mail.com"),
            ("patient_rahul",  "Rahul Gupta",  "rahul.gupta@mail.com"),
            ("patient_pooja",  "Pooja Patel",  "pooja.patel@mail.com"),
            ("patient_suresh", "Suresh Nair",  "suresh.nair@mail.com"),
            ("patient_kavya",  "Kavya Reddy",  "kavya.reddy@mail.com"),
            ("patient_manoj",  "Manoj Sharma", "manoj.sharma@mail.com"),
        ]
        for uname, display, email in patient_map:
            pat = by_email(conn, "patients", "patient_id", email)
            if pat and upsert_user(
                    conn, uname, "Patient@123", "PATIENT", pat["full_name"],
                    email=pat["email"], patient_id=str(pat["patient_id"])):
                created.append(("PATIENT", uname, "Patient@123"))

    print(f"\n{'─'*52}")
    print("✅  Done!\n")
    if created:
        print(f"  {'Role':<14}  {'Username':<20}  Password")
        print(f"  {'─'*14}  {'─'*20}  ─────────")
        for role, uname, pw in created:
            print(f"  {role:<14}  {uname:<20}  {pw}")
    else:
        print("  All accounts already existed — nothing changed.")
    print()
    print("  Note: real patients should sign in via Google OAuth.")
    print(f"  Google login URL: http://127.0.0.1:8000/auth/google/login")
    print()


if __name__ == "__main__":
    main()
