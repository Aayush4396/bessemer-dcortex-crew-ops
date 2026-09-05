"""
src/agent/tools.py
==================
LangChain tool wrappers for Tier 1 query functions and Tier 2/3 resolver functions.
"""

from datetime import date, datetime
from typing import Any

from langchain_core.tools import tool

from src.tier1 import (
    get_flights,
    get_departures,
    get_arrivals,
    get_flight_schedule_stats,
    get_crew_profile,
    get_reserves_at_station,
    get_pairing_roster,
    get_crew_duty_balance,
    get_expiring_certifications,
    get_crew_risk_signal,
    query_operations as _query_operations,
)
from src.resolver import (
    check_cover as _check_cover,
    cover_options as _cover_options,
    expand_sick_call as _expand_sick_call,
    expand_station_closure as _expand_station_closure,
    expand_delay as _expand_delay,
)
from src.resolver.cover import win_sum as _win_sum
from src.resolver.data import load_all, pairings, crew, FBY


@tool
def query_flight_schedule(
    date: str | None = None,
    origin: str | None = None,
    destination: str | None = None,
    flight_no: str | None = None,
    aircraft: str | None = None,
    aircraft_type: str | None = None,
    distinct_destinations: bool = False,
    count_only: bool = False,
) -> Any:
    """
    Lookup scheduled flights, route legs, operating tail numbers, aircraft types, seat capacities,
    or count of flights.
    Parameters:
    - date: ISO date string "YYYY-MM-DD" (e.g. "2026-09-15")
    - origin: 3-letter IATA station code (e.g. "BLR", "DEL", "BOM")
    - destination: 3-letter IATA station code (e.g. "BOM", "DEL", "CCU")
    - flight_no: Flight number (e.g. "DX412")
    - aircraft: Tail registration (e.g. "VT-DXA", "VT-DXB", "VT-DXC")
    - aircraft_type: Fleet type ("A320" or "ATR72")
    - distinct_destinations: If True with origin, returns list of unique destination stations
    - count_only: If True, returns total flight count as integer
    """
    return get_flights(
        date=date,
        origin=origin,
        destination=destination,
        flight_no=flight_no,
        aircraft=aircraft,
        aircraft_type=aircraft_type,
        distinct_destinations=distinct_destinations,
        count_only=count_only,
    )


