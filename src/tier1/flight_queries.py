"""
src/tier1/flight_queries.py
===========================
Deterministic queries for flight schedules, legs, city pairs, and movements.
"""

import sqlite3
from typing import Any

from .connection import get_connection


def get_flights(
    date: str | None = None,
    origin: str | None = None,
    destination: str | None = None,
    flight_no: str | None = None,
    aircraft: str | None = None,
    aircraft_type: str | None = None,
    distinct_destinations: bool = False,
    count_only: bool = False,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, Any]] | list[str] | int:
    """
    Flexible schedule lookup covering flight details, route queries,
    daily flight counts, and nonstop destination listings.

    Parameters
    ----------
    date : str, optional
        ISO date "YYYY-MM-DD", e.g. "2026-09-15"
    origin : str, optional
        Departure airport IATA code, e.g. "BLR"
    destination : str, optional
        Arrival airport IATA code, e.g. "BOM"
    flight_no : str, optional
        Flight number, e.g. "DX412"
    aircraft : str, optional
        Tail number, e.g. "VT-DXA"
    aircraft_type : str, optional
        Fleet type, e.g. "A320" or "ATR72"
    distinct_destinations : bool, optional
        If True with origin, returns list of unique arrival stations
    count_only : bool, optional
        If True, returns total matching flight count as int
    conn : sqlite3.Connection, optional
    """
    c = get_connection(conn)

    if distinct_destinations and origin:
        query = """
            SELECT DISTINCT arr_station
            FROM flights
            WHERE dep_station = ?
            ORDER BY arr_station ASC
        """
        rows = c.execute(query, (origin,)).fetchall()
        return [r[0] for r in rows]

    conditions = []
    params: list[Any] = []

    if date:
        conditions.append("date = ?")
        params.append(date)
    if origin:
        conditions.append("dep_station = ?")
        params.append(origin)
    if destination:
        conditions.append("arr_station = ?")
        params.append(destination)
    if flight_no:
        conditions.append("flight_no = ?")
        params.append(flight_no)
    if aircraft:
        conditions.append("aircraft = ?")
        params.append(aircraft)
    if aircraft_type:
        conditions.append("aircraft_type = ?")
        params.append(aircraft_type)

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    if count_only:
        query = f"SELECT COUNT(*) FROM flights {where_clause}"
        return int(c.execute(query, tuple(params)).fetchone()[0])

    query = f"""
        SELECT flight_id, flight_no, date, dep_station, arr_station,
               dep_utc, arr_utc, block_hours, aircraft, aircraft_type, seats
        FROM flights
        {where_clause}
        ORDER BY dep_utc ASC
    """
    rows = c.execute(query, tuple(params)).fetchall()
    return [
        {
            "flight_id": r["flight_id"],
            "flight_no": r["flight_no"],
            "date": r["date"],
            "origin": r["dep_station"],
            "destination": r["arr_station"],
            "dep_utc": r["dep_utc"],
            "arr_utc": r["arr_utc"],
            "block_hours": float(r["block_hours"]),
            "aircraft": r["aircraft"],
            "aircraft_type": r["aircraft_type"],
            "seats": int(r["seats"]),
        }
        for r in rows
    ]


def get_departures(
    station: str,
    date: str,
    start_time: str | None = None,
    end_time: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[str]:
    """
    List flight numbers departing a station on a given date, optionally
    within a specific departure time window.
    """
    c = get_connection(conn)
    query = """
        SELECT flight_no, dep_utc
        FROM flights
        WHERE dep_station = ?
          AND date = ?
        ORDER BY dep_utc ASC
    """
    rows = c.execute(query, (station, date)).fetchall()

    result = []
    for r in rows:
        dep_time = r["dep_utc"][11:16]
        if start_time and dep_time < start_time:
            continue
        if end_time and dep_time > end_time:
            continue
        result.append(r["flight_no"])
    return result


def get_arrivals(
    station: str,
    date: str,
    start_time: str | None = None,
    end_time: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[str]:
    """
    List flight numbers arriving at a station on a given date, optionally
    within a specific arrival time window.
    """
    c = get_connection(conn)
    query = """
        SELECT flight_no, arr_utc
        FROM flights
        WHERE arr_station = ?
          AND date = ?
        ORDER BY arr_utc ASC
    """
    rows = c.execute(query, (station, date)).fetchall()

    result = []
    for r in rows:
        arr_time = r["arr_utc"][11:16]
        if start_time and arr_time < start_time:
            continue
        if end_time and arr_time > end_time:
            continue
        result.append(r["flight_no"])
    return result


def get_flight_schedule_stats(
    metric: str = "longest_block",
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """
    Computes schedule statistics across all flights.

    Parameters
    ----------
    metric : str
        Supports "longest_block", "shortest_block"
    """
    c = get_connection(conn)
    if metric == "longest_block":
        max_b = c.execute("SELECT MAX(block_hours) FROM flights").fetchone()[0]
        rows = c.execute(
            """
            SELECT DISTINCT flight_no
            FROM flights
            WHERE block_hours = ?
            ORDER BY flight_no ASC
            """,
            (max_b,),
        ).fetchall()
        return {
            "block_hours": float(max_b),
            "flights": [r["flight_no"] for r in rows],
        }
    elif metric == "shortest_block":
        min_b = c.execute("SELECT MIN(block_hours) FROM flights").fetchone()[0]
        rows = c.execute(
            """
            SELECT DISTINCT flight_no
            FROM flights
            WHERE block_hours = ?
            ORDER BY flight_no ASC
            """,
            (min_b,),
        ).fetchall()
        return {
            "block_hours": float(min_b),
            "flights": [r["flight_no"] for r in rows],
        }
    elif metric == "max_seats":
        rows = c.execute(
            """
            SELECT aircraft_type, MAX(seats) AS max_seats
            FROM flights
            GROUP BY aircraft_type
            ORDER BY max_seats DESC, aircraft_type ASC
            """
        ).fetchall()
        return {
            "by_type": [
                {
                    "aircraft_type": r["aircraft_type"],
                    "max_seats": int(r["max_seats"]),
                }
                for r in rows
            ]
        }
    raise ValueError(f"Unknown metric {metric!r}")
