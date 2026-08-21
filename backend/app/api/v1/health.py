"""Health check endpoint.

Every production API needs a health check for:
- Load balancers (AWS ALB, GCP LB) to determine if the instance is healthy
- Monitoring systems to detect outages
- Docker HEALTHCHECK commands
- Kubernetes readiness/liveness probes
- Developers to verify the server is running

We expose two checks:
1. /health — basic liveness (is the server running?)
2. /health/ready — readiness (can it handle requests? is the DB connected?)
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str
    environment: str
    version: str = "0.1.0"
    timestamp: str


class ReadinessResponse(BaseModel):
    """Readiness check response with dependency status."""
    status: str
    database: str
    timestamp: str


@router.get("/health", response_model=HealthResponse)
async def health_check(
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Basic liveness check.

    Returns 200 if the server process is running.
    Does NOT check dependencies (database, external APIs).
    Use /health/ready for dependency checks.
    """
    return HealthResponse(
        status="healthy",
        environment=settings.environment,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check(
    db: AsyncSession = Depends(get_db_session),
) -> ReadinessResponse:
    """Readiness check — verifies all dependencies are available.

    Checks:
    - Database connectivity (executes SELECT 1)

    Returns 200 only if ALL dependencies are healthy.
    Returns 503 if any dependency is unavailable.
    """
    # Check database connectivity
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    overall = "ready" if db_status == "healthy" else "not_ready"

    return ReadinessResponse(
        status=overall,
        database=db_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
