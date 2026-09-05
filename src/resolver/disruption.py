"""
src/resolver/disruption.py
==========================
Disruption expansion functions for Tier 2/3 scenarios.
"""

import json
import sqlite3
from datetime import date, datetime, timedelta

from src.tier1.connection import get_connection
from src.resolver.data import (
    load_all,
    FBY,
    flights_list,
    pairings,
    costs,
)


def _hrs(td: timedelta) -> float:
    return round(td.total_seconds() / 3600.0, 2)


def _parse_dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


def _fdp_limit(n_sectors: int) -> float:
    return 13.0 - 0.5 * max(0, n_sectors - 2)


def _duty_len(day: dict) -> tuple[float, datetime, datetime]:
    rep = _parse_dt(day["report_utc"])
    rel = _parse_dt(day["release_utc"])
    return _hrs(rel - rep), rep, rel


def expand_sick_call(
    sick_cid: str,
    pairing_id: str | None = None,
    event_date: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict:
    """Expand a sick-call event from the SQLite roster and flight snapshot."""
    connection = get_connection(conn)
    try:
        if pairing_id is None:
            if event_date is None:
                raise ValueError("A pairing_id or event_date is required for a sick-call analysis")
            matching_pairings = connection.execute(
                """
                SELECT DISTINCT pc.pairing_id
                FROM pairing_crew pc
                JOIN pairings p ON p.pairing_id = pc.pairing_id
                WHERE pc.crew_id = ? AND p.date = ?
                ORDER BY pc.pairing_id
                """,
                (sick_cid, event_date),
            ).fetchall()
            if not matching_pairings:
                raise ValueError(f"Crew {sick_cid} has no pairing on {event_date}")
            if len(matching_pairings) > 1:
                pairing_ids = [row["pairing_id"] for row in matching_pairings]
                raise ValueError(f"Crew {sick_cid} has multiple pairings on {event_date}: {pairing_ids}")
            pairing_id = matching_pairings[0]["pairing_id"]

        assignment = connection.execute(
            """
            SELECT pc.role
            FROM pairing_crew pc
            WHERE pc.pairing_id = ? AND pc.crew_id = ?
            """,
            (pairing_id, sick_cid),
        ).fetchone()
        if assignment is None:
            raise ValueError(f"Crew {sick_cid} is not assigned to pairing {pairing_id}")

        pairing_days = connection.execute(
            """
            SELECT date, flights_json
            FROM pairings
            WHERE pairing_id = ?
            ORDER BY date, report_utc
            """,
            (pairing_id,),
        ).fetchall()
        if not pairing_days:
            raise ValueError(f"Pairing {pairing_id} was not found")

        relevant_days = [day for day in pairing_days if event_date is None or day["date"] >= event_date]
        if not relevant_days:
            raise ValueError(f"Pairing {pairing_id} has no duty on or after {event_date}")
        flights_by_day = [json.loads(day["flights_json"]) for day in relevant_days]
        day1_flights = flights_by_day[0]
        placeholders = ",".join("?" for _ in day1_flights)
        seat_rows = connection.execute(
            f"SELECT flight_id, seats FROM flights WHERE flight_id IN ({placeholders})",
            tuple(day1_flights),
        ).fetchall()
        seats_by_flight = {row["flight_id"]: int(row["seats"]) for row in seat_rows}
        missing_flights = [flight_id for flight_id in day1_flights if flight_id not in seats_by_flight]
        if missing_flights:
            raise ValueError(f"Missing flight records for pairing {pairing_id}: {missing_flights}")

        result = {
            "pairing_id": pairing_id,
            "sick_crew_id": sick_cid,
            "role": assignment["role"],
            "uncovered_flights_day1": day1_flights,
            "passengers_at_risk_day1": sum(seats_by_flight[flight_id] for flight_id in day1_flights),
        }
        if len(flights_by_day) > 1:
            result["uncovered_flights_day2"] = flights_by_day[1]
        return result
    finally:
        if conn is None:
            connection.close()


def expand_station_closure(
    station: str,
    date_str: str,
    window_start_utc: str,
    window_end_utc: str,
) -> dict:
    """Identify affected flights and per-flight delay/FDP assessment for a station closure."""
    load_all()
    w_start = _parse_dt(window_start_utc)
    w_end = _parse_dt(window_end_utc)

    affected = []
    for f in flights_list:
        if f["date"] != date_str:
            continue
        depd = _parse_dt(f["dep_utc"])
        arrd = _parse_dt(f["arr_utc"])
        hit = (f["dep_station"] == station and w_start <= depd < w_end) or \
              (f["arr_station"] == station and w_start <= arrd < w_end)
        if hit:
            affected.append(f["flight_id"])

    per_flight = []
    for fid in affected:
        f = FBY[fid]
        p = next(p for p in pairings for day in p["days"] if fid in day["flights"])
        day = next(day for day in p["days"] if fid in day["flights"])
        dl, rep, rel = _duty_len(day)

        depd = _parse_dt(f["dep_utc"])
        arrd = _parse_dt(f["arr_utc"])
        anchor = depd if (f["dep_station"] == station and w_start <= depd < w_end) else arrd
        shift = _hrs((w_end + timedelta(minutes=30)) - anchor)
        new_rel = rel + timedelta(hours=shift)
        new_fdp = _hrs(new_rel - rep)
        lim = _fdp_limit(len(day["flights"]))
        feasible = new_fdp <= lim

        per_flight.append({
            "flight_id": fid,
            "pairing_id": p["pairing_id"],
            "min_delay_hours": round(shift, 2),
            "crew_fdp_after_delay": round(new_fdp, 2),
            "fdp_limit": lim,
            "action": "delay (crew legal)" if feasible else "delay exceeds crew FDP — re-crew tail legs from reserves or cancel",
        })

    return {
        "affected_flights": affected,
        "per_flight_assessment": per_flight,
    }


def expand_delay(aircraft: str, date_str: str, delay_hours: float) -> dict:
    """Analyze FDP breach from a tech delay cascading through all legs."""
    load_all()
    p = next(
        p for p in pairings
        if p["aircraft"] == aircraft and p["days"][0]["date"] == date_str
    )
    day = p["days"][0]
    dl, rep, rel = _duty_len(day)
    new_fdp = round(dl + delay_hours, 2)
    n_sectors = len(day["flights"])
    lim = _fdp_limit(n_sectors)
    breach = new_fdp > lim

    result = {
        "pairing_id": p["pairing_id"],
        "original_fdp": dl,
        "fdp_after_delay": new_fdp,
        "fdp_limit": lim,
        "sectors": n_sectors,
        "breach": breach,
    }
    if breach:
        result["breach_detail"] = (
            f"RULE-FDP-01: delayed duty runs {new_fdp}h vs {lim}h limit "
            f"({n_sectors} sectors) — the rostered crew cannot legally complete the last leg."
        )
    return result
