"""
File Parsing Utilities

Provides utilities for parsing different file formats for AI processing.
"""

import json
import csv
import io
import pandas as pd
from typing import Dict, Any, List, Optional, Union
import logging

logger = logging.getLogger(__name__)


class FileParser:
    """Utility class for parsing different file formats"""
    
    @staticmethod
    def parse_sql_file(content: bytes, filename: str) -> Dict[str, Any]:
        """
        Parse SQL file content
        
        Args:
            content: Raw file bytes
            filename: Name of the file
            
        Returns:
            Dictionary with parsed content information
        """
        try:
            # Decode text content
            text_content = content.decode('utf-8')
            
            # Basic SQL statement detection
            statements = []
            lines = text_content.split('\n')
            current_statement = []
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('--'):
                    continue
                    
                current_statement.append(line)
                if line.endswith(';'):
                    statements.append(' '.join(current_statement))
                    current_statement = []
            
            # Add remaining statement if it doesn't end with semicolon
            if current_statement:
                statements.append(' '.join(current_statement))
            
            return {
                "type": "sql",
                "filename": filename,
                "content": text_content,
                "statements": statements,
                "statement_count": len(statements),
                "size": len(content)
            }
            
        except Exception as e:
            logger.error(f"Error parsing SQL file {filename}: {e}")
            return {
                "type": "sql",
                "filename": filename,
                "error": str(e),
                "size": len(content)
            }
    
    @staticmethod
    def parse_json_file(content: bytes, filename: str) -> Dict[str, Any]:
        """
        Parse JSON file content
        
        Args:
            content: Raw file bytes
            filename: Name of the file
            
        Returns:
            Dictionary with parsed content information
        """
        try:
            # Decode and parse JSON
            text_content = content.decode('utf-8')
            json_data = json.loads(text_content)
            
            # Analyze structure
            data_type = type(json_data).__name__
            
            structure_info = {}
            if isinstance(json_data, dict):
                structure_info = {
                    "keys": list(json_data.keys()),
                    "key_count": len(json_data)
                }
            elif isinstance(json_data, list):
                structure_info = {
                    "length": len(json_data),
                    "sample_item": json_data[0] if json_data else None
                }
            
            return {
                "type": "json",
                "filename": filename,
                "content": text_content,
                "parsed_data": json_data,
                "data_type": data_type,
                "structure": structure_info,
                "size": len(content)
            }
            
        except Exception as e:
            logger.error(f"Error parsing JSON file {filename}: {e}")
            return {
                "type": "json",
                "filename": filename,
                "error": str(e),
                "size": len(content)
            }
    
    @staticmethod
    def parse_csv_file(content: bytes, filename: str) -> Dict[str, Any]:
        """
        Parse CSV file content
        
        Args:
            content: Raw file bytes
            filename: Name of the file
            
        Returns:
            Dictionary with parsed content information
        """
        try:
            # Decode text content
            text_content = content.decode('utf-8')
            
            # Parse CSV
            csv_reader = csv.reader(io.StringIO(text_content))
            rows = list(csv_reader)
            
            headers = rows[0] if rows else []
            data_rows = rows[1:] if len(rows) > 1 else []
            
            return {
                "type": "csv",
                "filename": filename,
                "content": text_content,
                "headers": headers,
                "data_rows": data_rows,
                "row_count": len(data_rows),
                "column_count": len(headers),
                "size": len(content)
            }
            
        except Exception as e:
            logger.error(f"Error parsing CSV file {filename}: {e}")
            return {
                "type": "csv",
                "filename": filename,
                "error": str(e),
                "size": len(content)
            }
    
    @staticmethod
    def parse_excel_file(content: bytes, filename: str) -> Dict[str, Any]:
        """
        Parse Excel file content
        
        Args:
            content: Raw file bytes
            filename: Name of the file
            
        Returns:
            Dictionary with parsed content information
        """
        try:
            # Read Excel file from bytes
            excel_file = pd.ExcelFile(io.BytesIO(content))
            
            # Get sheet names
            sheet_names = excel_file.sheet_names
            
            # Parse first sheet (or all sheets if small)
            sheets_data = {}
            for sheet_name in sheet_names[:3]:  # Limit to first 3 sheets
                df = pd.read_excel(io.BytesIO(content), sheet_name=sheet_name)
                
                # Convert all data to records instead of just sample
                sheets_data[sheet_name] = {
                    "headers": df.columns.tolist(),
                    "row_count": len(df),
                    "column_count": len(df.columns),
                    "all_data": df.to_dict('records') if not df.empty else []
                }
            
            return {
                "type": "excel",
                "filename": filename,
                "sheet_names": sheet_names,
                "sheet_count": len(sheet_names),
                "sheets_data": sheets_data,
                "size": len(content)
            }
            
        except Exception as e:
            logger.error(f"Error parsing Excel file {filename}: {e}")
            return {
                "type": "excel",
                "filename": filename,
                "error": str(e),
                "size": len(content)
            }
    
    @staticmethod
    def parse_text_file(content: bytes, filename: str) -> Dict[str, Any]:
        """
        Parse plain text file content
        
        Args:
            content: Raw file bytes
            filename: Name of the file
            
        Returns:
            Dictionary with parsed content information
        """
        try:
            # Decode text content
            text_content = content.decode('utf-8')
            
            # Basic text analysis
            lines = text_content.split('\n')
            words = text_content.split()
            
            return {
                "type": "text",
                "filename": filename,
                "content": text_content,
                "line_count": len(lines),
                "word_count": len(words),
                "char_count": len(text_content),
                "size": len(content)
            }
            
        except Exception as e:
            logger.error(f"Error parsing text file {filename}: {e}")
            return {
                "type": "text",
                "filename": filename,
                "error": str(e),
                "size": len(content)
            }
    
    @classmethod
    def parse_file(cls, content: bytes, filename: str, content_type: str = None) -> Dict[str, Any]:
        """
        Parse file based on its type
        
        Args:
            content: Raw file bytes
            filename: Name of the file
            content_type: MIME type of the file
            
        Returns:
            Dictionary with parsed content information
        """
        # Determine file type from extension
        extension = filename.lower().split('.')[-1] if '.' in filename else ""
        
        # Route to appropriate parser
        if extension == 'sql':
            return cls.parse_sql_file(content, filename)
        elif extension == 'json':
            return cls.parse_json_file(content, filename)
        elif extension in ['csv']:
            return cls.parse_csv_file(content, filename)
        elif extension in ['xlsx', 'xls']:
            return cls.parse_excel_file(content, filename)
        elif extension in ['txt']:
            return cls.parse_text_file(content, filename)
        else:
            # Default to text parsing
            return cls.parse_text_file(content, filename)


