"""
src/tier1/duty_queries.py
=========================
Deterministic queries for crew duty hour balances and regulatory headroom.
"""

import sqlite3
from datetime import date
from typing import Any

from src.rules.config import DUTY_MAX_HOURS, DUTY_WINDOW_DAYS, FLT_MAX_HOURS, FLT_WINDOW_DAYS
from src.rules.models import SNAPSHOT_DATE
from src.rules.time_utils import calculate_rolling_sum
from .connection import get_connection


def get_crew_duty_balance(
    crew_id: str,
    as_of_date: str = "2026-09-14",
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """
    Computes exact accrued rolling 7-day duty hours, 28-day flight hours,
    and remaining headroom against the 60h duty cap (RULE-DUTY-02) and 100h flight cap (RULE-FLT-03).
    Accurately combines historical records (<= 2026-09-14) AND planned roster pairings (> 2026-09-14).

    Parameters
    ----------
    crew_id : str
        e.g. "C-1042"
    as_of_date : str
        End of rolling window "YYYY-MM-DD", default "2026-09-14"

    Returns
    -------
    dict:
        "crew_id": str,
        "rank": str,
        "as_of_date": str,
        "duty_hours_7d": float,
        "headroom_hours": float,
        "flight_hours_28d": float,
        "flight_headroom_hours": float
    """
    c = get_connection(conn)

    # Crew metadata
    crew_row = c.execute(
        "SELECT rank, base, ratings FROM crew WHERE crew_id = ?",
        (crew_id,),
    ).fetchone()
    rank = crew_row["rank"] if crew_row else None

    end_dt = date.fromisoformat(as_of_date)

    # Calculate 7-day rolling duty hours and headroom
    duty_7d = round(
        calculate_rolling_sum(c, crew_id, end_dt, DUTY_WINDOW_DAYS, "duty_hours"),
        2,
    )
    duty_headroom = round(max(0.0, DUTY_MAX_HOURS - duty_7d), 2)

    # Calculate 28-day rolling flight hours and headroom
    flight_28d = round(
        calculate_rolling_sum(c, crew_id, end_dt, FLT_WINDOW_DAYS, "flight_hours"),
        2,
    )
    flight_headroom = round(max(0.0, FLT_MAX_HOURS - flight_28d), 2)

    return {
        "crew_id": crew_id,
        "rank": rank,
        "as_of_date": as_of_date,
        "duty_hours_7d": duty_7d,
        "headroom_hours": duty_headroom,
        "flight_hours_28d": flight_28d,
        "flight_headroom_hours": flight_headroom,
    }
