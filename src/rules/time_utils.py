"""
src/rules/time_utils.py
=======================
Temporal arithmetic, date parsing, duty period calculation, and calendar-day
rolling window aggregations across duty_clock_history and planned pairings.
"""

import json
import sqlite3
from datetime import datetime, date, timedelta

from .models import SNAPSHOT_DATE


def parse_utc(s: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp string, e.g. '2026-09-15T02:00:00Z'."""
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


def parse_date(s: str) -> date:
    """Parse an ISO date string, e.g. '2026-09-15'."""
    return date.fromisoformat(s[:10])


def calculate_duty_period(first_dep_utc: str, last_arr_utc: str) -> tuple[str, str, float]:
    """
    Calculate report_utc, release_utc, and FDP hours according to rules.json:
    - Report = first departure minus 60 minutes
    - Release = last arrival plus 30 minutes
    - FDP hours = (release - report) in hours

    Returns
    -------
    tuple of (report_utc_str, release_utc_str, fdp_hours)
    """
    dep_dt = parse_utc(first_dep_utc)
    arr_dt = parse_utc(last_arr_utc)

    report_dt = dep_dt - timedelta(minutes=60)
    release_dt = arr_dt + timedelta(minutes=30)

    report_str = report_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    release_str = release_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    fdp_hours = (release_dt - report_dt).total_seconds() / 3600.0

    return report_str, release_str, round(fdp_hours, 4)


def calculate_rolling_sum(
    conn: sqlite3.Connection,
    crew_id: str,
    window_end: date,
    window_days: int,
    column: str,  # "duty_hours" | "flight_hours"
    exclude_pairing: str | None = None,
    prior_cover_duties: list[tuple[date, float, float]] | None = None,
) -> float:
    """
    Sum 'column' for crew_id over the calendar-day window:
        [window_end - (window_days - 1), window_end]  inclusive.

    Accurately combines:
    1. Historical records from duty_clock_history (dates <= 2026-09-14)
    2. Existing planned pairings from pairings table (dates > 2026-09-14 up to window_end)
    3. Any prior days of a multi-day cover pairing currently being evaluated
    """
    window_start = window_end - timedelta(days=window_days - 1)

    # 1. Historical records from duty_clock_history (<= snapshot date)
    h_end = min(window_end, SNAPSHOT_DATE)
    hist_val = 0.0
    if window_start <= h_end:
        r = conn.execute(
            f"""
            SELECT COALESCE(SUM({column}), 0.0)
            FROM duty_clock_history
            WHERE crew_id = ?
              AND date >= ?
              AND date <= ?
            """,
            (crew_id, window_start.isoformat(), h_end.isoformat()),
        ).fetchone()
        hist_val = float(r[0])

    # 2. Existing planned duties from pairings table (> snapshot date up to window_end)
    planned_val = 0.0
    if window_end > SNAPSHOT_DATE:
        rows = conn.execute(
            """
            SELECT p.pairing_id, p.date, p.report_utc, p.release_utc, p.flights_json
            FROM pairings p
            JOIN pairing_crew pc ON pc.pairing_id = p.pairing_id
            WHERE pc.crew_id = ?
              AND p.date >= '2026-09-15'
              AND p.date <= ?
            """,
            (crew_id, window_end.isoformat()),
        ).fetchall()
        for row in rows:
            if exclude_pairing and row["pairing_id"] == exclude_pairing:
                continue
            if column == "duty_hours":
                rep = parse_utc(row["report_utc"])
                rel = parse_utc(row["release_utc"])
                planned_val += (rel - rep).total_seconds() / 3600.0
            else:
                f_ids = json.loads(row["flights_json"])
                for fid in f_ids:
                    b_row = conn.execute(
                        "SELECT block_hours FROM flights WHERE flight_id = ?",
                        (fid,),
                    ).fetchone()
                    if b_row:
                        planned_val += float(b_row[0])

    # 3. Prior days of multi-day assignment being simulated
    cover_val = 0.0
    if prior_cover_duties:
        for (d_date, d_hours, f_hours) in prior_cover_duties:
            if window_start <= d_date <= window_end:
                cover_val += d_hours if column == "duty_hours" else f_hours

    return round(hist_val + planned_val + cover_val, 6)
