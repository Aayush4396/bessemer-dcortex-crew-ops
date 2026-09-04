"""
src/tier1.py
============
Tier 1 Deterministic Query Handlers for dCortex Crew Ops Advisor.

All functions execute hand-written, parameterized SQLite queries with ZERO LLM
involvement. The LLM acts purely as a caller / router.

Canonical Operational Handlers:
-------------------------------
1. get_reserves_at_station(station=None, date=None, rank=None, conn=None)
   -> Active reserve standby crew with on-call windows, rank, and active status.

2. get_crew_duty_balance(crew_id, as_of_date=None, conn=None)
   -> Rolling 7d duty hours, 28d flight hours, headroom against 60h/100h caps, and rank.
   Accurately computes across historical duty_clock_history AND planned pairings.

3. get_departures(station, date, start_time=None, end_time=None, conn=None)
   -> Flights departing an airport on a given date within optional time window.

4. get_arrivals(station, date, start_time=None, end_time=None, conn=None)
   -> Inbound flights arriving at an airport on a given date within optional time window.

5. get_expiring_certifications(as_of_date="2026-09-15", days_ahead=30, cert_type=None, crew_id=None, conn=None)
   -> Certifications expiring within a sliding calendar window [as_of_date, as_of_date + days_ahead].

6. get_flights(date=None, origin=None, destination=None, flight_no=None, aircraft=None, aircraft_type=None, distinct_destinations=False, count_only=False, conn=None)
   -> Flexible flight search (leg lookup, city pairs, daily counts, nonstop destinations).

7. get_flight_schedule_stats(metric="longest_block", conn=None)
   -> Computes schedule statistics like longest/shortest block duration and matching flights.

8. get_crew_profile(crew_id=None, rank=None, base=None, rating=None, status=None, conn=None)
   -> Base, ratings, reachability, reserve standby window, crew by station.

9. get_pairing_roster(pairing_id=None, crew_id=None, aircraft=None, date=None, role=None, conn=None)
   -> Assigned crew complement and roles for a pairing or aircraft/date assignment,
   plus reverse lookup of a crew member's rostered pairings.

10. get_crew_risk_signal(crew_id=None, min_score=None, conn=None)
    -> Pre-computed disruption risk score and driver tags from risk_signals table.
"""

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.rules.config import DUTY_MAX_HOURS, DUTY_WINDOW_DAYS, FLT_MAX_HOURS, FLT_WINDOW_DAYS
from src.rules.models import SNAPSHOT_DATE
from src.rules.time_utils import calculate_rolling_sum

_DEFAULT_DB_PATH = Path(__file__).parent.parent / "crew_ops.db"


def _get_conn(conn: sqlite3.Connection | None = None) -> sqlite3.Connection:
    """Ensure an active SQLite connection with row factory configured."""
    if conn is not None:
        return conn
    c = sqlite3.connect(_DEFAULT_DB_PATH)
    c.row_factory = sqlite3.Row
    return c


# ---------------------------------------------------------------------------
# 1. get_reserves_at_station
# ---------------------------------------------------------------------------
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
    c = _get_conn(conn)
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


