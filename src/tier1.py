"""
src/tier1.py
============
Tier 1 Deterministic Query Handlers for dCortex Crew Ops Advisor.

All functions execute hand-written, parameterized SQLite queries with ZERO LLM
involvement. The LLM acts purely as a caller / router.

The 9 Canonical Handlers covering 100% of tables & benchmark lookups (Q01-Q16):
-------------------------------------------------------------------------------
1. get_reserves_at_station(station, date, conn=None)
   -> Q01: Active reserve standby crew with on-call windows and rank.

2. get_crew_duty_balance(crew_id, as_of_date="2026-09-14", conn=None)
   -> Q02, Q13: Rolling 7d duty, 28d flight hours, headroom against 60h cap, rank.

3. get_departures(station, date, start_time=None, end_time=None, conn=None)
   -> Q03: Flights departing a station on a given date within optional time window.

4. get_expiring_certifications(as_of_date="2026-09-15", days_ahead=30, conn=None)
   -> Q04: Certifications expiring within [as_of_date, as_of_date + days_ahead].

5. get_flights(date=None, origin=None, destination=None, flight_no=None, aircraft=None, distinct_destinations=False, conn=None)
   -> Q05, Q09, Q10, Q14: Flexible flight search (leg lookup, city pairs, daily counts, nonstop destinations).

6. get_flight_schedule_stats(metric="longest_block", conn=None)
   -> Q12: Computes schedule statistics like longest block duration and matching flights.

7. get_crew_profile(crew_id=None, rank=None, base=None, conn=None)
   -> Q06, Q07, Q11: Base, ratings, reachability, reserve standby window, crew by station.

8. get_pairing_roster(pairing_id=None, aircraft=None, date=None, role=None, conn=None)
   -> Q08, Q15: Assigned crew complement and roles for a pairing or aircraft/date assignment.

9. get_crew_risk_signal(crew_id, conn=None)
   -> Q16: Pre-computed disruption risk score and driver tags from risk_signals table.
"""

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

_DEFAULT_DB_PATH = Path(__file__).parent.parent / "crew_ops.db"


def _get_conn(conn: sqlite3.Connection | None = None) -> sqlite3.Connection:
    """Ensure an active SQLite connection with row factory configured."""
    if conn is not None:
        return conn
    c = sqlite3.connect(_DEFAULT_DB_PATH)
    c.row_factory = sqlite3.Row
    return c


