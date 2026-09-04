"""
src/tier1/roster_queries.py
===========================
Deterministic queries for pairings, rosters, and crew assignment lookups.
"""

import json
import sqlite3
from typing import Any

from .connection import get_connection


def get_pairing_roster(
    pairing_id: str | None = None,
    crew_id: str | None = None,
    aircraft: str | None = None,
    date: str | None = None,
    role: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, Any]] | str | None:
    """
    Look up assigned crew members and roles for a pairing or aircraft assignment,
    or reverse look up which pairings/flights a specific crew member is rostered on.

    Parameters
    ----------
    pairing_id : str, optional
        Pairing code, e.g. "P-2291"
    crew_id : str, optional
        Crew ID for reverse assignment lookup, e.g. "C-1042"
    aircraft : str, optional
        Aircraft tail number, e.g. "VT-DXB"
    date : str, optional
        Date string "YYYY-MM-DD"
    role : str, optional
        Role filter, e.g. "Senior Cabin Crew", "Captain"
    conn : sqlite3.Connection, optional
    """
    c = get_connection(conn)

    # 1. Reverse lookup: pairings assigned to a crew member
    if crew_id:
        query = """
            SELECT p.pairing_id, p.aircraft, p.date, p.report_utc, p.release_utc,
                   p.flights_json, pc.role
            FROM pairings p
            JOIN pairing_crew pc ON p.pairing_id = pc.pairing_id
            WHERE pc.crew_id = ?
        """
        params: list[Any] = [crew_id]
        if date:
            query += " AND p.date = ?"
            params.append(date)
        query += " ORDER BY p.date ASC, p.report_utc ASC"
        rows = c.execute(query, tuple(params)).fetchall()
        return [
            {
                "pairing_id": r["pairing_id"],
                "aircraft": r["aircraft"],
                "date": r["date"],
                "report_utc": r["report_utc"],
                "release_utc": r["release_utc"],
                "flights": json.loads(r["flights_json"]),
                "role": r["role"],
            }
            for r in rows
        ]

    # 2. Roster for a specific pairing ID
    if pairing_id:
        rows = c.execute(
            """
            SELECT crew_id, role
            FROM pairing_crew
            WHERE pairing_id = ?
            ORDER BY rowid ASC
            """,
            (pairing_id,),
        ).fetchall()
        return [{"crew_id": r["crew_id"], "role": r["role"]} for r in rows]

    # 3. Roster by aircraft and date
    if aircraft and date:
        query = """
            SELECT pc.crew_id, pc.role
            FROM pairings p
            JOIN pairing_crew pc ON p.pairing_id = pc.pairing_id
            WHERE p.aircraft = ?
              AND p.date = ?
        """
        params = [aircraft, date]
        if role:
            query += " AND pc.role = ?"
            params.append(role)
        query += " ORDER BY pc.rowid ASC"

        rows = c.execute(query, tuple(params)).fetchall()
        if role and rows:
            return rows[0]["crew_id"]
        return [{"crew_id": r["crew_id"], "role": r["role"]} for r in rows]

    return []
