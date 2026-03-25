from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agents.router import router as agents_router
from app.modules.appointments import router as appointments_router
from app.modules.auth import router as auth_router
from app.modules.doctors import router as doctors_router
from app.modules.patients import router as patients_router
from app.modules.ratings import router as ratings_router
from app.modules.sessions import router as sessions_router
from app.modules.staff import router as staff_router
from app.modules.waitlist import router as waitlist_router


# ── Background schedulers ─────────────────────────────────────────────────────

def _start_schedulers():
    """
    Starts two background jobs:

    1. 2-hour appointment reminder  — runs every 5 minutes
       Finds CONFIRMED appointments within the next 2 hours, sends reminder email,
       marks reminder_2hr_sent = TRUE.

    2. Complete & review request    — runs every 10 minutes
       Finds CONFIRMED appointments whose slot time has passed, marks them COMPLETED,
       sends a post-appointment review-request email (once, review_sent = TRUE).

    Silently degrades if APScheduler is not installed or SMTP is not configured.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from app.modules.notifications.service import (
            send_pending_2hr_reminders,
            mark_completed_and_send_reviews,
        )

        scheduler = BackgroundScheduler(timezone="UTC")
        scheduler.add_job(
            send_pending_2hr_reminders,
            "interval", minutes=5,
            id="2hr_reminder", replace_existing=True,
        )
        scheduler.add_job(
            mark_completed_and_send_reviews,
            "interval", minutes=10,
            id="complete_and_review", replace_existing=True,
        )
        scheduler.start()
        return scheduler
    except ImportError:
        import logging
        logging.getLogger(__name__).warning(
            "apscheduler not installed — background jobs disabled. "
            "Run: pip install apscheduler"
        )
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = _start_schedulers()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="DPMS API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


@app.get("/", tags=["Root"])
def root():
    return {"message": "DPMS API is running"}


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(patients_router)
app.include_router(doctors_router)
app.include_router(staff_router)
app.include_router(sessions_router)
app.include_router(appointments_router)
app.include_router(waitlist_router)
app.include_router(agents_router)
app.include_router(ratings_router)   # GET/POST /rate/{token}
