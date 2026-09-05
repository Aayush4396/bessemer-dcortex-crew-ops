"""
src/tier1/entity_detail.py
==========================
Assembles flight and crew detail pages from SQLite + rules.json.
Does not invent fields that are not stored or rule-derived.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from src.rules.config import DUTY_MAX_HOURS, FLT_MAX_HOURS, REST_MIN_HOURS
from src.rules.models import SNAPSHOT_DATE
from src.tier1.connection import get_connection
from src.tier1.pairings_workspace import (
    RISK_CRITICAL,
    RISK_ELEVATED,
    RISK_HIGH_KPI,
    _cert_for_schedule,
    _hhmm,
    _initials,
    _risk_level,
    get_pairing,
)


def _flight_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "flight_id": row["flight_id"],
        "flight_no": row["flight_no"],
        "date": row["date"],
        "dep_station": row["dep_station"],
        "arr_station": row["arr_station"],
        "dep_utc": row["dep_utc"],
        "arr_utc": row["arr_utc"],
        "dep_hhmm": _hhmm(row["dep_utc"]),
        "arr_hhmm": _hhmm(row["arr_utc"]),
        "block_hours": float(row["block_hours"]),
        "aircraft": row["aircraft"],
        "aircraft_type": row["aircraft_type"],
        "seats": int(row["seats"]),
    }


def _pairing_for_flight(conn: sqlite3.Connection, flight_id: str) -> str | None:
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


def get_flight_detail(
    flight_id: str,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    owns_conn = conn is None
    c = get_connection(conn)
    try:
        row = c.execute(
            """
            SELECT flight_id, flight_no, date, dep_station, arr_station,
                   dep_utc, arr_utc, block_hours, aircraft, aircraft_type, seats
            FROM flights
            WHERE flight_id = ?
            """,
            (flight_id,),
        ).fetchone()
        if row is None:
            return None

        flight = _flight_row(row)
        pairing_id = _pairing_for_flight(c, flight_id)
        pairing = get_pairing(pairing_id, conn=c) if pairing_id else None

        previous = None
        nxt = None
        ground_hours = None
        duty_day = None
        if pairing:
            for day in pairing["days"]:
                ids = [f["flight_id"] for f in day["flights"]]
                if flight_id not in ids:
                    continue
                index = ids.index(flight_id)
                current = day["flights"][index]
                ground_hours = current.get("ground_hours")
                duty_day = {
                    "date": day["date"],
                    "day_index": day["day_index"],
                    "label": day["label"],
                    "report_hhmm": day["report_hhmm"],
                    "release_hhmm": day["release_hhmm"],
                    "duty_hours": day["duty_hours"],
                    "max_window_hours": day["max_window_hours"],
                    "sector_count": day["sector_count"],
                }
                if index > 0:
                    previous = day["flights"][index - 1]
                if index + 1 < len(day["flights"]):
                    nxt = day["flights"][index + 1]
                break

        return {
            **flight,
            "pairing": (
                {
                    "pairing_id": pairing["pairing_id"],
                    "route": pairing["route"],
                    "risk_score": pairing["risk_score"],
                    "risk_level": pairing["risk_level"],
                    "rotation_label": pairing["rotation_label"],
                    "day": duty_day,
                    "previous": previous,
                    "next": nxt,
                    "ground_hours": ground_hours,
                    "crew": pairing.get("crew") or [],
                }
                if pairing
                else None
            ),
        }
    finally:
        if owns_conn:
            c.close()


def get_crew_detail(
    crew_id: str,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    owns_conn = conn is None
    c = get_connection(conn)
    try:
        row = c.execute(
            """
            SELECT crew_id, name, rank, base, ratings, seniority,
                   reachability_minutes, status
            FROM crew
            WHERE crew_id = ?
            """,
            (crew_id,),
        ).fetchone()
        if row is None:
            return None

        risk_row = c.execute(
            """
            SELECT disruption_risk_score, drivers_json
            FROM risk_signals
            WHERE crew_id = ?
            """,
            (crew_id,),
        ).fetchone()
        risk_score = round(float(risk_row["disruption_risk_score"]), 2) if risk_row else 0.0
        drivers = json.loads(risk_row["drivers_json"]) if risk_row else []

        clock_row = c.execute(
            """
            SELECT as_of_utc, duty_hours_7d, flight_hours_28d, last_rest_ended
            FROM duty_clocks
            WHERE crew_id = ?
            """,
            (crew_id,),
        ).fetchone()

        cert_rows = c.execute(
            """
            SELECT cert_type, valid_from, valid_to
            FROM certifications
            WHERE crew_id = ?
            ORDER BY cert_type
            """,
            (crew_id,),
        ).fetchall()
        certs = [
            {
                "cert_type": cert["cert_type"],
                "valid_from": cert["valid_from"],
                "valid_to": cert["valid_to"],
            }
            for cert in cert_rows
        ]

        reserve_rows = c.execute(
            """
            SELECT date, base, on_call_start, on_call_end
            FROM reserve_pool
            WHERE crew_id = ?
            ORDER BY date
            """,
            (crew_id,),
        ).fetchall()
        reserve = [
            {
                "date": r["date"],
                "base": r["base"],
                "on_call_start": r["on_call_start"],
                "on_call_end": r["on_call_end"],
            }
            for r in reserve_rows
        ]

        assignment_rows = c.execute(
            """
            SELECT pairing_id, role
            FROM pairing_crew
            WHERE crew_id = ?
            ORDER BY pairing_id
            """,
            (crew_id,),
        ).fetchall()

        pairings: list[dict[str, Any]] = []
        duty_dates: list[str] = []
        for assignment in assignment_rows:
            pairing = get_pairing(assignment["pairing_id"], conn=c)
            if pairing is None:
                continue
            duty_dates.extend(d["date"] for d in pairing["days"])
            flights = [f for day in pairing["days"] for f in day["flights"]]
            pairings.append(
                {
                    "pairing_id": pairing["pairing_id"],
                    "role": assignment["role"],
                    "route": pairing["route"],
                    "risk_score": pairing["risk_score"],
                    "risk_level": pairing["risk_level"],
                    "rotation_label": pairing["rotation_label"],
                    "aircraft": pairing["aircraft"],
                    "dates": [d["date"] for d in pairing["days"]],
                    "flights": flights,
                    "crew": [
                        member
                        for member in pairing.get("crew") or []
                        if member["crew_id"] != crew_id
                    ],
                }
            )

        schedule_dates = duty_dates or [SNAPSHOT_DATE.isoformat()]
        cert_summary = _cert_for_schedule(certs, schedule_dates)
        for cert in certs:
            cert["status"] = _cert_for_schedule([cert], schedule_dates)["status"]

        return {
            "crew_id": row["crew_id"],
            "name": row["name"],
            "initials": _initials(row["name"]),
            "rank": row["rank"],
            "base": row["base"],
            "ratings": json.loads(row["ratings"]),
            "seniority": row["seniority"],
            "reachability_minutes": row["reachability_minutes"],
            "status": row["status"],
            "risk_score": risk_score,
            "risk_level": _risk_level(risk_score),
            "drivers": drivers,
            "duty": {
                "as_of_utc": clock_row["as_of_utc"] if clock_row else None,
                "duty_hours_7d": float(clock_row["duty_hours_7d"]) if clock_row else None,
                "duty_max_7d": DUTY_MAX_HOURS,
                "duty_rule": "RULE-DUTY-02",
                "flight_hours_28d": float(clock_row["flight_hours_28d"]) if clock_row else None,
                "flight_max_28d": FLT_MAX_HOURS,
                "flight_rule": "RULE-FLT-03",
                "last_rest_ended": clock_row["last_rest_ended"] if clock_row else None,
                "rest_min_hours": REST_MIN_HOURS,
                "rest_rule": "RULE-REST-04",
            },
            "certs": certs,
            "cert_status": cert_summary["status"],
            "reserve": reserve,
            "pairings": pairings,
        }
    finally:
        if owns_conn:
            c.close()


def list_crew(
    rank: str | None = None,
    base: str | None = None,
    risk: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Roster table for Crew Management. Fields are crew + risk_signals only."""
    owns_conn = conn is None
    c = get_connection(conn)
    try:
        rows = c.execute(
            """
            SELECT c.crew_id, c.name, c.rank, c.base, c.ratings, c.status,
                   COALESCE(rs.disruption_risk_score, 0.0) AS risk_score
            FROM crew c
            LEFT JOIN risk_signals rs ON rs.crew_id = c.crew_id
            ORDER BY risk_score DESC, c.crew_id ASC
            """
        ).fetchall()

        crew = []
        for row in rows:
            score = round(float(row["risk_score"]), 2)
            crew.append(
                {
                    "crew_id": row["crew_id"],
                    "name": row["name"],
                    "initials": _initials(row["name"]),
                    "rank": row["rank"],
                    "base": row["base"],
                    "ratings": json.loads(row["ratings"]),
                    "status": row["status"],
                    "risk_score": score,
                    "risk_level": _risk_level(score),
                }
            )

        ranks = sorted({m["rank"] for m in crew})
        bases = sorted({m["base"] for m in crew})
        risk_counts = {"all": len(crew), "high": 0, "elevated": 0, "low": 0}
        high_risk = 0
        for member in crew:
            if member["risk_score"] >= RISK_CRITICAL:
                risk_counts["high"] += 1
            elif member["risk_score"] >= RISK_ELEVATED:
                risk_counts["elevated"] += 1
            else:
                risk_counts["low"] += 1
            if member["risk_score"] >= RISK_HIGH_KPI:
                high_risk += 1

        if rank:
            crew = [m for m in crew if m["rank"] == rank]
        if base:
            crew = [m for m in crew if m["base"] == base]
        if risk == "high":
            crew = [m for m in crew if m["risk_score"] >= RISK_CRITICAL]
        elif risk == "elevated":
            crew = [m for m in crew if RISK_ELEVATED <= m["risk_score"] < RISK_CRITICAL]
        elif risk == "low":
            crew = [m for m in crew if m["risk_score"] < RISK_ELEVATED]

        return {
            "crew": crew,
            "ranks": ranks,
            "bases": bases,
            "risk_counts": risk_counts,
            "kpis": {
                "crew_total": risk_counts["all"],
                "high_risk_crew": high_risk,
            },
        }
    finally:
        if owns_conn:
            c.close()
