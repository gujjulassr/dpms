from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database.connection.database import get_db
from app.modules.auth.schemas import LoginRequest, TokenResponse, UserCreate, UserInfo
from app.modules.auth.schemas import GoogleRegisterRequest
from app.modules.auth.service import (
    build_google_auth_url,
    get_current_user_service,
    google_callback_service,
    google_register_service,
    login_service,
    register_user_service,
    list_users_service,
)

router = APIRouter(prefix="/auth", tags=["Auth"])
bearer = HTTPBearer()


# ── JWT dependency ────────────────────────────────────────────────────────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> UserInfo:
    try:
        return get_current_user_service(db, credentials.credentials)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


def require_admin(current_user: UserInfo = Depends(get_current_user)) -> UserInfo:
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Username + password → JWT token."""
    try:
        return login_service(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.get("/me", response_model=UserInfo)
def me(current_user: UserInfo = Depends(get_current_user)):
    """Return info about the currently logged-in user."""
    return current_user


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _admin: UserInfo = Depends(require_admin),
):
    """ADMIN only — create a new login account."""
    try:
        user = register_user_service(db, payload)
        user.pop("password_hash", None)
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/users", response_model=list)
def list_all_users(
    db: Session = Depends(get_db),
    _admin: UserInfo = Depends(require_admin),
):
    """ADMIN only — list all user accounts (no passwords)."""
    return list_users_service(db)


# ── Google OAuth ──────────────────────────────────────────────────────────────

@router.get("/google/login")
def google_login():
    """
    Redirect the browser to Google's OAuth consent screen.
    Intended for PATIENT sign-in only.
    Open this URL in a browser tab: http://127.0.0.1:8000/auth/google/login
    """
    url = build_google_auth_url()
    return RedirectResponse(url=url)


@router.post("/google/register", response_model=TokenResponse)
def google_register(payload: GoogleRegisterRequest, db: Session = Depends(get_db)):
    """
    Complete registration for a new patient who signed in with Google.
    Accepts the short-lived reg_token + phone (+ optional DOB).
    Returns a full JWT on success.
    """
    try:
        return google_register_service(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/google/callback")
def google_callback(
    code:  str = Query(...),
    state: str = Query(...),
    db:    Session = Depends(get_db),
):
    """
    Google redirects here after user grants consent.
    We exchange the code, find/create the patient, issue a JWT,
    then redirect back to the Streamlit frontend with ?token=...
    """
    try:
        redirect_url = google_callback_service(db, code, state)
        return RedirectResponse(url=redirect_url)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
