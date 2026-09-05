from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog

from app.config import settings
from app.api import risk, payments, transactions, vendor, webhooks, ai, feedback, admin, merchants, verification, simulator
from app.services.database import init_db


structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up", environment=settings.ENVIRONMENT, demo_mode=settings.DEMO_MODE)
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning("Database init skipped (demo mode or no DB)", error=str(e))
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="AI Risk Manager for Bharat",
    description="AI-powered payment risk management for citizens and micro-merchants",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(risk.router)
app.include_router(payments.router)
app.include_router(transactions.router)
app.include_router(vendor.router)
app.include_router(webhooks.router)
app.include_router(ai.router)
app.include_router(feedback.router)
app.include_router(admin.router)
app.include_router(merchants.router)
app.include_router(verification.router)
app.include_router(simulator.router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/")
async def root():
    return {
        "name": "AI Risk Manager for Bharat",
        "version": "1.0.0",
        "description": "AI-powered payment safety layer for everyday digital payments",
    }