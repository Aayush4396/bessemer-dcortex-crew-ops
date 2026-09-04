"""
src/tier1/crew_queries.py
=========================
Deterministic queries for crew profiles, type ratings, domiciles, and reserve pool.
"""

import json
import sqlite3
from typing import Any

from .connection import get_connection


def get_reserves_at_station(
    station: str | None = None,
    date: str | None = None,
    rank: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    """
    List crew members on reserve standby at a given station on a date,
    including their on-call standby window and rank.
    Filters exclusively for status='active'.

    Parameters
    ----------
    station : str, optional
        IATA code, e.g. "BLR". If None, returns reserves across all stations.
    date : str, optional
        ISO date "YYYY-MM-DD", e.g. "2026-09-15".
    rank : str, optional
        Filter by crew rank, e.g. "Captain" or "First Officer".
    conn : sqlite3.Connection, optional

    Returns
    -------
    list of {
        "crew_id": str,
        "rank": str,
        "window": {"start": "HH:MM", "end": "HH:MM"}
    }
    """
    c = get_connection(conn)
    conditions = ["c.status = 'active'"]
    params: list[Any] = []

    if station:
        conditions.append("rp.base = ?")
        params.append(station)
    if date:
        conditions.append("rp.date = ?")
        params.append(date)
    if rank:
        conditions.append("c.rank = ?")
        params.append(rank)

    where_clause = " WHERE " + " AND ".join(conditions)
    query = f"""
        SELECT rp.crew_id, c.rank, rp.on_call_start, rp.on_call_end
        FROM reserve_pool rp
        JOIN crew c ON c.crew_id = rp.crew_id
        {where_clause}
        ORDER BY rp.id ASC
    """
    rows = c.execute(query, tuple(params)).fetchall()
    return [
        {
            "crew_id": r["crew_id"],
            "rank": r["rank"],
            "window": {
                "start": r["on_call_start"],
                "end": r["on_call_end"],
            },
        }
        for r in rows
    ]


def get_crew_profile(
    crew_id: str | None = None,
    rank: str | None = None,
    base: str | None = None,
    rating: str | None = None,
    status: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, Any]] | dict[str, Any] | None:
    """
    Fetch crew member details including base, ratings, reachability minutes,
    reserve on-call standby window (if on reserve), or list crew IDs by rank/base/rating.

    Parameters
    ----------
    crew_id : str, optional
        Specific crew ID, e.g. "C-1042"
    rank : str, optional
        e.g. "Captain", "First Officer"
    base : str, optional
        e.g. "BLR", "DEL"
    rating : str, optional
        e.g. "A320", "ATR72"
    status : str, optional
        e.g. "active", "leave"
    conn : sqlite3.Connection, optional
    """
    c = get_connection(conn)

    if crew_id:
        crew_row = c.execute(
            """
            SELECT crew_id, name, rank, base, ratings, seniority, reachability_minutes, status
            FROM crew
            WHERE crew_id = ?
            """,
            (crew_id,),
        ).fetchone()
        if not crew_row:
            return None

        # Check reserve pool for on-call window
        rp_row = c.execute(
            """
            SELECT on_call_start, on_call_end
            FROM reserve_pool
            WHERE crew_id = ?
            ORDER BY date ASC
            LIMIT 1
            """,
            (crew_id,),
        ).fetchone()

        window = None
        if rp_row:
            window = {
                "start": rp_row["on_call_start"],
                "end": rp_row["on_call_end"],
            }

        return {
            "crew_id": crew_row["crew_id"],
            "name": crew_row["name"],
            "rank": crew_row["rank"],
            "base": crew_row["base"],
            "ratings": json.loads(crew_row["ratings"]),
            "reachability_minutes": crew_row["reachability_minutes"],
            "status": crew_row["status"],
            "window": window,
        }

    # Filter by rank, base, rating, status
    conditions = []
    params: list[Any] = []
    if rank:
        conditions.append("rank = ?")
        params.append(rank)
    if base:
        conditions.append("base = ?")
        params.append(base)
    if rating:
        conditions.append("ratings LIKE ?")
        params.append(f'%"{rating}"%')
    if status:
        conditions.append("status = ?")
        params.append(status)

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    query = f"""
        SELECT crew_id, name, rank, base, ratings, reachability_minutes, status
        FROM crew
        {where_clause}
        ORDER BY crew_id ASC
    """
    rows = c.execute(query, tuple(params)).fetchall()
    return [
        {
            "crew_id": r["crew_id"],
            "name": r["name"],
            "rank": r["rank"],
            "base": r["base"],
            "ratings": json.loads(r["ratings"]),
            "reachability_minutes": r["reachability_minutes"],
            "status": r["status"],
        }
        for r in rows
    ]
