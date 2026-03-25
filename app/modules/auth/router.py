from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database.connection.database import get_db
from app.modules.auth.schemas import LoginRequest, TokenResponse, UserCreate, UserInfo
from app.modules.auth.service import (
    get_current_user_service,
    login_service,
    register_user_service,
    list_users_service,
)

router = APIRouter(prefix="/auth", tags=["Auth"])
bearer = HTTPBearer()


# ── Helper: extract and validate JWT from request ─────────────────────────────

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
    """Authenticate and receive a JWT token."""
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
        # Don't return password_hash
        user.pop("password_hash", None)
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/users", response_model=list)
def list_all_users(
    db: Session = Depends(get_db),
    _admin: UserInfo = Depends(require_admin),
):
    """ADMIN only — list all user accounts."""
    return list_users_service(db)