# ---------------------------------------------------------------------------
# 2. get_crew_duty_balance
# ---------------------------------------------------------------------------
def get_crew_duty_balance(
    crew_id: str,
    as_of_date: str = "2026-09-14",
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """
    Computes exact accrued rolling 7-day duty hours, 28-day flight hours,
    and remaining headroom against the 60h duty cap (RULE-DUTY-02) and 100h flight cap (RULE-FLT-03).
    Accurately combines historical records (<= 2026-09-14) AND planned roster pairings (> 2026-09-14).

    Parameters
    ----------
    crew_id : str
        e.g. "C-1042"
    as_of_date : str
        End of rolling window "YYYY-MM-DD", default "2026-09-14"

    Returns
    -------
    dict:
        "crew_id": str,
        "rank": str,
        "as_of_date": str,
        "duty_hours_7d": float,
        "headroom_hours": float,
        "flight_hours_28d": float,
        "flight_headroom_hours": float
    """
    c = _get_conn(conn)

    # Crew metadata
    crew_row = c.execute(
        "SELECT rank, base, ratings FROM crew WHERE crew_id = ?",
        (crew_id,),
    ).fetchone()
    rank = crew_row["rank"] if crew_row else None

    end_dt = date.fromisoformat(as_of_date)

    # Calculate 7-day rolling duty hours and headroom
    duty_7d = round(
        calculate_rolling_sum(c, crew_id, end_dt, DUTY_WINDOW_DAYS, "duty_hours"),
        2,
    )
    duty_headroom = round(max(0.0, DUTY_MAX_HOURS - duty_7d), 2)

    # Calculate 28-day rolling flight hours and headroom
    flight_28d = round(
        calculate_rolling_sum(c, crew_id, end_dt, FLT_WINDOW_DAYS, "flight_hours"),
        2,
    )
    flight_headroom = round(max(0.0, FLT_MAX_HOURS - flight_28d), 2)

    return {
        "crew_id": crew_id,
        "rank": rank,
        "as_of_date": as_of_date,
        "duty_hours_7d": duty_7d,
        "headroom_hours": duty_headroom,
        "flight_hours_28d": flight_28d,
        "flight_headroom_hours": flight_headroom,
    }


# ---------------------------------------------------------------------------
# 3. get_departures
# ---------------------------------------------------------------------------
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

    Parameters
    ----------
    station : str
        Departure station IATA code, e.g. "DEL"
    date : str
        "YYYY-MM-DD", e.g. "2026-09-15"
    start_time : str, optional
        UTC time "HH:MM" e.g. "06:00"
    end_time : str, optional
        UTC time "HH:MM" e.g. "18:00"

    Returns
    -------
    list of flight_no strings, e.g. ["DX402"]
    """
    c = _get_conn(conn)
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


# ---------------------------------------------------------------------------
# 4. get_arrivals
# ---------------------------------------------------------------------------
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
    c = _get_conn(conn)
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


# ---------------------------------------------------------------------------
# 5. get_expiring_certifications
# ---------------------------------------------------------------------------
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

    Returns
    -------
    list of {
        "crew_id": str,
        "cert_type": str,
        "valid_to": str
    }
    """
    c = _get_conn(conn)
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
        ORDER BY valid_to ASC, crew_id ASC
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


# ---------------------------------------------------------------------------
# 6. get_flights
# ---------------------------------------------------------------------------
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

    Examples
    --------
    - Leg lookup: get_flights(date="2026-09-15", flight_no="DX412")
    - City pair: get_flights(date="2026-09-17", origin="BLR", destination="BOM")
    - Fleet type: get_flights(date="2026-09-16", aircraft_type="ATR72")
    - Destinations: get_flights(origin="BLR", distinct_destinations=True)
    """
    c = _get_conn(conn)

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


# ---------------------------------------------------------------------------
# 7. get_flight_schedule_stats
# ---------------------------------------------------------------------------
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

    Returns
    -------
    dict:
        "block_hours": float,
        "flights": list of flight_no strings
    """
    c = _get_conn(conn)
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
    raise ValueError(f"Unknown metric {metric!r}")


# ---------------------------------------------------------------------------
# 8. get_crew_profile
# ---------------------------------------------------------------------------
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

    Examples
    --------
    - Single crew: get_crew_profile(crew_id="C-3310") -> reachability & reserve window
    - Base & ratings: get_crew_profile(crew_id="C-2210") -> base & ratings
    - Fleet & station filter: get_crew_profile(rank="Captain", base="DEL") -> crew list
    """
    c = _get_conn(conn)

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


# ---------------------------------------------------------------------------
# 9. get_pairing_roster
# ---------------------------------------------------------------------------
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

    Examples
    --------
    - Pairing roster: get_pairing_roster(pairing_id="P-2291")
    - Role lookup: get_pairing_roster(aircraft="VT-DXB", date="2026-09-16", role="Senior Cabin Crew")
    - Reverse crew lookup: get_pairing_roster(crew_id="C-1042", date="2026-09-15")
    """
    c = _get_conn(conn)

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


# ---------------------------------------------------------------------------
# 10. get_crew_risk_signal
# ---------------------------------------------------------------------------
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

    Returns
    -------
    dict (for single crew) or list of dicts (for multi-crew query)
    """
    c = _get_conn(conn)

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
