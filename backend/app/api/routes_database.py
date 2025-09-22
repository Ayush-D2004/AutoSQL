"""
Database API Routes

Provides REST endpoints for database operations including:
- SQL query execution
- Schema introspection  
- Query history management
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from ..database.sql_executor import db_executor, SQLExecutionResult
from ..database.schema_inspector import schema_inspector
from ..database.history_service import history_service
from ..database.schema_visualizer import schema_visualizer, schema_to_mermaid_mindmap
from ..schemas.database_schemas import (
    ExecuteQueryRequest,
    ExecuteQueryResponse,
    SchemaResponse,
    QueryHistoryResponse,
    BatchExecuteRequest
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/execute", response_model=ExecuteQueryResponse)
async def execute_sql_query(
    request: ExecuteQueryRequest
) -> ExecuteQueryResponse:
    """
    Execute SQL query(s) and return results
    
    Supports both single and multiple SQL statements.
    Multiple statements are executed in a transaction.
    
    - **sql**: The SQL query or queries to execute (separated by semicolons)
    - **parameters**: Optional query parameters
    - **save_to_history**: Whether to save to query history (default: True)
    - **auto_commit**: Whether to auto-commit transaction (default: True)
    """
    try:
        # Use smart execution to handle single or multiple statements with auto-preprocessing
        results = await db_executor.execute_sql_smart(
            sql_text=request.sql,
            parameters=request.parameters,
            auto_commit=request.auto_commit,
            safety_check=request.safety_check,
            auto_preprocess=True  # Enable auto-preprocessing for clean table state
        )
        
        # Save all results to history if requested
        if request.save_to_history:
            for result in results:
                await history_service.save_query_result(
                    result,
                    session_id=request.session_id,
                    user_context={"endpoint": "execute", "multi_statement": len(results) > 1}
                )
        
        # For multiple statements, return the result of the last SELECT statement
        # or the last statement if no SELECT statements
        select_results = [r for r in results if r.metadata.get("query_type") == "SELECT"]
        
        # Collect ALL SELECT results for table display (similar to AI endpoint)
        table_results = []
        seen_results = set()  # Track unique result sets to avoid duplicates
        
        for i, result in enumerate(results):
            if result.success and result.rows:  # This is a SELECT query with data
                # Create a unique identifier for this result set
                result_hash = hash((
                    tuple(result.columns) if result.columns else (),
                    tuple(tuple(row.values()) if isinstance(row, dict) else tuple(row) for row in result.rows[:10])  # Use first 10 rows for hash
                ))
                
                # Only add if we haven't seen this exact result before
                if result_hash not in seen_results:
                    seen_results.add(result_hash)
                    
                    # Generate a meaningful table name
                    query_text = result.query.strip()
                    table_name = f"Query {len(table_results) + 1}"
                    
                    # Try to extract table name from SELECT statement
                    if query_text.upper().startswith('SELECT'):
                        import re
                        # Look for FROM clause
                        from_match = re.search(r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)', query_text, re.IGNORECASE)
                        if from_match:
                            table_name = f"{from_match.group(1)} ({len(table_results) + 1})"
                    
                    table_results.append({
                        "columns": result.columns,
                        "rows": result.rows,
                        "row_count": result.row_count,
                        "affected_rows": result.affected_rows,
                        "execution_time_ms": result.execution_time_ms,
                        "query": result.query,
                        "query_type": result.metadata.get("query_type", "SELECT"),
                        "table_name": table_name
                    })

        if select_results:
            # Return the last SELECT result (most likely what user wants to see)
            primary_result = select_results[-1]
        else:
            # Return the last statement result
            primary_result = results[-1]

        # Always add table_results metadata for consistency
        primary_result.metadata["table_results"] = table_results
        
        # Add metadata about multiple statements
        if len(results) > 1:
            primary_result.metadata["total_statements"] = len(results)
            primary_result.metadata["all_successful"] = all(r.success for r in results)
            primary_result.metadata["statement_types"] = [r.metadata.get("query_type", "UNKNOWN") for r in results]
        
        # Return response based on primary result
        return ExecuteQueryResponse(
            success=primary_result.success,
            query=primary_result.query,
            execution_time_ms=primary_result.execution_time_ms,
            rows=primary_result.rows,
            columns=primary_result.columns,
            row_count=primary_result.row_count,
            affected_rows=primary_result.affected_rows,
            error_message=primary_result.error_message,
            error_type=primary_result.error_type,
            metadata=primary_result.metadata,
            timestamp=primary_result.timestamp
        )
        
    except Exception as e:
        logger.error(f"Query execution endpoint failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Query execution failed: {str(e)}"
        )


@router.post("/execute-batch", response_model=List[ExecuteQueryResponse])
async def execute_batch_queries(
    request: BatchExecuteRequest
) -> List[ExecuteQueryResponse]:
    """
    Execute multiple SQL queries in batch
    
    - **queries**: List of SQL queries to execute
    - **use_transaction**: Whether to execute all in single transaction
    - **stop_on_error**: Whether to stop execution on first error
    """
    try:
        responses = []
        
        if request.use_transaction:
            # Execute all queries in transaction
            results = await db_executor.execute_multiple_sql(
                request.queries,
                use_transaction=True
            )
        else:
            # Execute queries individually
            results = []
            for query in request.queries:
                result = await db_executor.execute_sql(query)
                results.append(result)
                
                # Stop on error if requested
                if not result.success and request.stop_on_error:
                    break
        
        # Convert results to responses and save to history
        for result in results:
            if request.save_to_history:
                await history_service.save_query_result(
                    result,
                    session_id=request.session_id,
                    user_context={"endpoint": "execute-batch"}
                )
            
            responses.append(ExecuteQueryResponse(
                success=result.success,
                query=result.query,
                execution_time_ms=result.execution_time_ms,
                rows=result.rows,
                columns=result.columns,
                row_count=result.row_count,
                affected_rows=result.affected_rows,
                error_message=result.error_message,
                error_type=result.error_type,
                metadata=result.metadata,
                timestamp=result.timestamp
            ))
        
        return responses
        
    except Exception as e:
        logger.error(f"Batch execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Batch execution failed: {str(e)}"
        )


@router.get("/schema", response_model=SchemaResponse)
async def get_database_schema(
    schema_name: Optional[str] = Query(None, description="Specific schema to inspect")
) -> SchemaResponse:
    """
    Get complete database schema information
    
    Returns table structures, relationships, and metadata for schema visualization
    """
    try:
        # Get schema information
        schema = await schema_inspector.get_full_schema(schema_name)
        
        return SchemaResponse(
            database_name=schema.database_name,
            tables=schema.tables,
            views=schema.views,
            schemas=schema.schemas,
            metadata=schema.metadata,
            timestamp=schema.timestamp,
            summary={
                "table_count": len(schema.tables),
                "view_count": len(schema.views),
                "schema_count": len(schema.schemas),
                "total_columns": sum(len(table.columns) for table in schema.tables)
            }
        )
        
    except Exception as e:
        logger.error(f"Schema inspection failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Schema inspection failed: {str(e)}"
        )


@router.get("/schema/table/{table_name}")
async def get_table_schema(
    table_name: str,
    schema_name: Optional[str] = Query(None, description="Schema name")
) -> Dict[str, Any]:
    """
    Get detailed information about a specific table
    """
    try:
        table_info = await schema_inspector.get_table_info(table_name, schema_name)
        
        if not table_info:
            raise HTTPException(
                status_code=404,
                detail=f"Table '{table_name}' not found"
            )
        
        return table_info.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Table inspection failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Table inspection failed: {str(e)}"
        )


@router.get("/history", response_model=QueryHistoryResponse)
async def get_query_history(
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of records"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    success_only: Optional[bool] = Query(None, description="Filter by success status"),
    query_type: Optional[str] = Query(None, description="Filter by query type"),
    session_id: Optional[str] = Query(None, description="Filter by session ID")
) -> QueryHistoryResponse:
    """
    Get query execution history with optional filters
    """
    try:
        # Get history records
        history_records = await history_service.get_query_history(
            limit=limit,
            offset=offset,
            success_only=success_only,
            query_type=query_type,
            session_id=session_id
        )
        
        return QueryHistoryResponse(
            records=history_records,
            count=len(history_records),
            limit=limit,
            offset=offset,
            filters={
                "success_only": success_only,
                "query_type": query_type,
                "session_id": session_id
            }
        )
        
    except Exception as e:
        logger.error(f"History retrieval failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"History retrieval failed: {str(e)}"
        )


@router.get("/history/recent")
async def get_recent_queries(
    limit: int = Query(10, ge=1, le=50, description="Number of recent queries")
) -> List[Dict[str, Any]]:
    """
    Get most recent successful queries
    """
    try:
        recent_queries = await history_service.get_recent_queries(limit)
        return recent_queries
        
    except Exception as e:
        logger.error(f"Recent queries retrieval failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Recent queries retrieval failed: {str(e)}"
        )


@router.get("/history/statistics")
async def get_query_statistics(
    days: int = Query(7, ge=1, le=365, description="Number of days for statistics")
) -> Dict[str, Any]:
    """
    Get query execution statistics
    """
    try:
        stats = await history_service.get_query_statistics(days)
        return stats
        
    except Exception as e:
        logger.error(f"Statistics retrieval failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Statistics retrieval failed: {str(e)}"
        )


@router.get("/history/search")
async def search_query_history(
    q: str = Query(..., min_length=3, description="Search term"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results")
) -> List[Dict[str, Any]]:
    """
    Search query history by text content
    """
    try:
        search_results = await history_service.search_queries(q, limit)
        return search_results
        
    except Exception as e:
        logger.error(f"History search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"History search failed: {str(e)}"
        )


@router.delete("/history/cleanup")
async def cleanup_old_history(
    days_to_keep: int = Query(30, ge=1, le=365, description="Days of history to keep")
) -> Dict[str, Any]:
    """
    Delete old query history entries
    """
    try:
        deleted_count = await history_service.delete_old_history(days_to_keep)
        
        return {
            "deleted_count": deleted_count,
            "days_kept": days_to_keep,
            "cleanup_timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"History cleanup failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"History cleanup failed: {str(e)}"
        )


@router.get("/test-connection")
async def test_database_connection() -> Dict[str, Any]:
    """
    Test database connection and return status
    """
    try:
        # Test with simple query
        result = await db_executor.execute_sql("SELECT 1 as test_value")
        
        return {
            "connection_status": "healthy" if result.success else "error",
            "test_query_success": result.success,
            "execution_time_ms": result.execution_time_ms,
            "error_message": result.error_message if not result.success else None,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Connection test failed: {e}", exc_info=True)
        return {
            "connection_status": "error",
            "test_query_success": False,
            "error_message": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/schema/mermaid")
async def get_mermaid_schema() -> Dict[str, Any]:
    """
    Generate Mermaid ER diagram from current database schema
    
    Returns:
        Dictionary containing Mermaid diagram string and metadata
    """
    try:
        mermaid_diagram = await schema_visualizer.schema_to_mermaid()
        
        # Check if we have actual tables or just error/empty state
        has_tables = "erDiagram" in mermaid_diagram and "NO_USER_TABLES" not in mermaid_diagram and "NO_TABLES" not in mermaid_diagram and "ERROR" not in mermaid_diagram
        
        return {
            "mermaid": mermaid_diagram,
            "has_tables": has_tables,
            "generated_at": datetime.utcnow().isoformat(),
            "message": "Schema diagram generated successfully" if has_tables else "No tables found in database",
            "type": "er"
        }
        
    except Exception as e:
        logger.error(f"Mermaid schema generation failed: {e}", exc_info=True)
        return {
            "mermaid": f"erDiagram\n    ERROR {{\n        string error \"Schema generation failed: {str(e)}\"\n    }}",
            "has_tables": False,
            "generated_at": datetime.utcnow().isoformat(),
            "message": f"Schema generation failed: {str(e)}",
            "type": "er"
        }


@router.get("/schema/mindmap")
async def get_mindmap_schema() -> Dict[str, Any]:
    """
    Generate Mermaid mindmap from current database schema
    
    Returns:
        Dictionary containing Mermaid mindmap string and metadata
    """
    try:
        mermaid_diagram = await schema_to_mermaid_mindmap()
        
        # Check if we have actual tables or just error/empty state
        has_tables = "mindmap" in mermaid_diagram and "NO_TABLES" not in mermaid_diagram and "ERROR" not in mermaid_diagram
        
        return {
            "mermaid": mermaid_diagram,
            "has_tables": has_tables,
            "generated_at": datetime.utcnow().isoformat(),
            "message": "Schema mindmap generated successfully" if has_tables else "No tables found in database",
            "type": "mindmap"
        }
        
    except Exception as e:
        logger.error(f"Mermaid mindmap generation failed: {e}", exc_info=True)
        return {
            "mermaid": f"mindmap\n  root((Database Schema))\n    ERROR[Schema generation failed: {str(e)}]",
            "has_tables": False,
            "generated_at": datetime.utcnow().isoformat(),
            "message": f"Schema mindmap generation failed: {str(e)}",
            "type": "mindmap"
        }