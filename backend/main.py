"""
Procurement AI System — FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.db.init_db import create_all_tables
from backend.config.settings import get_settings
from backend.routes import request as request_router
from backend.routes import vendor as vendor_router
from backend.utils.logger import app_logger as logger

settings = get_settings()


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting %s v%s [%s]", settings.app_name, settings.app_version, settings.app_env)
    create_all_tables()
    logger.info("✅ Database tables initialised")
    yield
    logger.info("🛑 Shutting down %s", settings.app_name)


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
## Procurement AI System

A production-ready FastAPI backend for managing procurement purchase requests with **Azure OpenAI (GPT-4o)** AI validation.

### Features
- 📋 Submit and manage Purchase Requests (PRs)
- 🤖 AI-powered validation and description enhancement via **LangGraph + Azure OpenAI**
- 📄 Automatic PDF generation for every PR
- 🔄 Re-submission and update flow with AI re-validation
- 💾 SQLite persistence with SQLAlchemy ORM

### AI Validation
Each PR is run through a **LangGraph state machine** that:
1. Validates input fields
2. Calls Azure OpenAI GPT-4o to enhance the description and validate budget
3. Returns structured feedback (improved description, missing fields, budget assessment)
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ─── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(request_router.router, prefix="/api/v1")
app.include_router(vendor_router.router, prefix="/api/v1")


# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"], summary="Health Check")
async def health_check():
    return JSONResponse(content={
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
    })


@app.get("/", tags=["System"], summary="API Root")
async def root():
    return JSONResponse(content={
        "message": f"Welcome to {settings.app_name}",
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    })
