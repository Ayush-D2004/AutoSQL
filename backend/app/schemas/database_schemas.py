"""
Database API Schemas

Pydantic models for request/response validation in database operations.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional, Union
from datetime import datetime


class ExecuteQueryRequest(BaseModel):
    """Request model for SQL query execution"""
    sql: str = Field(..., description="SQL query to execute", min_length=1)
    parameters: Optional[Dict[str, Any]] = Field(None, description="Query parameters")
    auto_commit: bool = Field(True, description="Whether to auto-commit transaction")
    safety_check: bool = Field(True, description="Whether to perform safety checks")
    save_to_history: bool = Field(True, description="Whether to save to query history")
    session_id: Optional[str] = Field(None, description="Session identifier")
    
    @validator('sql')
    def validate_sql(cls, v):
        if not v or not v.strip():
            raise ValueError("SQL query cannot be empty")
        return v.strip()


class ExecuteQueryResponse(BaseModel):
    """Response model for SQL query execution"""
    success: bool = Field(..., description="Whether query executed successfully")
    query: str = Field(..., description="The executed SQL query")
    execution_time_ms: float = Field(..., description="Execution time in milliseconds")
    rows: List[Dict[str, Any]] = Field(default_factory=list, description="Query result rows")
    columns: List[str] = Field(default_factory=list, description="Column names")
    row_count: int = Field(0, description="Number of rows returned")
    affected_rows: int = Field(0, description="Number of rows affected")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    error_type: Optional[str] = Field(None, description="Error type")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    timestamp: datetime = Field(..., description="Execution timestamp")


class BatchExecuteRequest(BaseModel):
    """Request model for batch query execution"""
    queries: List[str] = Field(..., description="List of SQL queries to execute", min_items=1)
    use_transaction: bool = Field(True, description="Execute all in single transaction")
    stop_on_error: bool = Field(True, description="Stop execution on first error")
    save_to_history: bool = Field(True, description="Save all queries to history")
    session_id: Optional[str] = Field(None, description="Session identifier")
    
    @validator('queries')
    def validate_queries(cls, v):
        if not v:
            raise ValueError("At least one query is required")
        
        cleaned_queries = []
        for query in v:
            if not query or not query.strip():
                raise ValueError("Empty queries are not allowed")
            cleaned_queries.append(query.strip())
        
        return cleaned_queries


class ColumnInfo(BaseModel):
    """Model for table column information"""
    name: str = Field(..., description="Column name")
    type: str = Field(..., description="Column data type")
    nullable: bool = Field(True, description="Whether column allows NULL")
    default: Optional[Any] = Field(None, description="Default value")
    position: Optional[int] = Field(None, description="Column position")


class ForeignKeyInfo(BaseModel):
    """Model for foreign key information"""
    constrained_columns: List[str] = Field(..., description="Columns in this table")
    referred_table: str = Field(..., description="Referenced table name")
    referred_columns: List[str] = Field(..., description="Referenced columns")
    name: Optional[str] = Field(None, description="Foreign key constraint name")


class IndexInfo(BaseModel):
    """Model for index information"""
    name: str = Field(..., description="Index name")
    unique: bool = Field(False, description="Whether index is unique")
    columns: List[str] = Field(default_factory=list, description="Indexed columns")


class TableInfo(BaseModel):
    """Model for table information"""
    name: str = Field(..., description="Table name")
    schema_name: Optional[str] = Field(None, description="Schema name")
    columns: List[ColumnInfo] = Field(default_factory=list, description="Table columns")
    primary_keys: List[str] = Field(default_factory=list, description="Primary key columns")
    foreign_keys: List[ForeignKeyInfo] = Field(default_factory=list, description="Foreign keys")
    indexes: List[IndexInfo] = Field(default_factory=list, description="Table indexes")
    comment: Optional[str] = Field(None, description="Table comment")
    column_count: int = Field(0, description="Number of columns")
    has_primary_key: bool = Field(False, description="Whether table has primary key")
    has_foreign_keys: bool = Field(False, description="Whether table has foreign keys")


class SchemaResponse(BaseModel):
    """Response model for database schema"""
    database_name: str = Field(..., description="Database name")
    tables: List[TableInfo] = Field(default_factory=list, description="Database tables")
    views: List[str] = Field(default_factory=list, description="Database views")
    schemas: List[str] = Field(default_factory=list, description="Available schemas")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Database metadata")
    timestamp: datetime = Field(..., description="Schema retrieval timestamp")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Schema summary")


class QueryHistoryRecord(BaseModel):
    """Model for query history record"""
    id: int = Field(..., description="History record ID")
    query_text: str = Field(..., description="Executed SQL query")
    query_type: Optional[str] = Field(None, description="Query type")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Query parameters")
    success: bool = Field(..., description="Whether query succeeded")
    execution_time_ms: Optional[float] = Field(None, description="Execution time")
    row_count: Optional[int] = Field(None, description="Rows returned/affected")
    affected_rows: Optional[int] = Field(None, description="Rows affected")
    error_message: Optional[str] = Field(None, description="Error message")
    error_type: Optional[str] = Field(None, description="Error type")
    database_name: Optional[str] = Field(None, description="Database name")
    schema_name: Optional[str] = Field(None, description="Schema name")
    user_context: Optional[Dict[str, Any]] = Field(None, description="User context")
    created_at: datetime = Field(..., description="Execution timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class QueryHistoryResponse(BaseModel):
    """Response model for query history"""
    records: List[QueryHistoryRecord] = Field(default_factory=list, description="History records")
    count: int = Field(0, description="Number of records returned")
    limit: int = Field(..., description="Query limit")
    offset: int = Field(..., description="Query offset")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Applied filters")


class DatabaseConnectionTest(BaseModel):
    """Model for database connection test result"""
    connection_status: str = Field(..., description="Connection status")
    test_query_success: bool = Field(..., description="Whether test query succeeded")
    execution_time_ms: Optional[float] = Field(None, description="Test query execution time")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    timestamp: datetime = Field(..., description="Test timestamp")


class MermaidERD(BaseModel):
    """Model for Mermaid ERD response"""
    mermaid_syntax: str = Field(..., description="Mermaid ERD syntax")
    generated_at: datetime = Field(..., description="Generation timestamp")


class QueryStatistics(BaseModel):
    """Model for query execution statistics"""
    period_days: int = Field(..., description="Statistics period in days")
    total_queries: int = Field(0, description="Total number of queries")
    successful_queries: int = Field(0, description="Number of successful queries")
    failed_queries: int = Field(0, description="Number of failed queries")
    success_rate: float = Field(0.0, description="Success rate percentage")
    average_execution_time_ms: float = Field(0.0, description="Average execution time")
    query_types: Dict[str, int] = Field(default_factory=dict, description="Query types distribution")


class HistoryCleanupResponse(BaseModel):
    """Response model for history cleanup operation"""
    deleted_count: int = Field(0, description="Number of deleted records")
    days_kept: int = Field(..., description="Days of history kept")
    cleanup_timestamp: datetime = Field(..., description="Cleanup timestamp")