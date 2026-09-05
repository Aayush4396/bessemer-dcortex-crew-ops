"""
src/tier2/simulator.py
======================
Deterministic disruption impact simulation engine.
Simulates cascading consequences of operational disruptions:
1. Sick crew / Incapacitation
2. Station closures / Curfews / Weather groundings
3. Rotational flight delays / FDP breaches
4. Lapsed qualification / Certification expiries
5. Multi-crew simultaneous incapacitations
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from src.rules.config import (
    FDP_BASE_HOURS,
    FDP_FREE_SECTORS,
    FDP_REDUCTION_PER_EXTRA_SECTOR,
)
from src.rules.time_utils import parse_utc
from src.tier1.connection import get_connection


def _fdp_limit(sectors: int) -> float:
    """Calculates allowable FDP hours under DGCA CAR Section 7 Series J."""
    extra = max(0, sectors - FDP_FREE_SECTORS)
    return FDP_BASE_HOURS - FDP_REDUCTION_PER_EXTRA_SECTOR * extra


def simulate_sick_crew(
    crew_id: str,
    pairing_id: str | None = None,
    reported_utc: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """
    Simulates operational impact when a crew member calls sick or becomes incapacitated.
    Determines uncovered flight sectors, passengers at risk, crew role, and multi-day status.
    """
    c = get_connection(conn)

    # 1. Resolve pairing_id if not explicitly provided
    if not pairing_id:
        date_hint = reported_utc[:10] if reported_utc else "2026-09-15"
        row = c.execute(
            """
            SELECT p.pairing_id
            FROM pairings p
            JOIN pairing_crew pc ON pc.pairing_id = p.pairing_id
            WHERE pc.crew_id = ? AND p.date >= ?
            ORDER BY p.date ASC
            LIMIT 1
            """,
            (crew_id, date_hint),
        ).fetchone()
        if not row:
            raise ValueError(f"No pairing found for crew member {crew_id} on or after {date_hint}")
        pairing_id = row["pairing_id"]

    # 2. Query all days for this pairing
    pairing_rows = c.execute(
        """
        SELECT pairing_id, date, report_utc, release_utc, flights_json, aircraft
        FROM pairings
        WHERE pairing_id = ?
        ORDER BY date ASC
        """,
        (pairing_id,),
    ).fetchall()

    if not pairing_rows:
        raise ValueError(f"Pairing {pairing_id} not found in database")

    # 3. Resolve crew role, rank, ratings, and aircraft type
    crew_info = c.execute(
        "SELECT rank, base, ratings FROM crew WHERE crew_id = ?",
        (crew_id,),
    ).fetchone()
    rank = crew_info["rank"] if crew_info else "Unknown"

    role_info = c.execute(
        "SELECT role FROM pairing_crew WHERE pairing_id = ? AND crew_id = ?",
        (pairing_id, crew_id),
    ).fetchone()
    role = role_info["role"] if role_info else rank

    # Aircraft type from the first flight
    first_day_flights = json.loads(pairing_rows[0]["flights_json"])
    first_f = c.execute(
        "SELECT aircraft_type, aircraft FROM flights WHERE flight_id = ?",
        (first_day_flights[0],),
    ).fetchone()
    aircraft_type = first_f["aircraft_type"] if first_f else "A320"

    # 4. Extract active flight legs and seat capacity on or after reported date
    is_multi_day = len(pairing_rows) > 1
    rep_date = reported_utc[:10] if reported_utc else pairing_rows[0]["date"]
    active_rows = [r for r in pairing_rows if r["date"] >= rep_date]
    if not active_rows:
        active_rows = pairing_rows

    uncovered_flights_all: list[str] = []
    days_data: list[dict[str, Any]] = []

    for r in active_rows:
        f_list = json.loads(r["flights_json"])
        uncovered_flights_all.extend(f_list)

        day_seats = 0
        for fid in f_list:
            s_row = c.execute("SELECT seats FROM flights WHERE flight_id = ?", (fid,)).fetchone()
            if s_row and s_row["seats"]:
                day_seats += int(s_row["seats"])

        days_data.append({
            "date": r["date"],
            "flights": f_list,
            "seats": day_seats,
            "report_utc": r["report_utc"],
            "release_utc": r["release_utc"],
        })

    day1_flights = days_data[0]["flights"]
    day1_seats = days_data[0]["seats"]
    total_seats = sum(d["seats"] for d in days_data)

    result: dict[str, Any] = {
        "disruption_type": "SICK_CREW",
        "crew_id": crew_id,
        "pairing_id": pairing_id,
        "reported_utc": reported_utc or (pairing_rows[0]["report_utc"]),
        "role": role,
        "rank": rank,
        "aircraft_type": aircraft_type,
        "is_multi_day": is_multi_day,
        "uncovered_flights": uncovered_flights_all,
        "passengers_at_risk": total_seats,
    }

    if is_multi_day and len(days_data) > 1:
        result["uncovered_flights_day1"] = day1_flights
        result["uncovered_flights_day2"] = days_data[1]["flights"]
        result["passengers_at_risk_day1"] = day1_seats

    return result


def simulate_station_closure(
    station: str,
    start_utc: str,
    end_utc: str,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """
    Simulates airport station closure. Identifies all affected departures and arrivals,
    computes delay until reopening (+30m turnaround), and assesses crew FDP feasibility.
    """
    c = get_connection(conn)
    date_str = start_utc[:10]
    reopen_dt = parse_utc(end_utc) + timedelta(minutes=30)

    # 1. Fetch all departures and arrivals touching the closed station in the window
    query = """
        SELECT flight_id, flight_no, dep_station, arr_station, dep_utc, arr_utc, aircraft
        FROM flights
        WHERE date = ?
          AND (
            (dep_station = ? AND dep_utc >= ? AND dep_utc < ?)
            OR
            (arr_station = ? AND arr_utc > ? AND arr_utc <= ?)
          )
        ORDER BY dep_utc ASC
    """
    rows = c.execute(
        query,
        (date_str, station, start_utc, end_utc, station, start_utc, end_utc),
    ).fetchall()

    affected_flights = [r["flight_id"] for r in rows]
    assessments: list[dict[str, Any]] = []

    # Cache pairing lookups
    pairings_cache = c.execute(
        "SELECT pairing_id, date, report_utc, release_utc, flights_json FROM pairings WHERE date = ?",
        (date_str,),
    ).fetchall()

    for r in rows:
        fid = r["flight_id"]
        # Find pairing for this flight
        pairing_match = None
        for p in pairings_cache:
            p_flights = json.loads(p["flights_json"])
            if fid in p_flights:
                pairing_match = p
                break

        if not pairing_match:
            continue

        p_id = pairing_match["pairing_id"]
        p_flights = json.loads(pairing_match["flights_json"])
        sectors = len(p_flights)
        fdp_lim = _fdp_limit(sectors)

        # Min delay hours to reopen + 30m turn
        is_dep = (r["dep_station"] == station)
        touch_dt = parse_utc(r["dep_utc"]) if is_dep else parse_utc(r["arr_utc"])
        delay_hrs = round((reopen_dt - touch_dt).total_seconds() / 3600.0, 2)

        # Crew FDP calculation
        rep_dt = parse_utc(pairing_match["report_utc"])
        rel_dt = parse_utc(pairing_match["release_utc"])
        orig_fdp = (rel_dt - rep_dt).total_seconds() / 3600.0
        crew_fdp = round(orig_fdp + delay_hrs, 2)

        if crew_fdp > fdp_lim:
            action = "delay exceeds crew FDP — re-crew tail legs from reserves or cancel"
        else:
            action = "delay (crew legal)"

        assessments.append({
            "flight_id": fid,
            "pairing_id": p_id,
            "min_delay_hours": delay_hrs,
            "crew_fdp_after_delay": crew_fdp,
            "fdp_limit": fdp_lim,
            "action": action,
        })

    return {
        "disruption_type": "STATION_CLOSURE",
        "station": station,
        "window_utc": {"start": start_utc, "end": end_utc},
        "affected_flights": affected_flights,
        "per_flight_assessment": assessments,
        "note": "Delays are measured to reopen +30min turnaround. Where the extended duty exceeds RULE-FDP-01, tail legs need reserve re-crew or cancellation.",
    }


def simulate_flight_delay(
    aircraft: str,
    date: str,
    delay_hours: float,
    flight_no: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """
    Simulates rotational flight delay across an aircraft's daily duty chain.
    Calculates delayed duty period and checks for FDP breaches under RULE-FDP-01.
    """
    c = get_connection(conn)

    # 1. Fetch flights for this aircraft on the given date
    legs = c.execute(
        """
        SELECT flight_id, flight_no, dep_utc, arr_utc, block_hours
        FROM flights
        WHERE aircraft = ? AND date = ?
        ORDER BY dep_utc ASC
        """,
        (aircraft, date),
    ).fetchall()

    if not legs:
        raise ValueError(f"No flights found for aircraft {aircraft} on {date}")

    # 2. Fetch the rostered pairing
    p_row = c.execute(
        """
        SELECT pairing_id, report_utc, release_utc, flights_json
        FROM pairings
        WHERE aircraft = ? AND date = ?
        LIMIT 1
        """,
        (aircraft, date),
    ).fetchone()

    if not p_row:
        raise ValueError(f"No pairing found for aircraft {aircraft} on {date}")

    sectors = len(legs)
    fdp_lim = _fdp_limit(sectors)

    rep_dt = parse_utc(p_row["report_utc"])
    rel_dt = parse_utc(p_row["release_utc"])
    orig_fdp = round((rel_dt - rep_dt).total_seconds() / 3600.0, 2)

    # Delayed release shifts by delay_hours
    delayed_rel = rel_dt + timedelta(hours=delay_hours)
    delayed_fdp = round((delayed_rel - rep_dt).total_seconds() / 3600.0, 2)

    breach = delayed_fdp > fdp_lim
    last_leg_no = legs[-1]["flight_no"]

    if breach:
        breach_detail = (
            f"RULE-FDP-01: delayed duty runs {delayed_fdp}h vs {fdp_lim}h limit ({sectors} sectors) — "
            f"the rostered crew cannot legally complete {last_leg_no}."
        )
    else:
        breach_detail = f"Rostered crew remains legal under RULE-FDP-01 ({delayed_fdp}h <= {fdp_lim}h limit)."

    return {
        "disruption_type": "DELAY",
        "aircraft": aircraft,
        "date": date,
        "delay_hours": delay_hours,
        "pairing_id": p_row["pairing_id"],
        "affected_legs": [l["flight_id"] for l in legs],
        "scheduled_fdp": orig_fdp,
        "fdp_after_delay": delayed_fdp,
        "fdp_limit": fdp_lim,
        "breach": breach,
        "breach_detail": breach_detail,
    }


def simulate_cert_expiry(
    crew_id: str,
    pairing_id: str | None = None,
    reported_utc: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """
    Simulates discovery of an expired or lapsing qualification/medical/certification.
    Identifies the non-compliant duty and affected pairing.
    """
    c = get_connection(conn)

    # 1. Resolve pairing and duty date
    if not pairing_id:
        date_hint = reported_utc[:10] if reported_utc else "2026-09-18"
        p_match = c.execute(
            """
            SELECT p.pairing_id
            FROM pairings p
            JOIN pairing_crew pc ON pc.pairing_id = p.pairing_id
            WHERE pc.crew_id = ? AND p.date >= ?
            ORDER BY p.date ASC
            LIMIT 1
            """,
            (crew_id, date_hint),
        ).fetchone()
        if not p_match:
            raise ValueError(f"No pairing found for crew member {crew_id}")
        pairing_id = p_match["pairing_id"]

    p_row = c.execute(
        "SELECT date, flights_json, aircraft FROM pairings WHERE pairing_id = ? LIMIT 1",
        (pairing_id,),
    ).fetchone()

    duty_date = p_row["date"]
    f_list = json.loads(p_row["flights_json"])

    # 2. Identify expired cert
    cert_row = c.execute(
        """
        SELECT cert_type, valid_to
        FROM certifications
        WHERE crew_id = ? AND valid_to < ?
        ORDER BY valid_to DESC
        LIMIT 1
        """,
        (crew_id, duty_date),
    ).fetchone()

    lapsed_type = cert_row["cert_type"] if cert_row else "qualification"

    # 3. Resolve crew role and seats
    role_row = c.execute(
        "SELECT role FROM pairing_crew WHERE pairing_id = ? AND crew_id = ?",
        (pairing_id, crew_id),
    ).fetchone()
    crew_row = c.execute("SELECT rank FROM crew WHERE crew_id = ?", (crew_id,)).fetchone()

    role = role_row["role"] if role_row else (crew_row["rank"] if crew_row else "Crew")
    rank = crew_row["rank"] if crew_row else role

    seats = sum(
        c.execute("SELECT seats FROM flights WHERE flight_id = ?", (fid,)).fetchone()["seats"]
        for fid in f_list
    )

    return {
        "disruption_type": "CERT_EXPIRY",
        "crew_id": crew_id,
        "pairing_id": pairing_id,
        "reported_utc": reported_utc or f"{duty_date}T00:00:00Z",
        "role": role,
        "rank": rank,
        "date": duty_date,
        "lapsed_cert": lapsed_type,
        "illegal_assignment": {
            "crew_id": crew_id,
            "date": duty_date,
            "rule": "RULE-CERT-06",
        },
        "uncovered_flights": f_list,
        "passengers_at_risk": seats,
    }


def simulate_disruption(event: dict[str, Any], conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """
    Central dispatcher for all disruption simulation events.
    Accepts standardized event payloads and invokes the appropriate domain simulator.
    """
    c = get_connection(conn)
    etype = event.get("type") or event.get("disruption_type")
    if not etype:
        raise ValueError("Missing 'type' or 'disruption_type' in disruption event payload")

    etype_upper = etype.upper()

    if etype_upper == "SICK_CREW":
        return simulate_sick_crew(
            crew_id=event["crew_id"],
            pairing_id=event.get("pairing_id"),
            reported_utc=event.get("reported_utc"),
            conn=c,
        )

    elif etype_upper == "STATION_CLOSURE":
        win = event.get("window_utc") or {}
        start = win.get("start") or event.get("start_utc")
        end = win.get("end") or event.get("end_utc")
        return simulate_station_closure(
            station=event["station"],
            start_utc=start,
            end_utc=end,
            conn=c,
        )

    elif etype_upper in ("DELAY", "FLIGHT_DELAY"):
        return simulate_flight_delay(
            aircraft=event["aircraft"],
            date=event["date"],
            delay_hours=float(event.get("delay_hours", 0.0) or (event.get("delay_minutes", 0) / 60.0)),
            flight_no=event.get("flight_no"),
            conn=c,
        )

    elif etype_upper == "CERT_EXPIRY":
        return simulate_cert_expiry(
            crew_id=event["crew_id"],
            pairing_id=event.get("pairing_id"),
            reported_utc=event.get("reported_utc"),
            conn=c,
        )

    elif etype_upper == "MULTI_SICK":
        sub_events = event.get("events", [])
        sub_impacts = [
            simulate_sick_crew(
                crew_id=ev["crew_id"],
                pairing_id=ev.get("pairing_id"),
                reported_utc=ev.get("reported_utc"),
                conn=c,
            )
            for ev in sub_events
        ]
        total_flights = []
        seen_fids = set()
        for imp in sub_impacts:
            for fid in imp.get("uncovered_flights", []):
                if fid not in seen_fids:
                    seen_fids.add(fid)
                    total_flights.append(fid)

        total_seats = sum(
            c.execute("SELECT seats FROM flights WHERE flight_id = ?", (fid,)).fetchone()["seats"]
            for fid in total_flights
        )

        return {
            "disruption_type": "MULTI_SICK",
            "events": sub_events,
            "sub_impacts": sub_impacts,
            "uncovered_flights_total": total_flights,
            "passengers_at_risk_total": total_seats,
        }

    else:
        raise ValueError(f"Unsupported disruption type: {etype}")
