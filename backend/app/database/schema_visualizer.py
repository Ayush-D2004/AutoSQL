"""
Schema Visualization Utility

This module provides utilities for converting database schema
into Mermaid ER diagram format for frontend visualization.
"""

from sqlalchemy import inspect, Engine
from sqlalchemy.ext.asyncio import AsyncEngine
from typing import Dict, List, Any, Optional
import logging
from ..core.database import database_manager

logger = logging.getLogger(__name__)


class SchemaVisualizer:
    """
    Database schema to Mermaid ER diagram converter
    
    Provides methods to:
    - Inspect database schema
    - Generate Mermaid ER diagram syntax
    - Handle relationships and constraints
    """
    
    def __init__(self):
        pass
    
    async def schema_to_mermaid(self) -> str:
        """
        Generate a Mermaid ER diagram string from the database schema.
        
        Returns:
            Mermaid ER diagram as string
        """
        try:
            async with database_manager.get_session() as session:
                # Get the sync engine for inspection
                sync_engine = database_manager.get_sync_engine()
                inspector = inspect(sync_engine)
                
                diagram = "erDiagram\n"
                
                # Get all table names
                table_names = inspector.get_table_names()
                
                # Filter out internal application tables that shouldn't appear in user diagrams
                internal_tables = {
                    'database_connections',
                    'query_history', 
                    'session_info',
                    'system_metadata',
                    'employees',  # Example/demo table
                    'conversation_history',
                    'user_sessions',
                    'application_settings',
                    'migration_history',
                    'audit_log'
                }
                
                # Filter out internal tables
                user_tables = [table for table in table_names if table.lower() not in internal_tables]
                
                if not user_tables:
                    return "erDiagram\n    NO_TABLES {\n        string message \"No user tables found in database\"\n    }"
                
                # Step 1: Collect tables and columns
                for table_name in user_tables:
                    diagram += f"    {table_name} {{\n"
                    
                    # Get column details
                    columns = inspector.get_columns(table_name)
                    primary_keys = inspector.get_pk_constraint(table_name)
                    pk_columns = primary_keys.get('constrained_columns', []) if primary_keys else []
                    
                    for column in columns:
                        col_name = column["name"]
                        col_type = str(column["type"]).upper()
                        
                        # Handle common SQLite types and convert to Mermaid format
                        if "VARCHAR" in col_type:
                            col_type = "string"
                        elif "INTEGER" in col_type:
                            col_type = "int"
                        elif "TEXT" in col_type:
                            col_type = "string"
                        elif "DECIMAL" in col_type or "NUMERIC" in col_type:
                            col_type = "decimal"
                        elif "REAL" in col_type or "FLOAT" in col_type:
                            col_type = "float"
                        elif "BLOB" in col_type:
                            col_type = "blob"
                        elif "BOOLEAN" in col_type:
                            col_type = "boolean"
                        elif "DATE" in col_type:
                            col_type = "date"
                        elif "TIME" in col_type:
                            col_type = "datetime"
                        else:
                            col_type = "string"  # Default fallback
                        
                        # Check if it's a primary key
                        pk_flag = " PK" if col_name in pk_columns else ""
                        
                        # Check if nullable
                        nullable_flag = "" if column.get("nullable", True) else ""
                        
                        diagram += f"        {col_type} {col_name}{pk_flag}\n"
                    
                    diagram += "    }\n"
                
                # Step 2: Collect relationships
                for table_name in user_tables:
                    try:
                        fks = inspector.get_foreign_keys(table_name)
                        for fk in fks:
                            if not fk.get("referred_table"):
                                continue
                                
                            parent_table = fk["referred_table"]
                            child_table = table_name
                            
                            # Only include relationships between user tables
                            if parent_table.lower() in internal_tables:
                                continue
                            
                            # Also check if parent table is in user_tables
                            if parent_table not in user_tables:
                                continue
                            
                            # Get column names
                            constrained_cols = fk.get("constrained_columns", [])
                            referred_cols = fk.get("referred_columns", [])
                            
                            if constrained_cols and referred_cols:
                                from_col = constrained_cols[0]
                                to_col = referred_cols[0]
                                
                                # Create relationship line
                                diagram += f"    {child_table} }}o--|| {parent_table} : \"{from_col}_to_{to_col}\"\n"
                    
                    except Exception as e:
                        logger.warning(f"Could not process foreign keys for table {table_name}: {e}")
                        continue
                
                return diagram
                
        except Exception as e:
            logger.error(f"Schema to Mermaid conversion failed: {e}", exc_info=True)
            return f"erDiagram\n    ERROR {{\n        string error \"Schema generation failed: {str(e)}\"\n    }}"
    
    def _sanitize_table_name(self, name: str) -> str:
        """Sanitize table name for Mermaid compatibility"""
        # Replace special characters that might break Mermaid
        return name.replace("-", "_").replace(" ", "_").replace(".", "_")
    
    def _sanitize_column_name(self, name: str) -> str:
        """Sanitize column name for Mermaid compatibility"""
        # Replace special characters that might break Mermaid
        return name.replace("-", "_").replace(" ", "_").replace(".", "_")

    async def schema_to_mermaid_mindmap(self) -> str:
        """
        Generate a Mermaid mindmap visualization from the database schema.
        
        Returns:
            Mermaid mindmap diagram as string
        """
        try:
            async with database_manager.get_session() as session:
                # Get the sync engine for inspection
                sync_engine = database_manager.get_sync_engine()
                inspector = inspect(sync_engine)
                
                diagram = "mindmap\n  root((Database Schema))\n"
                
                # Get all table names
                table_names = inspector.get_table_names()
                
                # Filter out internal application tables that shouldn't appear in user diagrams
                internal_tables = {
                    'database_connections',
                    'query_history', 
                    'session_info',
                    'system_metadata',
                    'employees',  # Example/demo table
                    'conversation_history',
                    'user_sessions',
                    'application_settings',
                    'migration_history',
                    'audit_log'
                }
                
                # Filter out internal tables
                user_tables = [table for table in table_names if table.lower() not in internal_tables]
                
                if not user_tables:
                    return "mindmap\n  root((Database Schema))\n    NO_TABLES[No user tables found in database]"
                
                # Add tables as branches
                for table_name in user_tables:
                    sanitized_table = self._sanitize_table_name(table_name)
                    diagram += f"    {sanitized_table}\n"
                    
                    # Get column details
                    columns = inspector.get_columns(table_name)
                    primary_keys = inspector.get_pk_constraint(table_name)
                    pk_columns = primary_keys.get('constrained_columns', []) if primary_keys else []
                    
                    for column in columns:
                        col_name = self._sanitize_column_name(column["name"])
                        col_type = str(column["type"]).upper()
                        
                        # Handle common SQLite types
                        if "VARCHAR" in col_type:
                            col_type = "string"
                        elif "INTEGER" in col_type:
                            col_type = "int"
                        elif "TEXT" in col_type:
                            col_type = "string"
                        elif "DECIMAL" in col_type or "NUMERIC" in col_type:
                            col_type = "decimal"
                        elif "REAL" in col_type or "FLOAT" in col_type:
                            col_type = "float"
                        elif "BLOB" in col_type:
                            col_type = "blob"
                        elif "BOOLEAN" in col_type:
                            col_type = "boolean"
                        elif "DATE" in col_type:
                            col_type = "date"
                        elif "TIME" in col_type:
                            col_type = "datetime"
                        else:
                            col_type = "string"  # Default fallback
                        
                        # Check if it's a primary key
                        pk_flag = " (PK)" if column["name"] in pk_columns else ""
                        
                        diagram += f"      {col_name}: {col_type}{pk_flag}\n"
                
                return diagram
                
        except Exception as e:
            logger.error(f"Schema to Mermaid mindmap conversion failed: {e}", exc_info=True)
            return f"mindmap\n  root((Database Schema))\n    ERROR[Schema generation failed: {str(e)}]"


# Global schema visualizer instance
schema_visualizer = SchemaVisualizer()


# Convenience function for backward compatibility
async def schema_to_mermaid() -> str:
    """Generate Mermaid ER diagram from current database schema"""
    return await schema_visualizer.schema_to_mermaid()

async def schema_to_mermaid_mindmap() -> str:
    """Generate Mermaid mindmap from current database schema"""
    return await schema_visualizer.schema_to_mermaid_mindmap()