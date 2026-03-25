from fastapi import FastAPI

from app.agents.router import router as agents_router
from app.modules.appointments import router as appointments_router
from app.modules.auth import router as auth_router
from app.modules.doctors import router as doctors_router
from app.modules.patients import router as patients_router
from app.modules.sessions import router as sessions_router
from app.modules.staff import router as staff_router
from app.modules.waitlist import router as waitlist_router


app = FastAPI(
    title="DPMS API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
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
