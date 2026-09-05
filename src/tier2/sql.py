"""
src/tier2/sql.py
================
Read-only SQLite runner for ad-hoc crew/flight/roster questions.
The model writes SELECT SQL; this module executes it with guards.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from src.tier1.connection import get_connection

_MAX_ROWS = 300
_BLOCKED_TABLES = {"chat_sessions", "chat_messages"}
_WRITE_OR_ADMIN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|"
    r"PRAGMA|VACUUM|REINDEX|GRANT|REVOKE|TRUNCATE)\b",
    re.IGNORECASE,
)
_NON_SQLITE = re.compile(
    r"\bANY\s*\(|\bSOME\s*\(|\bILIKE\b|\bUNNEST\b|\bGENERATE_SERIES\b|"
    r"\bDATE_TRUNC\b|\bINTERVAL\b|\bSTRING_AGG\b|\bJSONB?\b|@>|<@|ARRAY\s*\[",
    re.IGNORECASE,
)


def _normalize_sql(sql: str) -> str:
    return sql.strip().rstrip(";").strip()


def validate_select(sql: str) -> str | None:
    """Return an error string if the statement is not a safe single SELECT."""
    if not sql:
        return "SQL is empty"
    if ";" in sql:
        return "Only one SQL statement is allowed"
    first = sql.split(None, 1)[0].upper()
    if first not in {"SELECT", "WITH"}:
        return "Only SELECT / WITH queries are allowed"
    if _WRITE_OR_ADMIN.search(sql):
        return "Write or admin SQL is not allowed"
    if _NON_SQLITE.search(sql):
        return (
            "This is SQLite. Rewrite without ANY/ILIKE/UNNEST/DATE_TRUNC/INTERVAL/"
            "STRING_AGG/ARRAY/jsonb. For ratings use json_each(ratings) or LIKE."
        )
    lowered = sql.lower()
    for table in _BLOCKED_TABLES:
        if re.search(rf"\b{table}\b", lowered):
            return f"Table {table} is not queryable"
    return None


def execute_readonly_sql(
    sql: str,
    conn: sqlite3.Connection | None = None,
    max_rows: int = _MAX_ROWS,
) -> dict[str, Any]:
    """
    Run a single read-only SELECT against crew_ops.db.
    Returns {columns, rows, row_count} or {error}.
    """
    owns = conn is None
    normalized = _normalize_sql(sql)
    err = validate_select(normalized)
    if err:
        return {"error": err, "sql": sql}

    c = get_connection(conn)
    try:
        c.execute("PRAGMA query_only = ON")
        cursor = c.execute(normalized)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        fetched = cursor.fetchmany(max_rows + 1)
        truncated = len(fetched) > max_rows
        rows = fetched[:max_rows]
        return {
            "sql": normalized,
            "columns": columns,
            "rows": [dict(zip(columns, row)) for row in rows],
            "row_count": len(rows),
            "truncated": truncated,
        }
    except sqlite3.Error as exc:
        return {"error": str(exc), "sql": normalized}
    finally:
        try:
            c.execute("PRAGMA query_only = OFF")
        except sqlite3.Error:
            pass
        if owns:
            c.close()
