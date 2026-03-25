"""
notifications/email.py
----------------------
Thin SMTP wrapper.  Configure via .env:

    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=you@gmail.com
    SMTP_PASSWORD=your_app_password   # Gmail → Settings → App Passwords
    SMTP_FROM=DPMS Clinic <you@gmail.com>

If SMTP_HOST or SMTP_USER is blank the send is silently skipped so the app
works without email being set up.
"""

from __future__ import annotations

import logging
import os
import smtplib
from email import encoders
from email.utils import parseaddr
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

log = logging.getLogger(__name__)

SMTP_HOST     = os.getenv("SMTP_HOST", "")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM     = os.getenv("SMTP_FROM", SMTP_USER)


def _smtp_settings() -> tuple[str, int, str, str, str]:
    """Read SMTP settings at call time to avoid stale import-time env values."""
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_addr = os.getenv("SMTP_FROM", user)
    return host, port, user, password, from_addr


def _build_message(
    to: str,
    subject: str,
    html_body: str,
    from_addr: str,
    ics_content: Optional[str] = None,
    ics_filename: str = "appointment.ics",
) -> MIMEMultipart:
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    if ics_content:
        ics_part = MIMEBase(
            "text",
            "calendar",
            method="REQUEST",
            name=ics_filename,
            charset="utf-8",
        )
        ics_part.set_payload(ics_content.encode("utf-8"))
        encoders.encode_base64(ics_part)
        ics_part.add_header("Content-Disposition", "attachment", filename=ics_filename)
        msg.attach(ics_part)

    return msg


def send_email(
    to: str,
    subject: str,
    html_body: str,
    ics_content: Optional[str] = None,
    ics_filename: str = "appointment.ics",
) -> bool:
    """
    Send an HTML email, optionally attaching a calendar invite (.ics).

    Parameters
    ----------
    to           : Recipient email address
    subject      : Email subject line
    html_body    : Full HTML string for the email body
    ics_content  : Raw iCalendar string to attach (or None)
    ics_filename : Filename shown for the attachment (default 'appointment.ics')

    Returns True on success, False if SMTP not configured or on error.
    Never raises — caller should not be affected by email failures.
    """
    smtp_host, smtp_port, smtp_user, smtp_password, smtp_from = _smtp_settings()

    if not smtp_host or not smtp_user or not to:
        return False

    envelope_from = parseaddr(smtp_from)[1] or smtp_user

    try:
        msg = _build_message(
            to=to,
            subject=subject,
            html_body=html_body,
            from_addr=smtp_from,
            ics_content=ics_content,
            ics_filename=ics_filename,
        )

        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(envelope_from, [to], msg.as_string())

        log.info("Email sent → %s  [%s]", to, subject)
        return True

    except Exception as exc:
        if not ics_content:
            log.warning("Email failed → %s: %s", to, exc)
            return False

        log.warning(
            "Email with calendar invite failed for %s: %s. Retrying without invite.",
            to,
            exc,
        )

        try:
            msg = _build_message(
                to=to,
                subject=subject,
                html_body=html_body,
                from_addr=smtp_from,
            )
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(envelope_from, [to], msg.as_string())

            log.info("Email sent without calendar invite → %s  [%s]", to, subject)
            return True
        except Exception as retry_exc:
            log.warning("Fallback email failed → %s: %s", to, retry_exc)
            return False
