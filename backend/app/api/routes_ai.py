"""
AI API Routes

Provides REST endpoints for AI-powered natural language to SQL processing.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, File, UploadFile, Form
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
from sqlalchemy import text

from ..ai.langgraph import sql_workflow
from ..ai.gemini import generate_sql_from_prompt, gemini_generator
from ..database.schema_inspector import schema_inspector
from ..database.sql_executor import db_executor
from ..services.conversation_memory import conversation_memory, MessageType
from ..core.config import settings
from ..core.database import database_manager

logger = logging.getLogger(__name__)

router = APIRouter()


async def _reset_database():
    """Reset database by dropping all user tables"""
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
            
            await session.commit()
            return True, tables
    except Exception as e:
        logger.error(f"Database reset failed: {e}")
        return False, []


@router.get("/config")
async def get_ai_config():
    """Get current AI configuration"""
    return {
        "gemini_model": settings.gemini_model,
        "has_api_key": bool(settings.google_api_key),
        "api_key_prefix": settings.google_api_key[:5] + "..." if settings.google_api_key else None
    }


class AIQueryRequest(BaseModel):
    """Request model for AI natural language query"""
    prompt: str = Field(..., description="Natural language query", min_length=1)
    session_id: Optional[str] = Field(None, description="Session identifier")
    max_retries: int = Field(2, description="Maximum retry attempts", ge=0, le=5)
    use_workflow: bool = Field(True, description="Use LangGraph workflow (recommended)")
    reset_database: bool = Field(True, description="Reset database before executing query")
    
    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "Create a table for employees with name, email, and salary",
                "session_id": "user_session_123",
                "max_retries": 2,
                "use_workflow": True,
                "reset_database": True
            }
        }


class AIQueryResponse(BaseModel):
    """Response model for AI natural language query"""
    success: bool = Field(..., description="Whether the query was successful")
    prompt: str = Field(..., description="Original user prompt")
    sql: Optional[str] = Field(None, description="Generated SQL query")
    columns: Optional[list] = Field(None, description="Result columns")
    rows: Optional[list] = Field(None, description="Result rows")
    row_count: int = Field(0, description="Number of rows returned")
    affected_rows: int = Field(0, description="Number of rows affected")
    execution_time_ms: float = Field(0, description="Execution time in milliseconds")
    error: Optional[str] = Field(None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    timestamp: str = Field(..., description="Response timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "prompt": "Show me all employees with salary above 50000",
                "sql": "SELECT * FROM employees WHERE salary > 50000;",
                "columns": ["id", "name", "email", "salary"],
                "rows": [[1, "Alice", "alice@example.com", 60000]],
                "row_count": 1,
                "affected_rows": 0,
                "execution_time_ms": 123.45,
                "error": None,
                "metadata": {"ai_generated": True},
                "timestamp": "2025-09-14T10:30:00Z"
            }
        }


class QuickSQLRequest(BaseModel):
    """Request model for quick SQL generation without execution"""
    prompt: str = Field(..., description="Natural language query", min_length=1)
    include_schema: bool = Field(True, description="Include current schema in context")
    
    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "Create a users table with id, name and email",
                "include_schema": True
            }
        }


class QuickSQLResponse(BaseModel):
    """Response model for quick SQL generation"""
    success: bool = Field(..., description="Whether SQL generation was successful")
    prompt: str = Field(..., description="Original user prompt")
    sql: Optional[str] = Field(None, description="Generated SQL query")
    error: Optional[str] = Field(None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Generation metadata")
    timestamp: str = Field(..., description="Response timestamp")


@router.post("/query", response_model=AIQueryResponse)
async def process_natural_language_query(
    request: AIQueryRequest,
    background_tasks: BackgroundTasks
) -> AIQueryResponse:
    """
    Process a natural language query and execute the generated SQL
    
    This endpoint:
    1. Takes a natural language prompt
    2. Generates SQL using AI (Gemini)
    3. Executes the SQL against the database
    4. Returns both the SQL and execution results
    5. Saves successful queries to history
    
    Use this for the complete AI → SQL → Execute → Results workflow.
    """
    try:
        logger.info(f"Processing AI query: {request.prompt}")
        
        # Initialize conversation memory if needed
        await conversation_memory.initialize()
        
        # Get conversation context
        session_id = request.session_id or f"session_{datetime.utcnow().timestamp()}"
        conversation_context = await conversation_memory.get_context_for_ai(session_id)
        
        # Add user message to conversation history
        await conversation_memory.add_message(
            session_id=session_id,
            message_type=MessageType.USER,
            content=request.prompt,
            metadata={"endpoint": "query", "use_workflow": request.use_workflow}
        )
        
        if request.use_workflow:
            # Use the full LangGraph workflow (recommended)
            result = await sql_workflow.process_natural_language_query(
                prompt=request.prompt,
                session_id=session_id,
                max_retries=request.max_retries
            )
        else:
            # Direct processing without workflow
            result = await _process_direct_query(request, conversation_context)
        
        # Convert to response model
        response = AIQueryResponse(
            success=result.get("success", False),
            prompt=result.get("prompt", request.prompt),
            sql=result.get("sql"),
            columns=result.get("columns", []),
            rows=result.get("rows", []),
            row_count=result.get("row_count", 0),
            affected_rows=result.get("affected_rows", 0),
            execution_time_ms=result.get("execution_time_ms", 0),
            error=result.get("error"),
            metadata=result.get("metadata", {}),
            timestamp=result.get("timestamp", datetime.utcnow().isoformat())
        )
        
        # Add assistant response to conversation history
        await conversation_memory.add_message(
            session_id=session_id,
            message_type=MessageType.ASSISTANT if response.success else MessageType.ERROR,
            content=f"Generated SQL: {response.sql}" if response.success else f"Error: {response.error}",
            sql_query=response.sql,
            execution_result={
                "success": response.success,
                "row_count": response.row_count,
                "affected_rows": response.affected_rows,
                "error": response.error
            },
            metadata={"execution_time_ms": response.execution_time_ms}
        )
        
        logger.info(f"AI query completed. Success: {response.success}")
        return response
        
    except Exception as e:
        logger.error(f"AI query processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"AI query processing failed: {str(e)}"
        )


@router.post("/generate-sql", response_model=QuickSQLResponse)
async def generate_sql_only(request: QuickSQLRequest) -> QuickSQLResponse:
    """
    Generate SQL from natural language without executing it
    
    This endpoint:
    1. Takes a natural language prompt
    2. Generates SQL using AI (Gemini)
    3. Returns the SQL without executing it
    
    Use this when you want to see the SQL before executing it,
    or for educational/debugging purposes.
    """
    try:
        logger.info(f"Generating SQL for prompt: {request.prompt}")
        
        # Get schema if requested
        schema = {}
        if request.include_schema:
            try:
                schema_obj = await schema_inspector.get_full_schema()
                schema = schema_obj.to_dict()
            except Exception as e:
                logger.warning(f"Failed to get schema: {e}")
        
        # Generate SQL
        sql, metadata = await generate_sql_from_prompt(
            prompt=request.prompt,
            schema=schema
        )
        
        response = QuickSQLResponse(
            success=True,
            prompt=request.prompt,
            sql=sql,
            error=None,
            metadata=metadata,
            timestamp=datetime.utcnow().isoformat()
        )
        
        logger.info(f"SQL generation completed: {sql}")
        return response
        
    except Exception as e:
        logger.error(f"SQL generation failed: {e}", exc_info=True)
        return QuickSQLResponse(
            success=False,
            prompt=request.prompt,
            sql=None,
            error=str(e),
            metadata={},
            timestamp=datetime.utcnow().isoformat()
        )


@router.get("/conversation/{session_id}")
async def get_conversation_history(
    session_id: str,
    limit: int = Query(10, ge=1, le=50, description="Maximum number of messages")
) -> Dict[str, Any]:
    """
    Get conversation history for a session
    
    Returns previous messages and context for the AI conversation.
    """
    try:
        await conversation_memory.initialize()
        
        messages = await conversation_memory.get_conversation_history(session_id, limit)
        stats = await conversation_memory.get_session_stats(session_id)
        
        return {
            "session_id": session_id,
            "messages": [
                {
                    "type": msg.type.value,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "sql_query": msg.sql_query,
                    "execution_result": msg.execution_result,
                    "metadata": msg.metadata
                }
                for msg in messages
            ],
            "stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get conversation history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get conversation history: {str(e)}"
        )


@router.delete("/conversation/{session_id}")
async def clear_conversation(
    session_id: str
) -> Dict[str, Any]:
    """
    Clear conversation history for a session
    
    This will reset the conversation context for the AI.
    """
    try:
        await conversation_memory.initialize()
        success = await conversation_memory.clear_session(session_id)
        
        return {
            "success": success,
            "session_id": session_id,
            "message": "Conversation history cleared successfully" if success else "Failed to clear history",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to clear conversation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear conversation: {str(e)}"
        )


@router.post("/cleanup-memory")
async def cleanup_old_conversations(
    hours_old: int = 24
) -> Dict[str, Any]:
    """
    Clean up old conversation memory
    
    This removes conversation history older than the specified hours.
    """
    try:
        await conversation_memory.initialize()
        cleaned_count = await conversation_memory.cleanup_old_sessions(hours_old)
        
        return {
            "success": True,
            "cleaned_sessions": cleaned_count,
            "hours_old": hours_old,
            "message": f"Cleaned up {cleaned_count} old conversation sessions",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup conversations: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cleanup conversations: {str(e)}"
        )


class EnhanceSQLRequest(BaseModel):
    """Request model for enhancing existing SQL code"""
    prompt: str = Field(..., description="Enhancement request", min_length=1)
    current_sql: Optional[str] = Field(None, description="Current SQL code in editor")
    
    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "Add an ORDER BY clause to sort by name",
                "current_sql": "SELECT * FROM users WHERE active = 1;"
            }
        }


@router.post("/enhance-code", response_model=QuickSQLResponse)
async def enhance_sql_code(
    request: EnhanceSQLRequest
) -> QuickSQLResponse:
    """
    Enhance or modify existing SQL code based on user prompt
    
    This endpoint:
    1. Takes a user prompt for modifications
    2. Uses current SQL code from editor as context (not conversation history)
    3. Generates enhanced/modified SQL
    4. Does NOT execute the SQL - user executes manually
    
    Use this for chat-based SQL code enhancement.
    """
    try:
        logger.info(f"Enhancing SQL code with prompt: {request.prompt}")
        
        # Get database schema for context
        schema = await schema_inspector.get_full_schema()
        schema_context = gemini_generator._build_schema_context(schema.to_dict())
        
        # Build context with current SQL code instead of conversation history
        code_context = ""
        if request.current_sql and request.current_sql.strip():
            code_context = f"""