# ---------------------------------------------------------------------------
# 1. get_reserves_at_station (Q01)
# ---------------------------------------------------------------------------
def get_reserves_at_station(
    station: str,
    date: str,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    """
    List crew members on reserve standby at a given station on a date,
    including their on-call standby window and rank.
    Filters exclusively for status='active'.

    Parameters
    ----------
    station : str
        IATA code, e.g. "BLR"
    date : str
        ISO date "YYYY-MM-DD", e.g. "2026-09-15"

    Returns
    -------
    list of {
        "crew_id": str,
        "rank": str,
        "window": {"start": "HH:MM", "end": "HH:MM"}
    }
    """
    c = _get_conn(conn)
    query = """
        SELECT rp.crew_id, c.rank, rp.on_call_start, rp.on_call_end
        FROM reserve_pool rp
        JOIN crew c ON c.crew_id = rp.crew_id
        WHERE rp.base = ?
          AND rp.date = ?
          AND c.status = 'active'
        ORDER BY rp.id ASC
    """
    rows = c.execute(query, (station, date)).fetchall()
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
# 2. get_crew_duty_balance (Q02, Q13)
# ---------------------------------------------------------------------------
def get_crew_duty_balance(
    crew_id: str,
    as_of_date: str = "2026-09-14",
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """
    Computes exact accrued rolling 7-day duty hours, 28-day flight hours,
    and remaining headroom against the 60h cap under RULE-DUTY-02.
    Also returns crew rank and ratings.

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

    # Calculate 7-day window [end - 6 days, end]
    end_dt = date.fromisoformat(as_of_date)
    start_7d = end_dt - timedelta(days=6)
    r7 = c.execute(
        """
        SELECT COALESCE(SUM(duty_hours), 0.0)
        FROM duty_clock_history
        WHERE crew_id = ?
          AND date >= ?
          AND date <= ?
        """,
        (crew_id, start_7d.isoformat(), end_dt.isoformat()),
    ).fetchone()
    duty_7d = round(float(r7[0]), 2)
    duty_headroom = round(max(0.0, 60.0 - duty_7d), 2)

    # Calculate 28-day window [end - 27 days, end]
    start_28d = end_dt - timedelta(days=27)
    r28 = c.execute(
        """
        SELECT COALESCE(SUM(flight_hours), 0.0)
        FROM duty_clock_history
        WHERE crew_id = ?
          AND date >= ?
          AND date <= ?
        """,
        (crew_id, start_28d.isoformat(), end_dt.isoformat()),
    ).fetchone()
    flight_28d = round(float(r28[0]), 2)
    flight_headroom = round(max(0.0, 100.0 - flight_28d), 2)

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
# 3. get_departures (Q03)
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
# 4. get_expiring_certifications (Q04)
# ---------------------------------------------------------------------------
def get_expiring_certifications(
    as_of_date: str = "2026-09-15",
    days_ahead: int = 30,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, str]]:
    """
    List all certifications expiring within [as_of_date, as_of_date + days_ahead].

    Parameters
    ----------
    as_of_date : str
        Starting date "YYYY-MM-DD", default "2026-09-15"
    days_ahead : int
        Window duration in calendar days, default 30

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

    query = """
        SELECT crew_id, cert_type, valid_to
        FROM certifications
        WHERE valid_to >= ?
          AND valid_to <= ?
        ORDER BY id ASC
    """
    rows = c.execute(query, (start_dt.isoformat(), end_dt.isoformat())).fetchall()
    return [
        {
            "crew_id": r["crew_id"],
            "cert_type": r["cert_type"],
            "valid_to": r["valid_to"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# 5. get_flights (Q05, Q09, Q10, Q14)
# ---------------------------------------------------------------------------
def get_flights(
    date: str | None = None,
    origin: str | None = None,
    destination: str | None = None,
    flight_no: str | None = None,
    aircraft: str | None = None,
    distinct_destinations: bool = False,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, Any]] | list[str] | int:
    """
    Flexible schedule lookup covering flight details, route queries,
    daily flight counts, and nonstop destination listings.

    Examples
    --------
    - Q05: get_flights(date="2026-09-15", flight_no="DX412")
    - Q09: get_flights(date="2026-09-17", origin="BLR", destination="BOM")
    - Q10: get_flights(date="2026-09-16") -> can count results or filter
    - Q14: get_flights(origin="BLR", distinct_destinations=True)
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

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
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
# 6. get_flight_schedule_stats (Q12)
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
        Currently supports "longest_block"

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
    raise ValueError(f"Unknown metric {metric!r}")


# ---------------------------------------------------------------------------
# 7. get_crew_profile (Q06, Q07, Q11)
# ---------------------------------------------------------------------------
def get_crew_profile(
    crew_id: str | None = None,
    rank: str | None = None,
    base: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, Any]] | dict[str, Any] | None:
    """
    Fetch crew member details including base, ratings, reachability minutes,
    reserve on-call standby window (if on reserve), or list crew IDs by rank/base.

    Examples
    --------
    - Q06: get_crew_profile(crew_id="C-3310") -> reachability & reserve window
    - Q07: get_crew_profile(crew_id="C-2210") -> base & ratings
    - Q11: get_crew_profile(rank="Captain", base="DEL") -> crew list
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

    # Filter by rank and/or base
    conditions = []
    params: list[Any] = []
    if rank:
        conditions.append("rank = ?")
        params.append(rank)
    if base:
        conditions.append("base = ?")
        params.append(base)

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
# 8. get_pairing_roster (Q08, Q15)
# ---------------------------------------------------------------------------
def get_pairing_roster(
    pairing_id: str | None = None,
    aircraft: str | None = None,
    date: str | None = None,
    role: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, str]] | str | None:
    """
    Look up assigned crew members and roles for a pairing or aircraft assignment.

    Examples
    --------
    - Q08: get_pairing_roster(pairing_id="P-2291")
    - Q15: get_pairing_roster(aircraft="VT-DXB", date="2026-09-16", role="Senior Cabin Crew")
    """
    c = _get_conn(conn)

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

    if aircraft and date:
        query = """
            SELECT pc.crew_id, pc.role
            FROM pairings p
            JOIN pairing_crew pc ON p.pairing_id = pc.pairing_id
            WHERE p.aircraft = ?
              AND p.date = ?
        """
        params: list[Any] = [aircraft, date]
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
# 9. get_crew_risk_signal (Q16)
# ---------------------------------------------------------------------------
def get_crew_risk_signal(
    crew_id: str,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    """
    Retrieve the pre-computed disruption risk score and driver tags for a crew member.

    Parameters
    ----------
    crew_id : str
        e.g. "C-1042"

    Returns
    -------
    dict:
        "crew_id": str,
        "score": float,
        "drivers": list of str
    """
    c = _get_conn(conn)
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
