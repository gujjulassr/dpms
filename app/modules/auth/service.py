"""
Auth service — JWT login, Google OAuth, token verification, user registration.

Requirements (in requirements.txt):
    PyJWT>=2.8.0
    passlib[bcrypt]>=1.7.4
    bcrypt>=4.0.0,<5
    requests (already bundled via httpx)
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import jwt
import requests as http_requests
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.modules.auth.repository import (
    create_user,
    get_user_by_id,
    get_user_by_username,
    list_users,
    update_last_login,
)
from app.modules.auth.schemas import LoginRequest, TokenResponse, UserCreate, UserInfo

# ── Google OAuth config ───────────────────────────────────────────────────────
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_OAUTH_REDIRECT_URI",  "http://127.0.0.1:8000/auth/google/callback")
GOOGLE_FRONTEND_URL  = os.getenv("GOOGLE_OAUTH_FRONTEND_URL",  "http://127.0.0.1:8501")

GOOGLE_AUTH_URL    = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL   = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL= "https://www.googleapis.com/oauth2/v3/userinfo"

# NOTE: we use signed JWT as the OAuth state so no server-side storage is needed.
# This survives hot-reloads (uvicorn --reload) and multi-worker deployments.

# ── Config ────────────────────────────────────────────────────────────────────
SECRET_KEY         = os.getenv("JWT_SECRET_KEY", "dpms-secret-change-in-production")
ALGORITHM          = "HS256"
TOKEN_EXPIRE_HOURS = 8

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(payload: dict) -> str:
    data = payload.copy()
    # Ensure all values are JSON-serializable (handles leftover UUID objects
    # from databases that haven't been fully migrated to SERIAL yet)
    for k, v in data.items():
        if not isinstance(v, (str, int, float, bool, type(None))):
            data[k] = str(v)
    data["exp"] = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    data["iat"] = datetime.utcnow()
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Returns decoded payload or None if invalid / expired."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


# ── Services ──────────────────────────────────────────────────────────────────

def login_service(db: Session, payload: LoginRequest) -> TokenResponse:
    user = get_user_by_username(db, payload.username)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise ValueError("Invalid username or password")

    token = create_access_token({
        "user_id":      user["user_id"],
        "username":     user["username"],
        "role":         user["role"],
        "display_name": user["display_name"],
        "staff_id":     user.get("staff_id"),
        "patient_id":   user.get("patient_id"),
        "doctor_id":    user.get("doctor_id"),
    })

    update_last_login(db, user["user_id"])
    db.commit()

    return TokenResponse(
        access_token=token,
        role=user["role"],
        username=user["username"],
        user_id=user["user_id"],
        display_name=user["display_name"],
    )


def get_current_user_service(db: Session, token: str) -> UserInfo:
    payload = decode_token(token)
    if not payload:
        raise PermissionError("Invalid or expired token")

    user = get_user_by_id(db, payload["user_id"])
    if not user or not user["is_active"]:
        raise PermissionError("User not found or inactive")

    return UserInfo(
        user_id=user["user_id"],
        username=user["username"],
        role=user["role"],
        display_name=user["display_name"],
        staff_id=user.get("staff_id"),
        patient_id=user.get("patient_id"),
        doctor_id=user.get("doctor_id"),
        is_active=user["is_active"],
    )


def register_user_service(db: Session, payload: UserCreate) -> dict:
    """ADMIN-only: create a new login account."""
    existing = get_user_by_username(db, payload.username)
    if existing:
        raise ValueError(f"Username '{payload.username}' already exists")

    data = {
        "username":      payload.username,
        "password_hash": hash_password(payload.password),
        "role":          payload.role,
        "display_name":  payload.display_name,
        "staff_id":      payload.staff_id,
        "patient_id":    payload.patient_id,
        "doctor_id":     payload.doctor_id,
    }
    user = create_user(db, data)
    db.commit()
    return user


def list_users_service(db: Session) -> list:
    return list_users(db)


def google_register_service(db: Session, payload) -> TokenResponse:
    """
    Called after the new-patient registration form is submitted.
    Validates the short-lived reg_token, creates the patient + user record,
    and returns a full JWT to log the user in.
    """

    # Decode and validate the registration token
    try:
        reg_data = jwt.decode(payload.reg_token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise ValueError("Registration session expired or invalid. Please sign in with Google again.")

    if reg_data.get("purpose") != "google_registration":
        raise ValueError("Invalid registration token.")

    google_sub = reg_data["google_sub"]
    email      = reg_data["email"]
    full_name  = reg_data["full_name"]

    # Validate phone length
    phone = payload.phone.strip()
    if not phone:
        raise ValueError("Phone number is required.")
    if len(phone) > 15:
        raise ValueError("Phone number must be 15 characters or fewer.")

    # Check phone uniqueness
    existing_phone = db.execute(
        text("SELECT patient_id FROM patients WHERE phone = :p"), {"p": phone}
    ).mappings().first()
    if existing_phone:
        raise ValueError("This phone number is already registered. Please use a different number.")

    # Parse optional date of birth
    dob = None
    if payload.date_of_birth:
        try:
            from datetime import date as date_cls
            dob = date_cls.fromisoformat(payload.date_of_birth)
        except ValueError:
            raise ValueError("Date of birth must be in YYYY-MM-DD format.")

    # Create patient record
    new_patient = db.execute(
        text("""
            INSERT INTO patients (full_name, email, phone, date_of_birth)
            VALUES (:name, :email, :phone, :dob)
            RETURNING patient_id, full_name
        """),
        {"name": full_name, "email": email, "phone": phone, "dob": dob},
    ).mappings().one()
    patient_id = new_patient["patient_id"]

    # Re-use existing user account if present (orphaned account re-registration),
    # otherwise create a brand new one.
    existing_user_id = reg_data.get("user_id")
    if existing_user_id:
        # Orphaned account — just re-link to the new patient record
        new_user = db.execute(
            text("""
                UPDATE users
                SET patient_id  = :patient_id,
                    google_sub  = :google_sub,
                    email       = :email,
                    auth_provider = 'GOOGLE'
                WHERE user_id = :user_id
                RETURNING *
            """),
            {
                "patient_id": patient_id,
                "google_sub": google_sub,
                "email":      email,
                "user_id":    existing_user_id,
            },
        ).mappings().one()
    else:
        # Brand new user — insert fresh
        username = f"g_{google_sub[:16]}"
        new_user = db.execute(
            text("""
                INSERT INTO users
                    (username, password_hash, role, display_name,
                     email, auth_provider, google_sub, patient_id)
                VALUES
                    (:username, '', 'PATIENT', :display_name,
                     :email, 'GOOGLE', :google_sub, :patient_id)
                RETURNING *
            """),
            {
                "username":     username,
                "display_name": full_name,
                "email":        email,
                "google_sub":   google_sub,
                "patient_id":   patient_id,
            },
        ).mappings().one()

    user = dict(new_user)
    db.commit()

    # Issue JWT
    token = create_access_token({
        "user_id":      user["user_id"],
        "username":     user["username"],
        "role":         "PATIENT",
        "display_name": user["display_name"],
        "patient_id":   patient_id,
        "staff_id":     None,
        "doctor_id":    None,
    })

    return TokenResponse(
        access_token=token,
        role="PATIENT",
        username=user["username"],
        user_id=user["user_id"],
        display_name=user["display_name"],
    )


# ── Google OAuth ──────────────────────────────────────────────────────────────

def _make_oauth_state() -> str:
    """
    Create a short-lived signed JWT to use as the OAuth `state` parameter.
    Verifiable on callback without any server-side storage — survives reloads.
    """
    return jwt.encode(
        {
            "purpose": "google_oauth_state",
            "nonce":   secrets.token_hex(16),
            "exp":     datetime.utcnow() + timedelta(minutes=10),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def _verify_oauth_state(state: str) -> bool:
    """Return True if state is a valid, unexpired JWT we issued."""
    try:
        payload = jwt.decode(state, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("purpose") == "google_oauth_state"
    except jwt.PyJWTError:
        return False


def build_google_auth_url() -> str:
    """Generate the Google OAuth consent-screen URL with a signed state token."""
    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope":         "openid email profile",
        "state":         _make_oauth_state(),
        "access_type":   "online",
        "prompt":        "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def _exchange_google_code(code: str) -> dict:
    """Exchange authorization code for Google's ID token + access token."""
    resp = http_requests.post(GOOGLE_TOKEN_URL, data={
        "code":          code,
        "client_id":     GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri":  GOOGLE_REDIRECT_URI,
        "grant_type":    "authorization_code",
    }, timeout=10)
    if not resp.ok:
        import logging
        logging.getLogger(__name__).error(
            "Google token exchange failed: %s %s", resp.status_code, resp.text
        )
    resp.raise_for_status()
    return resp.json()


