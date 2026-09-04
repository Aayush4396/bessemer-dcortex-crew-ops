"""
src/rules/operational.py
========================
Operational feasibility and assignment constraints:
- Schedule overlap / double-booking detection against published roster.
- Reserve standby on-call time window validation.
"""

import sqlite3

from .models import RuleResult


def check_schedule_overlap(
    conn: sqlite3.Connection,
    crew_id: str,
    report_utc_str: str,
    release_utc_str: str,
    exclude_pairing: str | None = None,
) -> RuleResult | None:
    """
    Checks whether the proposed duty overlaps with an already-assigned pairing in the roster.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active DB connection.
    crew_id : str
        Crew identifier, e.g. "C-1042".
    report_utc_str : str
        Proposed duty report UTC timestamp.
    release_utc_str : str
        Proposed duty release UTC timestamp.
    exclude_pairing : str | None
        Pairing being modified/replaced (ignored in overlap check).

    Returns
    -------
    RuleResult | None
        RuleResult with passed=False if overlap found, else None.
    """
    rows = conn.execute(
        """
        SELECT p.pairing_id, p.date, p.report_utc, p.release_utc
        FROM pairings p
        JOIN pairing_crew pc ON pc.pairing_id = p.pairing_id
        WHERE pc.crew_id = ?
          AND p.report_utc < ?
          AND p.release_utc > ?
        ORDER BY p.report_utc ASC
        """,
        (crew_id, release_utc_str, report_utc_str),
    ).fetchall()

    for r in rows:
        pid, d_str = r["pairing_id"], r["date"]
        if exclude_pairing and pid == exclude_pairing:
            continue
        if r["report_utc"] <= report_utc_str:
            detail = f"double-booked: {pid} overlaps COVER on {d_str}"
        else:
            detail = f"double-booked: COVER overlaps {pid} on {d_str}"
        return RuleResult(
            rule_id="DOUBLE_BOOKED",
            passed=False,
            detail=detail,
            breach=1.0,
        )

    return None


def check_reserve_window(
    conn: sqlite3.Connection,
    crew_id: str,
    report_utc_str: str,
    duty_date_str: str,
) -> RuleResult | None:
    """
    If crew_id is on reserve standby on duty_date_str, verifies that the required
    report time falls within their scheduled on-call window.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active DB connection.
    crew_id : str
        Crew identifier.
    report_utc_str : str
        Proposed report UTC timestamp.
    duty_date_str : str
        Date of the duty assignment ("YYYY-MM-DD").

    Returns
    -------
    RuleResult | None
        RuleResult with passed=False if outside standby window, else None.
    """
    row = conn.execute(
        "SELECT on_call_start, on_call_end FROM reserve_pool WHERE crew_id = ? AND date = ?",
        (crew_id, duty_date_str),
    ).fetchone()
    if not row:
        return None  # Crew member is not on reserve standby on this date

    rep_time = report_utc_str[11:16]  # "HH:MM"
    w_start = row["on_call_start"]
    w_end = row["on_call_end"]

    if not (w_start <= rep_time <= w_end):
        return RuleResult(
            rule_id="RESERVE_WINDOW",
            passed=False,
            detail=f"reserve on-call window {w_start}-{w_end}Z does not cover required report {rep_time}Z",
            breach=1.0,
        )

    return None
