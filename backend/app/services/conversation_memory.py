"""
Conversation Memory Service for AutoSQL Backend

This service manages conversation history and context for AI-powered SQL interactions.
"""
from typing import List, Dict, Any, Optional
from enum import Enum
import json
from datetime import datetime
import asyncio


class MessageType(Enum):
    """Types of messages in conversation"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    SQL_EXECUTION = "sql_execution"
    AI_RESPONSE = "ai_response"
    ERROR = "error"


class ConversationMemory:
    """Manages conversation memory and context for AI interactions"""
    
    def __init__(self):
        self._conversations: Dict[str, List[Dict[str, Any]]] = {}
        self._max_history_length = 50  # Maximum messages per conversation
        self._initialized = False
        
    async def initialize(self) -> None:
        """Initialize the conversation memory service"""
        if not self._initialized:
            # Any initialization logic can go here
            self._initialized = True
        
    async def add_message(
        self, 
        conversation_id: Optional[str] = None,
        message: Optional[str] = None,
        role: str = "user",
        metadata: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        message_type: Optional[str] = None,
        content: Optional[str] = None,
        sql_query: Optional[str] = None,
        execution_result: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add a message to the conversation history"""
        # Use session_id as conversation_id if provided
        if session_id:
            conversation_id = session_id
        
        # Use content as message if provided
        if content:
            message = content
            
        # Default conversation_id if not provided
        if not conversation_id:
            conversation_id = "default"
            
        # Default message if not provided
        if not message:
            message = content or ""
            
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []
            
        message_data = {
            "id": f"{conversation_id}_{len(self._conversations[conversation_id])}",
            "message": message,
            "role": role,  # user, assistant, system
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
            "session_id": session_id or conversation_id,
            "message_type": message_type or role,
            "content": content or message,
            "sql_query": sql_query,
            "execution_result": execution_result
        }
        
        self._conversations[conversation_id].append(message_data)
        
        # Trim history if it gets too long
        if len(self._conversations[conversation_id]) > self._max_history_length:
            self._conversations[conversation_id] = self._conversations[conversation_id][-self._max_history_length:]
    
    async def get_conversation_history(
        self, 
        conversation_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get conversation history for a specific conversation"""
        if conversation_id not in self._conversations:
            return []
            
        history = self._conversations[conversation_id]
        
        if limit:
            return history[-limit:]
        return history
    
    async def get_context_messages(
        self, 
        conversation_id: str,
        max_tokens: int = 4000
    ) -> List[Dict[str, str]]:
        """Get conversation context formatted for LLM consumption"""
        history = await self.get_conversation_history(conversation_id)
        
        # Format messages for LLM
        formatted_messages = []
        estimated_tokens = 0
        
        # Add messages in reverse order to prioritize recent context
        for message in reversed(history):
            formatted_message = {
                "role": message["role"],
                "content": message["message"]
            }
            
            # Rough token estimation (4 chars ≈ 1 token)
            message_tokens = len(message["message"]) // 4
            
            if estimated_tokens + message_tokens > max_tokens:
                break
                
            formatted_messages.insert(0, formatted_message)
            estimated_tokens += message_tokens
            
        return formatted_messages
    
    async def get_context_for_ai(
        self, 
        conversation_id: str,
        max_tokens: int = 4000
    ) -> List[Dict[str, str]]:
        """Get conversation context for AI processing (alias for get_context_messages)"""
        return await self.get_context_messages(conversation_id, max_tokens)
    
    async def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Get statistics for a specific session"""
        if session_id not in self._conversations:
            return {
                "session_id": session_id,
                "message_count": 0,
                "user_messages": 0,
                "assistant_messages": 0,
                "system_messages": 0,
                "first_message_time": None,
                "last_message_time": None
            }
        
        messages = self._conversations[session_id]
        user_messages = len([m for m in messages if m.get("role") == "user"])
        assistant_messages = len([m for m in messages if m.get("role") == "assistant"])
        system_messages = len([m for m in messages if m.get("role") == "system"])
        
        timestamps = [datetime.fromisoformat(m["timestamp"]) for m in messages]
        
        return {
            "session_id": session_id,
            "message_count": len(messages),
            "user_messages": user_messages,
            "assistant_messages": assistant_messages,
            "system_messages": system_messages,
            "first_message_time": min(timestamps).isoformat() if timestamps else None,
            "last_message_time": max(timestamps).isoformat() if timestamps else None
        }
    
    async def clear_session(self, session_id: str) -> bool:
        """Clear all messages from a specific session"""
        if session_id in self._conversations:
            del self._conversations[session_id]
            return True
        return False
    
    async def cleanup_old_sessions(self, hours_old: int = 24) -> int:
        """Clean up sessions older than specified hours"""
        from datetime import timedelta
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_old)
        cleaned_count = 0
        
        sessions_to_remove = []
        for session_id, messages in self._conversations.items():
            if messages:
                # Check the last message timestamp
                last_message_time = datetime.fromisoformat(messages[-1]["timestamp"])
                if last_message_time < cutoff_time:
                    sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self._conversations[session_id]
            cleaned_count += 1
        
        return cleaned_count
    
    async def clear_conversation(self, conversation_id: str) -> None:
        """Clear all messages from a conversation"""
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
    
    async def get_active_conversations(self) -> List[str]:
        """Get list of active conversation IDs"""
        return list(self._conversations.keys())
    
    async def add_sql_execution_result(
        self,
        conversation_id: str,
        query: str,
        result: Any,
        execution_time: float,
        error: Optional[str] = None
    ) -> None:
        """Add SQL execution result to conversation context"""
        metadata = {
            "type": "sql_execution",
            "query": query,
            "execution_time": execution_time,
            "error": error,
            "result_type": type(result).__name__
        }
        
        if error:
            message = f"SQL Query Error: {error}"
            role = "system"
        else:
            # Don't include full result in message to save space
            message = f"SQL Query executed successfully in {execution_time:.2f}s"
            role = "system"
            
        await self.add_message(
            conversation_id=conversation_id,
            message=message,
            role=role,
            metadata=metadata
        )
    
    async def add_ai_response(
        self,
        conversation_id: str,
        response: str,
        model_used: str,
        tokens_used: Optional[int] = None
    ) -> None:
        """Add AI response to conversation history"""
        metadata = {
            "type": "ai_response",
            "model_used": model_used,
            "tokens_used": tokens_used
        }
        
        await self.add_message(
            conversation_id=conversation_id,
            message=response,
            role="assistant",
            metadata=metadata
        )
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory usage statistics"""
        total_conversations = len(self._conversations)
        total_messages = sum(len(conv) for conv in self._conversations.values())
        
        return {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "average_messages_per_conversation": total_messages / max(total_conversations, 1)
        }


# Global conversation memory instance
conversation_memory = ConversationMemory()

# Alias for backward compatibility
ConversationHistory = ConversationMemory