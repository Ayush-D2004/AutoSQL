"""
Database Models for Query History and Application Data

This module defines SQLAlchemy models for storing:
- Query execution history
- User sessions
- Application metadata
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, JSON
from sqlalchemy.sql import func
from datetime import datetime
from typing import Dict, Any, Optional

from ..core.database import Base


class QueryHistory(Base):
    """
    Model for storing executed query history
    
    Tracks all SQL queries executed through the system for:
    - Query history display in frontend
    - Performance analysis
    - Debugging and auditing
    """
    __tablename__ = "query_history"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Query information
    query_text = Column(Text, nullable=False, comment="The SQL query that was executed")
    query_type = Column(String(50), nullable=True, comment="Type of query (SELECT, INSERT, etc.)")
    
    # Execution results
    success = Column(Boolean, nullable=False, comment="Whether query executed successfully")
    execution_time_ms = Column(Float, nullable=True, comment="Query execution time in milliseconds")
    row_count = Column(Integer, nullable=True, comment="Number of rows returned")
    affected_rows = Column(Integer, nullable=True, comment="Number of rows affected by query")
    
    # Error information
    error_message = Column(Text, nullable=True, comment="Error message if query failed")
    error_type = Column(String(100), nullable=True, comment="Type of error that occurred")
    
    # Context
    database_name = Column(String(100), nullable=True, comment="Database where query was executed")
    schema_name = Column(String(100), nullable=True, comment="Schema where query was executed")
    user_context = Column(JSON, nullable=True, comment="User context and session information")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="When query was executed")
    
    # Additional metadata
    query_metadata = Column(JSON, nullable=True, comment="Additional query metadata")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "query_text": self.query_text,
            "query_type": self.query_type,
            "success": self.success,
            "execution_time_ms": self.execution_time_ms,
            "row_count": self.row_count,
            "affected_rows": self.affected_rows,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "database_name": self.database_name,
            "schema_name": self.schema_name,
            "user_context": self.user_context,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "query_metadata": self.query_metadata
        }
    
    @classmethod
    def from_execution_result(cls, result, additional_context: Optional[Dict] = None):
        """Create QueryHistory instance from SQLExecutionResult"""
        return cls(
            query_text=result.query,
            query_type=result.metadata.get("query_type") if result.metadata else None,
            success=result.success,
            execution_time_ms=result.execution_time_ms,
            row_count=result.row_count,
            affected_rows=result.affected_rows,
            error_message=result.error_message,
            error_type=result.error_type,
            user_context=additional_context or {},
            query_metadata=result.metadata
        )


class SessionInfo(Base):
    """
    Model for storing user session information
    """
    __tablename__ = "session_info"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, index=True, nullable=False)
    
    # Session data
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_preferences = Column(JSON, nullable=True)
    
    # Activity tracking
    query_count = Column(Integer, default=0)
    last_activity = Column(DateTime(timezone=True), server_default=func.now())
    
    # Session lifecycle
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)


class DatabaseConnection(Base):
    """
    Model for storing saved database connections
    """
    __tablename__ = "database_connections"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Connection details
    name = Column(String(100), nullable=False, comment="User-friendly name for the connection")
    database_type = Column(String(50), nullable=False, comment="Database type (postgres, mysql, sqlite)")
    host = Column(String(255), nullable=True)
    port = Column(Integer, nullable=True)
    database_name = Column(String(100), nullable=True)
    username = Column(String(100), nullable=True)
    
    # Security note: passwords should be encrypted before storage
    password_encrypted = Column(Text, nullable=True, comment="Encrypted password")
    
    # Connection settings
    connection_params = Column(JSON, nullable=True, comment="Additional connection parameters")
    is_default = Column(Boolean, default=False, comment="Whether this is the default connection")
    is_active = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used = Column(DateTime(timezone=True), nullable=True)


class SystemMetadata(Base):
    """
    Model for storing system-wide metadata and configuration
    """
    __tablename__ = "system_metadata"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=True)
    description = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
