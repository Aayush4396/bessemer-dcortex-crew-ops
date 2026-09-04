"""
src/rules/engine.py
===================
Deterministic legality pipeline orchestrator for dCortex Crew Ops Advisor.

THE SINGLE SOURCE OF TRUTH for crew legality.
- Zero LLM involvement
- Zero approximation — exact arithmetic only
- All 7 rule limits read from rules.json via config module (never hardcoded)
- Clean domain-driven architecture delegating to dedicated validator modules

Public API
----------
    check_crew_legality(crew_id, proposed_assignment, conn, ...) -> dict
    check_crew_legality_for_pairing(crew_id, pairing_id, conn, ...) -> dict
"""

import json
import sqlite3
from datetime import date

from .models import ALL_RULE_IDS, SNAPSHOT_DATE, LegalityReport, RuleResult
from .operational import check_reserve_window, check_schedule_overlap
from .time_utils import calculate_duty_period, calculate_rolling_sum, parse_date, parse_utc
from .validators import (
    check_base,
    check_certifications,
    check_downstream_rest,
    check_duty_7d,
    check_fdp,
    check_flight_28d,
    check_qualification,
    check_rest,
)

# Re-export core domain entities so callers have direct canonical access
__all__ = [
    "check_crew_legality",
    "check_crew_legality_for_pairing",
    "RuleResult",
    "LegalityReport",
    "ALL_RULE_IDS",
    "SNAPSHOT_DATE",
    "check_fdp",
    "check_duty_7d",
    "check_flight_28d",
    "check_rest",
    "check_downstream_rest",
    "check_qualification",
    "check_certifications",
    "check_base",
    "check_schedule_overlap",
    "check_reserve_window",
    "parse_utc",
    "parse_date",
    "calculate_duty_period",
    "calculate_rolling_sum",
]


