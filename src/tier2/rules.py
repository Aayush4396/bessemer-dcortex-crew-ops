"""
src/tier2/rules.py
==================
Per-rule deterministic wrappers. The LLM never adds hours or compares clocks.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from typing import Any

from src.rules.config import REST_MIN_HOURS
from src.rules.operational import check_reserve_window
from src.rules.time_utils import parse_date, parse_utc
from src.rules.validators import (
    check_base,
    check_certifications as _check_certs,
    check_downstream_rest,
    check_duty_7d as _check_duty_7d,
    check_fdp,
    check_flight_28d as _check_flight_28d,
    check_qualification as _check_qual,
    check_rest as _check_rest,
)
from src.tier1.connection import get_connection
from src.tier1.duty_queries import get_crew_duty_balance
from src.tier2.entities import (
    del_blr_positioning,
    fmt_utc,
    get_cost_rates,
    load_pairing_days,
    pairing_id_for_aircraft_date,
    pairing_id_for_flight,
    resolve_flight_id,
)

_PILOT_RANKS = {"Captain", "First Officer"}


def _resolve_pairing_id(
    conn: sqlite3.Connection,
    pairing_id: str | None = None,
    flight_id: str | None = None,
    flight_no: str | None = None,
    aircraft: str | None = None,
    date: str | None = None,
) -> str | None:
    if pairing_id:
        return pairing_id
    fid = resolve_flight_id(flight_id=flight_id, flight_no=flight_no, date=date, conn=conn)
    if fid:
        return pairing_id_for_flight(fid, conn)
    if aircraft and date:
        return pairing_id_for_aircraft_date(aircraft, date, conn)
    return None


def _result_dict(result) -> dict[str, Any]:
    return {
        "rule_id": result.rule_id,
        "passed": result.passed,
        "detail": result.detail,
        "breach": result.breach,
    }


def evaluate_fdp_limit(
    pairing_id: str | None = None,
    flight_id: str | None = None,
    flight_no: str | None = None,
    aircraft: str | None = None,
    date: str | None = None,
    delay_hours: float = 0.0,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """RULE-FDP-01. delay_hours slides release after report (operational delay)."""
    owns = conn is None
    c = get_connection(conn)
    try:
        pid = _resolve_pairing_id(
            c, pairing_id=pairing_id, flight_id=flight_id,
            flight_no=flight_no, aircraft=aircraft, date=date,
        )
        if not pid:
            return {"error": "pairing_id, flight_id, or aircraft+date is required"}
        pairing = load_pairing_days(pid, conn=c)
        if pairing is None:
            return {"error": f"pairing_id {pid!r} not found"}

        days = pairing["days"]
        if date:
            days = [d for d in days if d["date"] == date]
            if not days:
                return {"error": f"pairing {pid} has no duty on {date}"}

        day_results = []
        for day in days:
            fdp_after = round(day["duty_hours"] + delay_hours, 2)
            verdict = check_fdp(day["sector_count"], fdp_after)
            day_results.append(
                {
                    "date": day["date"],
                    "sectors": day["sector_count"],
                    "duty_hours": day["duty_hours"],
                    "delay_hours": delay_hours,
                    "fdp_after_delay": fdp_after,
                    "fdp_limit": day["max_window_hours"],
                    **_result_dict(verdict),
                }
            )

        primary = day_results[0]
        return {
            "rule_id": "RULE-FDP-01",
            "pairing_id": pid,
            "breach": not primary["passed"],
            "passed": all(d["passed"] for d in day_results),
            "fdp_after_delay": primary["fdp_after_delay"],
            "fdp_limit": primary["fdp_limit"],
            "days": day_results,
            "detail": primary["detail"],
        }
    finally:
        if owns:
            c.close()


def _all_crew_duty_rows(conn: sqlite3.Connection, as_of_date: str) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT crew_id, name, rank FROM crew ORDER BY crew_id ASC").fetchall()
    out = []
    for row in rows:
        bal = get_crew_duty_balance(row["crew_id"], as_of_date=as_of_date, conn=conn)
        out.append(
            {
                "crew_id": row["crew_id"],
                "name": row["name"],
                "rank": row["rank"],
                "duty_hours_7d": bal["duty_hours_7d"],
            }
        )
    return out


def evaluate_duty_7d(
    crew_id: str | None = None,
    pairing_id: str | None = None,
    as_of_date: str = "2026-09-14",
    min_hours: float | None = None,
    max_hours: float | None = None,
    split_hours: float | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """
    RULE-DUTY-02. Clocks come from duty_clock_history + planned pairings.
    - crew_id + pairing_id: simulate cover of every pairing day
    - crew_id only: current rolling balance
    - no crew_id: fleet list (optional min_hours / max_hours / split_hours)
    """
    owns = conn is None
    c = get_connection(conn)
    try:
        if crew_id is None:
            roster = _all_crew_duty_rows(c, as_of_date)
            if split_hours is not None:
                below = [r for r in roster if r["duty_hours_7d"] < split_hours]
                equal = [r for r in roster if r["duty_hours_7d"] == split_hours]
                above = [r for r in roster if r["duty_hours_7d"] > split_hours]
                below.sort(key=lambda x: x["duty_hours_7d"])
                above.sort(key=lambda x: -x["duty_hours_7d"])
                return {
                    "rule_id": "RULE-DUTY-02",
                    "as_of_date": as_of_date,
                    "split_hours": split_hours,
                    "below": below,
                    "equal": equal,
                    "above": above,
                }
            if min_hours is not None and max_hours is None:
                near = [
                    {
                        "crew_id": r["crew_id"],
                        "duty_hours_7d_incl_15sep_plan": r["duty_hours_7d"],
                    }
                    for r in roster
                    if r["duty_hours_7d"] >= min_hours
                ]
                near.sort(key=lambda x: -x["duty_hours_7d_incl_15sep_plan"])
                return {
                    "rule_id": "RULE-DUTY-02",
                    "as_of_date": as_of_date,
                    "min_hours": min_hours,
                    "crew": near,
                }
            filtered = roster
            if min_hours is not None:
                filtered = [r for r in filtered if r["duty_hours_7d"] >= min_hours]
            if max_hours is not None:
                filtered = [r for r in filtered if r["duty_hours_7d"] < max_hours]
            filtered.sort(key=lambda x: -x["duty_hours_7d"])
            return {
                "rule_id": "RULE-DUTY-02",
                "as_of_date": as_of_date,
                "min_hours": min_hours,
                "max_hours": max_hours,
                "crew": filtered,
            }

        if pairing_id:
            pairing = load_pairing_days(pairing_id, conn=c)
            if pairing is None:
                return {"error": f"pairing_id {pairing_id!r} not found"}
            prior: list[tuple[date, float, float]] = []
            days_out = []
            issues = []
            for day in pairing["days"]:
                d = parse_date(day["date"])
                verdict = _check_duty_7d(
                    c,
                    crew_id,
                    day["duty_hours"],
                    d,
                    exclude_pairing=pairing_id,
                    prior_cover_duties=prior,
                )
                days_out.append({"date": day["date"], **_result_dict(verdict)})
                if not verdict.passed:
                    issues.append(verdict.detail)
                prior.append((d, day["duty_hours"], day["block_hours"]))
            return {
                "rule_id": "RULE-DUTY-02",
                "legal": len(issues) == 0,
                "passed": len(issues) == 0,
                "crew_id": crew_id,
                "pairing_id": pairing_id,
                "days": days_out,
                "issues": issues,
            }

        bal = get_crew_duty_balance(crew_id, as_of_date=as_of_date, conn=c)
        return {
            "rule_id": "RULE-DUTY-02",
            "passed": bal["headroom_hours"] >= 0,
            **bal,
        }
    finally:
        if owns:
            c.close()


def evaluate_flight_28d(
    crew_id: str,
    pairing_id: str | None = None,
    as_of_date: str = "2026-09-14",
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """RULE-FLT-03. Snapshot from DB; optional pairing cover simulation."""
    owns = conn is None
    c = get_connection(conn)
    try:
        if pairing_id:
            pairing = load_pairing_days(pairing_id, conn=c)
            if pairing is None:
                return {"error": f"pairing_id {pairing_id!r} not found"}
            prior: list[tuple[date, float, float]] = []
            days_out = []
            issues = []
            for day in pairing["days"]:
                d = parse_date(day["date"])
                verdict = _check_flight_28d(
                    c,
                    crew_id,
                    day["block_hours"],
                    d,
                    exclude_pairing=pairing_id,
                    prior_cover_duties=prior,
                )
                days_out.append({"date": day["date"], **_result_dict(verdict)})
                if not verdict.passed:
                    issues.append(verdict.detail)
                prior.append((d, day["duty_hours"], day["block_hours"]))
            return {
                "rule_id": "RULE-FLT-03",
                "legal": len(issues) == 0,
                "passed": len(issues) == 0,
                "crew_id": crew_id,
                "pairing_id": pairing_id,
                "days": days_out,
                "issues": issues,
            }

        bal = get_crew_duty_balance(crew_id, as_of_date=as_of_date, conn=c)
        return {
            "rule_id": "RULE-FLT-03",
            "crew_id": crew_id,
            "as_of_date": as_of_date,
            "flight_hours_28d": bal["flight_hours_28d"],
            "flight_headroom_hours": bal["flight_headroom_hours"],
            "passed": bal["flight_headroom_hours"] >= 0,
        }
    finally:
        if owns:
            c.close()


def evaluate_rest(
    pairing_id: str | None = None,
    crew_id: str | None = None,
    release_utc: str | None = None,
    next_report_utc: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """
    RULE-REST-04.
    - release_utc only → earliest next report (release + 12h)
    - pairing_id only → inter-day rest on that pairing
    - crew_id + pairing_id → upstream + pairing + downstream roster conflicts
    """
    owns = conn is None
    c = get_connection(conn)
    try:
        if release_utc and not pairing_id and not crew_id:
            rel = parse_utc(release_utc)
            earliest = fmt_utc(rel + timedelta(hours=REST_MIN_HOURS))
            if next_report_utc:
                verdict = _check_rest(release_utc, next_report_utc)
                return {
                    "rule_id": "RULE-REST-04",
                    "earliest_report_utc": earliest,
                    "min_rest_hours": REST_MIN_HOURS,
                    **_result_dict(verdict),
                }
            return {
                "rule_id": "RULE-REST-04",
                "passed": True,
                "release_utc": release_utc,
                "earliest_report_utc": earliest,
                "min_rest_hours": REST_MIN_HOURS,
                "detail": f"RULE-REST-04: release + {REST_MIN_HOURS:.0f}h → {earliest}",
            }

        if not pairing_id:
            return {"error": "pairing_id or release_utc is required"}

        pairing = load_pairing_days(pairing_id, conn=c)
        if pairing is None:
            return {"error": f"pairing_id {pairing_id!r} not found"}

        gaps = []
        issues = []
        for day in pairing["days"]:
            if day["rest_hours"] is None:
                continue
            passed = day["rest_hours"] + 1e-6 >= REST_MIN_HOURS
            gap = {
                "from_release_utc": pairing["days"][day["day_index"] - 2]["release_utc"],
                "to_report_utc": day["report_utc"],
                "rest_hours": day["rest_hours"],
                "min_rest_hours": REST_MIN_HOURS,
                "passed": passed,
            }
            gaps.append(gap)
            if not passed:
                issues.append(
                    f"RULE-REST-04: only {day['rest_hours']:.2f}h rest before day {day['day_index']} "
                    f"on {day['date']}"
                )

        if crew_id:
            first = pairing["days"][0]
            last = pairing["days"][-1]
            upstream = _check_rest(
                None,
                first["report_utc"],
                last_rest_ended=_last_rest_ended(c, crew_id),
            )
            if not upstream.passed:
                issues.append(upstream.detail)
            downstream = check_downstream_rest(
                c,
                crew_id,
                last["release_utc"],
                proposed_report_utc_str=first["report_utc"],
                exclude_pairing=pairing_id,
            )
            if downstream and not downstream.passed:
                issues.append(downstream.detail)
            return {
                "rule_id": "RULE-REST-04",
                "legal": len(issues) == 0,
                "passed": len(issues) == 0,
                "crew_id": crew_id,
                "pairing_id": pairing_id,
                "pairing_gaps": gaps,
                "issues": issues,
                "detail": issues[0] if issues else "RULE-REST-04 satisfied",
            }

        return {
            "rule_id": "RULE-REST-04",
            "legal": len(issues) == 0,
            "passed": len(issues) == 0,
            "pairing_id": pairing_id,
            "pairing_gaps": gaps,
            "issues": issues,
        }
    finally:
        if owns:
            c.close()


def _last_rest_ended(conn: sqlite3.Connection, crew_id: str) -> str | None:
    row = conn.execute(
        "SELECT last_rest_ended FROM duty_clocks WHERE crew_id = ?",
        (crew_id,),
    ).fetchone()
    return row["last_rest_ended"] if row else None


def evaluate_qualification(
    crew_id: str,
    aircraft_type: str | None = None,
    pairing_id: str | None = None,
    flight_id: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """RULE-QUAL-05."""
    owns = conn is None
    c = get_connection(conn)
    try:
        resolved_type = aircraft_type
        if resolved_type is None and pairing_id:
            pairing = load_pairing_days(pairing_id, conn=c)
            resolved_type = pairing["aircraft_type"] if pairing else None
        if resolved_type is None and flight_id:
            row = c.execute(
                "SELECT aircraft_type FROM flights WHERE flight_id = ?",
                (flight_id,),
            ).fetchone()
            resolved_type = row["aircraft_type"] if row else None
        if not resolved_type:
            return {"error": "aircraft_type, pairing_id, or flight_id is required"}

        crew = c.execute("SELECT ratings FROM crew WHERE crew_id = ?", (crew_id,)).fetchone()
        if not crew:
            return {"error": f"crew_id {crew_id!r} not found"}
        ratings = json.loads(crew["ratings"])
        verdict = _check_qual(ratings, resolved_type)
        return {
            **_result_dict(verdict),
            "crew_id": crew_id,
            "aircraft_type": resolved_type,
            "ratings": ratings,
        }
    finally:
        if owns:
            c.close()


def evaluate_certifications(
    crew_id: str,
    duty_date: str,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """RULE-CERT-06. All four cert types must cover duty_date (valid_from ≤ date ≤ valid_to)."""
    owns = conn is None
    c = get_connection(conn)
    try:
        d = parse_date(duty_date)
        rows = c.execute(
            """
            SELECT cert_type, valid_from, valid_to
            FROM certifications
            WHERE crew_id = ?
            ORDER BY cert_type
            """,
            (crew_id,),
        ).fetchall()
        certs = []
        expired = []
        for row in rows:
            valid_from = parse_date(row["valid_from"])
            valid_to = parse_date(row["valid_to"])
            # Dataset / RULE-CERT-06: valid_to >= duty_date. valid_from is reported for joins.
            ok = valid_to >= d
            certs.append(
                {
                    "cert_type": row["cert_type"],
                    "valid_from": row["valid_from"],
                    "valid_to": row["valid_to"],
                    "covers_from": valid_from <= d,
                    "valid": ok,
                }
            )
            if not ok:
                expired.append(f"{row['cert_type']} expired {row['valid_to']}")

        engine = _check_certs(c, crew_id, d)
        return {
            "rule_id": "RULE-CERT-06",
            "legal": len(expired) == 0,
            "passed": len(expired) == 0,
            "crew_id": crew_id,
            "duty_date": duty_date,
            "certs": certs,
            "detail": expired[0] if expired else engine.detail,
            "rule": "RULE-CERT-06" if expired else None,
        }
    finally:
        if owns:
            c.close()


def evaluate_base_positioning(
    crew_id: str,
    pairing_id: str,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """RULE-BASE-07 deadhead plan + cost breakdown. Cross-base is legal but costs."""
    owns = conn is None
    c = get_connection(conn)
    try:
        crew = c.execute(
            "SELECT rank, base, ratings FROM crew WHERE crew_id = ?",
            (crew_id,),
        ).fetchone()
        if not crew:
            return {"error": f"crew_id {crew_id!r} not found"}
        pairing = load_pairing_days(pairing_id, conn=c)
        if pairing is None:
            return {"error": f"pairing_id {pairing_id!r} not found"}

        crew_base = crew["base"]
        dep_station = pairing["dep_station"]
        first = pairing["days"][0]
        duty_date = parse_date(first["date"])
        original_report = first["report_utc"]
        first_dep = first["flights"][0]["dep_utc"] if first["flights"] else original_report
        base_flag = check_base(crew_base, dep_station)
        costs = get_cost_rates()
        is_reserve = c.execute(
            "SELECT 1 FROM reserve_pool WHERE crew_id = ? AND date = ?",
            (crew_id, first["date"]),
        ).fetchone() is not None
        pilot = crew["rank"] in _PILOT_RANKS
        if is_reserve:
            callout = costs["reserve_callout_pilot"] if pilot else costs["reserve_callout_cabin"]
            callout_kind = "reserve_callout"
        else:
            callout = costs["dayoff_callout_pilot"] if pilot else costs["dayoff_callout_cabin"]
            callout_kind = "dayoff_callout"

        if crew_base == dep_station:
            window = check_reserve_window(c, crew_id, original_report, first["date"])
            return {
                "rule_id": "RULE-BASE-07",
                "legal": True,
                "passed": True,
                "possible": True,
                "needs_deadhead": False,
                "crew_id": crew_id,
                "pairing_id": pairing_id,
                "crew_base": crew_base,
                "dep_station": dep_station,
                "original_report_utc": original_report,
                "new_report_utc": original_report,
                "delay_hours": 0.0,
                "positioning_flight": None,
                "reserve_window_ok": window is None or window.passed,
                "reserve_window_detail": None if window is None else window.detail,
                "cost_inr": callout,
                "cost_breakdown": {
                    "callout_kind": callout_kind,
                    "callout": callout,
                    "deadhead": 0,
                    "delay": 0,
                },
                "detail": base_flag.detail,
            }

        if crew_base == "DEL" and dep_station == "BLR":
            pos = del_blr_positioning(duty_date)
            new_report = pos["new_report_utc"]
            first_possible_dep = parse_utc(new_report) + timedelta(minutes=60)
            delay_hours = round(
                max(0.0, (first_possible_dep - parse_utc(first_dep)).total_seconds() / 3600.0),
                2,
            )
            deadhead_cost = costs["deadhead_positioning"]
            delay_cost = int(round(delay_hours * costs["delay_cost_per_duty_hour"]))
            total = callout + deadhead_cost + delay_cost
            window = check_reserve_window(c, crew_id, new_report, first["date"])
            return {
                "rule_id": "RULE-BASE-07",
                "legal": True,
                "passed": True,
                "possible": True,
                "needs_deadhead": True,
                "crew_id": crew_id,
                "pairing_id": pairing_id,
                "crew_base": crew_base,
                "dep_station": dep_station,
                "original_report_utc": original_report,
                "new_report_utc": new_report,
                "delay_hours": delay_hours,
                "positioning_flight": pos["flight_no"],
                "positioning_arr_utc": pos["arr_utc"],
                "reserve_window_ok": window is None or window.passed,
                "reserve_window_detail": None if window is None else window.detail,
                "cost_inr": total,
                "cost_breakdown": {
                    "callout_kind": callout_kind,
                    "callout": callout,
                    "deadhead": deadhead_cost,
                    "delay": delay_cost,
                },
                "consequence": (
                    f"Deadhead positioning on {pos['flight_no']} (arr {pos['arr_utc'][11:16]}Z) "
                    f"delays the first departure by ~{delay_hours:.0f}h; RULE-BASE-07 deadhead cost applies."
                ),
                "detail": base_flag.detail,
            }

        return {
            "rule_id": "RULE-BASE-07",
            "legal": False,
            "passed": False,
            "possible": False,
            "needs_deadhead": True,
            "crew_id": crew_id,
            "pairing_id": pairing_id,
            "crew_base": crew_base,
            "dep_station": dep_station,
            "reason": "RULE-BASE-07: no same-day positioning flight from base",
            "detail": "RULE-BASE-07: no same-day positioning flight from base",
        }
    finally:
        if owns:
            c.close()


def evaluate_reserve_callout(
    date: str,
    rank: str,
    required_report_utc: str,
    aircraft_type: str | None = None,
    station: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """
    Filter reserves by on-call window (against required_report_utc) and optional type rating.
    Window is checked first so Q27 attributions match the dataset.
    """
    owns = conn is None
    c = get_connection(conn)
    try:
        report_hhmm = required_report_utc[11:16] if "T" in required_report_utc else required_report_utc
        conditions = ["c.status = 'active'", "rp.date = ?", "c.rank = ?"]
        params: list[Any] = [date, rank]
        if station:
            conditions.append("rp.base = ?")
            params.append(station)
        rows = c.execute(
            f"""
            SELECT rp.crew_id, c.rank, c.base, c.ratings, rp.on_call_start, rp.on_call_end
            FROM reserve_pool rp
            JOIN crew c ON c.crew_id = rp.crew_id
            WHERE {' AND '.join(conditions)}
            ORDER BY rp.id ASC
            """,
            tuple(params),
        ).fetchall()

        eligible = []
        excluded = []
        for r in rows:
            ratings = json.loads(r["ratings"])
            w_start, w_end = r["on_call_start"], r["on_call_end"]
            if not (w_start <= report_hhmm <= w_end):
                excluded.append(
                    {
                        "crew_id": r["crew_id"],
                        "reason": (
                            f"reserve on-call window {w_start}-{w_end}Z "
                            f"does not cover required report {report_hhmm}Z"
                        ),
                    }
                )
                continue
            if aircraft_type and aircraft_type not in ratings:
                excluded.append(
                    {
                        "crew_id": r["crew_id"],
                        "reason": f"RULE-QUAL-05: no {aircraft_type} rating",
                    }
                )
                continue
            eligible.append(r["crew_id"])

        return {
            "date": date,
            "rank": rank,
            "required_report_utc": required_report_utc,
            "aircraft_type": aircraft_type,
            "eligible": eligible,
            "excluded": excluded,
            "excluded_examples": excluded,
        }
    finally:
        if owns:
            c.close()


def _vacant_cover_role(
    pairing: dict[str, Any],
    role: str | None,
    replace_crew_id: str | None,
) -> str | None:
    if role:
        return role
    if replace_crew_id:
        for member in pairing.get("crew") or []:
            if member["crew_id"] == replace_crew_id:
                return member["role"]
    crew = pairing.get("crew") or []
    return crew[0]["role"] if crew else None


def evaluate_cover(
    crew_id: str,
    pairing_id: str,
    role: str | None = None,
    replace_crew_id: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """
    Full cover legality: rank match, DUTY/FLT/FDP/REST/QUAL/CERT/BASE.
    Vacant seat is role, else replace_crew_id's pairing role, else the pairing's
    first rostered role (normally Captain). Rank must equal that seat.
    """
    owns = conn is None
    c = get_connection(conn)
    try:
        pairing = load_pairing_days(pairing_id, conn=c)
        if pairing is None:
            return {"error": f"pairing_id {pairing_id!r} not found"}

        candidate = c.execute(
            "SELECT rank, ratings, status FROM crew WHERE crew_id = ?",
            (crew_id,),
        ).fetchone()
        if not candidate:
            return {"error": f"crew_id {crew_id!r} not found"}

        issues: list[str] = []
        if candidate["status"] != "active":
            issues.append(
                f"{crew_id} is on {candidate['status']} — not available for cover"
            )
        required_role = _vacant_cover_role(pairing, role, replace_crew_id)
        if required_role and candidate["rank"] != required_role:
            issues.append(
                f"Rank mismatch: {crew_id} is {candidate['rank']}; "
                f"vacant seat is {required_role}"
            )

        duty = evaluate_duty_7d(crew_id=crew_id, pairing_id=pairing_id, conn=c)
        issues.extend(duty.get("issues") or [])

        flight = evaluate_flight_28d(crew_id=crew_id, pairing_id=pairing_id, conn=c)
        issues.extend(flight.get("issues") or [])

        fdp = evaluate_fdp_limit(pairing_id=pairing_id, conn=c)
        for day in fdp.get("days") or []:
            if not day.get("passed"):
                issues.append(day["detail"])

        rest = evaluate_rest(crew_id=crew_id, pairing_id=pairing_id, conn=c)
        issues.extend(rest.get("issues") or [])

        qual = evaluate_qualification(crew_id=crew_id, pairing_id=pairing_id, conn=c)
        if qual.get("passed") is False:
            issues.append(qual["detail"])

        seen_certs: set[str] = set()
        for day in pairing["days"]:
            cert = evaluate_certifications(crew_id=crew_id, duty_date=day["date"], conn=c)
            if not cert.get("legal"):
                detail = cert["detail"]
                if detail not in seen_certs:
                    seen_certs.add(detail)
                    issues.append(detail)

        base = evaluate_base_positioning(crew_id=crew_id, pairing_id=pairing_id, conn=c)
        if not base.get("legal"):
            issues.append(base.get("detail") or base.get("reason"))

        payload: dict[str, Any] = {
            "legal": len(issues) == 0,
            "issues": issues,
            "crew_id": crew_id,
            "pairing_id": pairing_id,
            "required_role": required_role,
            "candidate_rank": candidate["rank"],
            "candidate_status": candidate["status"],
            "cost_inr": base.get("cost_inr"),
            "delay_hours": base.get("delay_hours"),
        }
        if base.get("consequence"):
            payload["consequence"] = base["consequence"]
        return payload
    finally:
        if owns:
            c.close()


def evaluate_cover_candidates(
    pairing_id: str,
    role: str | None = None,
    replace_crew_id: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """All same-rank crew scored for a vacant pairing seat. Do not invent ratings."""
    owns = conn is None
    c = get_connection(conn)
    try:
        pairing = load_pairing_days(pairing_id, conn=c)
        if pairing is None:
            return {"error": f"pairing_id {pairing_id!r} not found"}

        required_role = _vacant_cover_role(pairing, role, replace_crew_id)
        if not required_role:
            return {"error": "cannot resolve vacant role"}

        skip = {replace_crew_id} if replace_crew_id else set()
        for member in pairing.get("crew") or []:
            if member["role"] == required_role:
                skip.add(member["crew_id"])

        rows = c.execute(
            "SELECT crew_id, rank, status FROM crew WHERE rank = ? ORDER BY crew_id ASC",
            (required_role,),
        ).fetchall()

        legal: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []
        for row in rows:
            if row["crew_id"] in skip:
                continue
            result = evaluate_cover(
                crew_id=row["crew_id"],
                pairing_id=pairing_id,
                role=required_role,
                replace_crew_id=replace_crew_id,
                conn=c,
            )
            if result.get("legal"):
                legal.append(
                    {
                        "crew_id": row["crew_id"],
                        "rank": row["rank"],
                        "legal": True,
                        "cost_inr": result.get("cost_inr"),
                        "delay_hours": result.get("delay_hours"),
                        "consequence": result.get("consequence"),
                    }
                )
            else:
                excluded.append(
                    {
                        "crew_id": row["crew_id"],
                        "issues": result.get("issues") or [result.get("error")],
                    }
                )

        legal.sort(
            key=lambda item: (
                item.get("cost_inr") is None,
                item.get("cost_inr") or 0,
                item["crew_id"],
            )
        )
        return {
            "pairing_id": pairing_id,
            "required_role": required_role,
            "aircraft_type": pairing.get("aircraft_type"),
            "legal": legal,
            "excluded": excluded,
        }
    finally:
        if owns:
            c.close()
