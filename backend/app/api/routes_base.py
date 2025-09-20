"""
Base API Routes

Contains foundational API endpoints that don't belong to specific feature modules.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..core.database import get_db_session, database_manager
from ..core.config import settings

router = APIRouter()


@router.get("/info")
async def get_app_info():
    """Get application information"""
    return {
        "app_name": settings.app_name,
        "version": settings.version,
        "environment": settings.environment,
        "debug": settings.debug,
        "features": {
            "ai_enabled": bool(settings.google_api_key),
            "database_connected": database_manager.is_connected,
            "cache_enabled": bool(settings.redis_url)
        }
    }


@router.get("/database/health")
async def check_database_health():
    """Check database connection health"""
    health_status = await database_manager.health_check()
    
    if health_status["status"] == "error":
        raise HTTPException(status_code=503, detail=health_status["message"])
    
    return health_status


@router.post("/database/reset")
async def reset_database():
    """Reset database by dropping all user tables (keeping system tables)"""
    try:
        async with database_manager.get_session() as session:
            # Get all user tables (excluding sqlite_* system tables)
            result = await session.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """))
            tables = [row[0] for row in result.fetchall()]
            
            # Drop all user tables
            for table_name in tables:
                await session.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
            
            # Drop all indexes
            result = await session.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND name NOT LIKE 'sqlite_%'
            """))
            indexes = [row[0] for row in result.fetchall()]
            
            for index_name in indexes:
                await session.execute(text(f'DROP INDEX IF EXISTS "{index_name}"'))
            
            await session.commit()
            
            return {
                "success": True,
                "message": f"Database reset successfully. Dropped {len(tables)} tables and {len(indexes)} indexes.",
                "dropped_tables": tables,
                "dropped_indexes": indexes
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to reset database: {str(e)}"
        }


@router.get("/database/tables")
async def list_all_tables():
    """List all tables in the database including system tables"""
    try:
        async with database_manager.get_session() as session:
            result = await session.execute(text("""
                SELECT name, type FROM sqlite_master 
                WHERE type IN ('table', 'view')
                ORDER BY name
            """))
            objects = [{"name": row[0], "type": row[1]} for row in result.fetchall()]
            
            return {
                "success": True,
                "objects": objects,
                "count": len(objects)
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to list tables: {str(e)}"
        }
        
        return {
            "status": "success",
            "message": "Database connection working",
            "test_result": test_value
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection failed: {str(e)}"
        )