from fastapi import FastAPI

from app.modules.patients import router as patients_router
from app.modules.doctors import router as doctors_router
from app.modules.staff import router as staff_router
from app.agents.router import router as agents_router


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


app.include_router(patients_router)
app.include_router(doctors_router)
app.include_router(staff_router)
app.include_router(agents_router)

