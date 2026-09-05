"""
src/tier1/pairings_workspace.py
================================
Assembles the Tactical Pairings Roster payload from SQLite.

All numbers come from joins against existing tables — pairings, pairing_crew,
flights, crew, risk_signals, certifications. Disruption scores come from
risk_signals. RULE-CERT-06 raises that score to 1.0 if a cert is expired on a
duty/flight date, or 0.65 if it expires the same day as a flight; otherwise
the cert is ignored. RULE-FDP-01 duty used% matches the duty bar: 0.65 at
≥75%, 0.9 at ≥90%, 1.0 when duty exceeds the max window.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from src.rules.config import (
    FDP_BASE_HOURS,
    FDP_FREE_SECTORS,
    FDP_REDUCTION_PER_EXTRA_SECTOR,
    REST_MIN_HOURS,
)
from src.rules.models import SNAPSHOT_DATE
from src.rules.time_utils import parse_utc
from src.tier1.cert_queries import get_expiring_certifications
from src.tier1.connection import get_connection

WEEK_START = date(2026, 9, 14)
WEEK_END = date(2026, 9, 20)
SNAPSHOT_UTC = datetime(2026, 9, 14, 18, 0, 0)

# Badge bands: 0.78/0.71 are critical. KPI high-risk includes 0.69 (3 crew in the dataset).
RISK_CRITICAL = 0.70
RISK_HIGH_KPI = 0.69
RISK_ELEVATED = 0.30
CERT_RISK_EXPIRED = 1.0
CERT_RISK_EXPIRING = 0.65
DUTY_RISK_OVER_LIMIT = 1.0
DUTY_RISK_OVER_90 = 0.9
DUTY_RISK_YELLOW = 0.65
DUTY_USED_RED = 0.90
DUTY_USED_YELLOW = 0.75

AIRCRAFT_LABELS = {
    "A320": "Airbus A320-neo",
    "ATR72": "ATR 72-600",
}

def _fdp_limit(sectors: int) -> float:
    extra = max(0, sectors - FDP_FREE_SECTORS)
    return FDP_BASE_HOURS - FDP_REDUCTION_PER_EXTRA_SECTOR * extra


def _duty_risk(duty_hours: float, max_window_hours: float) -> float:
    """
    RULE-FDP-01 used% — same bands as the duty bar.
    used > 100% → 1.0
    used ≥ 90% → 0.9
    used ≥ 75% (yellow) → 0.65
    otherwise ignore.
    """
    if max_window_hours <= 0:
        return 0.0
    used = duty_hours / max_window_hours
    if used > 1.0:
        return DUTY_RISK_OVER_LIMIT
    if used >= DUTY_USED_RED:
        return DUTY_RISK_OVER_90
    if used >= DUTY_USED_YELLOW:
        return DUTY_RISK_YELLOW
    return 0.0


def _risk_level(score: float) -> str:
    if score >= RISK_CRITICAL:
        return "critical"
    if score >= RISK_ELEVATED:
        return "elevated"
    return "low"


def _initials(name: str) -> str:
    parts = [p for p in name.replace(".", " ").split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return (name[:2] or "?").upper()


def _hhmm(iso_utc: str) -> str:
    return iso_utc[11:16]


def _hours_between(start_utc: str, end_utc: str) -> float:
    return round((parse_utc(end_utc) - parse_utc(start_utc)).total_seconds() / 3600.0, 2)


def _route_from_flights(flights: list[dict[str, Any]]) -> list[str]:
    if not flights:
        return []
    route = [flights[0]["dep_station"]]
    for flight in flights:
        route.append(flight["arr_station"])
    return route


def _week_days() -> list[dict[str, str]]:
    days = []
    cursor = WEEK_START
    while cursor <= WEEK_END:
        days.append(
            {
                "date": cursor.isoformat(),
                "weekday": cursor.strftime("%a"),
                "label": cursor.strftime("%a %d %b"),
            }
        )
        cursor += timedelta(days=1)
    return days


def _load_flights(conn: sqlite3.Connection, flight_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not flight_ids:
        return {}
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
    return {
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


def _kpis(conn: sqlite3.Connection) -> dict[str, Any]:
    pairing_count = conn.execute("SELECT COUNT(DISTINCT pairing_id) FROM pairings").fetchone()[0]
    flight_count = conn.execute("SELECT COUNT(*) FROM flights").fetchone()[0]
    crew_count = conn.execute("SELECT COUNT(*) FROM crew").fetchone()[0]
    high_risk = conn.execute(
        "SELECT COUNT(*) FROM risk_signals WHERE disruption_risk_score >= ?",
        (RISK_HIGH_KPI,),
    ).fetchone()[0]

    covered: set[str] = set()
    for row in conn.execute("SELECT flights_json FROM pairings"):
        covered.update(json.loads(row["flights_json"]))
    covered_pct = round((len(covered) / flight_count) * 100) if flight_count else 0

    expiring = get_expiring_certifications(
        as_of_date=SNAPSHOT_DATE.isoformat(),
        days_ahead=30,
        conn=conn,
    )

    return {
        "active_pairings": int(pairing_count),
        "flight_legs": int(flight_count),
        "legs_covered": len(covered),
        "legs_covered_pct": covered_pct,
        "crew_complement": int(crew_count),
        "high_risk_crew": int(high_risk),
        "high_risk_threshold": RISK_HIGH_KPI,
        "certs_expiring_30d": len(expiring),
    }


def _tails(conn: sqlite3.Connection) -> list[dict[str, str]]:
    rows = conn.execute(
        """
        SELECT DISTINCT p.aircraft, f.aircraft_type
        FROM pairings p
        JOIN flights f ON f.aircraft = p.aircraft
        ORDER BY p.aircraft ASC
        """
    ).fetchall()
    seen: set[str] = set()
    tails = []
    for row in rows:
        if row["aircraft"] in seen:
            continue
        seen.add(row["aircraft"])
        tails.append(
            {
                "tail": row["aircraft"],
                "type": row["aircraft_type"],
                "label": AIRCRAFT_LABELS.get(row["aircraft_type"], row["aircraft_type"]),
            }
        )
    return tails


def _cert_for_schedule(certs: list[dict[str, str]], schedule_dates: list[str]) -> dict[str, Any]:
    """
    RULE-CERT-06: valid_to >= duty_date.
    Expired on any schedule/flight date → risk 1.0.
    Expires the same calendar day as a flight (< 1 day) → risk 0.65.
    Otherwise ignore.
    """
    if not certs or not schedule_dates:
        return {"status": "valid", "label": "Certs valid", "risk": 0.0}

    duties = sorted({date.fromisoformat(d) for d in schedule_dates})
    worst_risk = 0.0
    worst_status = "valid"
    worst_cert: dict[str, str] | None = None

    for cert in certs:
        valid_to = date.fromisoformat(cert["valid_to"])
        for duty in duties:
            delta_days = (valid_to - duty).days
            if delta_days < 0 and worst_risk < CERT_RISK_EXPIRED:
                worst_risk = CERT_RISK_EXPIRED
                worst_status = "expired"
                worst_cert = cert
            elif 0 <= delta_days < 1 and worst_risk < CERT_RISK_EXPIRING:
                worst_risk = CERT_RISK_EXPIRING
                worst_status = "expiring"
                worst_cert = cert

    if worst_status == "valid" or worst_cert is None:
        return {"status": "valid", "label": "Certs valid", "risk": 0.0}

    return {
        "status": worst_status,
        "label": f"{worst_status} {worst_cert['cert_type']} {worst_cert['valid_to']}",
        "risk": worst_risk,
    }


def _build_roster(members: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(
        members,
        key=lambda m: (-m["risk_score"], m["role"], m["crew_id"]),
    )
    highlighted = []
    collapsed = []
    for member in ranked:
        cert = member.get("cert") or {"status": "valid", "label": "Certs valid"}
        if member["risk_score"] >= RISK_ELEVATED:
            highlighted.append(
                {
                    "crew_id": member["crew_id"],
                    "name": member["name"],
                    "initials": _initials(member["name"]),
                    "role": member["role"],
                    "risk_score": member["risk_score"],
                    "risk_level": _risk_level(member["risk_score"]),
                    "cert_status": cert["status"],
                    "cert_label": cert["label"],
                }
            )
        else:
            collapsed.append(member)

    captain = next((m for m in members if m["role"] == "Captain"), members[0] if members else None)
    cabin_collapsed = [m for m in collapsed if "Cabin" in m["role"]]

    return {
        "highlighted": highlighted,
        "collapsed_count": len(collapsed),
        "collapsed_initials": [_initials(m["name"]) for m in collapsed[:3]],
        "captain_name": captain["name"] if captain else None,
        "captain_initials": _initials(captain["name"]) if captain else None,
        "total": len(members),
        "cabin_legal_count": len(cabin_collapsed) if highlighted else len([m for m in members if "Cabin" in m["role"]]),
        "summary": (
            f"{captain['name']} + {max(0, len(members) - 1)}"
            if captain
            else f"{len(members)} crew"
        ),
    }


def _crew_detail(member: dict[str, Any]) -> dict[str, Any]:
    cert = member.get("cert") or {"status": "valid", "label": "Certs valid", "risk": 0.0}
    return {
        "crew_id": member["crew_id"],
        "name": member["name"],
        "initials": _initials(member["name"]),
        "role": member["role"],
        "rank": member["rank"],
        "base": member.get("base"),
        "ratings": member.get("ratings") or [],
        "seniority": member.get("seniority"),
        "status": member.get("status"),
        "risk_score": member["risk_score"],
        "risk_level": _risk_level(member["risk_score"]),
        "drivers": member.get("drivers") or [],
        "cert_status": cert["status"],
        "certs": member.get("certs") or [],
        "duty_hours_7d": member.get("duty_hours_7d"),
        "flight_hours_28d": member.get("flight_hours_28d"),
        "last_rest_ended": member.get("last_rest_ended"),
    }


def get_pairings_workspace(
    date_filter: str | None = None,
    aircraft: str | None = None,
    risk: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """
    Build the Pairings Workspace payload.

    date_filter
        If set, include pairings that operate on this UTC date, but still
        return every day of those pairings so a 2-day rotation stays intact.
    aircraft
        Tail registration filter, e.g. "VT-DXC".
    risk
        "all" | "high" | "elevated" | "low". Applied after pairing risk is
        the maximum of assigned-crew scores and RULE-FDP-01 duty-hour risk.
    """
    owns_conn = conn is None
    c = get_connection(conn)
    try:
        pairing_sql = "SELECT pairing_id, aircraft, date, report_utc, release_utc, flights_json FROM pairings"
        params: list[Any] = []
        clauses: list[str] = []
        if aircraft:
            clauses.append("aircraft = ?")
            params.append(aircraft)
        if clauses:
            pairing_sql += " WHERE " + " AND ".join(clauses)
        pairing_sql += " ORDER BY pairing_id ASC, date ASC"

        day_rows = c.execute(pairing_sql, tuple(params)).fetchall()

        grouped: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for row in day_rows:
            grouped[row["pairing_id"]].append(row)

        if date_filter:
            matching_ids = {
                pid for pid, days in grouped.items() if any(d["date"] == date_filter for d in days)
            }
            grouped = {pid: days for pid, days in grouped.items() if pid in matching_ids}

        pairing_ids = list(grouped.keys())

        crew_by_pairing: dict[str, list[dict[str, Any]]] = defaultdict(list)
        if pairing_ids:
            placeholders = ",".join("?" * len(pairing_ids))
            crew_rows = c.execute(
                f"""
                SELECT pc.pairing_id, pc.crew_id, pc.role, c.name, c.rank,
                       c.base, c.ratings, c.seniority, c.status,
                       COALESCE(rs.disruption_risk_score, 0.0) AS risk_score,
                       COALESCE(rs.drivers_json, '[]') AS drivers_json
                FROM pairing_crew pc
                JOIN crew c ON c.crew_id = pc.crew_id
                LEFT JOIN risk_signals rs ON rs.crew_id = pc.crew_id
                WHERE pc.pairing_id IN ({placeholders})
                ORDER BY pc.rowid ASC
                """,
                tuple(pairing_ids),
            ).fetchall()
            for row in crew_rows:
                crew_by_pairing[row["pairing_id"]].append(
                    {
                        "crew_id": row["crew_id"],
                        "name": row["name"],
                        "role": row["role"],
                        "rank": row["rank"],
                        "base": row["base"],
                        "ratings": json.loads(row["ratings"]),
                        "seniority": row["seniority"],
                        "status": row["status"],
                        "risk_score": round(float(row["risk_score"]), 2),
                        "drivers": json.loads(row["drivers_json"]),
                    }
                )

        certs_by_crew: dict[str, list[dict[str, str]]] = defaultdict(list)
        assigned_ids = {m["crew_id"] for members in crew_by_pairing.values() for m in members}
        if assigned_ids:
            placeholders = ",".join("?" * len(assigned_ids))
            for row in c.execute(
                f"""
                SELECT crew_id, cert_type, valid_from, valid_to
                FROM certifications
                WHERE crew_id IN ({placeholders})
                """,
                tuple(assigned_ids),
            ).fetchall():
                certs_by_crew[row["crew_id"]].append(
                    {
                        "cert_type": row["cert_type"],
                        "valid_from": row["valid_from"],
                        "valid_to": row["valid_to"],
                    }
                )

        clocks_by_crew: dict[str, dict[str, Any]] = {}
        if assigned_ids:
            placeholders = ",".join("?" * len(assigned_ids))
            for row in c.execute(
                f"""
                SELECT crew_id, duty_hours_7d, flight_hours_28d, last_rest_ended
                FROM duty_clocks
                WHERE crew_id IN ({placeholders})
                """,
                tuple(assigned_ids),
            ).fetchall():
                clocks_by_crew[row["crew_id"]] = {
                    "duty_hours_7d": float(row["duty_hours_7d"]),
                    "flight_hours_28d": float(row["flight_hours_28d"]),
                    "last_rest_ended": row["last_rest_ended"],
                }

        all_flight_ids: list[str] = []
        parsed_days: dict[str, list[list[str]]] = {}
        for pid, days in grouped.items():
            parsed_days[pid] = [json.loads(d["flights_json"]) for d in days]
            for ids in parsed_days[pid]:
                all_flight_ids.extend(ids)
        flight_map = _load_flights(c, all_flight_ids)

        pairings_out: list[dict[str, Any]] = []
        for pid, days in grouped.items():
            day_payloads = []
            all_flights: list[dict[str, Any]] = []

            for index, day in enumerate(days):
                ids = parsed_days[pid][index]
                flights = [flight_map[fid] for fid in ids if fid in flight_map]
                all_flights.extend(flights)

                fdp_hours = _hours_between(day["report_utc"], day["release_utc"])
                fdp_limit = _fdp_limit(len(flights))

                flight_payloads = []
                prev_arr = None
                for flight in flights:
                    ground_hours = _hours_between(prev_arr, flight["dep_utc"]) if prev_arr else None
                    flight_payloads.append(
                        {
                            "flight_id": flight["flight_id"],
                            "flight_no": flight["flight_no"],
                            "date": flight["date"],
                            "dep_station": flight["dep_station"],
                            "arr_station": flight["arr_station"],
                            "dep_utc": flight["dep_utc"],
                            "arr_utc": flight["arr_utc"],
                            "dep_hhmm": _hhmm(flight["dep_utc"]),
                            "arr_hhmm": _hhmm(flight["arr_utc"]),
                            "block_hours": flight["block_hours"],
                            "aircraft": flight["aircraft"],
                            "aircraft_type": flight["aircraft_type"],
                            "seats": flight["seats"],
                            "ground_hours": ground_hours,
                        }
                    )
                    prev_arr = flight["arr_utc"]

                rest_hours = None
                if index > 0:
                    rest_hours = _hours_between(days[index - 1]["release_utc"], day["report_utc"])

                used_pct = min(100, round((fdp_hours / fdp_limit) * 100)) if fdp_limit else 0
                day_payloads.append(
                    {
                        "date": day["date"],
                        "day_index": index + 1,
                        "label": datetime.strptime(day["date"], "%Y-%m-%d").strftime("%d %b"),
                        "report_utc": day["report_utc"],
                        "release_utc": day["release_utc"],
                        "report_hhmm": _hhmm(day["report_utc"]),
                        "release_hhmm": _hhmm(day["release_utc"]),
                        "duty_hours": fdp_hours,
                        "max_window_hours": fdp_limit,
                        "duty_used_pct": used_pct,
                        "sector_count": len(flights),
                        "rest_hours": rest_hours,
                        "rest_min_hours": REST_MIN_HOURS if rest_hours is not None else None,
                        "flights": flight_payloads,
                    }
                )

            first_type = all_flights[0]["aircraft_type"] if all_flights else "A320"
            members = crew_by_pairing.get(pid, [])
            schedule_dates = [d["date"] for d in days] + [f["date"] for f in all_flights]
            for member in members:
                raw_certs = certs_by_crew.get(member["crew_id"], [])
                cert = _cert_for_schedule(raw_certs, schedule_dates)
                clock = clocks_by_crew.get(member["crew_id"], {})
                member["cert"] = cert
                member["certs"] = raw_certs
                member["duty_hours_7d"] = clock.get("duty_hours_7d")
                member["flight_hours_28d"] = clock.get("flight_hours_28d")
                member["last_rest_ended"] = clock.get("last_rest_ended")
                member["risk_score"] = max(member["risk_score"], cert["risk"])
            crew_score = max((m["risk_score"] for m in members), default=0.0)
            duty_score = max(
                (_duty_risk(d["duty_hours"], d["max_window_hours"]) for d in day_payloads),
                default=0.0,
            )
            pairing_score = max(crew_score, duty_score)
            pairing_level = _risk_level(pairing_score)

            pairings_out.append(
                {
                    "pairing_id": pid,
                    "rotation_days": len(days),
                    "rotation_label": f"{len(days)}-Day Rotation",
                    "route": _route_from_flights(all_flights),
                    "risk_score": pairing_score,
                    "risk_level": pairing_level,
                    "aircraft": {
                        "tail": days[0]["aircraft"],
                        "type": first_type,
                        "label": AIRCRAFT_LABELS.get(first_type, first_type),
                    },
                    "days": day_payloads,
                    "roster": _build_roster(members),
                    "crew": [_crew_detail(m) for m in members],
                }
            )

        pairings_out.sort(key=lambda p: (-p["risk_score"], p["pairing_id"]))

        risk_counts = {"all": len(pairings_out), "high": 0, "elevated": 0, "low": 0}
        for pairing in pairings_out:
            if pairing["risk_score"] >= RISK_CRITICAL:
                risk_counts["high"] += 1
            elif pairing["risk_score"] >= RISK_ELEVATED:
                risk_counts["elevated"] += 1
            else:
                risk_counts["low"] += 1

        if risk == "high":
            pairings_out = [p for p in pairings_out if p["risk_score"] >= RISK_CRITICAL]
        elif risk == "elevated":
            pairings_out = [
                p for p in pairings_out if RISK_ELEVATED <= p["risk_score"] < RISK_CRITICAL
            ]
        elif risk == "low":
            pairings_out = [p for p in pairings_out if p["risk_score"] < RISK_ELEVATED]

        return {
            "snapshot_utc": SNAPSHOT_UTC.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "hub": "BLR",
            "week": {
                "start": WEEK_START.isoformat(),
                "end": WEEK_END.isoformat(),
                "label": "Week of 14 Sep 2026",
                "days": _week_days(),
            },
            "filters": {
                "date": date_filter,
                "aircraft": aircraft,
                "risk": risk or "all",
            },
            "kpis": _kpis(c),
            "tails": _tails(c),
            "risk_counts": risk_counts,
            "pairings": pairings_out,
        }
    finally:
        if owns_conn:
            c.close()


def get_pairing(
    pairing_id: str,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    """Return one assembled pairing, or None if the id is not in SQLite."""
    payload = get_pairings_workspace(conn=conn)
    return next((p for p in payload["pairings"] if p["pairing_id"] == pairing_id), None)
