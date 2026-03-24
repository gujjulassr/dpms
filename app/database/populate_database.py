from datetime import date, datetime, time, timedelta

from sqlalchemy import text

from app.database.connection.database import get_session


def populate_database() -> None:
    db = get_session()
    today = date.today()
    now = datetime.now()

    staff_rows = [
        {"full_name": "Anita Sharma", "email": "anita.sharma@dpam.com", "phone": "9000000001", "role": "ADMIN"},
        {"full_name": "Ravi Kumar", "email": "ravi.kumar@dpam.com", "phone": "9000000002", "role": "RECEPTIONIST"},
        {"full_name": "Sonia Iyer", "email": "sonia.iyer@dpam.com", "phone": "9000000003", "role": "RECEPTIONIST"},
        {"full_name": "Dr. Meera Rao", "email": "meera.rao.staff@dpam.com", "phone": "9000000004", "role": "DOCTOR"},
        {"full_name": "Dr. Arjun Nair", "email": "arjun.nair.staff@dpam.com", "phone": "9000000005", "role": "DOCTOR"},
    ]

    doctor_rows = [
        {
            "full_name": "Dr. Meera Rao",
            "specialization": "Cardiology",
            "email": "meera.rao@dpam.com",
            "phone": "9111111111",
            "slot_duration_mins": 15,
            "max_patients_per_day": 24,
        },
        {
            "full_name": "Dr. Arjun Nair",
            "specialization": "Dermatology",
            "email": "arjun.nair@dpam.com",
            "phone": "9222222222",
            "slot_duration_mins": 20,
            "max_patients_per_day": 20,
        },
        {
            "full_name": "Dr. Kavya Menon",
            "specialization": "Pediatrics",
            "email": "kavya.menon@dpam.com",
            "phone": "9333333339",
            "slot_duration_mins": 30,
            "max_patients_per_day": 16,
        },
    ]

    patient_rows = [
        {
            "full_name": "Priya Singh",
            "email": "priya.singh@gmail.com",
            "phone": "9333333331",
            "date_of_birth": date(1998, 4, 14),
            "cancellation_count": 0,
            "late_cancellation_count": 0,
            "no_show_count": 0,
            "risk_score": 0.00,
        },
        {
            "full_name": "Rahul Verma",
            "email": "rahul.verma@gmail.com",
            "phone": "9333333332",
            "date_of_birth": date(1989, 9, 2),
            "cancellation_count": 1,
            "late_cancellation_count": 0,
            "no_show_count": 0,
            "risk_score": 1.20,
        },
        {
            "full_name": "Neha Patel",
            "email": "neha.patel@gmail.com",
            "phone": "9333333333",
            "date_of_birth": date(1995, 1, 27),
            "cancellation_count": 2,
            "late_cancellation_count": 1,
            "no_show_count": 0,
            "risk_score": 2.40,
        },
        {
            "full_name": "Vikram Das",
            "email": "vikram.das@gmail.com",
            "phone": "9333333334",
            "date_of_birth": date(1978, 6, 8),
            "cancellation_count": 0,
            "late_cancellation_count": 0,
            "no_show_count": 1,
            "risk_score": 1.50,
        },
        {
            "full_name": "Aisha Khan",
            "email": "aisha.khan@gmail.com",
            "phone": "9333333335",
            "date_of_birth": date(2001, 11, 3),
            "cancellation_count": 0,
            "late_cancellation_count": 0,
            "no_show_count": 0,
            "risk_score": 0.20,
        },
        {
            "full_name": "Rohan Gupta",
            "email": "rohan.gupta@gmail.com",
            "phone": "9333333336",
            "date_of_birth": date(1984, 2, 19),
            "cancellation_count": 3,
            "late_cancellation_count": 2,
            "no_show_count": 1,
            "risk_score": 3.60,
        },
        {
            "full_name": "Sneha Reddy",
            "email": "sneha.reddy@gmail.com",
            "phone": "9333333337",
            "date_of_birth": date(1992, 7, 25),
            "cancellation_count": 1,
            "late_cancellation_count": 1,
            "no_show_count": 0,
            "risk_score": 1.90,
        },
        {
            "full_name": "Manoj Pillai",
            "email": "manoj.pillai@gmail.com",
            "phone": "9333333338",
            "date_of_birth": date(1970, 12, 10),
            "cancellation_count": 0,
            "late_cancellation_count": 0,
            "no_show_count": 0,
            "risk_score": 0.10,
        },
    ]

    try:
        staff_ids = {}
        for row in staff_rows:
            result = db.execute(
                text(
                    """
                    INSERT INTO staff (full_name, email, phone, role)
                    VALUES (:full_name, :email, :phone, :role)
                    RETURNING staff_id
                    """
                ),
                row,
            )
            staff_ids[row["email"]] = result.scalar_one()

        doctor_ids = {}
        for row in doctor_rows:
            result = db.execute(
                text(
                    """
                    INSERT INTO doctors (
                        full_name,
                        specialization,
                        email,
                        phone,
                        slot_duration_mins,
                        max_patients_per_day
                    )
                    VALUES (
                        :full_name,
                        :specialization,
                        :email,
                        :phone,
                        :slot_duration_mins,
                        :max_patients_per_day
                    )
                    RETURNING doctor_id
                    """
                ),
                row,
            )
            doctor_ids[row["email"]] = result.scalar_one()

        patient_ids = {}
        for row in patient_rows:
            result = db.execute(
                text(
                    """
                    INSERT INTO patients (
                        full_name,
                        email,
                        phone,
                        date_of_birth,
                        cancellation_count,
                        late_cancellation_count,
                        no_show_count,
                        risk_score
                    )
                    VALUES (
                        :full_name,
                        :email,
                        :phone,
                        :date_of_birth,
                        :cancellation_count,
                        :late_cancellation_count,
                        :no_show_count,
                        :risk_score
                    )
                    RETURNING patient_id
                    """
                ),
                row,
            )
            patient_ids[row["email"]] = result.scalar_one()

        session_rows = [
            {
                "key": "meera_today_morning",
                "doctor_id": doctor_ids["meera.rao@dpam.com"],
                "session_date": today,
                "session_name": "MORNING",
                "start_time": time(9, 0),
                "end_time": time(12, 0),
                "status": "FULL",
            },
            {
                "key": "meera_today_afternoon",
                "doctor_id": doctor_ids["meera.rao@dpam.com"],
                "session_date": today,
                "session_name": "AFTERNOON",
                "start_time": time(14, 0),
                "end_time": time(17, 0),
                "status": "OPEN",
            },
            {
                "key": "arjun_today_morning",
                "doctor_id": doctor_ids["arjun.nair@dpam.com"],
                "session_date": today,
                "session_name": "MORNING",
                "start_time": time(10, 0),
                "end_time": time(13, 0),
                "status": "OPEN",
            },
            {
                "key": "arjun_today_afternoon",
                "doctor_id": doctor_ids["arjun.nair@dpam.com"],
                "session_date": today,
                "session_name": "AFTERNOON",
                "start_time": time(15, 0),
                "end_time": time(18, 0),
                "status": "CLOSED",
            },
            {
                "key": "kavya_tomorrow_morning",
                "doctor_id": doctor_ids["kavya.menon@dpam.com"],
                "session_date": today + timedelta(days=1),
                "session_name": "MORNING",
                "start_time": time(9, 30),
                "end_time": time(12, 30),
                "status": "OPEN",
            },
            {
                "key": "kavya_tomorrow_afternoon",
                "doctor_id": doctor_ids["kavya.menon@dpam.com"],
                "session_date": today + timedelta(days=1),
                "session_name": "AFTERNOON",
                "start_time": time(14, 0),
                "end_time": time(16, 0),
                "status": "OPEN",
            },
        ]

        session_ids = {}
        for row in session_rows:
            result = db.execute(
                text(
                    """
                    INSERT INTO sessions (
                        doctor_id,
                        session_date,
                        session_name,
                        start_time,
                        end_time,
                        status
                    )
                    VALUES (
                        :doctor_id,
                        :session_date,
                        :session_name,
                        :start_time,
                        :end_time,
                        :status
                    )
                    RETURNING session_id
                    """
                ),
                row,
            )
            session_ids[row["key"]] = result.scalar_one()

        slot_rows = [
            {
                "key": "slot_1",
                "doctor_id": doctor_ids["meera.rao@dpam.com"],
                "session_id": session_ids["meera_today_morning"],
                "slot_date": today,
                "start_time": time(9, 0),
                "end_time": time(9, 15),
                "status": "BOOKED",
            },
            {
                "key": "slot_2",
                "doctor_id": doctor_ids["meera.rao@dpam.com"],
                "session_id": session_ids["meera_today_morning"],
                "slot_date": today,
                "start_time": time(9, 15),
                "end_time": time(9, 30),
                "status": "BOOKED",
            },
            {
                "key": "slot_3",
                "doctor_id": doctor_ids["meera.rao@dpam.com"],
                "session_id": session_ids["meera_today_morning"],
                "slot_date": today,
                "start_time": time(9, 30),
                "end_time": time(9, 45),
                "status": "CANCELLED",
            },
            {
                "key": "slot_4",
                "doctor_id": doctor_ids["meera.rao@dpam.com"],
                "session_id": session_ids["meera_today_afternoon"],
                "slot_date": today,
                "start_time": time(14, 0),
                "end_time": time(14, 15),
                "status": "AVAILABLE",
            },
            {
                "key": "slot_5",
                "doctor_id": doctor_ids["meera.rao@dpam.com"],
                "session_id": session_ids["meera_today_afternoon"],
                "slot_date": today,
                "start_time": time(14, 15),
                "end_time": time(14, 30),
                "status": "BLOCKED",
            },
            {
                "key": "slot_6",
                "doctor_id": doctor_ids["arjun.nair@dpam.com"],
                "session_id": session_ids["arjun_today_morning"],
                "slot_date": today,
                "start_time": time(10, 0),
                "end_time": time(10, 20),
                "status": "BOOKED",
            },
            {
                "key": "slot_7",
                "doctor_id": doctor_ids["arjun.nair@dpam.com"],
                "session_id": session_ids["arjun_today_morning"],
                "slot_date": today,
                "start_time": time(10, 20),
                "end_time": time(10, 40),
                "status": "BOOKED",
            },
            {
                "key": "slot_8",
                "doctor_id": doctor_ids["arjun.nair@dpam.com"],
                "session_id": session_ids["arjun_today_afternoon"],
                "slot_date": today,
                "start_time": time(15, 0),
                "end_time": time(15, 20),
                "status": "BOOKED",
            },
            {
                "key": "slot_9",
                "doctor_id": doctor_ids["kavya.menon@dpam.com"],
                "session_id": session_ids["kavya_tomorrow_morning"],
                "slot_date": today + timedelta(days=1),
                "start_time": time(9, 30),
                "end_time": time(10, 0),
                "status": "AVAILABLE",
            },
            {
                "key": "slot_10",
                "doctor_id": doctor_ids["kavya.menon@dpam.com"],
                "session_id": session_ids["kavya_tomorrow_morning"],
                "slot_date": today + timedelta(days=1),
                "start_time": time(10, 0),
                "end_time": time(10, 30),
                "status": "AVAILABLE",
            },
            {
                "key": "slot_11",
                "doctor_id": doctor_ids["kavya.menon@dpam.com"],
                "session_id": session_ids["kavya_tomorrow_afternoon"],
                "slot_date": today + timedelta(days=1),
                "start_time": time(14, 0),
                "end_time": time(14, 30),
                "status": "BOOKED",
            },
            {
                "key": "slot_12",
                "doctor_id": doctor_ids["kavya.menon@dpam.com"],
                "session_id": session_ids["kavya_tomorrow_afternoon"],
                "slot_date": today + timedelta(days=1),
                "start_time": time(14, 30),
                "end_time": time(15, 0),
                "status": "AVAILABLE",
            },
        ]

        slot_ids = {}
        for row in slot_rows:
            result = db.execute(
                text(
                    """
                    INSERT INTO slots (
                        doctor_id,
                        session_id,
                        slot_date,
                        start_time,
                        end_time,
                        status
                    )
                    VALUES (
                        :doctor_id,
                        :session_id,
                        :slot_date,
                        :start_time,
                        :end_time,
                        :status
                    )
                    RETURNING slot_id
                    """
                ),
                row,
            )
            slot_ids[row["key"]] = result.scalar_one()

        appointment_rows = [
            {
                "key": "appt_1",
                "slot_id": slot_ids["slot_1"],
                "patient_id": patient_ids["priya.singh@gmail.com"],
                "doctor_id": doctor_ids["meera.rao@dpam.com"],
                "status": "CONFIRMED",
                "reminder_24hr_sent": True,
                "reminder_2hr_sent": False,
                "confirmed_at": now - timedelta(hours=2),
                "cancelled_at": None,
            },
            {
                "key": "appt_2",
                "slot_id": slot_ids["slot_2"],
                "patient_id": patient_ids["rahul.verma@gmail.com"],
                "doctor_id": doctor_ids["meera.rao@dpam.com"],
                "status": "COMPLETED",
                "reminder_24hr_sent": True,
                "reminder_2hr_sent": True,
                "confirmed_at": now - timedelta(days=1),
                "cancelled_at": None,
            },
            {
                "key": "appt_3",
                "slot_id": slot_ids["slot_3"],
                "patient_id": patient_ids["rohan.gupta@gmail.com"],
                "doctor_id": doctor_ids["meera.rao@dpam.com"],
                "status": "CANCELLED",
                "reminder_24hr_sent": True,
                "reminder_2hr_sent": True,
                "confirmed_at": now - timedelta(days=2),
                "cancelled_at": now - timedelta(hours=1),
            },
            {
                "key": "appt_4",
                "slot_id": slot_ids["slot_6"],
                "patient_id": patient_ids["vikram.das@gmail.com"],
                "doctor_id": doctor_ids["arjun.nair@dpam.com"],
                "status": "NO_SHOW",
                "reminder_24hr_sent": True,
                "reminder_2hr_sent": True,
                "confirmed_at": now - timedelta(days=1),
                "cancelled_at": None,
            },
            {
                "key": "appt_5",
                "slot_id": slot_ids["slot_7"],
                "patient_id": patient_ids["sneha.reddy@gmail.com"],
                "doctor_id": doctor_ids["arjun.nair@dpam.com"],
                "status": "CONFIRMED",
                "reminder_24hr_sent": False,
                "reminder_2hr_sent": False,
                "confirmed_at": now - timedelta(minutes=30),
                "cancelled_at": None,
            },
            {
                "key": "appt_6",
                "slot_id": slot_ids["slot_8"],
                "patient_id": patient_ids["manoj.pillai@gmail.com"],
                "doctor_id": doctor_ids["arjun.nair@dpam.com"],
                "status": "CONFIRMED",
                "reminder_24hr_sent": True,
                "reminder_2hr_sent": True,
                "confirmed_at": now - timedelta(hours=3),
                "cancelled_at": None,
            },
            {
                "key": "appt_7",
                "slot_id": slot_ids["slot_11"],
                "patient_id": patient_ids["aisha.khan@gmail.com"],
                "doctor_id": doctor_ids["kavya.menon@dpam.com"],
                "status": "CONFIRMED",
                "reminder_24hr_sent": False,
                "reminder_2hr_sent": False,
                "confirmed_at": now,
                "cancelled_at": None,
            },
        ]

        appointment_ids = {}
        for row in appointment_rows:
            result = db.execute(
                text(
                    """
                    INSERT INTO appointments (
                        slot_id,
                        patient_id,
                        doctor_id,
                        status,
                        reminder_24hr_sent,
                        reminder_2hr_sent,
                        confirmed_at,
                        cancelled_at
                    )
                    VALUES (
                        :slot_id,
                        :patient_id,
                        :doctor_id,
                        :status,
                        :reminder_24hr_sent,
                        :reminder_2hr_sent,
                        :confirmed_at,
                        :cancelled_at
                    )
                    RETURNING appointment_id
                    """
                ),
                row,
            )
            appointment_ids[row["key"]] = result.scalar_one()

        waitlist_rows = [
            {
                "patient_id": patient_ids["neha.patel@gmail.com"],
                "doctor_id": doctor_ids["meera.rao@dpam.com"],
                "session_id": session_ids["meera_today_morning"],
                "waitlist_date": today,
                "priority": 1,
                "is_emergency": True,
                "emergency_declared_by": staff_ids["ravi.kumar@dpam.com"],
                "emergency_reason": "Chest pain and urgent review needed",
                "emergency_verified_at": now - timedelta(minutes=25),
                "status": "WAITING",
                "notified_at": None,
                "response_deadline": None,
            },
            {
                "patient_id": patient_ids["aisha.khan@gmail.com"],
                "doctor_id": doctor_ids["arjun.nair@dpam.com"],
                "session_id": session_ids["arjun_today_morning"],
                "waitlist_date": today,
                "priority": 2,
                "is_emergency": False,
                "emergency_declared_by": None,
                "emergency_reason": None,
                "emergency_verified_at": None,
                "status": "NOTIFIED",
                "notified_at": now - timedelta(minutes=10),
                "response_deadline": now + timedelta(minutes=20),
            },
            {
                "patient_id": patient_ids["manoj.pillai@gmail.com"],
                "doctor_id": doctor_ids["kavya.menon@dpam.com"],
                "session_id": session_ids["kavya_tomorrow_morning"],
                "waitlist_date": today + timedelta(days=1),
                "priority": 2,
                "is_emergency": False,
                "emergency_declared_by": None,
                "emergency_reason": None,
                "emergency_verified_at": None,
                "status": "CONFIRMED",
                "notified_at": now - timedelta(hours=1),
                "response_deadline": now + timedelta(minutes=5),
            },
            {
                "patient_id": patient_ids["rahul.verma@gmail.com"],
                "doctor_id": doctor_ids["meera.rao@dpam.com"],
                "session_id": session_ids["meera_today_afternoon"],
                "waitlist_date": today,
                "priority": 2,
                "is_emergency": False,
                "emergency_declared_by": None,
                "emergency_reason": None,
                "emergency_verified_at": None,
                "status": "EXPIRED",
                "notified_at": now - timedelta(hours=2),
                "response_deadline": now - timedelta(hours=1, minutes=30),
            },
            {
                "patient_id": patient_ids["sneha.reddy@gmail.com"],
                "doctor_id": doctor_ids["kavya.menon@dpam.com"],
                "session_id": session_ids["kavya_tomorrow_afternoon"],
                "waitlist_date": today + timedelta(days=1),
                "priority": 2,
                "is_emergency": False,
                "emergency_declared_by": None,
                "emergency_reason": None,
                "emergency_verified_at": None,
                "status": "CANCELLED",
                "notified_at": now - timedelta(days=1),
                "response_deadline": now - timedelta(days=1) + timedelta(minutes=30),
            },
        ]

        waitlist_ids = []
        for row in waitlist_rows:
            result = db.execute(
                text(
                    """
                    INSERT INTO waitlist (
                        patient_id,
                        doctor_id,
                        session_id,
                        waitlist_date,
                        priority,
                        is_emergency,
                        emergency_declared_by,
                        emergency_reason,
                        emergency_verified_at,
                        status,
                        notified_at,
                        response_deadline
                    )
                    VALUES (
                        :patient_id,
                        :doctor_id,
                        :session_id,
                        :waitlist_date,
                        :priority,
                        :is_emergency,
                        :emergency_declared_by,
                        :emergency_reason,
                        :emergency_verified_at,
                        :status,
                        :notified_at,
                        :response_deadline
                    )
                    RETURNING waitlist_id
                    """
                ),
                row,
            )
            waitlist_ids.append(result.scalar_one())

        db.execute(
            text(
                """
                INSERT INTO notification_log (
                    patient_id,
                    appointment_id,
                    waitlist_id,
                    notification_type,
                    channel,
                    sent_at,
                    responded_at,
                    response,
                    is_expired
                )
                VALUES (
                    :patient_id,
                    :appointment_id,
                    :waitlist_id,
                    :notification_type,
                    :channel,
                    :sent_at,
                    :responded_at,
                    :response,
                    :is_expired
                )
                """
            ),
            [
                {
                    "patient_id": patient_ids["priya.singh@gmail.com"],
                    "appointment_id": appointment_ids["appt_1"],
                    "waitlist_id": None,
                    "notification_type": "BOOKING_CONFIRM",
                    "channel": "EMAIL",
                    "sent_at": now - timedelta(hours=2),
                    "responded_at": now - timedelta(hours=2),
                    "response": "CONFIRMED",
                    "is_expired": False,
                },
                {
                    "patient_id": patient_ids["rahul.verma@gmail.com"],
                    "appointment_id": appointment_ids["appt_2"],
                    "waitlist_id": None,
                    "notification_type": "REMINDER_24HR",
                    "channel": "SMS",
                    "sent_at": now - timedelta(days=1),
                    "responded_at": None,
                    "response": "NO_RESPONSE",
                    "is_expired": False,
                },
                {
                    "patient_id": patient_ids["rahul.verma@gmail.com"],
                    "appointment_id": appointment_ids["appt_2"],
                    "waitlist_id": None,
                    "notification_type": "REMINDER_2HR",
                    "channel": "WHATSAPP",
                    "sent_at": now - timedelta(hours=3),
                    "responded_at": now - timedelta(hours=2, minutes=50),
                    "response": "CONFIRMED",
                    "is_expired": False,
                },
                {
                    "patient_id": patient_ids["rohan.gupta@gmail.com"],
                    "appointment_id": appointment_ids["appt_3"],
                    "waitlist_id": None,
                    "notification_type": "CANCELLATION",
                    "channel": "EMAIL",
                    "sent_at": now - timedelta(minutes=50),
                    "responded_at": now - timedelta(minutes=40),
                    "response": "CANCELLED",
                    "is_expired": False,
                },
                {
                    "patient_id": patient_ids["neha.patel@gmail.com"],
                    "appointment_id": None,
                    "waitlist_id": waitlist_ids[0],
                    "notification_type": "WAITLIST_NOTIFY",
                    "channel": "WHATSAPP",
                    "sent_at": now - timedelta(minutes=20),
                    "responded_at": None,
                    "response": "NO_RESPONSE",
                    "is_expired": False,
                },
                {
                    "patient_id": patient_ids["rahul.verma@gmail.com"],
                    "appointment_id": None,
                    "waitlist_id": waitlist_ids[3],
                    "notification_type": "WAITLIST_EXPIRED",
                    "channel": "SMS",
                    "sent_at": now - timedelta(hours=1, minutes=25),
                    "responded_at": None,
                    "response": "NO_RESPONSE",
                    "is_expired": True,
                },
                {
                    "patient_id": patient_ids["aisha.khan@gmail.com"],
                    "appointment_id": appointment_ids["appt_7"],
                    "waitlist_id": None,
                    "notification_type": "BOOKING_CONFIRM",
                    "channel": "EMAIL",
                    "sent_at": now,
                    "responded_at": now,
                    "response": "CONFIRMED",
                    "is_expired": False,
                },
            ],
        )

        db.execute(
            text(
                """
                INSERT INTO cancellation_log (
                    appointment_id,
                    patient_id,
                    processed_by,
                    cancelled_at,
                    is_late_cancellation,
                    reason,
                    cancelled_by
                )
                VALUES (
                    :appointment_id,
                    :patient_id,
                    :processed_by,
                    :cancelled_at,
                    :is_late_cancellation,
                    :reason,
                    :cancelled_by
                )
                """
            ),
            [
                {
                    "appointment_id": appointment_ids["appt_3"],
                    "patient_id": patient_ids["rohan.gupta@gmail.com"],
                    "processed_by": staff_ids["anita.sharma@dpam.com"],
                    "cancelled_at": now - timedelta(hours=1),
                    "is_late_cancellation": True,
                    "reason": "Cancelled within two hours of the slot",
                    "cancelled_by": "PATIENT",
                },
                {
                    "appointment_id": appointment_ids["appt_2"],
                    "patient_id": patient_ids["rahul.verma@gmail.com"],
                    "processed_by": staff_ids["sonia.iyer@dpam.com"],
                    "cancelled_at": now - timedelta(days=5),
                    "is_late_cancellation": False,
                    "reason": "Historical staff-assisted reschedule record",
                    "cancelled_by": "STAFF",
                },
            ],
        )

        db.commit()
        print("Sample data inserted successfully with multiple variations")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    populate_database()