def check_crew_legality(
    crew_id: str,
    proposed_assignment: dict,
    conn: sqlite3.Connection,
    exclude_pairing: str | None = None,
    prior_cover_duties: list[tuple[date, float, float]] | None = None,
    prior_release_utc: str | None = None,
    check_overlap: bool = True,
    check_downstream: bool = True,
    check_reserve: bool = False,
) -> dict:
    """
    Run all 7 CAR legality rules plus operational constraints against a proposed assignment.

    Parameters
    ----------
    crew_id : str
        e.g. "C-1042"
    proposed_assignment : dict
        {
            "pairing_id":    str,       # e.g. "P-2291"
            "duty_date":     str,       # "YYYY-MM-DD"
            "report_utc":    str,       # "2026-09-15T02:00:00Z"
            "release_utc":   str,       # "2026-09-15T12:45:00Z"
            "sectors":       int,       # number of flight legs in this duty day
            "block_hours":   float,     # total airborne hours this duty day
            "aircraft_type": str,       # "A320" | "ATR72"
            "dep_station":   str,       # departure station for base check
        }
    conn : sqlite3.Connection
        Active DB connection.
    exclude_pairing : str | None
        Existing pairing_id to exclude (when modifying or swapping an assignment).
    prior_cover_duties : list[tuple[date, float, float]] | None
        Accumulated prior days of a multi-day cover: (date, duty_hours, flight_hours).
    prior_release_utc : str | None
        Release timestamp of prior day when chaining multi-day duty evaluations.
    check_overlap : bool
        Whether to check for double-booking against published roster (default True).
    check_downstream : bool
        Whether to verify >=12h rest before next scheduled duty (default True).
    check_reserve : bool
        Whether to check reserve on-call standby window (default False).

    Returns
    -------
    dict
        {
            "is_legal": bool,
            "rules_checked": ["RULE-FDP-01", ...],
            "violations": [{"rule": "...", "detail": "..."}],
            "advisories": [{"rule": "...", "detail": "..."}],
            "_rule_results": [RuleResult, ...],
        }
    """
    # ── Fetch crew record ────────────────────────────────────────────────────
    crew_row = conn.execute(
        "SELECT rank, base, ratings, status FROM crew WHERE crew_id = ?",
        (crew_id,),
    ).fetchone()
    if not crew_row:
        return {
            "is_legal": False,
            "rules_checked": [],
            "violations": [{"rule": "LOOKUP", "detail": f"crew_id {crew_id!r} not found in DB"}],
            "advisories": [],
            "_rule_results": [],
        }

    # Availability guard: status must be 'active'
    if crew_row["status"] != "active":
        return {
            "is_legal": False,
            "rules_checked": ALL_RULE_IDS,
            "violations": [{"rule": "STATUS", "detail": f"Crew member is on {crew_row['status']} (not active)"}],
            "advisories": [],
            "_rule_results": [],
        }

    crew_base = crew_row["base"]
    crew_ratings = json.loads(crew_row["ratings"])

    # ── Parse proposal fields ────────────────────────────────────────────────
    duty_date_str = proposed_assignment["duty_date"]
    duty_date = parse_date(duty_date_str)
    report_utc = proposed_assignment["report_utc"]
    release_utc = proposed_assignment["release_utc"]
    sectors = proposed_assignment["sectors"]
    block_hours = proposed_assignment["block_hours"]
    aircraft_type = proposed_assignment["aircraft_type"]
    dep_station = proposed_assignment["dep_station"]
    pairing_id = proposed_assignment.get("pairing_id")
    effective_exclude = exclude_pairing or pairing_id

    # ── Determine upstream release for rest check ────────────────────────────
    last_release = prior_release_utc
    last_rest_ended = None
    is_cover_upstream_conflict = False

    if not last_release:
        # Check pairings table for any duty completed by crew prior to or overlapping proposed report
        prior_p_row = conn.execute(
            """
            SELECT p.pairing_id, p.date, p.report_utc, p.release_utc
            FROM pairings p
            JOIN pairing_crew pc ON pc.pairing_id = p.pairing_id
            WHERE pc.crew_id = ?
              AND p.pairing_id != ?
              AND p.report_utc <= ?
            ORDER BY p.release_utc DESC
            LIMIT 1
            """,
            (crew_id, effective_exclude or "", report_utc),
        ).fetchone()

        if prior_p_row:
            last_release = prior_p_row["release_utc"]
            is_cover_upstream_conflict = True
        else:
            # Fallback to duty_clocks snapshot
            clock_row = conn.execute(
                "SELECT last_rest_ended FROM duty_clocks WHERE crew_id = ?",
                (crew_id,),
            ).fetchone()
            last_rest_ended = clock_row["last_rest_ended"] if clock_row else None

    # FDP = (release - report) in hours
    fdp_hours = (parse_utc(release_utc) - parse_utc(report_utc)).total_seconds() / 3600.0

    # ── Run all 7 rules — never short-circuit ────────────────────────────────
    rest_date_str = duty_date_str if is_cover_upstream_conflict else None
    results: list[RuleResult] = [
        check_fdp(sectors, fdp_hours),
        check_duty_7d(
            conn,
            crew_id,
            fdp_hours,
            duty_date,
            exclude_pairing=effective_exclude,
            prior_cover_duties=prior_cover_duties,
        ),
        check_flight_28d(
            conn,
            crew_id,
            block_hours,
            duty_date,
            exclude_pairing=effective_exclude,
            prior_cover_duties=prior_cover_duties,
        ),
        check_rest(last_release, report_utc, last_rest_ended=last_rest_ended, duty_date_str=rest_date_str),
        check_qualification(crew_ratings, aircraft_type),
        check_certifications(conn, crew_id, duty_date),
        check_base(crew_base, dep_station),
    ]

    # ── Operational constraint 1: Schedule overlap / double-booking ──────────
    if check_overlap:
        overlap_res = check_schedule_overlap(
            conn, crew_id, report_utc, release_utc, exclude_pairing=effective_exclude
        )
        if overlap_res and not overlap_res.passed:
            results.append(overlap_res)

    # ── Operational constraint 2: Downstream rest conflict ──────────────────
    if check_downstream:
        downstream_res = check_downstream_rest(
            conn, crew_id, release_utc, proposed_report_utc_str=report_utc, exclude_pairing=effective_exclude
        )
        if downstream_res and not downstream_res.passed:
            results.append(downstream_res)

    # ── Operational constraint 3: Reserve on-call window ────────────────────
    if check_reserve:
        reserve_res = check_reserve_window(conn, crew_id, report_utc, duty_date_str)
        if reserve_res and not reserve_res.passed:
            results.append(reserve_res)

    # ── RULE-BASE-07 is a cost flag, not a disqualifier ──────────────────────
    disqualifying = [
        r for r in results
        if not r.passed and not (r.rule_id == "RULE-BASE-07" and r.breach == 0.0)
    ]
    advisories = [
        {"rule": r.rule_id, "detail": r.detail}
        for r in results
        if not r.passed and (r.rule_id == "RULE-BASE-07" and r.breach == 0.0)
    ]

    is_legal = len(disqualifying) == 0
    violations = [
        {"rule": r.rule_id, "detail": r.detail}
        for r in disqualifying
    ]

    return {
        "is_legal": is_legal,
        "rules_checked": ALL_RULE_IDS,
        "violations": violations,
        "advisories": advisories,
        "_rule_results": results,  # kept for explainability trace; underscore = internal
    }


