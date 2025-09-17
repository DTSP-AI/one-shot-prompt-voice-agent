from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging
from core.config import settings
from api import agents, livekit, voice, health, mcp, agent_api

# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lifespan manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting OneShotVoiceAgent...")
    logger.info(f"Environment: {'Development' if settings.DEBUG else 'Production'}")
    logger.info(f"CORS Origins: {settings.BACKEND_CORS_ORIGINS}")

    # Initialize services, validate environment
    validation = settings.validate_required_services()
    if not validation["valid"]:
        logger.error(f"Configuration errors: {validation['errors']}")

    yield
    # Shutdown
    logger.info("Shutting down...")

app = FastAPI(
    title="OneShotVoiceAgent API",
    description="AI agent with real-time voice capabilities",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(agent_api.router, tags=["agent"])  # New centralized agent API
app.include_router(livekit.router, prefix="/api/v1/livekit", tags=["livekit"])
app.include_router(voice.router, prefix="/api/v1/voices", tags=["voice"])
app.include_router(mcp.router, prefix="/api/v1/mcp", tags=["mcp"])

@app.get("/")
async def root():
    return {
        "message": "OneShotVoiceAgent API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )