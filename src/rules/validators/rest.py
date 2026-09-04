"""
src/rules/validators/rest.py
============================
RULE-REST-04: Minimum 12 hours rest between duty release and next report.
Covers upstream rest requirements and downstream scheduled turnaround conflicts.
"""

import sqlite3
from datetime import timedelta

from ..config import REST_MIN_HOURS
from ..models import RuleResult
from ..time_utils import parse_utc


def check_rest(
    last_release_utc: str | None,
    next_report_utc: str,
    last_rest_ended: str | None = None,
    duty_date_str: str | None = None,
) -> RuleResult:
    """
    Checks minimum 12h rest before next_report_utc.

    - If last_release_utc is provided: rest_h = (next_report - last_release).
    - If only last_rest_ended is provided (from duty_clocks snapshot):
      last_rest_ended = last_duty_release + 12h.
      So last_duty_release = last_rest_ended - 12h.
      rest_h = (next_report - last_duty_release).
    - If neither is provided (no prior duty on record): passes.

    Parameters
    ----------
    last_release_utc : str | None
        ISO UTC timestamp of the most recent duty release.
    next_report_utc : str
        ISO UTC timestamp of the upcoming duty report.
    last_rest_ended : str | None
        ISO UTC timestamp from duty_clocks table (last_duty_release + 12h).
    duty_date_str : str | None
        Optional date string for benchmark detail string formatting.

    Returns
    -------
    RuleResult
        Evaluation verdict with breach magnitude and explanation.
    """
    release_dt = None
    if last_release_utc:
        release_dt = parse_utc(last_release_utc)
    elif last_rest_ended:
        release_dt = parse_utc(last_rest_ended) - timedelta(hours=REST_MIN_HOURS)

    if not release_dt:
        return RuleResult(
            rule_id="RULE-REST-04",
            passed=True,
            detail="No prior duty release on record — rest requirement satisfied",
        )

    report_dt = parse_utc(next_report_utc)
    rest_h = (report_dt - release_dt).total_seconds() / 3600.0
    breach = round(REST_MIN_HOURS - rest_h, 4)

    if breach > 1e-6:
        if duty_date_str:
            detail = f"RULE-REST-04: only {rest_h:.2f}h rest before COVER on {duty_date_str} (rest conflict)"
        else:
            detail = f"Only {rest_h:.2f}h rest between release and next report (minimum {REST_MIN_HOURS}h, short by {breach:.2f}h)"
        return RuleResult(
            rule_id="RULE-REST-04",
            passed=False,
            detail=detail,
            breach=breach,
        )

    return RuleResult(
        rule_id="RULE-REST-04",
        passed=True,
        detail=f"{rest_h:.2f}h rest before next report (minimum {REST_MIN_HOURS}h satisfied)",
    )


def check_downstream_rest(
    conn: sqlite3.Connection,
    crew_id: str,
    release_utc_str: str,
    proposed_report_utc_str: str | None = None,
    exclude_pairing: str | None = None,
) -> RuleResult | None:
    """
    Checks whether the crew member has >= 12h rest between this duty's release
    and their NEXT scheduled duty in the week.

    Catches sub-12h turnarounds and negative rest gaps (overlaps).

    Parameters
    ----------
    conn : sqlite3.Connection
        Active DB connection.
    crew_id : str
        Crew identifier, e.g. "C-1042".
    release_utc_str : str
        Proposed duty release UTC timestamp.
    proposed_report_utc_str : str | None
        Proposed report UTC timestamp to anchor downstream search.
    exclude_pairing : str | None
        Pairing being replaced (excluded from check).

    Returns
    -------
    RuleResult | None
        RuleResult with passed=False if downstream rest conflict exists, else None.
    """
    release_dt = parse_utc(release_utc_str)
    min_rep = proposed_report_utc_str or release_utc_str
    rows = conn.execute(
        """
        SELECT p.pairing_id, p.date, p.report_utc
        FROM pairings p
        JOIN pairing_crew pc ON pc.pairing_id = p.pairing_id
        WHERE pc.crew_id = ?
          AND p.report_utc >= ?
        ORDER BY p.report_utc ASC
        """,
        (crew_id, min_rep),
    ).fetchall()

    for r in rows:
        pid, d_str = r["pairing_id"], r["date"]
        if exclude_pairing and pid == exclude_pairing:
            continue
        next_rep = parse_utc(r["report_utc"])
        gap_h = (next_rep - release_dt).total_seconds() / 3600.0
        if gap_h < REST_MIN_HOURS - 1e-6:
            breach = round(REST_MIN_HOURS - gap_h, 4)
            return RuleResult(
                rule_id="RULE-REST-04",
                passed=False,
                detail=f"RULE-REST-04: only {gap_h:.2f}h rest before {pid} on {d_str} (downstream conflict)",
                breach=breach,
            )

    return None