def format_parsed_files_for_ai(parsed_files: List[Dict[str, Any]]) -> str:
    """
    Format parsed file data for AI consumption
    
    Args:
        parsed_files: List of parsed file dictionaries
        
    Returns:
        Formatted string for AI context
    """
    if not parsed_files:
        return ""
    
    sections = []
    
    for i, file_data in enumerate(parsed_files, 1):
        filename = file_data.get('filename', f'File {i}')
        file_type = file_data.get('type', 'unknown')
        
        section = f"\n## File {i}: {filename} ({file_type.upper()})\n"
        
        if 'error' in file_data:
            section += f"❌ Error parsing file: {file_data['error']}\n"
            sections.append(section)
            continue
        
        # Format based on file type
        if file_type == 'sql':
            section += f"SQL Statements ({file_data.get('statement_count', 0)}):\n"
            section += "```sql\n"
            section += file_data.get('content', '')[:2000]  # Limit content
            if len(file_data.get('content', '')) > 2000:
                section += "\n... (truncated)"
            section += "\n```\n"
            
        elif file_type == 'json':
            section += f"JSON Data ({file_data.get('data_type', 'unknown')} type):\n"
            section += "```json\n"
            content = file_data.get('content', '')
            section += content[:1500]  # Limit content
            if len(content) > 1500:
                section += "\n... (truncated)"
            section += "\n```\n"
            
        elif file_type == 'csv':
            section += f"CSV Data ({file_data.get('row_count', 0)} rows, {file_data.get('column_count', 0)} columns):\n"
            section += f"Headers: {', '.join(file_data.get('headers', []))}\n"
            if file_data.get('data_rows'):
                section += "ALL DATA (create INSERT statements for ALL rows):\n```\n"
                # Include ALL data rows, not just a sample
                for row in file_data['data_rows']:
                    section += f"{', '.join(str(cell) for cell in row)}\n"
                section += "```\n"
                
        elif file_type == 'excel':
            section += f"Excel File ({file_data.get('sheet_count', 0)} sheets):\n"
            for sheet_name, sheet_data in file_data.get('sheets_data', {}).items():
                section += f"\n**Sheet: {sheet_name}**\n"
                section += f"- {sheet_data.get('row_count', 0)} rows, {sheet_data.get('column_count', 0)} columns\n"
                section += f"- Headers: {', '.join(sheet_data.get('headers', []))}\n"
                
                # Include ALL data for Excel sheets too
                if sheet_data.get('all_data'):
                    section += "ALL DATA (create INSERT statements for ALL rows):\n```json\n"
                    # Format each row as a readable data entry
                    import json
                    for row_data in sheet_data['all_data']:
                        section += f"{json.dumps(row_data)}\n"
                    section += "```\n"
                
        elif file_type == 'text':
            section += f"Text File ({file_data.get('line_count', 0)} lines, {file_data.get('word_count', 0)} words):\n"
            section += "```\n"
            content = file_data.get('content', '')
            section += content[:1000]  # Limit content
            if len(content) > 1000:
                section += "\n... (truncated)"
            section += "\n```\n"
        
        sections.append(section)
    
    return "\n".join(sections)