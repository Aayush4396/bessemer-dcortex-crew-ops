"""
src/rules/validators/duty.py
============================
RULE-DUTY-02: Maximum 60 duty hours in any 7 consecutive calendar days.
RULE-FLT-03: Maximum 100 flight (block) hours in any 28 consecutive calendar days.
"""

import sqlite3
from datetime import date

from ..config import DUTY_MAX_HOURS, DUTY_WINDOW_DAYS, FLT_MAX_HOURS, FLT_WINDOW_DAYS
from ..models import RuleResult
from ..time_utils import calculate_rolling_sum


def check_duty_7d(
    conn: sqlite3.Connection,
    crew_id: str,
    proposed_duty_hours: float,
    window_end_date: date,
    exclude_pairing: str | None = None,
    prior_cover_duties: list[tuple[date, float, float]] | None = None,
) -> RuleResult:
    """
    Evaluates cumulative duty hours over the 7-day calendar window ending on window_end_date.
    Breach occurs if (historical + planned + proposed) exceeds 60h.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active DB connection.
    crew_id : str
        Crew identifier, e.g. "C-1042".
    proposed_duty_hours : float
        Elapsed duty hours for the proposed duty day.
    window_end_date : date
        End of the 7-day calendar window (inclusive).
    exclude_pairing : str | None
        Existing pairing_id to exclude (e.g. when replacing or modifying an assignment).
    prior_cover_duties : list[tuple[date, float, float]] | None
        Accumulated prior days of a multi-day cover: (date, duty_hours, flight_hours).

    Returns
    -------
    RuleResult
        Evaluation verdict with breach magnitude and detailed explanation.
    """
    historical = calculate_rolling_sum(
        conn=conn,
        crew_id=crew_id,
        window_end=window_end_date,
        window_days=DUTY_WINDOW_DAYS,
        column="duty_hours",
        exclude_pairing=exclude_pairing,
        prior_cover_duties=prior_cover_duties,
    )
    total = round(historical + proposed_duty_hours, 4)
    breach = round(total - DUTY_MAX_HOURS, 4)

    if breach > 1e-6:
        mins = int(round(breach * 60))
        h, m = divmod(mins, 60)
        breach_str = f"{h}h{m:02d}m" if h else f"{m}m"
        return RuleResult(
            rule_id="RULE-DUTY-02",
            passed=False,
            detail=(
                f"RULE-DUTY-02: would exceed {DUTY_MAX_HOURS:g}h/7d by {breach_str} on {window_end_date} (total {total:.2f}h)"
            ),
            breach=breach,
        )

    remaining = round(DUTY_MAX_HOURS - total, 2)
    return RuleResult(
        rule_id="RULE-DUTY-02",
        passed=True,
        detail=f"{total:.2f}h / {DUTY_MAX_HOURS}h in 7d window ending {window_end_date} ({remaining:.2f}h remaining)",
    )


def check_flight_28d(
    conn: sqlite3.Connection,
    crew_id: str,
    proposed_flight_hours: float,
    window_end_date: date,
    exclude_pairing: str | None = None,
    prior_cover_duties: list[tuple[date, float, float]] | None = None,
) -> RuleResult:
    """
    Evaluates cumulative flight (block) hours over the 28-day calendar window ending on window_end_date.
    Breach occurs if (historical + planned + proposed) exceeds 100h.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active DB connection.
    crew_id : str
        Crew identifier, e.g. "C-1042".
    proposed_flight_hours : float
        Airborne flight (block) hours for the proposed duty day.
    window_end_date : date
        End of the 28-day calendar window (inclusive).
    exclude_pairing : str | None
        Existing pairing_id to exclude.
    prior_cover_duties : list[tuple[date, float, float]] | None
        Accumulated prior days of a multi-day cover: (date, duty_hours, flight_hours).

    Returns
    -------
    RuleResult
        Evaluation verdict with breach magnitude and detailed explanation.
    """
    historical = calculate_rolling_sum(
        conn=conn,
        crew_id=crew_id,
        window_end=window_end_date,
        window_days=FLT_WINDOW_DAYS,
        column="flight_hours",
        exclude_pairing=exclude_pairing,
        prior_cover_duties=prior_cover_duties,
    )
    total = round(historical + proposed_flight_hours, 4)
    breach = round(total - FLT_MAX_HOURS, 4)

    if breach > 1e-6:
        return RuleResult(
            rule_id="RULE-FLT-03",
            passed=False,
            detail=(
                f"Would accumulate {total:.2f}h flight hours in 28d window ending {window_end_date} "
                f"(limit {FLT_MAX_HOURS}h, breach +{breach:.2f}h)"
            ),
            breach=breach,
        )

    remaining = round(FLT_MAX_HOURS - total, 2)
    return RuleResult(
        rule_id="RULE-FLT-03",
        passed=True,
        detail=f"{total:.2f}h / {FLT_MAX_HOURS}h in 28d window ending {window_end_date} ({remaining:.2f}h remaining)",
    )
