"""
src/tier1/cert_queries.py
=========================
Deterministic queries for crew qualifications, licences, medicals, and training expiry.
"""

import sqlite3
from datetime import date, timedelta
from typing import Any

from .connection import get_connection


def get_expiring_certifications(
    as_of_date: str = "2026-09-15",
    days_ahead: int = 30,
    cert_type: str | None = None,
    crew_id: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, str]]:
    """
    List all certifications expiring within [as_of_date, as_of_date + days_ahead].
    Optionally filter by certification type or crew member.

    Parameters
    ----------
    as_of_date : str
        Starting date "YYYY-MM-DD", default "2026-09-15"
    days_ahead : int
        Window duration in calendar days, default 30
    cert_type : str, optional
        Filter by cert type: "licence", "medical_class1", "recurrent_training", "dangerous_goods"
    crew_id : str, optional
        Filter by crew ID, e.g. "C-2087"
    conn : sqlite3.Connection, optional

    Returns
    -------
    list of {
        "crew_id": str,
        "cert_type": str,
        "valid_to": str
    }
    """
    c = get_connection(conn)
    start_dt = date.fromisoformat(as_of_date)
    end_dt = start_dt + timedelta(days=days_ahead)

    conditions = ["valid_to >= ?", "valid_to <= ?"]
    params: list[Any] = [start_dt.isoformat(), end_dt.isoformat()]

    if cert_type:
        conditions.append("cert_type = ?")
        params.append(cert_type)
    if crew_id:
        conditions.append("crew_id = ?")
        params.append(crew_id)

    where_clause = " WHERE " + " AND ".join(conditions)
    query = f"""
        SELECT crew_id, cert_type, valid_to
        FROM certifications
        {where_clause}
        ORDER BY id ASC
    """
    rows = c.execute(query, tuple(params)).fetchall()
    return [
        {
            "crew_id": r["crew_id"],
            "cert_type": r["cert_type"],
            "valid_to": r["valid_to"],
        }
        for r in rows
    ]
