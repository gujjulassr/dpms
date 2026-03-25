"""
modules/ratings/router.py
--------------------------
GET  /rate/{token}        — Serves the HTML star-rating page
POST /rate/{token}        — Submits the rating (form POST from the page)
GET  /rate/{token}?stars=N — Quick-rate from email button (pre-fills stars)

The {token} is a signed JWT created by notify_review_request().
It contains: appointment_id, patient_id, doctor_id, exp (7 days).

No login required — the token IS the authentication for this one action.
"""

from __future__ import annotations

import os
from typing import Optional

import jwt
from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse
from sqlalchemy import text

from app.database.connection.database import get_session

router = APIRouter(prefix="/rate", tags=["Ratings"])

_SECRET = os.getenv("JWT_SECRET_KEY", "dpms-secret-change-in-production")
_ALG    = "HS256"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _decode_review_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, _SECRET, algorithms=[_ALG])
        if payload.get("purpose") != "doctor_review":
            return None
        return payload
    except jwt.PyJWTError:
        return None


def _load_appointment_info(appointment_id: int) -> dict:
    db = get_session()
    try:
        row = db.execute(
            text("""
                SELECT
                    p.full_name     AS patient_name,
                    d.full_name     AS doctor_name,
                    d.specialization,
                    a.appointment_date AS slot_date,
                    a.start_time,
                    a.review_sent
                FROM appointments a
                JOIN patients p ON p.patient_id = a.patient_id
                JOIN doctors  d ON d.doctor_id  = a.doctor_id
                WHERE a.appointment_id = :aid
            """),
            {"aid": appointment_id},
        ).mappings().fetchone()
        return dict(row) if row else {}
    finally:
        db.close()


def _already_rated(appointment_id: int) -> bool:
    db = get_session()
    try:
        row = db.execute(
            text(
                "SELECT 1 FROM doctor_ratings WHERE appointment_id = :aid"
            ),
            {"aid": appointment_id},
        ).fetchone()
        return row is not None
    finally:
        db.close()


def _save_rating(appointment_id: int, patient_id: int, doctor_id: int,
                 stars: int, comment: str) -> None:
    db = get_session()
    try:
        db.execute(
            text("""
                INSERT INTO doctor_ratings
                    (appointment_id, patient_id, doctor_id, stars, comment)
                VALUES
                    (:aid, :pid, :did, :stars, :comment)
                ON CONFLICT (appointment_id) DO NOTHING
            """),
            {
                "aid":     appointment_id,
                "pid":     patient_id,
                "did":     doctor_id,
                "stars":   stars,
                "comment": comment.strip() if comment else None,
            },
        )
        db.commit()
    finally:
        db.close()


