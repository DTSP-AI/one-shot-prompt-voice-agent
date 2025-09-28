from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging
from core.config import settings
from api import agents, livekit, voice, health, mcp, feedback
from services.reflection_service import reflection_service

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

    # Start reflection service for RL/learning layer
    try:
        reflection_service.start()
        logger.info("Reflection service started successfully")
    except Exception as e:
        logger.error(f"Failed to start reflection service: {e}")

    yield
    # Shutdown
    logger.info("Shutting down...")

    # Stop reflection service
    try:
        reflection_service.stop()
        logger.info("Reflection service stopped")
    except Exception as e:
        logger.error(f"Error stopping reflection service: {e}")

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
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "X-CSRF-Token",
    ],
)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(agents.router, tags=["agents"])  # Unified agent API (management + runtime)
app.include_router(livekit.router, prefix="/api/v1/livekit", tags=["livekit"])
app.include_router(voice.router, prefix="/api/v1/voices", tags=["voice"])
app.include_router(mcp.router, prefix="/api/v1/mcp", tags=["mcp"])
app.include_router(feedback.router, tags=["feedback", "rl"])

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