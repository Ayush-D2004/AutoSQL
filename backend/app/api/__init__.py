"""
API Router Configuration

Main router that includes all API endpoints and organizes them into logical groups.
"""

from fastapi import APIRouter

# Import route modules
from .routes_base import router as base_router
from .routes_database import router as database_router
from .routes_ai import router as ai_router
# Future imports:
# from .routes import auth

# Create main API router
router = APIRouter()

# Health check endpoints at API level
@router.get("/ping")
async def api_ping():
    """API-level ping endpoint"""
    return {"message": "API is running", "version": "2.0.0"}

@router.get("/status")
async def api_status():
    """API status with more details"""
    return {
        "api": "running",
        "version": "2.0.0",
        "endpoints": {
            "health": "/health",
            "ping": "/ping",
            "docs": "/docs",
            "ai": "/api/ai (coming soon)",
            "database": "/api/database (coming soon)",
            "schema": "/api/schema (coming soon)"
        }
    }

# Include route modules
router.include_router(base_router, tags=["Base"])
router.include_router(database_router, prefix="/db", tags=["Database"])
router.include_router(ai_router, prefix="/ai", tags=["AI"])

# Future route inclusions (will be uncommented as we build them)
# router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
# router.include_router(ai.router, prefix="/ai", tags=["AI & Machine Learning"])