📝 CURRENT SQL CODE IN EDITOR:
{request.current_sql.strip()}

User wants to enhance/modify this code: {request.prompt}

Please generate the enhanced SQL code based on the current code and user's request.
Do NOT execute the code, just provide the enhanced SQL.
"""
        else:
            code_context = f"""
🆕 NO EXISTING CODE
User request: {request.prompt}

Please generate SQL code based on the user's request.
"""
        
        # Generate enhanced SQL
        sql, metadata = await gemini_generator.generate_sql_from_prompt(
            prompt=request.prompt,
            schema=schema.to_dict(),
            conversation_context=code_context,  # Use code context instead of conversation
            max_retries=2
        )
        
        if not sql:
            raise ValueError("Failed to generate enhanced SQL")
        
        response = QuickSQLResponse(
            success=True,
            prompt=request.prompt,
            sql=sql,
            error=None,
            metadata=metadata,
            timestamp=datetime.utcnow().isoformat()
        )
        
        logger.info(f"SQL enhancement completed: {sql}")
        return response
        
    except Exception as e:
        logger.error(f"SQL enhancement failed: {e}", exc_info=True)
        return QuickSQLResponse(
            success=False,
            prompt=request.prompt,
            sql=None,
            error=str(e),
            metadata={},
            timestamp=datetime.utcnow().isoformat()
        )
async def get_ai_capabilities() -> Dict[str, Any]:
    """
    Get information about AI capabilities and configuration
    
    Returns current AI model configuration, available features,
    and example queries that work well.
    """
    from ..core.config import settings
    
    return {
        "ai_enabled": bool(settings.google_api_key),
        "model": settings.gemini_model,
        "features": {
            "natural_language_query": True,
            "sql_generation": True,
            "automatic_execution": True,
            "error_recovery": True,
            "schema_awareness": True,
            "query_history": True
        },
        "supported_operations": [
            "CREATE TABLE",
            "INSERT INTO",
            "SELECT queries",
            "UPDATE statements",
            "DELETE statements",
            "ALTER TABLE",
            "DROP TABLE"
        ],
        "example_prompts": [
            "Create a table for storing user information",
            "Add a new user named Alice with email alice@example.com",
            "Show me all users",
            "Update the salary of employee John to 60000",
            "Delete users who haven't logged in for 6 months",
            "Create an index on the email column",
            "Show me the schema of all tables"
        ],
        "limitations": [
            "SQLite syntax only",
            "No stored procedures",
            "Limited to single database operations",
            "Rate limited by Gemini API"
        ]
    }


async def _process_direct_query(request: AIQueryRequest, conversation_context: str = None) -> Dict[str, Any]:
    """
    Process query directly without LangGraph workflow
    
    Args:
        request: AI query request
        conversation_context: Previous conversation context
        
    Returns:
        Result dictionary
    """
    from ..database.history_service import history_service
    
    try:
        # Reset database if requested
        reset_success = True
        dropped_tables = []
        if request.reset_database:
            reset_success, dropped_tables = await _reset_database()
            if not reset_success:
                logger.warning("Database reset failed, continuing with existing state")
        
        # Get schema (after potential reset)
        schema_obj = await schema_inspector.get_full_schema()
        schema = schema_obj.to_dict()
        
        # Generate SQL
        sql, metadata = await generate_sql_from_prompt(
            prompt=request.prompt,
            schema=schema,
            conversation_context=conversation_context,
            max_retries=request.max_retries
        )
        
        # Split SQL into multiple statements if needed
        sql_statements = db_executor.parse_sql_statements(sql)
        
        if len(sql_statements) == 1:
            # Single statement - use forgiving execution
            result = await db_executor.execute_sql(
                sql=sql_statements[0],
                auto_commit=True,
                safety_check=True,
                forgiving_mode=True
            )
            
            # Build response
            response = {
                "success": result.success,
                "prompt": request.prompt,
                "sql": sql,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {
                    **metadata, 
                    "workflow_used": False,
                    "database_reset": request.reset_database,
                    "reset_success": reset_success,
                    "dropped_tables": dropped_tables
                }
            }
            
            if result.success:
                # Add table results for consistent structure
                table_results = []
                if result.rows:  # This is a SELECT query with data
                    table_results.append({
                        "columns": result.columns,
                        "rows": result.rows,
                        "row_count": result.row_count,
                        "affected_rows": result.affected_rows,
                        "execution_time_ms": result.execution_time_ms,
                        "query": sql_statements[0],
                        "query_type": result.metadata.get("query_type", "SELECT"),
                        "table_name": "Result 1"
                    })
                
                response.update({
                    "columns": result.columns,
                    "rows": result.rows,
                    "row_count": result.row_count,
                    "affected_rows": result.affected_rows,
                    "execution_time_ms": result.execution_time_ms,
                    "table_results": table_results
                })
            else:
                response["error"] = result.error_message
                
        else:
            # Multiple statements - use forgiving execution
            results = await db_executor.execute_multiple_sql(
                sql_statements=sql_statements,
                use_transaction=False,  # No transaction in forgiving mode
                forgiving_mode=True
            )
            
            # Collect ALL results, especially SELECT results for display
            overall_success = all(r.success for r in results)
            total_execution_time = sum(r.execution_time_ms for r in results)
            total_affected_rows = sum(r.affected_rows for r in results)
            
            # Collect all SELECT results for table display
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
                        query_text = sql_statements[i].strip()
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
                            "query": sql_statements[i],
                            "query_type": result.metadata.get("query_type", "SELECT"),
                            "table_name": table_name
                        })
            
            # Get the last successful result for backward compatibility
            display_result = None
            for result in reversed(results):
                if result.success and (result.rows or result.affected_rows > 0):
                    display_result = result
                    break
            
            if not display_result and results:
                display_result = results[-1]  # Use last result
            
            response = {
                "success": overall_success,
                "prompt": request.prompt,
                "sql": sql,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {
                    **metadata, 
                    "workflow_used": False,
                    "database_reset": request.reset_database,
                    "reset_success": reset_success,
                    "dropped_tables": dropped_tables,
                    "statements_executed": len(sql_statements),
                    "individual_results": [
                        {"success": r.success, "error": r.error_message, "affected_rows": r.affected_rows}
                        for r in results
                    ]
                },
                "table_results": table_results  # Add all table results
            }
            
            if overall_success and display_result:
                response.update({
                    "columns": display_result.columns,
                    "rows": display_result.rows,
                    "row_count": display_result.row_count,
                    "affected_rows": total_affected_rows,
                    "execution_time_ms": total_execution_time
                })
            else:
                # Find first error
                error_results = [r for r in results if not r.success]
                if error_results:
                    response["error"] = error_results[0].error_message
                else:
                    response["error"] = "Unknown error occurred"
        
        # Save to history if successful
        if response["success"]:
            try:
                # Use the first successful result for history
                history_result = display_result if 'display_result' in locals() else result if 'result' in locals() else None
                if history_result:
                    await history_service.save_query_result(
                        history_result,
                        session_id=request.session_id,
                        user_context={"ai_generated": True, "prompt": request.prompt}
                    )
            except Exception as e:
                logger.warning(f"Failed to save to history: {e}")
        
        return response
        
    except Exception as e:
        return {
            "success": False,
            "prompt": request.prompt,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {"workflow_used": False}
        }


@router.post("/solve")
async def solve_from_input(
    prompt: Optional[str] = Form(None),
    files: List[UploadFile] = File(default=[])
):
    """
    Solve questions from multimodal input (text and/or files)
    
    Accepts:
    - Text only: Just the prompt
    - Files only: Upload image or document files
    - Text + Files: Both prompt and files
    
    Supported file types:
    - Images: PNG, JPEG
    - Documents: SQL, JSON, XLSX, CSV, TXT
    """
    try:
        # Validate input
        if not prompt and not files:
            raise HTTPException(status_code=400, detail="Either prompt or files must be provided")
        
        # Validate and process files
        images = []
        image_mimes = []
        document_files = []
        document_contents = []
        
        # Supported file types
        image_types = ['image/png', 'image/jpeg', 'image/jpg']
        document_types = [
            'application/json',
            'text/plain',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'text/csv',
            'application/vnd.ms-excel'
        ]
        
        for file in files:
            filename = file.filename or ""
            content_type = file.content_type or ""
            
            # Determine file type by extension if content_type is unclear
            file_extension = filename.lower().split('.')[-1] if '.' in filename else ""
            
            # Check if it's an image
            if content_type in image_types:
                # Read image content
                try:
                    content = await file.read()
                    if len(content) == 0:
                        raise HTTPException(status_code=400, detail=f"Empty file: {filename}")
                    
                    images.append(content)
                    image_mimes.append(content_type)
                    
                except Exception as e:
                    raise HTTPException(status_code=400, detail=f"Error reading image file {filename}: {str(e)}")
            
            # Check if it's a supported document
            elif (content_type in document_types or 
                  file_extension in ['sql', 'json', 'xlsx', 'csv', 'txt']):
                
                # Read document content
                try:
                    content = await file.read()
                    if len(content) == 0:
                        raise HTTPException(status_code=400, detail=f"Empty file: {filename}")
                    
                    document_files.append({
                        'filename': filename,
                        'content_type': content_type,
                        'extension': file_extension,
                        'size': len(content)
                    })
                    document_contents.append(content)
                    
                except Exception as e:
                    raise HTTPException(status_code=400, detail=f"Error reading document file {filename}: {str(e)}")
            
            else:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Unsupported file type: {content_type} for file {filename}. Supported types: images (PNG, JPEG) and documents (SQL, JSON, XLSX, CSV, TXT)."
                )
        
        # Get current database schema for context
        try:
            schema_obj = await schema_inspector.get_full_schema()
            schema = schema_obj.to_dict() if schema_obj else {"tables": []}
        except Exception as e:
            logger.warning(f"Failed to get schema: {e}")
            schema = {"tables": []}
        
        # Use Gemini multimodal capabilities
        if not gemini_generator:
            raise HTTPException(status_code=500, detail="Gemini AI is not configured")
        
        response_text, metadata = await gemini_generator.solve_from_multimodal_input(
            prompt=prompt,
            images=images if images else None,
            image_mimes=image_mimes if image_mimes else None,
            documents=document_contents if document_contents else None,
            document_info=document_files if document_files else None,
            schema=schema,
            max_retries=2
        )
        
        return {
            "success": True,
            "response": response_text,
            "metadata": {
                **metadata,
                "input_type": "multimodal" if (images or document_contents) else "text_only",
                "image_count": len(images),
                "document_count": len(document_contents),
                "document_types": [f['extension'] for f in document_files] if document_files else [],
                "has_text_prompt": bool(prompt),
                "schema_available": bool(schema.get('tables'))
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in solve endpoint: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "input_type": "multimodal" if files else "text_only",
                "file_count": len(files),
                "has_text_prompt": bool(prompt)
            }
        }
