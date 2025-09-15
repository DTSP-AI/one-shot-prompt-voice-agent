from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any
import httpx
import asyncio
from core.config import settings

router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    services: Dict[str, str]
    version: str = "1.0.0"

class ServiceStatus(BaseModel):
    status: str
    latency_ms: float
    error: str = None

async def check_service_health(service_name: str, health_check_func) -> ServiceStatus:
    """Generic service health check wrapper"""
    start_time = datetime.now()
    try:
        result = await health_check_func()
        latency = (datetime.now() - start_time).total_seconds() * 1000
        return ServiceStatus(
            status="healthy" if result else "unhealthy",
            latency_ms=round(latency, 2)
        )
    except Exception as e:
        latency = (datetime.now() - start_time).total_seconds() * 1000
        return ServiceStatus(
            status="error",
            latency_ms=round(latency, 2),
            error=str(e)
        )

async def check_openai_health() -> bool:
    """Check OpenAI API connectivity"""
    if not settings.OPENAI_API_KEY:
        return False
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                timeout=5.0
            )
            return response.status_code == 200
    except:
        return False

async def check_deepgram_health() -> bool:
    """Check Deepgram API connectivity"""
    if not settings.DEEPGRAM_API_KEY:
        return False
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.deepgram.com/v1/projects",
                headers={"Authorization": f"Token {settings.DEEPGRAM_API_KEY}"},
                timeout=5.0
            )
            return response.status_code == 200
    except:
        return False

async def check_elevenlabs_health() -> bool:
    """Check ElevenLabs API connectivity"""
    if not settings.ELEVENLABS_API_KEY:
        return False
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": settings.ELEVENLABS_API_KEY},
                timeout=5.0
            )
            return response.status_code == 200
    except:
        return False

async def check_livekit_health() -> bool:
    """Check LiveKit service availability"""
    if not settings.LIVEKIT_URL or not settings.LIVEKIT_API_KEY:
        return False
    # For WebSocket services, just check if config is present
    return bool(settings.LIVEKIT_URL and settings.LIVEKIT_API_KEY and settings.LIVEKIT_API_SECRET)

@router.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check endpoint"""

    # Perform service checks in parallel
    service_checks = {
        "openai": check_openai_health(),
        "deepgram": check_deepgram_health(),
        "elevenlabs": check_elevenlabs_health(),
        "livekit": check_livekit_health()
    }

    service_results = {}
    try:
        # Run all health checks concurrently with timeout
        results = await asyncio.wait_for(
            asyncio.gather(*[
                check_service_health(name, check_func)
                for name, check_func in service_checks.items()
            ], return_exceptions=True),
            timeout=10.0
        )

        for i, (service_name, _) in enumerate(service_checks.items()):
            if isinstance(results[i], ServiceStatus):
                service_results[service_name] = results[i].status
            else:
                service_results[service_name] = "error"

    except asyncio.TimeoutError:
        # If health checks timeout, mark all as timeout
        service_results = {name: "timeout" for name in service_checks.keys()}

    # Determine overall status
    all_healthy = all(status == "healthy" for status in service_results.values())
    overall_status = "healthy" if all_healthy else "degraded"

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat(),
        services=service_results
    )

@router.get("/health")
async def simple_health_check():
    """Simple health check for container health checks"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}