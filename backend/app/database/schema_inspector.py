"""
Database Schema Introspection

This module provides utilities for inspecting database schema,
extracting table information, relationships, and generating
structured data for frontend visualization.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, MetaData, inspect, Table, Column
from sqlalchemy.engine import Inspector
from typing import Dict, List, Any, Optional, Set
import logging
from datetime import datetime

from ..core.database import database_manager
from ..core.config import settings

logger = logging.getLogger(__name__)


class TableInfo:
    """Information about a database table"""
    
    def __init__(
        self,
        name: str,
        schema_name: Optional[str] = None,
        columns: Optional[List[Dict[str, Any]]] = None,
        primary_keys: Optional[List[str]] = None,
        foreign_keys: Optional[List[Dict[str, Any]]] = None,
        indexes: Optional[List[Dict[str, Any]]] = None,
        comment: Optional[str] = None
    ):
        self.name = name
        self.schema_name = schema_name
        self.columns = columns or []
        self.primary_keys = primary_keys or []
        self.foreign_keys = foreign_keys or []
        self.indexes = indexes or []
        self.comment = comment
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "name": self.name,
            "schema_name": self.schema_name,
            "columns": self.columns,
            "primary_keys": self.primary_keys,
            "foreign_keys": self.foreign_keys,
            "indexes": self.indexes,
            "comment": self.comment,
            "column_count": len(self.columns),
            "has_primary_key": len(self.primary_keys) > 0,
            "has_foreign_keys": len(self.foreign_keys) > 0
        }


class DatabaseSchema:
    """Complete database schema information"""
    
    def __init__(
        self,
        database_name: str,
        tables: Optional[List[TableInfo]] = None,
        views: Optional[List[str]] = None,
        schemas: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.database_name = database_name
        self.tables = tables or []
        self.views = views or []
        self.schemas = schemas or []
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "database_name": self.database_name,
            "tables": [table.to_dict() for table in self.tables],
            "views": self.views,
            "schemas": self.schemas,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "summary": {
                "table_count": len(self.tables),
                "view_count": len(self.views),
                "schema_count": len(self.schemas),
                "total_columns": sum(len(table.columns) for table in self.tables),
                "tables_with_fk": sum(1 for table in self.tables if table.foreign_keys)
            }
        }


class SchemaInspector:
    """
    Database schema inspection utility
    
    Provides methods to:
    - Inspect table structures
    - Extract relationships
    - Generate schema summaries
    - Create visualization data
    """
    
    def __init__(self):
        pass
    
    async def get_full_schema(self, schema_name: Optional[str] = None) -> DatabaseSchema:
        """
        Get complete database schema information
        
        Args:
            schema_name: Optional specific schema to inspect
        
        Returns:
            DatabaseSchema with complete information
        """
        try:
            async with database_manager.get_session() as session:
                # Get database name
                db_name = await self._get_database_name(session)
                
                # Get all tables
                tables = await self._get_all_tables(session, schema_name)
                
                # Get all views
                views = await self._get_all_views(session, schema_name)
                
                # Get available schemas
                schemas = await self._get_all_schemas(session)
                
                # Get additional metadata
                metadata = await self._get_database_metadata(session)
                
                return DatabaseSchema(
                    database_name=db_name,
                    tables=tables,
                    views=views,
                    schemas=schemas,
                    metadata=metadata
                )
                
        except Exception as e:
            logger.error(f"Schema inspection failed: {e}", exc_info=True)
            return DatabaseSchema(
                database_name="Unknown",
                metadata={"error": str(e)}
            )
    
    async def get_table_info(self, table_name: str, schema_name: Optional[str] = None) -> Optional[TableInfo]:
        """
        Get detailed information about a specific table
        
        Args:
            table_name: Name of the table to inspect
            schema_name: Optional schema name
        
        Returns:
            TableInfo object or None if table not found
        """
        try:
            async with database_manager.get_session() as session:
                # Check if table exists
                exists = await self._table_exists(session, table_name, schema_name)
                if not exists:
                    return None
                
                # Get column information
                columns = await self._get_table_columns(session, table_name, schema_name)
                
                # Get primary keys
                primary_keys = await self._get_primary_keys(session, table_name, schema_name)
                
                # Get foreign keys
                foreign_keys = await self._get_foreign_keys(session, table_name, schema_name)
                
                # Get indexes
                indexes = await self._get_indexes(session, table_name, schema_name)
                
                # Get table comment
                comment = await self._get_table_comment(session, table_name, schema_name)
                
                return TableInfo(
                    name=table_name,
                    schema=schema_name,
                    columns=columns,
                    primary_keys=primary_keys,
                    foreign_keys=foreign_keys,
                    indexes=indexes,
                    comment=comment
                )
                
        except Exception as e:
            logger.error(f"Table inspection failed for {table_name}: {e}")
            return None
    
    async def get_relationships(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all foreign key relationships in the database
        
        Returns:
            Dictionary mapping table names to their relationships
        """
        relationships = {}
        
        try:
            schema = await self.get_full_schema()
            
            for table in schema.tables:
                if table.foreign_keys:
                    relationships[table.name] = table.foreign_keys
            
            return relationships
            
        except Exception as e:
            logger.error(f"Relationship extraction failed: {e}")
            return {}
    
    async def generate_mermaid_erd(self) -> str:
        """
        Generate Mermaid.js Entity Relationship Diagram syntax
        
        Returns:
            Mermaid ERD string for frontend visualization
        """
        try:
            schema = await self.get_full_schema()
            
            mermaid_lines = ["erDiagram"]
            
            # Add tables and their columns
            for table in schema.tables:
                table_def = f"    {table.name} {{"
                mermaid_lines.append(table_def)
                
                for column in table.columns:
                    column_type = column.get('type', 'VARCHAR')
                    nullable = "" if column.get('nullable', True) else " NOT NULL"
                    pk = " PK" if column['name'] in table.primary_keys else ""
                    
                    column_line = f"        {column_type} {column['name']}{nullable}{pk}"
                    mermaid_lines.append(column_line)
                
                mermaid_lines.append("    }")
            
            # Add relationships
            for table in schema.tables:
                for fk in table.foreign_keys:
                    relationship = f"    {table.name} ||--o{{ {fk['referred_table']} : {fk['constrained_columns'][0]}"
                    mermaid_lines.append(relationship)
            
            return "\n".join(mermaid_lines)
            
        except Exception as e:
            logger.error(f"Mermaid ERD generation failed: {e}")
            return f"erDiagram\n    ERROR {{\n        string error 'Schema generation failed'\n    }}"
    
    # Private helper methods
    async def _get_database_name(self, session: AsyncSession) -> str:
        """Get the current database name"""
        try:
            # This is database-specific
            if "sqlite" in str(session.bind.url):
                return "SQLite Database"
            elif "postgresql" in str(session.bind.url):
                result = await session.execute(text("SELECT current_database()"))
                return result.scalar() or "PostgreSQL Database"
            elif "mysql" in str(session.bind.url):
                result = await session.execute(text("SELECT DATABASE()"))
                return result.scalar() or "MySQL Database"
            else:
                return "Unknown Database"
        except:
            return "Database"
    
    async def _get_all_tables(self, session: AsyncSession, schema_name: Optional[str] = None) -> List[TableInfo]:
        """Get all tables in the database"""
        tables = []
        
        try:
            # Get table names
            if "sqlite" in str(session.bind.url):
                query = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                result = await session.execute(text(query))
                table_names = [row[0] for row in result]
            else:
                # For PostgreSQL/MySQL, we'd use information_schema
                # This is a simplified version for SQLite
                table_names = []
            
            # Get detailed info for each table
            for table_name in table_names:
                table_info = await self.get_table_info(table_name, schema_name)
                if table_info:
                    tables.append(table_info)
            
            return tables
            
        except Exception as e:
            logger.error(f"Failed to get tables: {e}")
            return []
    
    async def _get_all_views(self, session: AsyncSession, schema_name: Optional[str] = None) -> List[str]:
        """Get all view names"""
        try:
            if "sqlite" in str(session.bind.url):
                query = "SELECT name FROM sqlite_master WHERE type='view'"
                result = await session.execute(text(query))
                return [row[0] for row in result]
            else:
                return []  # TODO: Implement for other databases
        except:
            return []
    
    async def _get_all_schemas(self, session: AsyncSession) -> List[str]:
        """Get all schema names"""
        try:
            if "postgresql" in str(session.bind.url):
                query = "SELECT schema_name FROM information_schema.schemata"
                result = await session.execute(text(query))
                return [row[0] for row in result]
            else:
                return ["main"]  # SQLite default
        except:
            return ["main"]
    
    async def _get_database_metadata(self, session: AsyncSession) -> Dict[str, Any]:
        """Get additional database metadata"""
        metadata = {}
        
        try:
            # Database version
            if "sqlite" in str(session.bind.url):
                result = await session.execute(text("SELECT sqlite_version()"))
                metadata["version"] = result.scalar()
                metadata["engine"] = "SQLite"
            
            # Add more metadata as needed
            metadata["connection_url"] = str(session.bind.url).split("@")[-1] if "@" in str(session.bind.url) else "local"
            
        except Exception as e:
            metadata["error"] = str(e)
        
        return metadata
    
    async def _table_exists(self, session: AsyncSession, table_name: str, schema_name: Optional[str] = None) -> bool:
        """Check if table exists"""
        try:
            if "sqlite" in str(session.bind.url):
                query = "SELECT name FROM sqlite_master WHERE type='table' AND name = ?"
                result = await session.execute(text(query), {"name": table_name})
                return result.scalar() is not None
            else:
                # TODO: Implement for other databases
                return True
        except:
            return False
    
    async def _get_table_columns(self, session: AsyncSession, table_name: str, schema_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get column information for a table"""
        columns = []
        
        try:
            if "sqlite" in str(session.bind.url):
                query = f"PRAGMA table_info({table_name})"
                result = await session.execute(text(query))
                
                for row in result:
                    columns.append({
                        "name": row[1],
                        "type": row[2],
                        "nullable": not bool(row[3]),
                        "default": row[4],
                        "position": row[0]
                    })
            
            return columns
            
        except Exception as e:
            logger.error(f"Failed to get columns for {table_name}: {e}")
            return []
    
    async def _get_primary_keys(self, session: AsyncSession, table_name: str, schema_name: Optional[str] = None) -> List[str]:
        """Get primary key columns"""
        try:
            if "sqlite" in str(session.bind.url):
                query = f"PRAGMA table_info({table_name})"
                result = await session.execute(text(query))
                
                pk_columns = []
                for row in result:
                    if row[5]:  # pk column is 1
                        pk_columns.append(row[1])  # column name
                
                return pk_columns
            
            return []
            
        except:
            return []
    
    async def _get_foreign_keys(self, session: AsyncSession, table_name: str, schema_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get foreign key information"""
        foreign_keys = []
        
        try:
            if "sqlite" in str(session.bind.url):
                query = f"PRAGMA foreign_key_list({table_name})"
                result = await session.execute(text(query))
                
                for row in result:
                    foreign_keys.append({
                        "constrained_columns": [row[3]],  # from column
                        "referred_table": row[2],         # to table
                        "referred_columns": [row[4]],     # to column
                        "name": f"fk_{table_name}_{row[3]}"
                    })
            
            return foreign_keys
            
        except:
            return []
    
    async def _get_indexes(self, session: AsyncSession, table_name: str, schema_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get index information"""
        try:
            if "sqlite" in str(session.bind.url):
                query = f"PRAGMA index_list({table_name})"
                result = await session.execute(text(query))
                
                indexes = []
                for row in result:
                    indexes.append({
                        "name": row[1],
                        "unique": bool(row[2]),
                        "columns": []  # TODO: Get column details
                    })
                
                return indexes
            
            return []
            
        except:
            return []
    
    async def _get_table_comment(self, session: AsyncSession, table_name: str, schema_name: Optional[str] = None) -> Optional[str]:
        """Get table comment/description"""
        # SQLite doesn't support table comments natively
        return None


# Global schema inspector instance
schema_inspector = SchemaInspector()