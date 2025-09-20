"""
Query History Service for AutoSQL Backend

This service manages query execution history and provides analytics.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import asyncio
from dataclasses import dataclass, asdict


@dataclass
class QueryHistoryEntry:
    """Represents a query execution history entry"""
    id: str
    query: str
    execution_time: float
    timestamp: datetime
    status: str  # success, error, cancelled
    result_count: Optional[int] = None
    error_message: Optional[str] = None
    database_name: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class HistoryService:
    """Manages query execution history"""
    
    def __init__(self):
        self._history: List[QueryHistoryEntry] = []
        self._max_history_size = 1000  # Maximum number of entries to keep
        
    async def add_query_execution(
        self,
        query: str,
        execution_time: float,
        status: str,
        result_count: Optional[int] = None,
        error_message: Optional[str] = None,
        database_name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add a query execution to history"""
        
        entry_id = f"query_{len(self._history)}_{int(datetime.utcnow().timestamp())}"
        
        entry = QueryHistoryEntry(
            id=entry_id,
            query=query,
            execution_time=execution_time,
            timestamp=datetime.utcnow(),
            status=status,
            result_count=result_count,
            error_message=error_message,
            database_name=database_name,
            user_id=user_id,
            metadata=metadata or {}
        )
        
        self._history.append(entry)
        
        # Trim history if it exceeds max size
        if len(self._history) > self._max_history_size:
            self._history = self._history[-self._max_history_size:]
            
        return entry_id
    
    async def get_query_history(
        self,
        limit: Optional[int] = 100,
        offset: int = 0,
        user_id: Optional[str] = None,
        database_name: Optional[str] = None,
        status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get query history with optional filtering"""
        
        filtered_history = self._history
        
        # Apply filters
        if user_id:
            filtered_history = [h for h in filtered_history if h.user_id == user_id]
            
        if database_name:
            filtered_history = [h for h in filtered_history if h.database_name == database_name]
            
        if status_filter:
            filtered_history = [h for h in filtered_history if h.status == status_filter]
        
        # Sort by timestamp (most recent first)
        filtered_history = sorted(filtered_history, key=lambda x: x.timestamp, reverse=True)
        
        # Apply pagination
        end_index = offset + limit if limit else len(filtered_history)
        paginated_history = filtered_history[offset:end_index]
        
        # Convert to dict format
        return [self._entry_to_dict(entry) for entry in paginated_history]
    
    async def get_query_by_id(self, query_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific query by ID"""
        for entry in self._history:
            if entry.id == query_id:
                return self._entry_to_dict(entry)
        return None
    
    async def get_recent_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the most recent queries"""
        recent = sorted(self._history, key=lambda x: x.timestamp, reverse=True)[:limit]
        return [self._entry_to_dict(entry) for entry in recent]
    
    async def get_query_statistics(self) -> Dict[str, Any]:
        """Get statistics about query execution"""
        total_queries = len(self._history)
        
        if total_queries == 0:
            return {
                "total_queries": 0,
                "successful_queries": 0,
                "failed_queries": 0,
                "average_execution_time": 0,
                "success_rate": 0
            }
        
        successful_queries = len([h for h in self._history if h.status == "success"])
        failed_queries = len([h for h in self._history if h.status == "error"])
        
        total_execution_time = sum(h.execution_time for h in self._history)
        average_execution_time = total_execution_time / total_queries
        
        success_rate = (successful_queries / total_queries) * 100
        
        return {
            "total_queries": total_queries,
            "successful_queries": successful_queries,
            "failed_queries": failed_queries,
            "average_execution_time": round(average_execution_time, 3),
            "success_rate": round(success_rate, 2)
        }
    
    async def clear_history(self, user_id: Optional[str] = None) -> int:
        """Clear query history, optionally for a specific user"""
        if user_id:
            original_count = len(self._history)
            self._history = [h for h in self._history if h.user_id != user_id]
            return original_count - len(self._history)
        else:
            count = len(self._history)
            self._history = []
            return count
    
    def _entry_to_dict(self, entry: QueryHistoryEntry) -> Dict[str, Any]:
        """Convert a QueryHistoryEntry to dictionary"""
        result = asdict(entry)
        # Convert datetime to ISO format for JSON serialization
        result["timestamp"] = entry.timestamp.isoformat()
        return result
    
    async def get_popular_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most frequently executed queries"""
        query_counts = {}
        query_examples = {}
        
        for entry in self._history:
            # Normalize query for counting (remove extra whitespace)
            normalized_query = " ".join(entry.query.split()).lower()
            
            if normalized_query in query_counts:
                query_counts[normalized_query] += 1
            else:
                query_counts[normalized_query] = 1
                query_examples[normalized_query] = entry.query
        
        # Sort by frequency
        popular = sorted(query_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        
        return [
            {
                "query": query_examples[query],
                "execution_count": count,
                "normalized_query": query
            }
            for query, count in popular
        ]

    async def save_query_result(
        self,
        result,  # SQLExecutionResult object
        session_id: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Save a query execution result to history"""
        return await self.add_query_execution(
            query=result.query,
            execution_time=result.execution_time_ms,
            status="success" if result.success else "error",
            result_count=result.row_count,
            error_message=result.error_message,
            database_name=user_context.get("database_name") if user_context else None,
            user_id=session_id,
            metadata={
                "query_type": result.metadata.get("query_type") if result.metadata else None,
                "affected_rows": result.affected_rows,
                "columns": result.columns,
                "user_context": user_context or {}
            }
        )


# Global history service instance
history_service = HistoryService()