# ── HTML fragments ────────────────────────────────────────────────────────────

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rate your appointment — DPMS</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Segoe UI', Arial, sans-serif;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }}
    .card {{
      background: #fff;
      border-radius: 16px;
      box-shadow: 0 20px 60px rgba(0,0,0,.2);
      max-width: 520px;
      width: 100%;
      overflow: hidden;
    }}
    .header {{
      background: linear-gradient(90deg, #8e44ad, #6c3483);
      padding: 28px 32px;
      color: #fff;
    }}
    .header h1 {{ font-size: 1.5rem; font-weight: 700; }}
    .header p  {{ margin-top: 4px; opacity: .85; font-size: .92rem; }}
    .body {{ padding: 28px 32px; }}
    .apt-info {{
      background: #f8f5ff;
      border-left: 4px solid #8e44ad;
      border-radius: 4px;
      padding: 14px 18px;
      margin-bottom: 24px;
      font-size: .93rem;
      color: #444;
      line-height: 1.7;
    }}
    .apt-info strong {{ color: #333; }}

    /* Star rating */
    .stars-label {{ font-weight: 600; color: #333; margin-bottom: 12px; display:block; }}
    .stars {{
      display: flex;
      flex-direction: row-reverse;
      justify-content: flex-end;
      gap: 4px;
      margin-bottom: 22px;
    }}
    .stars input {{ display: none; }}
    .stars label {{
      font-size: 2.6rem;
      color: #ccc;
      cursor: pointer;
      transition: color .15s;
      line-height: 1;
    }}
    .stars input:checked ~ label,
    .stars label:hover,
    .stars label:hover ~ label {{ color: #f4a900; }}
    .stars input:checked + label {{ color: #f4a900; }}

    textarea {{
      width: 100%;
      min-height: 100px;
      border: 1px solid #ddd;
      border-radius: 8px;
      padding: 12px;
      font-size: .95rem;
      font-family: inherit;
      resize: vertical;
      margin-bottom: 22px;
      color: #333;
      transition: border-color .2s;
    }}
    textarea:focus {{ outline: none; border-color: #8e44ad; }}
    textarea::placeholder {{ color: #bbb; }}

    button[type=submit] {{
      width: 100%;
      padding: 14px;
      background: linear-gradient(90deg, #8e44ad, #6c3483);
      color: #fff;
      font-size: 1.05rem;
      font-weight: 700;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      letter-spacing: .03em;
      transition: opacity .2s;
    }}
    button[type=submit]:hover {{ opacity: .9; }}

    .footer {{
      background: #f8f5ff;
      padding: 14px 32px;
      font-size: .78rem;
      color: #aaa;
      text-align: center;
    }}
    .msg {{
      text-align: center;
      padding: 48px 32px;
      font-size: 1.05rem;
      color: #555;
      line-height: 1.7;
    }}
    .msg .big {{ font-size: 3rem; display:block; margin-bottom: 14px; }}
    .msg h2 {{ font-size: 1.4rem; color: #333; margin-bottom: 10px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h1>⭐ Rate Your Appointment</h1>
      <p>DPMS — Doctor Patient Management System</p>
    </div>
    {content}
    <div class="footer">DPMS — Doctor Patient Management System</div>
  </div>
</body>
</html>"""


def _rating_form(token: str, info: dict, prefill_stars: int = 0) -> str:
    stars_html = ""
    for s in range(5, 0, -1):
        checked = "checked" if s == prefill_stars else ""
        stars_html += (
            f'<input type="radio" id="s{s}" name="stars" value="{s}" {checked} required>'
            f'<label for="s{s}" title="{s} star{"s" if s > 1 else ""}">★</label>'
        )

    content = f"""
    <div class="body">
      <p style="margin-bottom:20px;color:#555">
        Hi <strong>{info.get("patient_name","")}</strong>, we hope your visit went well!
        Please take a moment to rate your experience — it helps us serve you better.
      </p>
      <div class="apt-info">
        <strong>Doctor:</strong> Dr. {info.get("doctor_name","")}<br>
        <strong>Specialty:</strong> {info.get("specialization","")}<br>
        <strong>Date:</strong> {info.get("slot_date","")}&nbsp;&nbsp;
        <strong>Time:</strong> {str(info.get("start_time",""))[:5]}
      </div>

      <form method="post" action="/rate/{token}">
        <span class="stars-label">Your rating *</span>
        <div class="stars">{stars_html}</div>

        <textarea name="comment" placeholder="Tell us about your experience (optional)…"></textarea>

        <button type="submit">Submit Review</button>
      </form>
    </div>"""
    return _PAGE.format(content=content)


def _success_page(stars: int, doctor_name: str) -> str:
    star_str = "★" * stars + "☆" * (5 - stars)
    content = f"""
    <div class="body">
      <div class="msg">
        <span class="big">🎉</span>
        <h2>Thank you for your review!</h2>
        <p>You rated <strong>Dr. {doctor_name}</strong><br>
           <span style="font-size:1.8rem;color:#f4a900">{star_str}</span></p>
        <p style="margin-top:18px;font-size:.9rem;color:#999">
          Your feedback helps improve our clinic for everyone.<br>
          You can close this window.
        </p>
      </div>
    </div>"""
    return _PAGE.format(content=content)


def _error_page(message: str) -> str:
    content = f"""
    <div class="body">
      <div class="msg">
        <span class="big">⚠️</span>
        <h2>Oops!</h2>
        <p>{message}</p>
      </div>
    </div>"""
    return _PAGE.format(content=content)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/{token}", response_class=HTMLResponse)
def rating_page(token: str, stars: Optional[int] = None):
    """Render the rating form. If ?stars=N is in the URL (from email button), pre-fill."""
    payload = _decode_review_token(token)
    if not payload:
        return HTMLResponse(_error_page("This review link has expired or is invalid."), status_code=400)

    if _already_rated(payload["appointment_id"]):
        return HTMLResponse(_error_page("You have already submitted a review for this appointment. Thank you!"))

    info = _load_appointment_info(payload["appointment_id"])
    if not info:
        return HTMLResponse(_error_page("Appointment details could not be found."), status_code=404)

    prefill = stars if stars and 1 <= stars <= 5 else 0
    return HTMLResponse(_rating_form(token, info, prefill))


@router.post("/{token}", response_class=HTMLResponse)
async def submit_rating(
    token: str,
    stars: int = Form(...),
    comment: str = Form(""),
):
    """Handle form submission from the rating page."""
    payload = _decode_review_token(token)
    if not payload:
        return HTMLResponse(_error_page("This review link has expired or is invalid."), status_code=400)

    if _already_rated(payload["appointment_id"]):
        return HTMLResponse(_error_page("You have already submitted a review for this appointment."))

    if not (1 <= stars <= 5):
        return HTMLResponse(_error_page("Please select a star rating between 1 and 5."), status_code=400)

    info = _load_appointment_info(payload["appointment_id"])
    _save_rating(
        appointment_id = payload["appointment_id"],
        patient_id     = payload["patient_id"],
        doctor_id      = payload["doctor_id"],
        stars          = stars,
        comment        = comment,
    )

    return HTMLResponse(_success_page(stars, info.get("doctor_name", "")))
