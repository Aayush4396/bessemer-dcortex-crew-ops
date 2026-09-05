"""
src/tier1/connection.py
=======================
Database connection resolver for Tier 1 deterministic queries.
"""

import sqlite3
from pathlib import Path

_DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "crew_ops.db"


def get_connection(conn: sqlite3.Connection | None = None) -> sqlite3.Connection:
    """
    Ensure an active SQLite connection with row factory configured to sqlite3.Row.

    Parameters
    ----------
    conn : sqlite3.Connection | None
        Existing connection if provided, else creates a connection to default DB file.

    Returns
    -------
    sqlite3.Connection
    """
    if conn is not None:
        return conn
    if not _DEFAULT_DB_PATH.exists():
        from src.db.loader import init_db

        return init_db(db_path=str(_DEFAULT_DB_PATH))
    c = sqlite3.connect(_DEFAULT_DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c
