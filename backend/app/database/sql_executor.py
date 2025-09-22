"""
Database Utilities for SQL Execution and Result Handling

This module provides utilities for executing arbitrary SQL statements,
handling results, and managing database operations safely.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, MetaData, inspect
from sqlalchemy.engine import Result
from typing import Dict, List, Any, Optional, Union, Tuple
import asyncio
import json
import logging
import traceback
import re
from datetime import datetime

from ..core.database import database_manager
from ..core.config import settings

logger = logging.getLogger(__name__)


class SQLExecutionResult:
    """
    Structured result from SQL execution
    
    Contains all information needed for frontend display:
    - Query results (rows, columns)
    - Metadata (row count, execution time, etc.)
    - Error information if applicable
    """
    
    def __init__(
        self,
        success: bool,
        query: str,
        execution_time_ms: float,
        rows: Optional[List[Dict[str, Any]]] = None,
        columns: Optional[List[str]] = None,
        row_count: int = 0,
        affected_rows: int = 0,
        error_message: Optional[str] = None,
        error_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.success = success
        self.query = query
        self.execution_time_ms = execution_time_ms
        self.rows = rows or []
        self.columns = columns or []
        self.row_count = row_count
        self.affected_rows = affected_rows
        self.error_message = error_message
        self.error_type = error_type
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for JSON serialization"""
        return {
            "success": self.success,
            "query": self.query,
            "execution_time_ms": self.execution_time_ms,
            "rows": self.rows,
            "columns": self.columns,
            "row_count": self.row_count,
            "affected_rows": self.affected_rows,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


class DatabaseExecutor:
    """
    Main database execution utility class
    
    Handles:
    - SQL execution with proper error handling
    - Result formatting and serialization
    - Transaction management
    - Query validation and safety checks
    """
    
    def __init__(self):
        self.forbidden_keywords = {
            "DROP DATABASE", "DROP SCHEMA", "TRUNCATE DATABASE",
            "DELETE FROM information_schema", "DELETE FROM sys",
            "SHUTDOWN", "RESTART"
        }
    
    async def execute_sql(
        self, 
        sql: str, 
        parameters: Optional[Dict[str, Any]] = None,
        auto_commit: bool = True,
        safety_check: bool = True,
        forgiving_mode: bool = True
    ) -> SQLExecutionResult:
        """
        Execute SQL statement and return structured result
        
        Args:
            sql: SQL statement to execute
            parameters: Optional parameters for parameterized queries
            auto_commit: Whether to auto-commit the transaction
            safety_check: Whether to perform safety checks on SQL
            forgiving_mode: Whether to treat harmless errors (like "table already exists") as success
        
        Returns:
            SQLExecutionResult with execution details
        """
        start_time = asyncio.get_event_loop().time()
        
        # Safety check
        if safety_check and self._is_dangerous_query(sql):
            return SQLExecutionResult(
                success=False,
                query=sql,
                execution_time_ms=0,
                error_message="Dangerous operation detected and blocked",
                error_type="SAFETY_ERROR"
            )
        
        try:
            async with database_manager.get_session() as session:
                # Execute the query
                if parameters:
                    result = await session.execute(text(sql), parameters)
                else:
                    result = await session.execute(text(sql))
                
                # Calculate execution time
                execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
                
                # Handle different types of results
                if result.returns_rows:
                    # SELECT-like queries
                    rows = []
                    columns = list(result.keys()) if result.keys() else []
                    
                    for row in result:
                        row_dict = {}
                        for i, column in enumerate(columns):
                            value = row[i]
                            # Handle special types for JSON serialization
                            if hasattr(value, 'isoformat'):  # datetime objects
                                value = value.isoformat()
                            elif isinstance(value, (bytes, bytearray)):
                                value = value.decode('utf-8', errors='replace')
                            row_dict[column] = value
                        rows.append(row_dict)
                    
                    return SQLExecutionResult(
                        success=True,
                        query=sql,
                        execution_time_ms=execution_time,
                        rows=rows,
                        columns=columns,
                        row_count=len(rows),
                        metadata={"query_type": "SELECT"}
                    )
                else:
                    # DDL/DML queries (CREATE, INSERT, UPDATE, DELETE, etc.)
                    affected_rows = result.rowcount if hasattr(result, 'rowcount') else 0
                    
                    # Determine query type
                    query_type = self._get_query_type(sql)
                    
                    return SQLExecutionResult(
                        success=True,
                        query=sql,
                        execution_time_ms=execution_time,
                        affected_rows=affected_rows,
                        metadata={"query_type": query_type}
                    )
                    
        except Exception as e:
            execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
            error_type = type(e).__name__
            error_message = str(e)
            
            # Forgiving mode: treat harmless errors as success
            if forgiving_mode and self._is_harmless_error(error_message):
                logger.info(f"Harmless error ignored in forgiving mode: {error_message}")
                return SQLExecutionResult(
                    success=True,
                    query=sql,
                    execution_time_ms=execution_time,
                    affected_rows=0,
                    metadata={
                        "query_type": self._get_query_type(sql),
                        "note": f"Skipped: {self._get_friendly_error_message(error_message)}",
                        "forgiving_mode": True
                    }
                )
            
            # Real error - format it in a user-friendly way
            friendly_error = self._get_friendly_error_message(error_message)
            logger.error(f"SQL execution failed: {error_message}", exc_info=True)
            
            return SQLExecutionResult(
                success=False,
                query=sql,
                execution_time_ms=execution_time,
                error_message=friendly_error,
                error_type=error_type,
                metadata={
                    "original_error": error_message,
                    "traceback": traceback.format_exc()
                }
            )
    
    async def execute_multiple_sql(
        self, 
        sql_statements: List[str],
        use_transaction: bool = True,
        forgiving_mode: bool = True
    ) -> List[SQLExecutionResult]:
        """
        Execute multiple SQL statements with enhanced error handling
        
        Args:
            sql_statements: List of SQL statements to execute
            use_transaction: Whether to wrap all statements in a single transaction
            forgiving_mode: Whether to treat harmless errors as success
        
        Returns:
            List of SQLExecutionResult for each statement
        """
        results = []
        
        if use_transaction and not forgiving_mode:
            # Traditional transaction mode - fail fast on any error
            results = await self._execute_transaction_mode(sql_statements)
        else:
            # Forgiving mode - execute each statement independently
            logger.info(f"Executing {len(sql_statements)} statements in forgiving mode")
            
            for i, sql in enumerate(sql_statements):
                if sql.strip():  # Skip empty statements
                    logger.info(f"Executing statement {i+1}/{len(sql_statements)}: {sql[:50]}...")
                    
                    result = await self.execute_sql(
                        sql=sql,
                        forgiving_mode=forgiving_mode,
                        safety_check=True
                    )
                    results.append(result)
                    
                    # Log the result
                    if result.success:
                        if result.metadata and result.metadata.get("note"):
                            logger.info(f"Statement {i+1} skipped: {result.metadata['note']}")
                        else:
                            logger.info(f"Statement {i+1} executed successfully")
                    else:
                        logger.warning(f"Statement {i+1} failed: {result.error_message}")
        
        return results
    
    async def _execute_transaction_mode(self, sql_statements: List[str]) -> List[SQLExecutionResult]:
        """Execute all statements in a single transaction (legacy mode)"""
        results = []
        start_time = asyncio.get_event_loop().time()
        
        try:
            async with database_manager.get_session() as session:
                # Begin transaction explicitly
                await session.begin()
                
                for sql in sql_statements:
                    stmt_start_time = asyncio.get_event_loop().time()
                    
                    try:
                        # Execute the statement
                        if sql.strip():
                            result = await session.execute(text(sql))
                            stmt_execution_time = (asyncio.get_event_loop().time() - stmt_start_time) * 1000
                            
                            # Handle different types of results
                            if result.returns_rows:
                                # SELECT-like queries
                                rows = []
                                columns = list(result.keys()) if result.keys() else []
                                
                                for row in result:
                                    row_dict = {}
                                    for i, column in enumerate(columns):
                                        value = row[i]
                                        # Handle special types for JSON serialization
                                        if hasattr(value, 'isoformat'):  # datetime objects
                                            value = value.isoformat()
                                        elif isinstance(value, (bytes, bytearray)):
                                            value = value.decode('utf-8', errors='replace')
                                        row_dict[column] = value
                                    rows.append(row_dict)
                                
                                stmt_result = SQLExecutionResult(
                                    success=True,
                                    query=sql,
                                    execution_time_ms=stmt_execution_time,
                                    rows=rows,
                                    columns=columns,
                                    row_count=len(rows),
                                    metadata={"query_type": self._get_query_type(sql), "transaction": True}
                                )
                            else:
                                # DDL/DML queries
                                affected_rows = result.rowcount if hasattr(result, 'rowcount') else 0
                                stmt_result = SQLExecutionResult(
                                    success=True,
                                    query=sql,
                                    execution_time_ms=stmt_execution_time,
                                    affected_rows=affected_rows,
                                    metadata={"query_type": self._get_query_type(sql), "transaction": True}
                                )
                            
                            results.append(stmt_result)
                        
                    except Exception as e:
                        # Statement failed - create error result and rollback
                        stmt_execution_time = (asyncio.get_event_loop().time() - stmt_start_time) * 1000
                        error_result = SQLExecutionResult(
                            success=False,
                            query=sql,
                            execution_time_ms=stmt_execution_time,
                            error_message=self._get_friendly_error_message(str(e)),
                            error_type=type(e).__name__,
                            metadata={"query_type": self._get_query_type(sql), "transaction": True}
                        )
                        results.append(error_result)
                        
                        # Rollback transaction
                        await session.rollback()
                        logger.error(f"Statement failed in transaction, rolling back: {e}")
                        break
                else:
                    # All statements succeeded, commit transaction
                    await session.commit()
                    
        except Exception as e:
            logger.error(f"Transaction failed: {e}", exc_info=True)
            # Add error result for any remaining statements
            for sql in sql_statements[len(results):]:
                results.append(SQLExecutionResult(
                    success=False,
                    query=sql,
                    execution_time_ms=0,
                    error_message=f"Transaction rollback: {self._get_friendly_error_message(str(e))}",
                    error_type="TRANSACTION_ERROR",
                    metadata={"query_type": self._get_query_type(sql), "transaction": True}
                ))
        
        return results
    
    def _is_dangerous_query(self, sql: str) -> bool:
        """Check if SQL query contains dangerous operations"""
        sql_upper = sql.upper().strip()
        
        # Check for forbidden keywords
        for keyword in self.forbidden_keywords:
            if keyword in sql_upper:
                return True
        
        # Additional safety checks can be added here
        # For example, preventing certain operations in production
        if settings.is_production:
            production_forbidden = ["DROP TABLE", "ALTER TABLE DROP"]
            for keyword in production_forbidden:
                if keyword in sql_upper:
                    return True
        
        return False
    
    def _get_query_type(self, sql: str) -> str:
        """Determine the type of SQL query"""
        sql_upper = sql.upper().strip()
        
        if sql_upper.startswith('SELECT'):
            return 'SELECT'
        elif sql_upper.startswith('INSERT'):
            return 'INSERT'
        elif sql_upper.startswith('UPDATE'):
            return 'UPDATE'
        elif sql_upper.startswith('DELETE'):
            return 'DELETE'
        elif sql_upper.startswith('CREATE'):
            return 'CREATE'
        elif sql_upper.startswith('ALTER'):
            return 'ALTER'
        elif sql_upper.startswith('DROP'):
            return 'DROP'
        elif sql_upper.startswith('TRUNCATE'):
            return 'TRUNCATE'
        else:
            return 'OTHER'
    
    def _is_harmless_error(self, error_message: str) -> bool:
        """
        Check if an error is harmless and can be safely ignored in forgiving mode
        
        Args:
            error_message: The error message to check
            
        Returns:
            True if the error is harmless and can be ignored
        """
        error_lower = error_message.lower()
        
        harmless_patterns = [
            "already exists",
            "duplicate column name",
            "duplicate column",
            "index already exists",
            "table already exists",
            "constraint already exists",
            "trigger already exists",
            "view already exists",
            "sequence already exists"
        ]
        
        return any(pattern in error_lower for pattern in harmless_patterns)
    
    def _get_friendly_error_message(self, error_message: str) -> str:
        """
        Convert technical error messages to user-friendly explanations
        
        Args:
            error_message: The original technical error message
            
        Returns:
            A more user-friendly error explanation
        """
        error_lower = error_message.lower()
        
        # Common SQL error patterns and their friendly explanations
        error_patterns = {
            "no such table": "Table doesn't exist. Check the table name or create it first.",
            "no such column": "Column doesn't exist. Check the column name or add it to the table.",
            "syntax error": "SQL syntax error. Check your query structure, commas, and parentheses.",
            "not null constraint": "Required field is empty. Make sure all required columns have values.",
            "unique constraint": "Duplicate value detected. This field must be unique. Try using INSERT OR IGNORE or DELETE existing data first.",
            "foreign key constraint": "Invalid reference. The referenced row doesn't exist in the parent table.",
            "ambiguous column": "Column name is ambiguous. Use table prefixes to clarify (e.g., table.column).",
            "datatype mismatch": "Data type mismatch. Check that values match the expected column types.",
            "division by zero": "Cannot divide by zero. Check your calculations.",
            "invalid datetime": "Invalid date or time format. Use proper date/time formats.",
            "permission denied": "Access denied. You don't have permission for this operation.",
            "disk full": "Not enough storage space. Contact your administrator.",
            "connection lost": "Database connection was lost. Try again in a moment."
        }
        
        # Check for known patterns and return friendly message
        for pattern, friendly_msg in error_patterns.items():
            if pattern in error_lower:
                return f"{friendly_msg} (Technical: {error_message})"
        
        # For harmless errors, provide a more reassuring message
        if self._is_harmless_error(error_message):
            return f"Already exists (safely ignored)"
        
        # If no pattern matches, return a generic friendly wrapper
        return f"Query error: {error_message}"
    
    def parse_sql_statements(self, sql_text: str) -> List[str]:
        """
        Parse multiple SQL statements from a single string
        
        Args:
            sql_text: String containing one or more SQL statements
            
        Returns:
            List of individual SQL statements
        """
        # Remove comments and normalize whitespace
        sql_text = re.sub(r'--.*?\n', '\n', sql_text)  # Remove single-line comments
        sql_text = re.sub(r'/\*.*?\*/', '', sql_text, flags=re.DOTALL)  # Remove multi-line comments
        
        # Split by semicolons, but be careful about semicolons in strings
        statements = []
        current_statement = ""
        in_string = False
        quote_char = None
        
        i = 0
        while i < len(sql_text):
            char = sql_text[i]
            
            if not in_string:
                if char in ["'", '"']:
                    in_string = True
                    quote_char = char
                elif char == ';':
                    # End of statement
                    statement = current_statement.strip()
                    if statement:
                        statements.append(statement)
                    current_statement = ""
                    i += 1
                    continue
            else:
                if char == quote_char:
                    # Check if it's escaped
                    if i + 1 < len(sql_text) and sql_text[i + 1] == quote_char:
                        # Escaped quote, skip both
                        current_statement += char + sql_text[i + 1]
                        i += 2
                        continue
                    else:
                        # End of string
                        in_string = False
                        quote_char = None
            
            current_statement += char
            i += 1
        
        # Add the last statement if it doesn't end with semicolon
        final_statement = current_statement.strip()
        if final_statement:
            statements.append(final_statement)
        
        return statements
    
    def _auto_preprocess_sql(self, sql_text: str) -> str:
        """
        Auto-preprocess SQL to add DROP TABLE IF EXISTS before CREATE TABLE statements
        for better user experience and clean table state.
        
        Args:
            sql_text: Original SQL text from user/AI
            
        Returns:
            Preprocessed SQL with automatic DROP statements added
        """
        statements = self.parse_sql_statements(sql_text)
        processed_statements = []
        
        for statement in statements:
            statement_upper = statement.strip().upper()
            
            # Check if this is a CREATE TABLE statement
            if statement_upper.startswith('CREATE TABLE'):
                # Extract table name using regex
                create_table_pattern = r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([`"\[]?\w+[`"\]]?)'
                match = re.search(create_table_pattern, statement_upper)
                
                if match:
                    table_name = match.group(1)
                    # Remove any quotes or brackets for the DROP statement
                    clean_table_name = table_name.strip('`"[]')
                    
                    # Add DROP TABLE IF EXISTS before the CREATE TABLE
                    drop_statement = f"DROP TABLE IF EXISTS {clean_table_name};"
                    processed_statements.append(drop_statement)
                    
                    logger.info(f"Auto-preprocessing: Added DROP TABLE IF EXISTS {clean_table_name}")
            
            # Add the original statement (ensure it ends with semicolon)
            original_statement = statement.strip()
            if original_statement and not original_statement.endswith(';'):
                original_statement += ';'
            processed_statements.append(original_statement)
        
        # Join statements back together with proper separation
        return '\n'.join(processed_statements)
    
    async def execute_sql_smart(self, sql_text: str, forgiving_mode: bool = True, auto_preprocess: bool = True, **kwargs) -> List[SQLExecutionResult]:
        """
        Smart SQL execution that handles both single and multiple statements with forgiving mode
        and optional auto-preprocessing for clean table state.
        
        Args:
            sql_text: SQL text (can contain multiple statements)
            forgiving_mode: Whether to treat harmless errors as success
            auto_preprocess: Whether to automatically add DROP TABLE IF EXISTS for CREATE TABLE statements
            **kwargs: Additional parameters for execute_sql
            
        Returns:
            List of SQLExecutionResult (single item if only one statement)
        """
        # Auto-preprocess SQL if enabled
        if auto_preprocess:
            sql_text = self._auto_preprocess_sql(sql_text)
        
        statements = self.parse_sql_statements(sql_text)
        
        if len(statements) == 1:
            # Single statement
            result = await self.execute_sql(statements[0], forgiving_mode=forgiving_mode, **kwargs)
            return [result]
        else:
            # Multiple statements - use forgiving mode by default
            return await self.execute_multiple_sql(
                statements, 
                use_transaction=not forgiving_mode,  # No transaction in forgiving mode
                forgiving_mode=forgiving_mode
            )


# Global database executor instance
db_executor = DatabaseExecutor()


# Utility functions for common operations
async def execute_query(sql: str, parameters: Optional[Dict] = None, forgiving_mode: bool = True) -> SQLExecutionResult:
    """Execute a single SQL query with forgiving mode by default"""
    return await db_executor.execute_sql(sql, parameters, forgiving_mode=forgiving_mode)


async def execute_safe_query(sql: str, parameters: Optional[Dict] = None) -> SQLExecutionResult:
    """Execute a query with enhanced safety checks but no forgiving mode"""
    return await db_executor.execute_sql(sql, parameters, safety_check=True, forgiving_mode=False)


async def execute_transaction(sql_statements: List[str]) -> List[SQLExecutionResult]:
    """Execute multiple statements in a single transaction (strict mode)"""
    return await db_executor.execute_multiple_sql(sql_statements, use_transaction=True, forgiving_mode=False)


async def execute_smart_query(sql_text: str, forgiving_mode: bool = True, auto_preprocess: bool = True, **kwargs) -> List[SQLExecutionResult]:
    """Smart execution that handles both single and multiple SQL statements with forgiving mode and auto-preprocessing"""
    return await db_executor.execute_sql_smart(sql_text, forgiving_mode=forgiving_mode, auto_preprocess=auto_preprocess, **kwargs)