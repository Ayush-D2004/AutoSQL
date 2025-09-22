"""
Google Gemini AI Integration

This module provides AI-powered SQL generation using Google's Gemini model.
Handles natural language to SQL conversion with retry logic and error handling.
"""

import google.generativeai as genai
from typing import Dict, Any, Optional, List, Tuple
import logging
import json
import re
from datetime import datetime

from ..core.config import settings
from .sql_examples import get_examples_context
from .prompts import build_enhanced_prompt, get_error_guidance

logger = logging.getLogger(__name__)


class GeminiSQLGenerator:
    """
    Google Gemini integration for natural language to SQL conversion
    """
    
    def __init__(self):
        """Initialize Gemini client"""
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)
        logger.info(f"Initialized Gemini model: {settings.gemini_model}")
    
    def _build_schema_context(self, schema: Dict[str, Any]) -> str:
        """
        Build a concise schema description for AI context
        
        Args:
            schema: Database schema information dictionary
            
        Returns:
            Formatted schema description string
        """
        if not schema or not schema.get('tables'):
            return "No tables exist in the database yet."
        
        context_parts = ["Database contains the following tables with EXACT column definitions:"]
        
        for table in schema.get('tables', []):
            table_name = table.get('name', 'unknown')
            columns = table.get('columns', [])
            
            if columns:
                column_descriptions = []
                for col in columns:
                    col_desc = f"{col.get('name', 'unknown')} ({col.get('type', 'unknown')})"
                    if col.get('primary_key'):
                        col_desc += " PRIMARY KEY"
                    if not col.get('nullable', True):
                        col_desc += " NOT NULL"
                    column_descriptions.append(col_desc)
                
                context_parts.append(f"Table '{table_name}' has ONLY these columns: {', '.join(column_descriptions)}")
            else:
                context_parts.append(f"Table '{table_name}': (no columns defined)")
        
        # Add foreign key relationships if available
        for table in schema.get('tables', []):
            table_name = table.get('name', 'unknown')
            foreign_keys = table.get('foreign_keys', [])
            if foreign_keys:
                for fk in foreign_keys:
                    context_parts.append(f"  {table_name}.{fk.get('column')} → {fk.get('referenced_table')}.{fk.get('referenced_column')}")
        
        context_parts.append("")
        context_parts.append("IMPORTANT: You must ONLY use the columns that exist in the above schema. Do NOT assume or add columns that are not explicitly listed.")
        
        return "\n".join(context_parts)
    
    def _build_prompt(self, user_prompt: str, schema_context: str, conversation_context: Optional[str] = None, error_context: Optional[str] = None) -> str:
        """
        Build the complete prompt for Gemini with comprehensive instructions
        
        Args:
            user_prompt: User's natural language request
            schema_context: Current database schema description
            conversation_context: Previous conversation context
            error_context: Previous error to help with correction
            
        Returns:
            Complete prompt string for Gemini
        """
        # Use the enhanced prompting system
        if error_context:
            error_guidance = get_error_guidance(error_context)
            enhanced_error_context = f"{error_context}\n\nGuidance: {error_guidance}"
        else:
            enhanced_error_context = None
            
        return build_enhanced_prompt(
            user_prompt=user_prompt,
            editor_content=f"CURRENT DATABASE SCHEMA (AUTHORITATIVE - USE ONLY THESE TABLES AND COLUMNS):\n{schema_context}" + (f"\n\nPrevious conversation context:\n{conversation_context}" if conversation_context else ""),
            include_examples=True,
            error_context=enhanced_error_context
        )
    
    def _extract_sql_from_response(self, response: str) -> str:
        """
        Extract SQL query from Gemini response
        
        Args:
            response: Raw response from Gemini
            
        Returns:
            Cleaned SQL query
        """
        # Handle None or empty response
        if not response:
            return ""
            
        # Remove markdown code blocks if present
        sql = re.sub(r'```sql\s*\n?', '', response)
        sql = re.sub(r'```\s*\n?', '', sql)
        
        # Remove common prefixes
        sql = re.sub(r'^(SQL|Query|Answer):\s*', '', sql, flags=re.IGNORECASE)
        
        # Clean up whitespace but preserve internal structure
        sql = sql.strip()
        
        # If still empty after cleanup, return empty string
        if not sql:
            return ""
        
        # Ensure semicolon at the end
        if sql and not sql.endswith(';'):
            sql += ';'
        
        return sql
    
    async def generate_sql_from_prompt(
        self, 
        prompt: str, 
        schema: Dict[str, Any],
        conversation_context: Optional[str] = None,
        max_retries: int = 3,
        error_context: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Generate SQL from natural language prompt with conversation context
        
        Args:
            prompt: User's natural language request
            schema: Current database schema
            conversation_context: Previous conversation context
            max_retries: Maximum number of retry attempts
            error_context: Previous error for correction attempts
            
        Returns:
            Tuple of (generated_sql, metadata)
            
        Raises:
            Exception: If SQL generation fails after all retries
        """
        schema_context = self._build_schema_context(schema)
        full_prompt = self._build_prompt(prompt, schema_context, conversation_context, error_context)
        
        metadata = {
            "original_prompt": prompt,
            "schema_context": schema_context,
            "model_used": settings.gemini_model,
            "timestamp": datetime.utcnow().isoformat(),
            "attempts": 0,
            "error_context": error_context
        }
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                metadata["attempts"] = attempt + 1
                logger.info(f"Generating SQL (attempt {attempt + 1}/{max_retries}) for prompt: {prompt[:100]}...")
                
                # Generate response from Gemini
                response = await self._generate_with_retry(full_prompt)
                
                # Extract SQL from response
                sql = self._extract_sql_from_response(response.text)
                
                if not sql:
                    raise ValueError("Empty SQL response from Gemini")
                
                # Basic SQL validation
                if not self._basic_sql_validation(sql):
                    raise ValueError("Generated SQL failed basic validation")
                
                metadata["generated_sql"] = sql
                metadata["raw_response"] = response.text
                metadata["success"] = True
                
                logger.info(f"Successfully generated SQL: {sql}")
                return sql, metadata
                
            except Exception as e:
                last_error = str(e)
                metadata["last_error"] = last_error
                logger.warning(f"SQL generation attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    # Update prompt with error context for retry
                    full_prompt = self._build_prompt(prompt, schema_context, conversation_context, last_error)
        
        # All attempts failed
        metadata["success"] = False
        error_msg = f"Failed to generate SQL after {max_retries} attempts. Last error: {last_error}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    async def _generate_with_retry(self, prompt: str, max_api_retries: int = 2):
        """
        Generate response with API-level retry logic
        
        Args:
            prompt: The prompt to send to Gemini
            max_api_retries: Maximum API retry attempts
            
        Returns:
            Gemini response object
        """
        import asyncio
        
        for attempt in range(max_api_retries):
            try:
                # Run the synchronous Gemini call in a thread pool
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.model.generate_content(
                        prompt,
                        generation_config={
                            "temperature": 0.1,  # Low temperature for more deterministic output
                            "top_p": 0.95,
                            "top_k": 40,
                            "max_output_tokens": 2048,  # Increased for complex queries
                            # Removed problematic stop_sequences that might interfere with SQL generation
                        }
                    )
                )
                
                # Check if response is valid - be more tolerant of empty-looking responses
                if response and hasattr(response, 'text'):
                    # Even if text is empty string, let it through - might be whitespace issue
                    if response.text is not None:
                        return response
                    else:
                        raise ValueError("Response text is None")
                else:
                    raise ValueError(f"Invalid response structure: {type(response)}")
                
            except Exception as e:
                logger.warning(f"Gemini API call attempt {attempt + 1} failed: {e}")
                # Add more detailed logging
                if hasattr(e, '__dict__'):
                    logger.warning(f"Exception details: {e.__dict__}")
                if attempt == max_api_retries - 1:
                    raise
                # Wait before retry
                await asyncio.sleep(1)
        
        raise Exception("Failed to get response from Gemini API")
    
    async def _generate_multimodal_with_retry(self, contents: List[Dict[str, Any]], max_api_retries: int = 2):
        """
        Generate response with multimodal input (text + images) and API-level retry logic
        
        Args:
            contents: List of content parts (text and/or images)
            max_api_retries: Maximum API retry attempts
            
        Returns:
            Gemini response object
        """
        import asyncio
        
        for attempt in range(max_api_retries):
            try:
                # Run the synchronous Gemini call in a thread pool
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.model.generate_content(
                        contents,
                        generation_config={
                            "temperature": 0.1,
                            "top_p": 0.95,
                            "top_k": 40,
                            "max_output_tokens": 4096,  # Increased for image analysis
                        }
                    )
                )
                
                if response and hasattr(response, 'text'):
                    if response.text is not None:
                        return response
                    else:
                        raise ValueError("Response text is None")
                else:
                    raise ValueError(f"Invalid response structure: {type(response)}")
                
            except Exception as e:
                logger.warning(f"Gemini multimodal API call attempt {attempt + 1} failed: {e}")
                if hasattr(e, '__dict__'):
                    logger.warning(f"Exception details: {e.__dict__}")
                if attempt == max_api_retries - 1:
                    raise
                await asyncio.sleep(1)
        
        raise Exception("Failed to get response from Gemini multimodal API")
    
    def _basic_sql_validation(self, sql: str) -> bool:
        """
        Perform basic SQL validation
        
        Args:
            sql: SQL query to validate
            
        Returns:
            True if basic validation passes
        """
        if not sql or not sql.strip():
            return False
        
        sql_lower = sql.lower().strip()
        
        # Check for any transaction control statements (not allowed in our context)
        transaction_patterns = [
            'begin;', 'commit;', 'rollback;', 'begin transaction;',
            'start transaction;', 'end transaction;', 'begin exclusive;',
            'begin immediate;', 'begin deferred;'
        ]
        
        # Check if the entire SQL is just a transaction control statement
        if any(sql_lower == pattern for pattern in transaction_patterns):
            logger.warning(f"SQL validation failed: Standalone transaction control statement not allowed: {sql}")
            return False
            
        # Also check if the SQL contains only transaction control keywords
        sql_tokens = sql_lower.replace(';', '').split()
        if len(sql_tokens) <= 2 and any(token in ['begin', 'commit', 'rollback', 'transaction', 'start', 'end'] for token in sql_tokens):
            logger.warning(f"SQL validation failed: Transaction control statement detected: {sql}")
            return False
        
        # Check for basic SQL keywords (excluding standalone transaction control)
        sql_keywords = ['select', 'insert', 'update', 'delete', 'create', 'drop', 'alter', 'with']
        
        # Check if any line starts with a SQL keyword
        lines = sql_lower.split('\n')
        has_sql_keyword = False
        for line in lines:
            line = line.strip()
            if line and any(line.startswith(keyword) for keyword in sql_keywords):
                has_sql_keyword = True
                break
        
        if not has_sql_keyword:
            logger.warning(f"SQL validation failed: No recognized SQL keyword found in: {sql}")
            return False
        
        # Check for balanced parentheses
        if sql.count('(') != sql.count(')'):
            logger.warning(f"SQL validation failed: Unbalanced parentheses in: {sql}")
            return False
        
        # Check for semicolon termination
        if not sql.rstrip().endswith(';'):
            logger.warning(f"SQL validation failed: Missing semicolon in: {sql}")
            return False
        
        return True

    async def solve_from_multimodal_input(
        self,
        prompt: Optional[str] = None,
        images: Optional[List[bytes]] = None,
        image_mimes: Optional[List[str]] = None,
        schema: Optional[Dict[str, Any]] = None,
        max_retries: int = 2
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Solve questions from multimodal input (text + images)
        
        Args:
            prompt: Optional text prompt
            images: List of image bytes
            image_mimes: List of MIME types for images
            schema: Database schema for SQL context
            max_retries: Maximum retry attempts
            
        Returns:
            Tuple of (response_text, metadata)
        """
        if not prompt and not images:
            raise ValueError("Either prompt or images must be provided")
        
        # Build multimodal content
        contents = []
        
        # Add system instruction
        system_prompt = """You are an AI assistant that analyzes images containing database tables and data.

CORE PRINCIPLE: Only do what the user specifically requests. Do not solve questions unless explicitly asked.

CAPABILITIES:
1. Extract table structures and data from images
2. Generate CREATE TABLE statements
3. Generate INSERT statements with exact data from images  
4. Answer specific SQL questions when asked

RESPONSE FORMAT:
Use this exact format for table creation requests:

## Table Analysis
[Brief description of tables found]

## SQL Code

```sql
-- Creating Students table
CREATE TABLE Students (
    StudentID INT PRIMARY KEY,
    Name VARCHAR(255),
    Age INT,
    Department VARCHAR(255),
    CGPA DECIMAL(3,1)
);

-- Inserting data into Students table
INSERT INTO Students (StudentID, Name, Age, Department, CGPA) VALUES
(101, 'Asha', 20, 'CSE', 8.5),
(102, 'Priya', 21, 'IT', 7.2);

-- [Continue for other tables]
```

FORMATTING RULES:
- Use double line breaks between sections
- Use proper markdown headers with ##
- Use ```sql code blocks for all SQL
- Add descriptive comments before each statement
- Extract exact data from the image - do not invent data
- ALWAYS use proper table naming: First letter Capital, rest lowercase (e.g., Students, Courses, Enrollments)
- ALWAYS end with SELECT statements to display the data from all created tables

EXAMPLE ENDING:
```sql
-- Display all data from created tables
SELECT * FROM Students;
SELECT * FROM Courses;
SELECT * FROM Enrollments;
```

DATABASE CONTEXT:"""
        
        if schema and schema.get('tables'):
            system_prompt += f"\nCurrent database schema:\n{self._build_schema_context(schema)}"
        else:
            system_prompt += "\nNo existing database schema available."
            
        system_prompt += """

REMEMBER: Extract exactly what you see in the image - do not add extra information or solve unsolicited questions."""
        
        contents.append({"role": "user", "parts": [{"text": system_prompt}]})
        
        # Add text prompt if provided
        if prompt:
            contents.append({"role": "user", "parts": [{"text": f"""USER REQUEST: {prompt}

IMPORTANT:
- Focus ONLY on what the user is asking for
- If they want table creation with data, provide CREATE TABLE + INSERT statements
- If they want to solve questions, solve only the questions they specify
- Extract exact data from the image - do not invent data
- Use proper SQL formatting with clear line breaks
- ALWAYS end with SELECT statements to show the data from created tables
- Do not answer unsolicited questions from the image"""}]})
        
        # Add images if provided
        if images and image_mimes:
            import base64
            for image_bytes, mime_type in zip(images, image_mimes):
                b64_image = base64.b64encode(image_bytes).decode("utf-8")
                contents.append({
                    "role": "user", 
                    "parts": [{
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_image
                        }
                    }]
                })
        
        # Generate response with retry logic
        try:
            response = await self._generate_multimodal_with_retry(contents, max_retries)
            response_text = response.text
            
            if not response_text or not response_text.strip():
                raise ValueError("Received empty response from Gemini")
            
            # Only strip leading/trailing whitespace but preserve internal formatting
            response_text = response_text.strip()
            
            # Metadata
            metadata = {
                "model": settings.gemini_model,
                "timestamp": datetime.utcnow().isoformat(),
                "has_images": bool(images),
                "has_text": bool(prompt),
                "image_count": len(images) if images else 0,
                "retries_used": 0,  # Could track this if needed
                "raw_response_length": len(response_text)
            }
            
            logger.info(f"Successfully generated multimodal response. Length: {len(response_text)}")
            return response_text, metadata
            
        except Exception as e:
            logger.error(f"Failed to generate multimodal response: {e}")
            error_metadata = {
                "error": str(e),
                "model": settings.gemini_model,
                "timestamp": datetime.utcnow().isoformat(),
                "has_images": bool(images),
                "has_text": bool(prompt),
                "image_count": len(images) if images else 0,
            }
            
            return f"Error processing request: {str(e)}", error_metadata


# Global instance
gemini_generator = GeminiSQLGenerator() if settings.google_api_key else None


async def generate_sql_from_prompt(
    prompt: str, 
    schema: Dict[str, Any],
    conversation_context: Optional[str] = None,
    max_retries: int = 3,
    error_context: Optional[str] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Main function to generate SQL from natural language prompt with conversation context
    
    Args:
        prompt: User's natural language request
        schema: Current database schema
        conversation_context: Previous conversation context
        max_retries: Maximum number of retry attempts
        error_context: Previous error for correction attempts
        
    Returns:
        Tuple of (generated_sql, metadata)
    """
    if not gemini_generator:
        raise ValueError("Gemini is not configured. Please set GOOGLE_API_KEY environment variable.")
    
    return await gemini_generator.generate_sql_from_prompt(
        prompt=prompt,
        schema=schema,
        conversation_context=conversation_context,
        max_retries=max_retries,
        error_context=error_context
    )
