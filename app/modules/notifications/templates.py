"""
notifications/templates.py
--------------------------
Clean HTML email templates for each notification type.
"""

_BASE = """
<html>
<body style="margin:0;padding:0;background:#f4f6f8;font-family:Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0">
  <tr><td align="center" style="padding:32px 16px">
    <table width="520" cellpadding="0" cellspacing="0"
           style="background:#ffffff;border-radius:8px;
                  box-shadow:0 2px 8px rgba(0,0,0,.08);overflow:hidden">

      <!-- Header -->
      <tr>
        <td style="background:{header_color};padding:24px 32px">
          <span style="font-size:1.4rem;font-weight:700;color:#fff">{header_icon} {header_title}</span>
        </td>
      </tr>

      <!-- Body -->
      <tr>
        <td style="padding:28px 32px 8px">
          <p style="margin:0 0 16px;font-size:1rem;color:#333">
            Dear <strong>{patient_name}</strong>,
          </p>
          {body_html}
        </td>
      </tr>

      <!-- Details table -->
      <tr>
        <td style="padding:0 32px 20px">
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="border:1px solid #e8e8e8;border-radius:6px;overflow:hidden">
            {rows_html}
          </table>
        </td>
      </tr>

      <!-- Footer note -->
      <tr>
        <td style="padding:0 32px 28px">
          <p style="margin:0;font-size:0.82rem;color:#999">{footer_note}</p>
        </td>
      </tr>

      <!-- Brand strip -->
      <tr>
        <td style="background:#f4f6f8;padding:14px 32px;
                   font-size:0.78rem;color:#aaa;text-align:center">
          DPMS — Doctor-Patient Management System
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body>
</html>
"""


def _doctor_label(name: str) -> str:
  n = (name or "").strip()
  if n.lower().startswith("dr."):
    return n
  return f"Dr. {n}" if n else "Doctor"


def _row(label: str, value: str, shade: bool = False) -> str:
    bg = "background:#f9f9f9;" if shade else ""
    return (
        f'<tr style="{bg}">'
        f'<td style="padding:10px 14px;font-weight:600;color:#555;width:40%">{label}</td>'
        f'<td style="padding:10px 14px;color:#333">{value}</td>'
        "</tr>"
    )


def _build(*, header_color, header_icon, header_title,
           patient_name, body_html, rows: list[tuple],
           footer_note: str) -> str:
    rows_html = "".join(_row(l, v, i % 2 == 1) for i, (l, v) in enumerate(rows))
    return _BASE.format(
        header_color=header_color,
        header_icon=header_icon,
        header_title=header_title,
        patient_name=patient_name,
        body_html=body_html,
        rows_html=rows_html,
        footer_note=footer_note,
    )


# ── Templates ─────────────────────────────────────────────────────────────────

def booking_confirmation(patient_name, doctor_name, specialization, date, time_str):
    return _build(
        header_color="#27ae60", header_icon="✅", header_title="Appointment Confirmed",
        patient_name=patient_name,
        body_html="<p style='margin:0 0 16px;color:#555'>Your appointment is all set. See you soon!</p>",
        rows=[
          ("Doctor",         _doctor_label(doctor_name)),
            ("Specialization", specialization),
            ("Date",           date),
            ("Time",           time_str),
        ],
        footer_note=(
            "Please arrive 10 minutes early. "
            "Cancellations must be made at least 2 hours before your slot."
        ),
    )


def cancellation(patient_name, doctor_name, date, time_str):
    return _build(
        header_color="#e74c3c", header_icon="❌", header_title="Appointment Cancelled",
        patient_name=patient_name,
        body_html=(
            "<p style='margin:0 0 16px;color:#555'>"
            "Your appointment has been cancelled. "
            "You can book a new slot anytime through the DPMS portal."
            "</p>"
        ),
        rows=[
          ("Doctor", _doctor_label(doctor_name)),
            ("Date",   date),
            ("Time",   time_str),
        ],
        footer_note="If this cancellation was unexpected, please contact reception.",
    )


def waitlist_allocated(patient_name, doctor_name, specialization, date, time_str):
    return _build(
        header_color="#2980b9", header_icon="🎉", header_title="Waitlist Slot Confirmed!",
        patient_name=patient_name,
        body_html=(
            "<p style='margin:0 0 16px;color:#555'>"
            "Good news — a slot has opened up and you've been automatically confirmed "
            "from the waitlist. Your appointment details are below."
            "</p>"
        ),
        rows=[
          ("Doctor",         _doctor_label(doctor_name)),
            ("Specialization", specialization),
            ("Date",           date),
            ("Time",           time_str),
        ],
        footer_note=(
            "Please arrive 10 minutes early. "
            "Cancellations must be made at least 2 hours before your slot."
        ),
    )


def reminder_2hr(patient_name, doctor_name, specialization, date, time_str):
    return _build(
        header_color="#e67e22", header_icon="⏰", header_title="Appointment Reminder",
        patient_name=patient_name,
        body_html=(
            "<p style='margin:0 0 16px;color:#555'>"
            "This is a friendly reminder that you have an appointment coming up "
            "<strong>in approximately 2 hours</strong>."
            "</p>"
        ),
        rows=[
          ("Doctor",         _doctor_label(doctor_name)),
            ("Specialization", specialization),
            ("Date",           date),
            ("Time",           time_str),
        ],
        footer_note="Please plan to arrive 10 minutes early.",
    )


def review_request(patient_name, doctor_name, specialization, date, time_str, rating_url):
    star_buttons = "".join(
    f'<a href="{rating_url}?stars={s}" '
        f'style="display:inline-block;margin:0 4px;padding:10px 18px;'
        f'background:#f4a900;color:#fff;font-size:1rem;font-weight:700;'
        f'border-radius:6px;text-decoration:none">{"★" * s}</a>'
        for s in range(1, 6)
    )
    body = f"""
<p style='margin:0 0 14px;color:#555'>
  We hope your visit went well! Your feedback helps us improve our service
  and helps other patients choose the right doctor.
</p>
<p style='margin:0 0 18px;color:#555'>
  How would you rate your experience with <strong>{_doctor_label(doctor_name)}</strong>?
</p>
<div style='margin:0 0 18px;text-align:center'>
  {star_buttons}
</div>
<p style='margin:0 0 10px;font-size:0.88rem;color:#999'>
  Or click the link to leave a detailed review:
  <a href="{rating_url}" style='color:#2980b9'>Leave a review</a>
</p>
"""
    return _build(
        header_color="#8e44ad", header_icon="⭐", header_title="How was your appointment?",
        patient_name=patient_name,
        body_html=body,
        rows=[
        ("Doctor",         _doctor_label(doctor_name)),
            ("Specialization", specialization),
            ("Date",           date),
            ("Time",           time_str),
        ],
        footer_note=(
            "This review link expires in 7 days. "
            "Your honest feedback is greatly appreciated."
        ),
    )
