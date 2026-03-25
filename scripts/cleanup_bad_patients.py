"""
Cleanup script — removes bad/placeholder patient records created by the
old Google OAuth flow (before the proper registration form was added).

Run from the project root:
    python scripts/cleanup_bad_patients.py

What it removes:
  • Any patient whose phone starts with 'G-' (old placeholder format)
  • Any patient whose email is saivivekdailyroutine@gmail.com
  • Their linked user accounts are deleted first (FK constraint)
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from sqlalchemy import create_engine, text
from app.database.config.settings import DATABASE_URL

engine = create_engine(DATABASE_URL)

def main():
    print("\n╔══════════════════════════════════════════╗")
    print("║   DPAM — Cleanup Bad Patient Records     ║")
    print("╚══════════════════════════════════════════╝\n")

    with engine.begin() as conn:
        # Find bad patients
        bad_patients = conn.execute(text("""
            SELECT patient_id, full_name, email, phone
            FROM patients
            WHERE phone LIKE 'G-%'
               OR email = 'saivivekdailyroutine@gmail.com'
               OR full_name = '[REDACTED]'
        """)).mappings().all()

        if not bad_patients:
            print("✅  No bad patient records found. Database is clean.")
            return

        print(f"Found {len(bad_patients)} bad record(s) to remove:\n")
        for p in bad_patients:
            print(f"  • {p['full_name']} | {p['email']} | phone: {p['phone']}")

        print()
        confirm = input("Permanently delete these records? [yes/no]: ").strip().lower()
        if confirm != "yes":
            print("Aborted — nothing deleted.")
            return

        deleted_count = 0
        for p in bad_patients:
            pid = str(p["patient_id"])

            # Delete linked user account first
            u = conn.execute(
                text("DELETE FROM users WHERE patient_id = :pid RETURNING username"),
                {"pid": pid}
            ).mappings().all()
            if u:
                for row in u:
                    print(f"  🗑  Deleted user account: {row['username']}")

            # Delete the patient
            conn.execute(
                text("DELETE FROM patients WHERE patient_id = :pid"),
                {"pid": pid}
            )
            print(f"  🗑  Deleted patient: {p['full_name']} ({p['email']})")
            deleted_count += 1

    print(f"\n✅  Done — {deleted_count} record(s) permanently removed.\n")


if __name__ == "__main__":
    main()
