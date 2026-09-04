"""
src/agent/tools.py
==================
LangChain tool wrappers for deterministic Tier 1 query functions.
Strictly delegates to the deterministic domain package `src.tier1`.
"""

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
)


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
]

TOOL_MAP = {t.name: t for t in TIER1_TOOLS}