@tool
def query_station_departures(
    station: str,
    date: str,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[str]:
    """
    List flight numbers scheduled to depart an airport station on a given date,
    optionally within a departure time window (HH:MM in UTC).
    Parameters:
    - station: 3-letter IATA station code (e.g. "DEL", "BLR")
    - date: "YYYY-MM-DD" (e.g. "2026-09-15")
    - start_time: Optional start time "HH:MM"
    - end_time: Optional end time "HH:MM"
    """
    return get_departures(
        station=station,
        date=date,
        start_time=start_time,
        end_time=end_time,
    )


@tool
def query_station_arrivals(
    station: str,
    date: str,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[str]:
    """
    List flight numbers scheduled to arrive at an airport station on a given date,
    optionally within an arrival time window (HH:MM in UTC).
    Parameters:
    - station: 3-letter IATA station code (e.g. "DEL", "BLR")
    - date: "YYYY-MM-DD" (e.g. "2026-09-15")
    - start_time: Optional start time "HH:MM"
    - end_time: Optional end time "HH:MM"
    """
    return get_arrivals(
        station=station,
        date=date,
        start_time=start_time,
        end_time=end_time,
    )


@tool
def query_flight_schedule_stats(
    metric: str = "longest_block",
) -> dict[str, Any]:
    """
    Compute fleet schedule extremes across all flights in the network.
    Parameters:
    - metric: "longest_block" (longest flight duration) or "shortest_block" (shortest flight duration)
    """
    return get_flight_schedule_stats(metric=metric)


@tool
def query_crew_profile(
    crew_id: str | None = None,
    rank: str | None = None,
    base: str | None = None,
    rating: str | None = None,
    status: str | None = None,
) -> Any:
    """
    Fetch crew member details including base, ratings, reachability minutes,
    reserve on-call standby window (if on reserve), or list crew IDs by rank/base/rating.
    Parameters:
    - crew_id: Specific crew member ID (e.g. "C-1042", "C-3310", "C-2210")
    - rank: Filter by rank ("Captain", "First Officer", "Senior Cabin Crew", "Cabin Crew")
    - base: Filter by home base station ("BLR", "DEL", "BOM")
    - rating: Filter by aircraft type rating ("A320", "ATR72")
    - status: Filter by status ("active", "leave")
    """
    return get_crew_profile(
        crew_id=crew_id,
        rank=rank,
        base=base,
        rating=rating,
        status=status,
    )


@tool
def query_reserve_crew(
    station: str | None = None,
    date: str | None = None,
    rank: str | None = None,
) -> list[dict[str, Any]]:
    """
    List active crew members on reserve standby at a given station on a date,
    including their on-call standby window (start/end UTC) and rank.
    Parameters:
    - station: Airport station code (e.g. "BLR", "DEL", "BOM")
    - date: "YYYY-MM-DD" (e.g. "2026-09-15")
    - rank: Optional rank filter ("Captain", "First Officer", etc.)
    """
    return get_reserves_at_station(
        station=station,
        date=date,
        rank=rank,
    )


@tool
def query_pairing_roster(
    pairing_id: str | None = None,
    crew_id: str | None = None,
    aircraft: str | None = None,
    date: str | None = None,
    role: str | None = None,
) -> Any:
    """
    Lookup assigned crew members and roles for a pairing (e.g. pairing_id="P-2291"),
    or reverse lookup what pairing/flights a specific crew member is rostered on (e.g. crew_id="C-1042"),
    or check who is operating on a specific aircraft tail on a date (e.g. aircraft="VT-DXB", role="Senior Cabin Crew").
    """
    return get_pairing_roster(
        pairing_id=pairing_id,
        crew_id=crew_id,
        aircraft=aircraft,
        date=date,
        role=role,
    )


@tool
def query_crew_duty_balance(
    crew_id: str,
    as_of_date: str = "2026-09-14",
) -> dict[str, Any]:
    """
    Computes exact accrued rolling 7-day duty hours, 28-day flight hours,
    and remaining headroom against the 60h duty cap (RULE-DUTY-02) and 100h flight cap (RULE-FLT-03).
    Parameters:
    - crew_id: Crew member ID (e.g. "C-1042", "C-2087")
    - as_of_date: End of rolling window "YYYY-MM-DD" (default "2026-09-14")
    """
    return get_crew_duty_balance(
        crew_id=crew_id,
        as_of_date=as_of_date,
    )


@tool
def query_operations(
    resource: str,
    filters: dict[str, Any] | None = None,
    fields: list[str] | None = None,
    aggregation: dict[str, Any] | None = None,
    sort: list[str] | None = None,
    limit: int = 100,
    as_of_date: str = "2026-09-14",
    window_days: int = 7,
) -> dict[str, Any]:
    """Run a generalized allowlisted operational query.

    Resources: flights, crew, pairings, crew_duty, reserves, certifications,
    risk_signals. Filters support equality/list membership. Use aggregation
    with metric/operator/value for crew_duty thresholds, or function/field for
    count, distinct, sum, min, max, and average operations.
    Results are deterministic and sourced from SQLite plus the existing duty
    window calculator.
    """
    return _query_operations(
        resource=resource,
        filters=filters,
        fields=fields,
        aggregation=aggregation,
        sort=sort,
        limit=limit,
        as_of_date=as_of_date,
        window_days=window_days,
    )


@tool
def query_expiring_certifications(
    as_of_date: str = "2026-09-15",
    days_ahead: int = 30,
    cert_type: str | None = None,
    crew_id: str | None = None,
) -> list[dict[str, str]]:
    """
    List all qualifications, licences, medicals, or recurrent training expiring within [as_of_date, as_of_date + days_ahead].
    Parameters:
    - as_of_date: Start date "YYYY-MM-DD" (default "2026-09-15")
    - days_ahead: Calendar day window (default 30)
    - cert_type: Filter by cert type ("licence", "medical_class1", "recurrent_training", "dangerous_goods")
    - crew_id: Optional crew ID filter
    """
    return get_expiring_certifications(
        as_of_date=as_of_date,
        days_ahead=days_ahead,
        cert_type=cert_type,
        crew_id=crew_id,
    )


@tool
def query_crew_risk_signal(
    crew_id: str | None = None,
    min_score: float | None = None,
) -> Any:
    """
    Retrieve pre-computed disruption and fatigue risk score (0.0 to 1.0) and operational driver tags for a crew member,
    or list all crew members with risk score >= min_score.
    Parameters:
    - crew_id: Specific crew member ID (e.g. "C-1042")
    - min_score: Threshold to filter high-risk crew (e.g. 0.70)
    """
    return get_crew_risk_signal(
        crew_id=crew_id,
        min_score=min_score,
    )



# ── Tier 2 / Tier 3 tools ─────────────────────────────────────────────

def _find_pairing(pairing_id: str) -> dict:
    load_all()
    return next(p for p in pairings if p["pairing_id"] == pairing_id)


@tool
def check_crew_cover_legality(
    crew_id: str,
    pairing_id: str,
    exclude_pairing: str | None = None,
    delay_hours: float = 0.0,
) -> dict[str, Any]:
    """
    Simulate whether a crew member can legally cover a pairing (all days).
    Checks RULE-FDP-01, RULE-DUTY-02, RULE-REST-04, RULE-QUAL-05, RULE-CERT-06 against
    their existing duties + the proposed cover assignment.
    Parameters:
    - crew_id: Candidate crew member ID (e.g. "C-3310", "C-2087")
    - pairing_id: Pairing to cover (e.g. "P-2291")
    - exclude_pairing: Pairing to remove from the crew's existing roster before simulation (e.g. if they are being swapped)
    - delay_hours: Hours the first departure is delayed (e.g. due to deadhead positioning)
    """
    p = _find_pairing(pairing_id)
    ok, issues = _check_cover(crew_id, p["days"], exclude_pairing=exclude_pairing, delay_h=delay_hours)
    return {"crew_id": crew_id, "pairing_id": pairing_id, "legal": ok, "issues": issues}


@tool
def get_cover_options(
    pairing_id: str,
    role: str,
    sick_crew_id: str,
) -> dict[str, Any]:
    """
    Enumerate and rank all legal replacement candidates for a crew member who is unavailable
    for a pairing. Returns ranked options (cheapest first, cancel last) and excluded candidates with reasons.
    Parameters:
    - pairing_id: The pairing that needs cover (e.g. "P-2291")
    - role: The role to fill ("Captain", "First Officer", "Senior Cabin Crew", "Cabin Crew")
    - sick_crew_id: The unavailable crew member's ID (e.g. "C-1042")
    """
    p = _find_pairing(pairing_id)
    rep_dt = datetime.strptime(p["days"][0]["report_utc"], "%Y-%m-%dT%H:%M:%SZ")
    opts, exc = _cover_options(p["days"], role, sick_crew_id, pairing_id, rep_dt)
    return {"options": opts, "excluded_candidates": exc}


@tool
def analyze_sick_call(
    crew_id: str,
    pairing_id: str,
) -> dict[str, Any]:
    """
    Analyze a sick call: which flights are uncovered, how many passengers are at risk.
    Parameters:
    - crew_id: The sick crew member's ID (e.g. "C-1042")
    - pairing_id: Their pairing ID (e.g. "P-2291")
    """
    return _expand_sick_call(crew_id, pairing_id)


@tool
def analyze_station_closure(
    station: str,
    date: str,
    window_start_utc: str,
    window_end_utc: str,
) -> dict[str, Any]:
    """
    Analyze which flights are affected by a station closure and whether crew can absorb the delay.
    Returns affected flights and per-flight delay/FDP assessment.
    Parameters:
    - station: Airport IATA code (e.g. "BLR", "HYD")
    - date: ISO date "YYYY-MM-DD"
    - window_start_utc: Closure start ISO datetime (e.g. "2026-09-17T08:00:00Z")
    - window_end_utc: Closure end ISO datetime (e.g. "2026-09-17T14:00:00Z")
    """
    return _expand_station_closure(station, date, window_start_utc, window_end_utc)


@tool
def analyze_delay_impact(
    aircraft: str,
    date: str,
    delay_hours: float,
) -> dict[str, Any]:
    """
    Analyze how a technical delay cascades through all legs of an aircraft's pairing,
    check for FDP breach, and suggest recovery actions.
    Parameters:
    - aircraft: Tail registration (e.g. "VT-DXA")
    - date: ISO date "YYYY-MM-DD"
    - delay_hours: Delay duration in hours (e.g. 1.5)
    """
    return _expand_delay(aircraft, date, delay_hours)


@tool
def compute_duty_window(
    crew_id: str,
    as_of_date: str,
    window_days: int = 7,
) -> dict[str, Any]:
    """
    Compute a crew member's total duty hours over a rolling calendar window
    including both historical and planned week duties.
    Parameters:
    - crew_id: Crew member ID
    - as_of_date: End date of the window "YYYY-MM-DD"
    - window_days: Window size in days (default 7 for RULE-DUTY-02)
    """
    load_all()
    d = date.fromisoformat(as_of_date) if isinstance(as_of_date, str) else as_of_date
    duty_h = _win_sum(crew_id, d, window_days, kind=0)
    flight_h = _win_sum(crew_id, d, window_days, kind=1)
    return {
        "crew_id": crew_id,
        "window_days": window_days,
        "as_of_date": as_of_date,
        "duty_hours": duty_h,
        "flight_hours": flight_h,
        "duty_headroom_60h": round(60 - duty_h, 2),
    }


# ── Tool lists ─────────────────────────────────────────────────────────

TIER1_TOOLS = [
    query_flight_schedule,
    query_station_departures,
    query_station_arrivals,
    query_flight_schedule_stats,
    query_crew_profile,
    query_reserve_crew,
    query_pairing_roster,
    query_crew_duty_balance,
    query_expiring_certifications,
    query_crew_risk_signal,
    query_operations,
]

TIER2_TOOLS = [
    check_crew_cover_legality,
    get_cover_options,
    analyze_sick_call,
    analyze_station_closure,
    analyze_delay_impact,
    compute_duty_window,
]

ALL_TOOLS = TIER1_TOOLS + TIER2_TOOLS
TOOL_MAP = {t.name: t for t in ALL_TOOLS}
