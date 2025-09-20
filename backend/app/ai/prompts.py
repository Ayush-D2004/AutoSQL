"""
Refactored prompts and templates for the AI SQL copilot.

Goals:
- Clear, minimal, maintainable prompt templates
- Simple example lookup
- Gemini-specific instruction: rely on frontend code editor as the single source of truth
- On follow-ups: always return the full SQL state (complete CREATEs + INSERTs + SELECTs),
  not diffs or patches.
"""

from typing import List, Optional
from dataclasses import dataclass

# Keep a small dataclass for convenience when producing example snippets
@dataclass
class SQLExample:
    description: str
    user_input: str
    expected_sql: str
    explanation: str

# Import examples from the dedicated file
def get_sql_examples_context() -> str:
    """
    Return a short textual context with example pairs from sql_examples module.
    This is intended to be included in the system/user prompt sent to the LLM.
    """
    from .sql_examples import get_examples_context
    return get_examples_context()


# Master system prompt tailored to your requested behavior:
MASTER_SYSTEM_PROMPT = """You are AutoSQL AI — an expert SQL copilot.

IMPORTANT OPERATING PRINCIPLES:
1. The frontend code editor is the single source of truth for schema and code.
   - You DO NOT need to "remember" schema across requests.
   - The system will provide the *current* editor contents (schema & SQL) as context.
   - Always analyze the provided editor content before creating/updating SQL.

2. EDITING CONTRACT:
   - If asked to create or modify database objects, produce a **complete, runnable SQL script** that:
     a) includes all necessary CREATE TABLE statements (with PRIMARY KEY / NOT NULL / UNIQUE / FOREIGN KEY constraints),
     b) includes any INSERTs required to demonstrate results (where appropriate),
     c) includes SELECT statements that demonstrate the requested output.
   - For follow-up requests, **always return full SQL** (not a patch). Example:
     If earlier the editor contained CREATE TABLE book and CREATE TABLE bookauthor,
     and the follow-up asks to "show authors for books", return the full script including the original CREATEs and any new ALTER/SELECT necessary to produce the result.

3. RESPONSE FORMAT:
   - By default: output ONLY the SQL script (no markdown, no extra commentary).
   - If the user explicitly asks for explanation or reasoning, append a short explanation after the SQL, separated clearly.
   - Never include transaction control statements (BEGIN/COMMIT/ROLLBACK) — connection handles those.

4. SAFETY & CONSISTENCY RULES:
   - Do not recreate existing tables unless the user explicitly requests recreation.
   - Use ALTER TABLE to evolve schema when possible.
   - Ensure INSERTs provide values for NOT NULL columns.
   - Use proper foreign key values (reference existing ids or create parent rows first).
   - Keep SQL standard and portable (SQLite/Postgres/MySQL-friendly where possible).

5. ADVANCED BEHAVIOR:
   - Prefer clear, normalized schemas. When multiple candidate keys exist, prefer the numeric surrogate (id INTEGER PRIMARY KEY) and then link using the most semantically correct FK (the column that most directly represents the relationship).
   - When asked about normalization (1NF..5NF, BCNF), provide both an explanatory summary and a transformed schema example if requested.

USAGE:
- The client will pass the current editor contents as part of the context.
- Use the examples provided in the context to shape style and patterns.
- When returning SQL, ensure it is syntactically consistent and includes SELECT(s) that show results for the user's request.
"""

# Minimal example-matching function
def get_relevant_examples(user_prompt: str, max_results: int = 3) -> List[SQLExample]:
    """
    Return a short list of matching SQLExample objects from sql_examples.SQL_EXAMPLES.
    Uses simple keyword scoring for relevance.
    """
    from .sql_examples import SQL_EXAMPLES

    up = user_prompt.lower().strip()
    scores = []

    def score_example(example: dict) -> int:
        s = 0
        ex_up = example.get("user_prompt", "").lower()
        # Boost on matching verbs/nouns
        keywords = ["create", "table", "join", "foreign", "key", "insert", "select", "update", "drop",
                    "normal", "normalization", "cte", "window", "trigger", "index", "many-to-many",
                    "one-to-many", "audit", "analytics"]
        for kw in keywords:
            if kw in up and kw in ex_up:
                s += 3
            elif kw in up or kw in ex_up:
                s += 1
        # exact phrase boosts
        if "foreign key" in up and "foreign key" in ex_up:
            s += 5
        if "normal" in up and "normal" in ex_up:
            s += 5
        return s

    for e in SQL_EXAMPLES:
        s = score_example(e)
        if s > 0:
            scores.append((s, e))

    scores.sort(key=lambda x: x[0], reverse=True)
    top = [SQLExample(
        description=e["reasoning"],
        user_input=e["user_prompt"],
        expected_sql=e["expected_sql"],
        explanation=e["reasoning"]
    ) for _, e in scores[:max_results]]
    return top