def check_crew_legality_for_pairing(
    crew_id: str,
    pairing_id: str,
    conn: sqlite3.Connection,
    duty_date: str | None = None,
    exclude_pairing: str | None = None,
    check_overlap: bool = True,
    check_downstream: bool = True,
    check_reserve: bool = False,
) -> dict:
    """
    Evaluates legality for a pairing in the DB.
    If duty_date is None, sequentially evaluates all days of the pairing,
    accumulating duty hours and rest checks across days (e.g. Day 1 -> Day 2).
    """
    query = (
        "SELECT date, report_utc, release_utc, flights_json, aircraft "
        "FROM pairings WHERE pairing_id = ? ORDER BY date ASC"
    )
    rows = conn.execute(query, (pairing_id,)).fetchall()
    if not rows:
        return {
            "is_legal": False,
            "rules_checked": [],
            "violations": [{"rule": "LOOKUP", "detail": f"Pairing {pairing_id} not found in DB"}],
            "advisories": [],
        }

    # Fetch crew base to accurately handle multi-day overnight base positioning
    crew_row = conn.execute("SELECT base FROM crew WHERE crew_id = ?", (crew_id,)).fetchone()
    crew_base = crew_row["base"] if crew_row else ""

    # If duty_date specified, filter to days <= duty_date
    if duty_date:
        target_rows = [r for r in rows if r["date"] == duty_date]
        if not target_rows:
            return {
                "is_legal": False,
                "rules_checked": [],
                "violations": [{"rule": "LOOKUP", "detail": f"Pairing {pairing_id} on {duty_date} not found"}],
                "advisories": [],
            }
        days_to_check = [r for r in rows if r["date"] <= duty_date]
    else:
        days_to_check = rows

    all_rule_results = []
    all_violations = []
    all_advisories = []
    prior_cover = []
    prior_release = None
    effective_exclude = exclude_pairing or pairing_id

    for idx, r in enumerate(days_to_check):
        d_str = r["date"]
        d_date = parse_date(d_str)
        flights_list = json.loads(r["flights_json"])
        is_first_day = (idx == 0)

        # Aircraft type and dep station from first flight
        f_row = conn.execute(
            "SELECT aircraft_type, dep_station FROM flights WHERE flight_id = ?",
            (flights_list[0],),
        ).fetchone()

        total_block = sum(
            conn.execute("SELECT block_hours FROM flights WHERE flight_id = ?", (fid,)).fetchone()[0]
            for fid in flights_list
        )

        # On Day 2+ of a multi-day pairing, crew is already positioned at overnight station
        assigned_dep_station = f_row["dep_station"] if is_first_day else crew_base

        proposed = {
            "pairing_id": pairing_id,
            "duty_date": d_str,
            "report_utc": r["report_utc"],
            "release_utc": r["release_utc"],
            "sectors": len(flights_list),
            "block_hours": total_block,
            "aircraft_type": f_row["aircraft_type"],
            "dep_station": assigned_dep_station,
        }

        # Run legality for this day
        rep = check_crew_legality(
            crew_id=crew_id,
            proposed_assignment=proposed,
            conn=conn,
            exclude_pairing=effective_exclude,
            prior_cover_duties=prior_cover,
            prior_release_utc=prior_release,
            check_overlap=check_overlap,
            check_downstream=check_downstream,
            check_reserve=(check_reserve and is_first_day),
        )

        fdp_h = (parse_utc(r["release_utc"]) - parse_utc(r["report_utc"])).total_seconds() / 3600.0
        prior_cover.append((d_date, fdp_h, total_block))
        prior_release = r["release_utc"]

        if duty_date and d_str != duty_date:
            continue

        all_rule_results.extend(rep.get("_rule_results", []))
        if not rep["is_legal"]:
            for v in rep["violations"]:
                all_violations.append({"date": d_str, "rule": v["rule"], "detail": f"[{d_str}] {v['detail']}"})
        if rep.get("advisories"):
            for a in rep["advisories"]:
                all_advisories.append({"date": d_str, "rule": a["rule"], "detail": f"[{d_str}] {a['detail']}"})

    is_legal = len(all_violations) == 0
    return {
        "is_legal": is_legal,
        "rules_checked": ALL_RULE_IDS,
        "violations": all_violations,
        "advisories": all_advisories,
        "_rule_results": all_rule_results,
    }