def _get_google_user_info(access_token: str) -> dict:
    """Fetch the signed-in Google user's profile (name, email, sub)."""
    resp = http_requests.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def google_callback_service(db: Session, code: str, state: str) -> str:
    """
    Full Google OAuth callback:
      1. Validate CSRF state
      2. Exchange code for tokens
      3. Get Google user profile
      4. Find existing user by google_sub OR email
      5. If first login: auto-create patient record + user account
      6. Issue our JWT and return redirect URL for the frontend

    Returns: redirect URL (Streamlit) with ?token= appended
    """
    # 1. CSRF state check — verify the signed JWT state we generated
    if not _verify_oauth_state(state):
        raise PermissionError("Invalid OAuth state — possible CSRF attempt")

    # 2 + 3. Exchange code → get Google profile
    token_data  = _exchange_google_code(code)
    google_info = _get_google_user_info(token_data["access_token"])

    google_sub  = google_info.get("sub")        # unique Google user ID
    email       = google_info.get("email", "")
    given_name  = google_info.get("given_name", "")
    family_name = google_info.get("family_name", "")
    full_name   = google_info.get("name") or f"{given_name} {family_name}".strip() or email

    # 4. Look up existing user by google_sub or email
    user_row = db.execute(
        text("SELECT * FROM users WHERE google_sub = :sub AND is_active = TRUE"),
        {"sub": google_sub},
    ).mappings().first()

    if not user_row and email:
        # Try matching by email (handles re-linking)
        user_row = db.execute(
            text("SELECT * FROM users WHERE email = :email AND is_active = TRUE"),
            {"email": email},
        ).mappings().first()

    if user_row:
        user = dict(user_row)

        # ── Orphaned account: user exists but patient record was deleted ──
        # Send them back through the registration form to re-link.
        if not user.get("patient_id"):
            reg_token = jwt.encode(
                {
                    "purpose":    "google_registration",
                    "google_sub": google_sub,
                    "email":      email,
                    "full_name":  full_name,
                    "user_id":    user["user_id"],   # re-use existing user account
                    "exp":        datetime.utcnow() + timedelta(minutes=15),
                },
                SECRET_KEY,
                algorithm=ALGORITHM,
            )
            return (
                f"{GOOGLE_FRONTEND_URL}"
                f"?needs_registration=true"
                f"&reg_token={reg_token}"
                f"&name={full_name}"
                f"&email={email}"
            )

        # ── Returning patient — log them in ───────────────────────────────
        if not user.get("google_sub"):
            db.execute(
                text("UPDATE users SET google_sub = :sub WHERE user_id = :uid"),
                {"sub": google_sub, "uid": user["user_id"]},
            )
        update_last_login(db, user["user_id"])
        db.commit()

        jwt_token = create_access_token({
            "user_id":      user["user_id"],
            "username":     user["username"],
            "role":         user["role"],
            "display_name": user["display_name"],
            "patient_id":   user["patient_id"],
            "staff_id":     None,
            "doctor_id":    None,
        })
        return f"{GOOGLE_FRONTEND_URL}?token={jwt_token}"

    else:
        # ── First-ever login — check if patient record exists by email ────
        patient_row = db.execute(
            text("SELECT patient_id, full_name FROM patients WHERE email = :e"),
            {"e": email},
        ).mappings().first()

        if patient_row:
            # Patient record already exists (e.g. added by receptionist)
            # Create user account and log them in directly
            username = f"g_{google_sub[:16]}"
            new_user = db.execute(
                text("""
                    INSERT INTO users
                        (username, password_hash, role, display_name,
                         email, auth_provider, google_sub, patient_id)
                    VALUES
                        (:username, '', 'PATIENT', :display_name,
                         :email, 'GOOGLE', :google_sub, :patient_id)
                    RETURNING *
                """),
                {
                    "username":     username,
                    "display_name": patient_row["full_name"],
                    "email":        email,
                    "google_sub":   google_sub,
                    "patient_id":   patient_row["patient_id"],
                },
            ).mappings().one()
            user = dict(new_user)
            update_last_login(db, user["user_id"])
            db.commit()

            jwt_token = create_access_token({
                "user_id":      user["user_id"],
                "username":     user["username"],
                "role":         "PATIENT",
                "display_name": user["display_name"],
                "patient_id":   user["patient_id"],
                "staff_id":     None,
                "doctor_id":    None,
            })
            return f"{GOOGLE_FRONTEND_URL}?token={jwt_token}"

        else:
            # ── Brand new patient — issue a short-lived registration token ──
            # Do NOT create any record yet; redirect to the registration form.
            reg_token = jwt.encode(
                {
                    "purpose":    "google_registration",
                    "google_sub": google_sub,
                    "email":      email,
                    "full_name":  full_name,
                    "exp":        datetime.utcnow() + timedelta(minutes=15),
                },
                SECRET_KEY,
                algorithm=ALGORITHM,
            )
            return (
                f"{GOOGLE_FRONTEND_URL}"
                f"?needs_registration=true"
                f"&reg_token={reg_token}"
                f"&name={full_name}"
                f"&email={email}"
            )