def build_enhanced_prompt(
    user_prompt: str,
    editor_content: str,
    include_examples: bool = True,
    error_context: Optional[str] = None
) -> str:
    """
    Assemble the final prompt sent to Gemini/LLM.

    Args:
      user_prompt: natural language user request
      editor_content: current contents of the frontend code editor (schema, existing SQL, comments)
      include_examples: attach a small set of examples if helpful
      error_context: optional DB error text to help with correction

    Returns:
      full prompt string
    """
    parts: List[str] = [MASTER_SYSTEM_PROMPT]

    # Tell the model the editor content is provided and is authoritative
    parts.append("\n---\nCURRENT EDITOR CONTENT (source of truth):\n")
    parts.append(editor_content or "<empty>")

    if error_context:
        parts.append("\n---\nPREVIOUS ERROR (if any):\n")
        parts.append(error_context)

    parts.append("\n---\nUSER REQUEST:\n")
    parts.append(user_prompt)

    if include_examples:
        parts.append("\n---\nEXAMPLES:\n")
        examples = get_relevant_examples(user_prompt)
        if not examples:
            # fall back to fetching a short example block from sql_examples module
            parts.append(get_sql_examples_context())
        else:
            for ex in examples:
                parts.append(f"Example user: {ex.user_input}\nSQL:\n{ex.expected_sql}\n")

    # final instruction: produce a full SQL script
    parts.append("\n---\nINSTRUCTIONS FOR THE RESPONSE:\n")
    parts.append("- Produce a complete, runnable SQL script that satisfies the user request.")
    parts.append("- Include all CREATE/ALTER/INSERT statements required to make the final SELECT(s) work.")
    parts.append("- If this is a follow-up that modifies schema or queries, include the original CREATE statements from editor_content (do not omit them).")
    parts.append("- By default return ONLY SQL (no markdown). If the user explicitly asked for an explanation, include a short explanation AFTER the SQL separated by a newline.")

    return "\n".join(parts)


# Error guidance mapping (kept concise)
ERROR_CORRECTION_PROMPTS = {
    "table_already_exists": "Table already exists. Use existing table or ALTER it. Do NOT recreate unless explicitly requested.",
    "table_not_found": "Table not found. Verify names in the provided editor content.",
    "column_not_found": "Column not found. Check column names and spellings against the editor content.",
    "syntax_error": "Syntax error. Check commas, parentheses, and SQL keywords.",
    "constraint_violation": "Constraint failed. Ensure your INSERT/UPDATE respects NOT NULL and UNIQUE constraints.",
    "foreign_key_constraint": "Foreign key failed. Create parent rows first or set proper FK values.",
    "general": "Review the query and the editor content for mismatches between expected schema and actual schema."
}

def get_error_guidance(error_message: str) -> str:
    """
    Minimal mapping from DB error message to actionable guidance.
    """
    e = (error_message or "").lower()
    if "not null" in e:
        return ERROR_CORRECTION_PROMPTS["constraint_violation"] + " Ensure required columns are present in INSERT."
    if "foreign key" in e:
        return ERROR_CORRECTION_PROMPTS["foreign_key_constraint"]
    if "no such table" in e or "not found" in e:
        return ERROR_CORRECTION_PROMPTS["table_not_found"]
    if "syntax" in e:
        return ERROR_CORRECTION_PROMPTS["syntax_error"]
    return ERROR_CORRECTION_PROMPTS["general"]
