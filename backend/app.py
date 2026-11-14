"""LifeLane FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import ALLOWED_ORIGINS, API_VERSION, PROJECT_NAME
from backend.database import init_db
from backend.services.inference import get_inference_service
from backend.services.simulation import get_simulation_service
from backend.routers import health, detection, dispatch, signals


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    get_inference_service().load_or_train()
    get_simulation_service()  # initialize
    yield


app = FastAPI(
    title=PROJECT_NAME,
    version=API_VERSION,
    description="LifeLane Smart Ambulance Signal Preemption System - Simulation POC",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# All routers use /api prefix
app.include_router(health.router, prefix="/api")
app.include_router(detection.router, prefix="/api")
app.include_router(dispatch.router, prefix="/api")
app.include_router(signals.router, prefix="/api")
