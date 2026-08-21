"""Aggregated v1 API router.

This module imports all individual route modules and combines them
into a single v1 router with the /api/v1 prefix.

Why aggregate routers?
- Single import in main.py (clean entry point)
- Easy to add/remove feature routes
- Consistent prefix for all v1 endpoints
- Mirrors how large FastAPI apps are structured
"""

from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.chat import router as chat_router

# Create the v1 aggregated router
v1_router = APIRouter(prefix="/api/v1")

# Include all feature routers
v1_router.include_router(health_router)
v1_router.include_router(chat_router)
