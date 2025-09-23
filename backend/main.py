"""
AutoSQL Backend - AI-Powered SQL Query Processing

This backend provides AI-powered SQL query generation, execution, and visualization
using Google Gemini and LangGraph for complex workflow management.

Features:
- Natural language to SQL conversion using Gemini
- Complex query processing with LangGraph workflows
- Database schema analysis and visualization
- Query optimization and explanation
- Multi-database support (PostgreSQL, MySQL, SQLite)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import os

# Import application modules
from app.core.config import settings
from app.core.database import database_manager, create_tables
from app.services.conversation_memory import conversation_memory
from app.api import router as api_router

# Import models to ensure they're registered with SQLAlchemy before table creation
import app.models

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print("🚀 AutoSQL Backend starting up...")
    print(f"Environment: {settings.environment}")
    print(f"Debug mode: {settings.debug}")
    
    # Initialize database
    await database_manager.initialize()
    print("✅ Database connection initialized")
    
    # Create database tables
    try:
        await create_tables()
        print("✅ Database tables created/verified")
    except Exception as e:
        print(f"⚠️ Database table creation warning: {e}")
    
    # Initialize conversation memory service
    try:
        await conversation_memory.initialize()
        print("✅ Conversation memory service initialized")
    except Exception as e:
        print(f"⚠️ Conversation memory initialization warning: {e}")
    
    yield
    
    # Shutdown
    print("🔒 AutoSQL Backend shutting down...")
    await database_manager.close()
    print("✅ Database connection closed")

# Create FastAPI application
app = FastAPI(
    title="AutoSQL AI Backend",
    description="AI-powered SQL query processing with Gemini and LangGraph",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
cors_origins = settings.get_cors_origins()
print(f"CORS Origins configured: {cors_origins}")  # Debug log

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,  # Use explicit list of origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "AutoSQL AI Backend is running!",
        "version": settings.version,
        "status": "healthy",
        "docs": "/docs",
        "api": "/api"
    }

@app.get("/ping")
async def ping():
    """Simple ping endpoint for health checks"""
    return {"message": "pong"}

@app.get("/health")
async def health_check():
    """Detailed health check"""
    db_status = "connected" if database_manager.is_connected else "disconnected"
    
    return {
        "status": "healthy",
        "environment": settings.environment,
        "version": settings.version,
        "services": {
            "database": db_status,
            "ai": "ready",
            "langraph": "ready"
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )