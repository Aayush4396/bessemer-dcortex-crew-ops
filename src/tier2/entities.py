"""
src/tier2/entities.py
=====================
Join-friendly entity lookups for flights, pairings, crew, stations, and costs.
Every payload includes the next-hop keys (crew_id, pairing_id, flight_id).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from src.db.loader import get_constants
from src.rules.config import (
    FDP_BASE_HOURS,
    FDP_FREE_SECTORS,
    FDP_REDUCTION_PER_EXTRA_SECTOR,
    REST_MIN_HOURS,
)
from src.rules.time_utils import parse_utc
from src.tier1.connection import get_connection
from src.tier1.entity_detail import get_crew_detail

_EVEN_DEL_BLR_DATES = {date(2026, 9, d) for d in (14, 16, 18, 20)}


def fdp_limit(sectors: int) -> float:
    extra = max(0, sectors - FDP_FREE_SECTORS)
    return FDP_BASE_HOURS - FDP_REDUCTION_PER_EXTRA_SECTOR * extra


def hours_between(start_utc: str, end_utc: str) -> float:
    return round((parse_utc(end_utc) - parse_utc(start_utc)).total_seconds() / 3600.0, 2)


def fmt_utc(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_flights(conn: sqlite3.Connection, flight_ids: list[str]) -> list[dict[str, Any]]:
    if not flight_ids:
        return []
    placeholders = ",".join("?" * len(flight_ids))
    rows = conn.execute(
        f"""
        SELECT flight_id, flight_no, date, dep_station, arr_station,
               dep_utc, arr_utc, block_hours, aircraft, aircraft_type, seats
        FROM flights
        WHERE flight_id IN ({placeholders})
        """,
        tuple(flight_ids),
    ).fetchall()
    by_id = {
        r["flight_id"]: {
            "flight_id": r["flight_id"],
            "flight_no": r["flight_no"],
            "date": r["date"],
            "dep_station": r["dep_station"],
            "arr_station": r["arr_station"],
            "dep_utc": r["dep_utc"],
            "arr_utc": r["arr_utc"],
            "block_hours": float(r["block_hours"]),
            "aircraft": r["aircraft"],
            "aircraft_type": r["aircraft_type"],
            "seats": int(r["seats"]),
        }
        for r in rows
    }
    return [by_id[fid] for fid in flight_ids if fid in by_id]


def pairing_id_for_flight(flight_id: str, conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
        SELECT pairing_id
        FROM pairings
        WHERE EXISTS (
            SELECT 1 FROM json_each(flights_json) WHERE value = ?
        )
        LIMIT 1
        """,
        (flight_id,),
    ).fetchone()
    return row["pairing_id"] if row else None


def pairing_id_for_aircraft_date(
    aircraft: str,
    duty_date: str,
    conn: sqlite3.Connection,
) -> str | None:
    row = conn.execute(
        """
        SELECT pairing_id
        FROM pairings
        WHERE aircraft = ? AND date = ?
        LIMIT 1
        """,
        (aircraft, duty_date),
    ).fetchone()
    return row["pairing_id"] if row else None


def resolve_flight_id(
    flight_id: str | None = None,
    flight_no: str | None = None,
    date: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> str | None:
    if flight_id:
        return flight_id
    if flight_no and date:
        c = get_connection(conn)
        row = c.execute(
            "SELECT flight_id FROM flights WHERE flight_no = ? AND date = ?",
            (flight_no, date),
        ).fetchone()
        return row["flight_id"] if row else None
    return None


def _absence_impact(days: list[dict[str, Any]], as_of_date: str | None) -> dict[str, Any]:
    """Impact of a no-show (sick, missed report, or any absence) on every pairing day."""
    if not days:
        return {
            "as_of_date": as_of_date,
            "days": [],
            "immediately_uncrewed": [],
            "subsequent_at_risk": [],
            "already_operated": [],
            "passengers_immediately_uncrewed": 0,
            "note": "Pairing has no duty days.",
        }

    cutoff = as_of_date or days[0]["date"]
    impact_days: list[dict[str, Any]] = []
    immediately_uncrewed: list[str] = []
    subsequent_at_risk: list[str] = []
    already_operated: list[str] = []
    first_remaining = True

    for day in days:
        if day["date"] < cutoff:
            status = "already_operated"
            already_operated.extend(day["flight_ids"])
        elif first_remaining:
            status = "immediately_uncrewed"
            immediately_uncrewed.extend(day["flight_ids"])
            first_remaining = False
        else:
            status = "at_risk"
            subsequent_at_risk.extend(day["flight_ids"])
        impact_days.append(
            {
                "day_index": day["day_index"],
                "date": day["date"],
                "impact": status,
                "flight_ids": day["flight_ids"],
                "passengers": day["passengers"],
                "dep_station": day["dep_station"],
            }
        )

    remaining = [d for d in impact_days if d["impact"] != "already_operated"]
    later_n = max(0, len(remaining) - 1)
    return {
        "as_of_date": cutoff,
        "days": impact_days,
        "immediately_uncrewed": immediately_uncrewed,
        "subsequent_at_risk": subsequent_at_risk,
        "already_operated": already_operated,
        "passengers_immediately_uncrewed": next(
            (d["passengers"] for d in impact_days if d["impact"] == "immediately_uncrewed"),
            0,
        ),
        "day1": immediately_uncrewed,
        "day2_also_at_risk": subsequent_at_risk,
        "passengers_day1": next(
            (d["passengers"] for d in impact_days if d["impact"] == "immediately_uncrewed"),
            0,
        ),
        "note": (
            f"{len(days)}-day pairing as of {cutoff}: "
            f"{len(immediately_uncrewed)} immediately uncrewed, "
            f"{later_n} later day(s) at risk."
        ),
    }


def load_pairing_days(
    pairing_id: str,
    conn: sqlite3.Connection | None = None,
    as_of_date: str | None = None,
) -> dict[str, Any] | None:
    """Compact pairing with per-day duty windows, flights, seats, and crew."""
    owns = conn is None
    c = get_connection(conn)
    try:
        rows = c.execute(
            """
            SELECT date, report_utc, release_utc, flights_json, aircraft
            FROM pairings
            WHERE pairing_id = ?
            ORDER BY date ASC
            """,
            (pairing_id,),
        ).fetchall()
        if not rows:
            return None

        crew_rows = c.execute(
            """
            SELECT pc.crew_id, pc.role, cr.name, cr.rank, cr.base, cr.ratings
            FROM pairing_crew pc
            JOIN crew cr ON cr.crew_id = pc.crew_id
            WHERE pc.pairing_id = ?
            ORDER BY pc.rowid ASC
            """,
            (pairing_id,),
        ).fetchall()
        crew = [
            {
                "crew_id": r["crew_id"],
                "role": r["role"],
                "name": r["name"],
                "rank": r["rank"],
                "base": r["base"],
                "ratings": json.loads(r["ratings"]),
            }
            for r in crew_rows
        ]

        days: list[dict[str, Any]] = []
        prev_release = None
        for index, row in enumerate(rows):
            flight_ids = json.loads(row["flights_json"])
            flights = _load_flights(c, flight_ids)
            duty_hours = hours_between(row["report_utc"], row["release_utc"])
            sectors = len(flights)
            limit = fdp_limit(sectors)
            rest_hours = hours_between(prev_release, row["report_utc"]) if prev_release else None
            passengers = sum(f["seats"] for f in flights)
            block_hours = round(sum(f["block_hours"] for f in flights), 2)
            days.append(
                {
                    "date": row["date"],
                    "day_index": index + 1,
                    "report_utc": row["report_utc"],
                    "release_utc": row["release_utc"],
                    "duty_hours": duty_hours,
                    "max_window_hours": limit,
                    "sector_count": sectors,
                    "block_hours": block_hours,
                    "rest_hours": rest_hours,
                    "rest_min_hours": REST_MIN_HOURS if rest_hours is not None else None,
                    "passengers": passengers,
                    "dep_station": flights[0]["dep_station"] if flights else None,
                    "aircraft_type": flights[0]["aircraft_type"] if flights else None,
                    "flights": flights,
                    "flight_ids": flight_ids,
                }
            )
            prev_release = row["release_utc"]

        first = days[0] if days else {}
        return {
            "pairing_id": pairing_id,
            "aircraft": rows[0]["aircraft"],
            "aircraft_type": first.get("aircraft_type"),
            "dep_station": first.get("dep_station"),
            "rotation_days": len(days),
            "crew": crew,
            "days": days,
            "passengers_day1": days[0]["passengers"] if days else 0,
            "passengers_total": sum(d["passengers"] for d in days),
            "absence_impact": _absence_impact(days, as_of_date),
        }
    finally:
        if owns:
            c.close()


def get_pairing_entity(
    pairing_id: str,
    conn: sqlite3.Connection | None = None,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    payload = load_pairing_days(pairing_id, conn=conn, as_of_date=as_of_date)
    if payload is None:
        return {"error": f"pairing_id {pairing_id!r} not found"}
    return payload


def get_flight_duty_times(
    flight_id: str | None = None,
    flight_no: str | None = None,
    date: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """
    Flight facts plus the containing pairing day's report/release (RULE-FDP-01 duty period).
    Join keys: pairing_id, crew_id list, aircraft.
    """
    owns = conn is None
    c = get_connection(conn)
    try:
        resolved = resolve_flight_id(flight_id=flight_id, flight_no=flight_no, date=date, conn=c)
        if not resolved:
            return {"error": "flight_id or (flight_no + date) is required"}

        row = c.execute(
            """
            SELECT flight_id, flight_no, date, dep_station, arr_station,
                   dep_utc, arr_utc, block_hours, aircraft, aircraft_type, seats
            FROM flights
            WHERE flight_id = ?
            """,
            (resolved,),
        ).fetchone()
        if row is None:
            return {"error": f"flight_id {resolved!r} not found"}

        pairing_id = pairing_id_for_flight(resolved, c)
        pairing = load_pairing_days(pairing_id, conn=c) if pairing_id else None
        duty_day = None
        if pairing:
            for day in pairing["days"]:
                if resolved in day["flight_ids"]:
                    duty_day = day
                    break

        return {
            "flight_id": row["flight_id"],
            "flight_no": row["flight_no"],
            "date": row["date"],
            "dep_station": row["dep_station"],
            "arr_station": row["arr_station"],
            "dep_utc": row["dep_utc"],
            "arr_utc": row["arr_utc"],
            "block_hours": float(row["block_hours"]),
            "aircraft": row["aircraft"],
            "aircraft_type": row["aircraft_type"],
            "seats": int(row["seats"]),
            "pairing_id": pairing_id,
            "report_utc": duty_day["report_utc"] if duty_day else None,
            "release_utc": duty_day["release_utc"] if duty_day else None,
            "duty_hours": duty_day["duty_hours"] if duty_day else None,
            "max_window_hours": duty_day["max_window_hours"] if duty_day else None,
            "sector_count": duty_day["sector_count"] if duty_day else None,
            "day_index": duty_day["day_index"] if duty_day else None,
            "crew": pairing["crew"] if pairing else [],
        }
    finally:
        if owns:
            c.close()


def get_crew_entity(crew_id: str, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Full crew join: profile, clocks, certs, reserve, rostered pairings and flights."""
    detail = get_crew_detail(crew_id, conn=conn)
    if detail is None:
        return {"error": f"crew_id {crew_id!r} not found"}
    return detail


def get_station_movements(
    station: str,
    date: str,
    start_time: str,
    end_time: str,
    conn: sqlite3.Connection | None = None,
) -> list[str]:
    """
    Flight ids that depart or arrive at `station` on `date` with the movement
    time in [start_time, end_time) UTC (HH:MM). Matches generate.py closure logic.
    """
    owns = conn is None
    c = get_connection(conn)
    try:
        window_start = datetime.strptime(f"{date}T{start_time}:00Z", "%Y-%m-%dT%H:%M:%SZ")
        window_end = datetime.strptime(f"{date}T{end_time}:00Z", "%Y-%m-%dT%H:%M:%SZ")
        rows = c.execute(
            """
            SELECT flight_id, dep_station, arr_station, dep_utc, arr_utc
            FROM flights
            WHERE date = ?
            ORDER BY rowid ASC
            """,
            (date,),
        ).fetchall()
        hit: list[str] = []
        for r in rows:
            dep = parse_utc(r["dep_utc"])
            arr = parse_utc(r["arr_utc"])
            if (r["dep_station"] == station and window_start <= dep < window_end) or (
                r["arr_station"] == station and window_start <= arr < window_end
            ):
                hit.append(r["flight_id"])
        return hit
    finally:
        if owns:
            c.close()


def get_cost_rates() -> dict[str, Any]:
    return get_constants()["costs"]


def del_blr_positioning(duty_date: date) -> dict[str, Any]:
    """Fixed DEL→BLR deadhead pair from the dataset convention."""
    even = duty_date in _EVEN_DEL_BLR_DATES
    arr_hhmm = "07:45" if even else "08:45"
    flight_no = "DX589" if even else "DX402"
    arr_utc = f"{duty_date.isoformat()}T{arr_hhmm}:00Z"
    new_report = fmt_utc(parse_utc(arr_utc) + timedelta(minutes=15))
    return {
        "flight_no": flight_no,
        "arr_utc": arr_utc,
        "new_report_utc": new_report,
    }
