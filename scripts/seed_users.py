"""
Seed default user accounts for every role.

Works with either dataset:
1. scripts/seed_data.py
2. app/database/populate_database.py
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


def get_one(conn, sql, params):
    row = conn.execute(text(sql), params).mappings().first()
    return dict(row) if row else None


def get_staff_by_emails(conn, emails):
    for email in emails:
        row = get_one(conn, "SELECT staff_id, full_name FROM staff WHERE email=:e", {"e": email})
        if row:
            return row
    return None


def get_doctor_by_emails(conn, emails):
    for email in emails:
        row = get_one(conn, "SELECT doctor_id, full_name FROM doctors WHERE email=:e", {"e": email})
        if row:
            return row
    return None


def get_patient_by_emails(conn, emails):
    for email in emails:
        row = get_one(conn, "SELECT patient_id, full_name FROM patients WHERE email=:e", {"e": email})
        if row:
            return row
    return None


def upsert_user(conn, username, password, role, display_name,
                staff_id=None, patient_id=None, doctor_id=None):
    existing = get_one(conn, "SELECT user_id FROM users WHERE username=:u", {"u": username})
    if existing:
        print(f"  ⚠  {username} already exists — skipping")
        return False

    conn.execute(text("""
        INSERT INTO users
            (username, password_hash, role, display_name, staff_id, patient_id, doctor_id)
        VALUES
            (:username, :ph, :role, :dn, :sid, :pid, :did)
    """), dict(
        username=username,
        ph=hash_password(password),
        role=role,
        dn=display_name,
        sid=staff_id,
        pid=patient_id,
        did=doctor_id,
    ))
    print(f"  ✓  {role:<14}  {username:<20}  → {display_name}")
    return True


def main():
    print("\n╔══════════════════════════════════╗")
    print("║   DPAM — Seed User Accounts      ║")
    print("╚══════════════════════════════════╝\n")

    created_accounts = []

    with engine.begin() as conn:

        # ── Staff accounts ────────────────────────────────────────────
        admin_s  = get_staff_by_emails(conn, ["admin.raj@clinic.com", "anita.sharma@dpam.com"])
        recep1_s = get_staff_by_emails(conn, ["anu.recep@clinic.com", "ravi.kumar@dpam.com"])
        recep2_s = get_staff_by_emails(conn, ["dev.recep@clinic.com", "sonia.iyer@dpam.com"])

        if admin_s:
            if upsert_user(conn, "admin", "Admin@123", "ADMIN", admin_s["full_name"],
                           staff_id=str(admin_s["staff_id"])):
                created_accounts.append(("ADMIN", "admin", "Admin@123"))
        if recep1_s:
            if upsert_user(conn, "receptionist", "Recep@123", "RECEPTIONIST", recep1_s["full_name"],
                           staff_id=str(recep1_s["staff_id"])):
                created_accounts.append(("RECEPTIONIST", "receptionist", "Recep@123"))
        if recep2_s:
            if upsert_user(conn, "receptionist2", "Recep@123", "RECEPTIONIST", recep2_s["full_name"],
                           staff_id=str(recep2_s["staff_id"])):
                created_accounts.append(("RECEPTIONIST", "receptionist2", "Recep@123"))

        # ── Doctor accounts ───────────────────────────────────────────
        doctor_map = [
            (["arun.mehta@clinic.com"], "doctor_arun",   "Dr. Arun Mehta"),
            (["priya.sharma@clinic.com"], "doctor_priya",  "Dr. Priya Sharma"),
            (["ravi.kumar@clinic.com"],   "doctor_ravi",   "Dr. Ravi Kumar"),
            (["sunita.joshi@clinic.com"], "doctor_sunita", "Dr. Sunita Joshi"),
            (["kiran.patel@clinic.com"],  "doctor_kiran",  "Dr. Kiran Patel"),
            (["meera.rao@dpam.com"],      "doctor_meera",  "Dr. Meera Rao"),
            (["arjun.nair@dpam.com"],     "doctor_arjun",  "Dr. Arjun Nair"),
            (["kavya.menon@dpam.com"],    "doctor_kavya",  "Dr. Kavya Menon"),
        ]
        for emails, uname, display in doctor_map:
            doc = get_doctor_by_emails(conn, emails)
            if doc:
                if upsert_user(conn, uname, "Doctor@123", "DOCTOR", display,
                               doctor_id=str(doc["doctor_id"])):
                    created_accounts.append(("DOCTOR", uname, "Doctor@123"))

        # ── Patient accounts ──────────────────────────────────────────
        patient_map = [
            (["amit.verma@mail.com"],      "patient_amit",   "Amit Verma"),
            (["neha.singh@mail.com"],      "patient_neha",   "Neha Singh"),
            (["rahul.gupta@mail.com"],     "patient_rahul",  "Rahul Gupta"),
            (["pooja.patel@mail.com"],     "patient_pooja",  "Pooja Patel"),
            (["suresh.nair@mail.com"],     "patient_suresh", "Suresh Nair"),
            (["kavya.reddy@mail.com"],     "patient_kavya",  "Kavya Reddy"),
            (["manoj.sharma@mail.com"],    "patient_manoj",  "Manoj Sharma"),
            (["priya.singh@gmail.com"],    "patient_priya",  "Priya Singh"),
            (["rahul.verma@gmail.com"],    "patient_rahulv", "Rahul Verma"),
            (["neha.patel@gmail.com"],     "patient_neha_p", "Neha Patel"),
            (["aisha.khan@gmail.com"],     "patient_aisha",  "Aisha Khan"),
        ]
        for emails, uname, display in patient_map:
            pat = get_patient_by_emails(conn, emails)
            if pat:
                if upsert_user(conn, uname, "Patient@123", "PATIENT", display,
                               patient_id=str(pat["patient_id"])):
                    created_accounts.append(("PATIENT", uname, "Patient@123"))

    print(f"\n{'─'*50}")
    print("✅  Done! Login credentials summary:\n")
    if created_accounts:
        for role, username, password in created_accounts:
            print(f"  {role:<13} →  {username:<15} /  {password}")
    else:
        print("  No new accounts were created. Existing users were kept.")
    print()


if __name__ == "__main__":
    main()
