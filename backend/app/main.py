from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.db.database import init_db, get_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database schemas on startup
    await init_db()
    yield

from app.api.routes import router as api_router

app = FastAPI(
    title="Havenkeep API Gateway",
    description="Multi-Agent Orchestration Engine with Built-in Governance",
    version="0.4.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)



@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "havenkeep-backend",
        "environment": settings.environment,
        "database": settings.database_url.split(":")[0]
    }

@app.get("/api/config")
async def get_system_config():
    return {
        "soft_budget_usd": settings.session_soft_budget_usd,
        "hard_budget_usd": settings.session_hard_budget_usd,
        "supervisor_model": settings.supervisor_model,
        "planner_model": settings.planner_model,
        "worker_model": settings.worker_model,
        "critic_model": settings.critic_model,
    }
