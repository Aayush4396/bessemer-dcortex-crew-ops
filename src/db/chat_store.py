"""
src/db/chat_store.py
====================
Thread-safe persistence layer for multi-turn operational chat sessions
and uncompacted message audit history stored in SQLite (crew_ops.db).
"""

import datetime
import json
import sqlite3
import uuid
from typing import Any

from src.tier1.connection import get_connection


def _now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def ensure_chat_tables(conn: sqlite3.Connection | None = None) -> None:
    """
    Ensure chat_sessions and chat_messages tables and indices exist in SQLite.
    Idempotent and safe to call on startup.
    """
    c = get_connection(conn)
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                session_id  TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                tier        INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_cs_updated_at ON chat_sessions(updated_at DESC);")
        c.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                message_id      TEXT PRIMARY KEY,
                session_id      TEXT NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
                sender          TEXT NOT NULL,
                content         TEXT NOT NULL,
                tier_used       INTEGER NOT NULL DEFAULT 1,
                tool_calls      TEXT,
                tool_results    TEXT,
                reasoning_trace TEXT,
                created_at      TEXT NOT NULL
            );
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_cm_session_created ON chat_messages(session_id, created_at ASC);")
        c.commit()
    finally:
        if conn is None:
            c.close()


def create_session(
    session_id: str | None = None,
    title: str = "New Operational Inquiry",
    tier: int = 1,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """
    Create a new chat session.
    """
    sid = session_id or f"sess_{uuid.uuid4().hex[:12]}"
    now = _now_iso()
    c = get_connection(conn)
    try:
        c.execute(
            """
            INSERT OR REPLACE INTO chat_sessions (session_id, title, tier, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (sid, title, tier, now, now),
        )
        c.commit()
        return {
            "session_id": sid,
            "title": title,
            "tier": tier,
            "created_at": now,
            "updated_at": now,
            "message_count": 0,
        }
    finally:
        if conn is None:
            c.close()


def get_or_create_session(
    session_id: str,
    title: str = "New Operational Inquiry",
    tier: int = 1,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """
    Retrieve existing session by ID or create one if it does not exist.
    """
    sess = get_session(session_id, conn=conn)
    if sess is not None:
        return sess
    return create_session(session_id=session_id, title=title, tier=tier, conn=conn)


def get_session(session_id: str, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
    """
    Retrieve a single session by session_id, including its message count.
    """
    c = get_connection(conn)
    try:
        ensure_chat_tables(c)
        row = c.execute(
            """
            SELECT s.session_id, s.title, s.tier, s.created_at, s.updated_at,
                   COUNT(m.message_id) AS message_count
            FROM chat_sessions s
            LEFT JOIN chat_messages m ON s.session_id = m.session_id
            WHERE s.session_id = ?
            GROUP BY s.session_id
            """,
            (session_id,),
        ).fetchone()

        if not row:
            return None

        return {
            "session_id": row["session_id"],
            "title": row["title"],
            "tier": row["tier"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "message_count": row["message_count"],
        }
    finally:
        if conn is None:
            c.close()


def list_sessions(conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    """
    List all saved sessions sorted by most recently updated first.
    """
    c = get_connection(conn)
    try:
        ensure_chat_tables(c)
        rows = c.execute(
            """
            SELECT s.session_id, s.title, s.tier, s.created_at, s.updated_at,
                   COUNT(m.message_id) AS message_count
            FROM chat_sessions s
            LEFT JOIN chat_messages m ON s.session_id = m.session_id
            GROUP BY s.session_id
            ORDER BY s.updated_at DESC
            """
        ).fetchall()

        return [
            {
                "session_id": r["session_id"],
                "title": r["title"],
                "tier": r["tier"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "message_count": r["message_count"],
            }
            for r in rows
        ]
    finally:
        if conn is None:
            c.close()


def update_session_title(
    session_id: str,
    title: str,
    conn: sqlite3.Connection | None = None,
) -> bool:
    """
    Update a session's title and touch updated_at.
    """
    c = get_connection(conn)
    now = _now_iso()
    try:
        cur = c.execute(
            "UPDATE chat_sessions SET title = ?, updated_at = ? WHERE session_id = ?",
            (title, now, session_id),
        )
        c.commit()
        return cur.rowcount > 0
    finally:
        if conn is None:
            c.close()


def delete_session(session_id: str, conn: sqlite3.Connection | None = None) -> bool:
    """
    Delete a session and all its cascading messages.
    """
    c = get_connection(conn)
    try:
        c.execute("PRAGMA foreign_keys = ON")
        cur = c.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
        c.commit()
        return cur.rowcount > 0
    finally:
        if conn is None:
            c.close()


def save_message(
    session_id: str,
    sender: str,
    content: str,
    tool_calls: list[dict[str, Any]] | None = None,
    tool_results: list[dict[str, Any]] | None = None,
    reasoning_trace: list[str] | None = None,
    tier_used: int = 1,
    message_id: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """
    Append an uncompacted message to the session audit history and touch session updated_at.
    """
    mid = message_id or f"msg_{uuid.uuid4().hex[:12]}"
    now = _now_iso()
    tc_json = json.dumps(tool_calls, default=str) if tool_calls else None
    tr_json = json.dumps(tool_results, default=str) if tool_results else None
    trace_json = json.dumps(reasoning_trace, default=str) if reasoning_trace else None

    c = get_connection(conn)
    try:
        ensure_chat_tables(c)
        # Auto-create session if not present
        c.execute(
            """
            INSERT OR IGNORE INTO chat_sessions (session_id, title, tier, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, content[:40] + ("..." if len(content) > 40 else ""), tier_used, now, now),
        )

        c.execute(
            """
            INSERT INTO chat_messages (
                message_id, session_id, sender, content, tier_used,
                tool_calls, tool_results, reasoning_trace, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (mid, session_id, sender, content, tier_used, tc_json, tr_json, trace_json, now),
        )

        # Update session touch timestamp
        c.execute("UPDATE chat_sessions SET updated_at = ? WHERE session_id = ?", (now, session_id))
        c.commit()

        return {
            "message_id": mid,
            "session_id": session_id,
            "sender": sender,
            "content": content,
            "tier_used": tier_used,
            "tool_calls": tool_calls or [],
            "tool_results": tool_results or [],
            "reasoning_trace": reasoning_trace or [],
            "created_at": now,
        }
    finally:
        if conn is None:
            c.close()


def get_session_messages(
    session_id: str,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch all messages for a session in chronological order with parsed JSON payloads.
    """
    c = get_connection(conn)
    try:
        ensure_chat_tables(c)
        rows = c.execute(
            """
            SELECT message_id, session_id, sender, content, tier_used,
                   tool_calls, tool_results, reasoning_trace, created_at
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY created_at ASC
            """,
            (session_id,),
        ).fetchall()

        messages = []
        for r in rows:
            tc = json.loads(r["tool_calls"]) if r["tool_calls"] else []
            tr = json.loads(r["tool_results"]) if r["tool_results"] else []
            trace = json.loads(r["reasoning_trace"]) if r["reasoning_trace"] else []
            messages.append({
                "message_id": r["message_id"],
                "session_id": r["session_id"],
                "sender": r["sender"],
                "content": r["content"],
                "tier_used": r["tier_used"],
                "tool_calls": tc,
                "tool_results": tr,
                "reasoning_trace": trace,
                "created_at": r["created_at"],
            })
        return messages
    finally:
        if conn is None:
            c.close()
