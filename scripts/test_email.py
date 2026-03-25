"""
Quick test — sends one email of each type to a given address.

Usage (from project root, with venv active):
    python scripts/test_email.py recipient@example.com
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from app.modules.notifications import templates
from app.modules.notifications.email import SMTP_HOST, SMTP_USER, send_email


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_email.py recipient@example.com")
        sys.exit(1)

    to = sys.argv[1]

    # Check config
    if not SMTP_HOST or not SMTP_USER:
        print("\n❌  SMTP not configured.")
        print("    Fill in SMTP_USER and SMTP_PASSWORD in .env first.\n")
        sys.exit(1)

    print(f"\nSending test emails to: {to}")
    print(f"Using SMTP: {SMTP_USER} → {SMTP_HOST}\n")

    sample = dict(
        patient_name="Test Patient",
        doctor_name="Meera Rao",
        specialization="Cardiology",
        date="2026-03-27",
        time_str="09:00",
    )

    tests = [
        ("Booking Confirmation",
         f"[TEST] Appointment Confirmed — Dr. {sample['doctor_name']}",
         templates.booking_confirmation(**sample)),

        ("Cancellation",
         f"[TEST] Appointment Cancelled — Dr. {sample['doctor_name']}",
         templates.cancellation(
             patient_name=sample["patient_name"],
             doctor_name=sample["doctor_name"],
             date=sample["date"],
             time_str=sample["time_str"],
         )),

        ("Waitlist Allocated",
         f"[TEST] 🎉 Waitlist Confirmed — Dr. {sample['doctor_name']}",
         templates.waitlist_allocated(**sample)),

        ("2-Hour Reminder",
         f"[TEST] ⏰ Appointment Reminder — Dr. {sample['doctor_name']}",
         templates.reminder_2hr(**sample)),
    ]

    for name, subject, html in tests:
        ok = send_email(to, subject, html)
        status = "✅ sent" if ok else "❌ failed"
        print(f"  {status}  {name}")

    print()


if __name__ == "__main__":
    main()
