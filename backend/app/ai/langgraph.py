"""
LangGraph AI Workflow

This module implements a comprehensive workflow for natural language to SQL processing
using LangGraph for state management and complex multi-step operations.
"""

from typing import Dict, Any, Optional, List, TypedDict, Union
from datetime import datetime
import logging
import asyncio

from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from .gemini import generate_sql_from_prompt
from ..database.sql_executor import db_executor
from ..database.schema_inspector import schema_inspector
from ..database.history_service import history_service

logger = logging.getLogger(__name__)


class WorkflowState(TypedDict):
    """State object for the AI workflow"""
    # Input
    user_prompt: str
    session_id: Optional[str]
    
    # Schema context
    schema: Dict[str, Any]
    
    # AI Processing
    generated_sql: Optional[str]
    sql_metadata: Dict[str, Any]
    
    # Execution
    execution_result: Optional[Dict[str, Any]]
    execution_success: bool
    
    # Error handling
    errors: List[str]
    retry_count: int
    max_retries: int
    
    # Final output
    final_response: Dict[str, Any]
    
    # Messages for conversation history
    messages: List[BaseMessage]


class SQLWorkflow:
    """
    LangGraph workflow for natural language to SQL processing
    """
    
    def __init__(self):
        """Initialize the workflow"""
        self.graph = self._build_workflow_graph()
        logger.info("SQL Workflow initialized")
    
    def _build_workflow_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow
        
        Returns:
            Configured StateGraph
        """
        workflow = StateGraph(WorkflowState)
        
        # Add nodes
        workflow.add_node("get_schema", self._get_schema_node)
        workflow.add_node("generate_sql", self._generate_sql_node)
        workflow.add_node("validate_sql", self._validate_sql_node)
        workflow.add_node("execute_sql", self._execute_sql_node)
        workflow.add_node("handle_error", self._handle_error_node)
        workflow.add_node("save_history", self._save_history_node)
        workflow.add_node("build_response", self._build_response_node)
        
        # Define workflow edges
        workflow.set_entry_point("get_schema")
        
        workflow.add_edge("get_schema", "generate_sql")
        workflow.add_edge("generate_sql", "validate_sql")
        
        # Conditional edges based on validation
        workflow.add_conditional_edges(
            "validate_sql",
            self._should_execute_sql,
            {
                "execute": "execute_sql",
                "retry": "handle_error",
                "failed": "build_response"
            }
        )
        
        # Conditional edges based on execution
        workflow.add_conditional_edges(
            "execute_sql",
            self._handle_execution_result,
            {
                "success": "save_history",
                "retry": "handle_error",
                "failed": "build_response"
            }
        )
        
        workflow.add_edge("save_history", "build_response")
        
        # Error handling can retry or end
        workflow.add_conditional_edges(
            "handle_error",
            self._should_retry,
            {
                "retry": "generate_sql",
                "failed": "build_response"
            }
        )
        
        workflow.add_edge("build_response", END)
        
        return workflow.compile()
    
    async def _get_schema_node(self, state: WorkflowState) -> WorkflowState:
        """
        Get current database schema
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with schema information
        """
        try:
            logger.info("Getting database schema...")
            schema_obj = await schema_inspector.get_full_schema()
            schema = schema_obj.to_dict()
            
            state["schema"] = schema
            state["messages"].append(AIMessage(content="Retrieved database schema"))
            
            logger.info(f"Schema retrieved: {len(schema.get('tables', []))} tables found")
            
        except Exception as e:
            error_msg = f"Failed to get schema: {str(e)}"
            logger.error(error_msg)
            state["errors"].append(error_msg)
            state["schema"] = {"tables": [], "relations": []}
        
        return state
    
    async def _generate_sql_node(self, state: WorkflowState) -> WorkflowState:
        """
        Generate SQL from natural language prompt
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with generated SQL
        """
        try:
            logger.info(f"Generating SQL for prompt: {state['user_prompt']}")
            
            # Get error context if this is a retry
            error_context = None
            if state["retry_count"] > 0 and state["errors"]:
                error_context = state["errors"][-1]
            
            sql, metadata = await generate_sql_from_prompt(
                prompt=state["user_prompt"],
                schema=state["schema"],
                error_context=error_context
            )
            
            state["generated_sql"] = sql
            state["sql_metadata"] = metadata
            state["messages"].append(AIMessage(content=f"Generated SQL: {sql}"))
            
            logger.info(f"SQL generated successfully: {sql}")
            
        except Exception as e:
            error_msg = f"Failed to generate SQL: {str(e)}"
            logger.error(error_msg)
            state["errors"].append(error_msg)
            state["generated_sql"] = None
            state["sql_metadata"] = {}
        
        return state
    
    async def _validate_sql_node(self, state: WorkflowState) -> WorkflowState:
        """
        Validate generated SQL
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with validation results
        """
        if not state["generated_sql"]:
            state["errors"].append("No SQL to validate")
            return state
        
        try:
            # Basic syntax validation (could add more sophisticated validation)
            sql = state["generated_sql"].strip()
            
            # Check for dangerous operations in production
            dangerous_keywords = ["drop", "truncate", "delete from", "update"]
            sql_lower = sql.lower()
            
            for keyword in dangerous_keywords:
                if keyword in sql_lower:
                    logger.warning(f"Potentially dangerous SQL detected: {keyword}")
                    # In production, you might want to require explicit confirmation
            
            state["messages"].append(AIMessage(content="SQL validation passed"))
            logger.info("SQL validation successful")
            
        except Exception as e:
            error_msg = f"SQL validation failed: {str(e)}"
            logger.error(error_msg)
            state["errors"].append(error_msg)
        
        return state
    
    async def _execute_sql_node(self, state: WorkflowState) -> WorkflowState:
        """
        Execute the generated SQL
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with execution results
        """
        if not state["generated_sql"]:
            state["errors"].append("No SQL to execute")
            state["execution_success"] = False
            return state
        
        try:
            logger.info(f"Executing SQL: {state['generated_sql']}")
            
            # Execute the SQL using smart execution for multiple statements with auto-preprocessing
            results = await db_executor.execute_sql_smart(
                sql_text=state["generated_sql"],
                auto_commit=True,
                safety_check=True,
                forgiving_mode=True,
                auto_preprocess=True  # Enable auto-preprocessing for clean table state
            )
            
            # Handle multiple results - use the last successful one for display
            if results:
                # Find the best result to display (prefer SELECT results)
                display_result = None
                for result in reversed(results):
                    if result.success and (result.rows or result.affected_rows > 0):
                        display_result = result
                        break
                
                if not display_result:
                    display_result = results[-1]  # Use last result if no good one found
                
                # Check if all results were successful
                all_successful = all(r.success for r in results)
                
                state["execution_result"] = display_result.to_dict()
                state["execution_success"] = all_successful
                
                if all_successful:
                    if len(results) > 1:
                        state["messages"].append(AIMessage(content=f"Multiple SQL statements executed successfully. Final result rows: {display_result.row_count}"))
                        logger.info(f"Multiple SQL statements executed successfully. Statements: {len(results)}, Final rows: {display_result.row_count}")
                    else:
                        state["messages"].append(AIMessage(content=f"SQL executed successfully. Rows: {display_result.row_count}"))
                        logger.info(f"SQL execution successful. Rows: {display_result.row_count}")
                else:
                    # Find first error
                    error_results = [r for r in results if not r.success]
                    if error_results:
                        error_msg = f"SQL execution failed: {error_results[0].error_message}"
                    else:
                        error_msg = "SQL execution failed: Unknown error"
                    state["errors"].append(error_msg)
                    state["messages"].append(AIMessage(content=error_msg))
                    logger.error(error_msg)
            else:
                error_msg = "SQL execution failed: No results returned"
                state["errors"].append(error_msg)
                state["execution_success"] = False
                state["execution_result"] = None
            
        except Exception as e:
            error_msg = f"SQL execution error: {str(e)}"
            logger.error(error_msg)
            state["errors"].append(error_msg)
            state["execution_success"] = False
            state["execution_result"] = None
        
        return state
    
    async def _handle_error_node(self, state: WorkflowState) -> WorkflowState:
        """
        Handle errors and prepare for retry
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with error handling
        """
        state["retry_count"] += 1
        
        if state["retry_count"] <= state["max_retries"]:
            logger.info(f"Preparing retry {state['retry_count']}/{state['max_retries']}")
            state["messages"].append(AIMessage(content=f"Retry attempt {state['retry_count']}"))
        else:
            logger.error(f"Max retries ({state['max_retries']}) exceeded")
            state["messages"].append(AIMessage(content="Max retries exceeded"))
        
        return state
    
    async def _save_history_node(self, state: WorkflowState) -> WorkflowState:
        """
        Save successful query to history
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state
        """
        if state["execution_success"] and state["execution_result"]:
            try:
                # Create execution result object for history
                from ..database.sql_executor import SQLExecutionResult
                
                result_data = state["execution_result"]
                result = SQLExecutionResult(
                    success=result_data["success"],
                    query=result_data["query"],
                    execution_time_ms=result_data["execution_time_ms"],
                    rows=result_data.get("rows", []),
                    columns=result_data.get("columns", []),
                    row_count=result_data.get("row_count", 0),
                    affected_rows=result_data.get("affected_rows", 0),
                    error_message=result_data.get("error_message"),
                    error_type=result_data.get("error_type"),
                    metadata={
                        **state["sql_metadata"],
                        "ai_generated": True,
                        "original_prompt": state["user_prompt"]
                    }
                )
                
                await history_service.save_query_result(
                    result,
                    session_id=state["session_id"],
                    user_context={"ai_workflow": True, "prompt": state["user_prompt"]}
                )
                
                state["messages"].append(AIMessage(content="Query saved to history"))
                logger.info("Query saved to history successfully")
                
            except Exception as e:
                logger.warning(f"Failed to save to history: {e}")
                # Don't fail the whole workflow for history save failure
        
        return state
    
    async def _build_response_node(self, state: WorkflowState) -> WorkflowState:
        """
        Build final response
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with final response
        """
        response = {
            "success": state["execution_success"],
            "prompt": state["user_prompt"],
            "sql": state.get("generated_sql"),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if state["execution_success"] and state["execution_result"]:
            result = state["execution_result"]
            response.update({
                "columns": result.get("columns", []),
                "rows": result.get("rows", []),
                "row_count": result.get("row_count", 0),
                "affected_rows": result.get("affected_rows", 0),
                "execution_time_ms": result.get("execution_time_ms", 0)
            })
        else:
            response.update({
                "error": state["errors"][-1] if state["errors"] else "Unknown error",
                "errors": state["errors"],
                "retry_count": state["retry_count"]
            })
        
        # Add metadata
        response["metadata"] = {
            "sql_metadata": state.get("sql_metadata", {}),
            "retry_count": state["retry_count"],
            "schema_tables": len(state.get("schema", {}).get("tables", []))
        }
        
        state["final_response"] = response
        logger.info(f"Final response built. Success: {response['success']}")
        
        return state
    
    def _should_execute_sql(self, state: WorkflowState) -> str:
        """Decide whether to execute SQL based on validation"""
        if state.get("generated_sql") and not state["errors"]:
            return "execute"
        elif state["retry_count"] < state["max_retries"]:
            return "retry"
        else:
            return "failed"
    
    def _handle_execution_result(self, state: WorkflowState) -> str:
        """Handle execution results"""
        if state["execution_success"]:
            return "success"
        elif state["retry_count"] < state["max_retries"]:
            return "retry"
        else:
            return "failed"
    
    def _should_retry(self, state: WorkflowState) -> str:
        """Decide whether to retry based on retry count"""
        if state["retry_count"] < state["max_retries"]:
            return "retry"
        else:
            return "failed"
    
    async def process_natural_language_query(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Process a natural language query through the complete workflow
        
        Args:
            prompt: User's natural language request
            session_id: Optional session identifier
            max_retries: Maximum number of retry attempts
            
        Returns:
            Final response dictionary
        """
        initial_state = WorkflowState(
            user_prompt=prompt,
            session_id=session_id,
            schema={},
            generated_sql=None,
            sql_metadata={},
            execution_result=None,
            execution_success=False,
            errors=[],
            retry_count=0,
            max_retries=max_retries,
            final_response={},
            messages=[HumanMessage(content=prompt)]
        )
        
        logger.info(f"Starting workflow for prompt: {prompt}")
        
        try:
            # Run the workflow
            final_state = await self.graph.ainvoke(initial_state)
            return final_state["final_response"]
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}", exc_info=True)
            return {
                "success": False,
                "prompt": prompt,
                "error": f"Workflow execution failed: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }


# Global workflow instance
sql_workflow = SQLWorkflow()
