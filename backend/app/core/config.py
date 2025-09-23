"""
Configuration settings for AutoSQL Backend
"""
import os
from typing import List, Any, Optional
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, ConfigDict
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()


class Settings(BaseSettings):
    """Application settings"""
    
    # Basic app configuration
    app_name: str = "AutoSQL Backend"
    version: str = "1.0.0"
    environment: str = "development"
    debug: bool = True
    is_production: bool = False
    
    # API configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"
    
    # Frontend configuration
    frontend_url: str = "http://localhost:3000"
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000,https://localhost:3000"
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # CORS settings
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001"
    ]
    
    # Production CORS origins (set via environment variables)
    production_frontend_url: Optional[str] = None
    
    # Database configuration
    database_url: str = "sqlite:///./autosql.db"
    database_echo: bool = False
    
    # AI/LLM Configuration
    google_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    gemini_model: str = "gemini-1.5-flash"
    
    # LangGraph Configuration
    langraph_checkpoint_store: str = "memory"
    langraph_max_iterations: int = 10
    
    # Security
    secret_key: str = "your-secret-key-here-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Rate Limiting
    rate_limit_requests_per_minute: int = 60
    
    # Cache Configuration
    cache_ttl: int = 3600
    
    # File Upload Configuration
    max_file_size: int = 10485760  # 10MB
    upload_dir: str = "./uploads"
    
    # External APIs
    allow_external_db_connections: bool = True
    max_query_execution_time: int = 30  # seconds
    
    model_config = ConfigDict(
        case_sensitive=False,
        env_file=".env",
        extra="ignore"  # Allow extra fields from environment
    )
    
    def get_cors_origins(self) -> List[str]:
        """Get CORS origins including development URLs"""
        origins = self.cors_origins.copy()
        
        # Parse allowed_origins from environment
        if self.allowed_origins:
            env_origins = [origin.strip() for origin in self.allowed_origins.split(",")]
            for origin in env_origins:
                if origin not in origins:
                    origins.append(origin)
        
        # Add production frontend URL if specified
        if self.production_frontend_url:
            if self.production_frontend_url not in origins:
                origins.append(self.production_frontend_url)
        
        if self.environment == "development":
            # Add additional development origins
            dev_origins = [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:3001", 
                "http://127.0.0.1:3001",
                "http://localhost:8080",
                "http://127.0.0.1:8080"
            ]
            for origin in dev_origins:
                if origin not in origins:
                    origins.append(origin)
        else:
            # In production, be more restrictive but allow common patterns
            production_patterns = [
                "https://*.vercel.app",
                "https://*.netlify.app", 
                "https://*.onrender.com"
            ]
            # Note: FastAPI doesn't support wildcards in CORS origins
            # You'll need to set specific URLs via environment variables
            
        return origins


# Create settings instance
settings = Settings()