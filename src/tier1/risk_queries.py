"""
src/tier1/risk_queries.py
=========================
Deterministic queries for pre-computed crew fatigue and disruption risk signals.
"""

import json
import sqlite3
from typing import Any

from .connection import get_connection


def get_crew_risk_signal(
    crew_id: str | None = None,
    min_score: float | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any] | list[dict[str, Any]] | None:
    """
    Retrieve pre-computed disruption risk score and driver tags for a crew member,
    or list all crew members with risk score >= min_score.

    Parameters
    ----------
    crew_id : str, optional
        e.g. "C-1042"
    min_score : float, optional
        Threshold to filter high-risk crew members (e.g. 0.70)
    conn : sqlite3.Connection, optional

    Returns
    -------
    dict (for single crew) or list of dicts (for multi-crew query)
    """
    c = get_connection(conn)

    if crew_id:
        row = c.execute(
            """
            SELECT disruption_risk_score, drivers_json
            FROM risk_signals
            WHERE crew_id = ?
            """,
            (crew_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "crew_id": crew_id,
            "score": round(float(row["disruption_risk_score"]), 2),
            "drivers": json.loads(row["drivers_json"]),
        }

    # Query all crew matching min_score
    query = "SELECT crew_id, disruption_risk_score, drivers_json FROM risk_signals"
    params = []
    if min_score is not None:
        query += " WHERE disruption_risk_score >= ?"
        params.append(min_score)
    query += " ORDER BY disruption_risk_score DESC, crew_id ASC"

    rows = c.execute(query, tuple(params)).fetchall()
    return [
        {
            "crew_id": r["crew_id"],
            "score": round(float(r["disruption_risk_score"]), 2),
            "drivers": json.loads(r["drivers_json"]),
        }
        for r in rows
    ]
