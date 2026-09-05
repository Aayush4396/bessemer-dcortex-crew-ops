"""
src/agent/tools.py
==================
LangChain tool wrappers for deterministic Tier 1 lookups and Tier 2 rule checks.
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
from src.tier2 import (
    evaluate_base_positioning,
    evaluate_certifications,
    evaluate_cover,
    evaluate_cover_candidates,
    evaluate_duty_7d,
    evaluate_fdp_limit,
    evaluate_flight_28d,
    evaluate_qualification,
    evaluate_reserve_callout,
    evaluate_rest,
    execute_readonly_sql,
    get_cost_rates,
    get_crew_entity,
    get_flight_duty_times,
    get_pairing_entity,
    get_station_movements,
    simulate_disruption,
)
from src.tier3 import generate_callout_notification, optimize_recovery


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
    - metric: "longest_block", "shortest_block", or "max_seats" (MAX(seats) per aircraft_type)
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
    required_report_utc: str | None = None,
    aircraft_type: str | None = None,
) -> Any:
    """
    List active crew members on reserve standby at a given station on a date,
    including their on-call standby window (start/end UTC) and rank.
    When required_report_utc is set, returns eligible vs excluded reserves
    (window checked against the required report; optional aircraft_type applies RULE-QUAL-05).
    Parameters:
    - station: Airport station code (e.g. "BLR", "DEL", "BOM")
    - date: "YYYY-MM-DD" (e.g. "2026-09-15")
    - rank: Optional rank filter ("Captain", "First Officer", etc.)
    - required_report_utc: ISO timestamp or HH:MM used to filter on-call windows
    - aircraft_type: Optional type rating filter ("A320", "ATR72")
    """
    if required_report_utc:
        duty_date = date or (required_report_utc[:10] if "T" in required_report_utc else None)
        if not duty_date or not rank:
            return {"error": "date and rank are required when filtering a reserve callout"}
        return evaluate_reserve_callout(
            date=duty_date,
            rank=rank,
            required_report_utc=required_report_utc,
            aircraft_type=aircraft_type,
            station=station,
        )
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
    Single-crew snapshot only. Accrued rolling 7-day duty hours, 28-day flight hours,
    and remaining headroom against the 60h duty cap (RULE-DUTY-02) and 100h flight cap (RULE-FLT-03).
    Do NOT use this for "all crew" / fleet lists — use check_duty_7d without crew_id.
    Parameters:
    - crew_id: One crew member ID (e.g. "C-1042", "C-2087")
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


@tool
def query_flight_duty_times(
    flight_id: str | None = None,
    flight_no: str | None = None,
    date: str | None = None,
) -> dict[str, Any]:
    """
    Given a flight_id (e.g. "DX412-2026-09-15") or flight_no+date, return the
    containing pairing day's report_utc / release_utc, duty hours, FDP limit,
    pairing_id, aircraft, seats, and assigned crew. Use this to hop from a
    flight to its pairing and duty window. Do not compute report/release yourself.
    """
    return get_flight_duty_times(flight_id=flight_id, flight_no=flight_no, date=date)


@tool
def query_pairing(pairing_id: str, as_of_date: str | None = None) -> dict[str, Any]:
    """
    Full pairing: crew team + roles, each duty day with flight_ids, seats,
    report_utc, release_utc, duty_hours, max_window_hours (RULE-FDP-01), and
    rest_hours between days. Optional as_of_date (YYYY-MM-DD) labels
    absence_impact. For a no-show, copy absence_impact.day1,
    day2_also_at_risk (every later pairing day), and passengers_day1.
    This tool does not decide cover legality — use check_cover.
    """
    return get_pairing_entity(pairing_id, as_of_date=as_of_date)


@tool
def query_crew_detail(crew_id: str) -> dict[str, Any]:
    """
    Join hub for a crew member: profile, ratings, 7d/28d clocks, all four
    certifications, reserve windows, and every rostered pairing with flight_ids.
    Use returned pairing_id / flight_id keys for the next tool hop.
    """
    return get_crew_entity(crew_id)


@tool
def query_station_movements(
    station: str,
    date: str,
    start_time: str,
    end_time: str,
) -> list[str]:
    """
    Flight ids that depart OR arrive at a station inside a UTC window [start, end).
    Use for airport closures. Returns flight_id values like "DX402-2026-09-17".
    Parameters: station IATA, date YYYY-MM-DD, start_time/end_time HH:MM UTC.
    """
    return get_station_movements(station=station, date=date, start_time=start_time, end_time=end_time)


@tool
def query_database(sql: str) -> dict[str, Any]:
    """
    Run one read-only SELECT against crew_ops.db (SQLite). Write SQLite only —
    PostgreSQL/MySQL syntax will fail. No ANY, ALL/SOME array form, ILIKE,
    UNNEST, GENERATE_SERIES, DATE_TRUNC, INTERVAL, STRING_AGG, ARRAY[], @>,
    or jsonb. Ratings is JSON text: use EXISTS (SELECT 1 FROM json_each(c.ratings)
    WHERE value = 'A320') or ratings LIKE '%A320%'. Use LIKE, IN (...), CASE.
    SELECT / WITH only. Use this instead of looping per crew.

    Tables:
    - crew(crew_id, name, rank, base, ratings, seniority, reachability_minutes, status)
    - duty_clocks(crew_id, as_of_utc, duty_hours_7d, flight_hours_28d, last_rest_ended)
      Snapshot as of 2026-09-14. Weekly = duty_hours_7d. Month/28d flight = flight_hours_28d.
    - duty_clock_history(crew_id, date, duty_hours, flight_hours)
      Daily rows 2026-08-18..2026-09-14. SUM for any custom window.
    - flights(flight_id, flight_no, date, dep_station, arr_station, dep_utc, arr_utc,
      block_hours, aircraft, aircraft_type, seats)
    - pairings(pairing_id, aircraft, date, report_utc, release_utc, flights_json)
    - pairing_crew(pairing_id, crew_id, role)
    - reserve_pool(crew_id, base, date, on_call_start, on_call_end)
    - certifications(crew_id, cert_type, valid_from, valid_to)
    - risk_signals(crew_id, disruption_risk_score, drivers_json)

    Weekly under/over 30h:
      SELECT c.crew_id, c.name, c.rank, d.duty_hours_7d
      FROM crew c JOIN duty_clocks d ON d.crew_id = c.crew_id
      WHERE d.duty_hours_7d < 30 ORDER BY d.duty_hours_7d;
    Monthly/28d flight hours:
      SUM(h.flight_hours) FROM duty_clock_history h, or d.flight_hours_28d on duty_clocks.
    Always include name and rank when listing people. as_of snapshot date is 2026-09-14.
    """
    return execute_readonly_sql(sql)


@tool
def query_cost_rates() -> dict[str, Any]:
    """
    Return the published cost card (INR): reserve/day-off callout, deadhead,
    delay per duty hour, cancellation per flight. Cancellation is a flat
    per-leg rate, not seats × rate.
    """
    return get_cost_rates()


@tool
def check_fdp_limit(
    pairing_id: str | None = None,
    flight_id: str | None = None,
    flight_no: str | None = None,
    aircraft: str | None = None,
    date: str | None = None,
    delay_hours: float = 0.0,
) -> dict[str, Any]:
    """
    RULE-FDP-01: max FDP = 13h − 0.5h per sector beyond the 2nd.
    Resolve the pairing (pairing_id, flight_id, or aircraft+date). delay_hours
    extends duty after report (operational delay). Returns fdp_after_delay,
    fdp_limit, and passed/breach. Never compute the limit yourself.
    """
    return evaluate_fdp_limit(
        pairing_id=pairing_id,
        flight_id=flight_id,
        flight_no=flight_no,
        aircraft=aircraft,
        date=date,
        delay_hours=delay_hours,
    )


@tool
def check_duty_7d(
    crew_id: str | None = None,
    pairing_id: str | None = None,
    as_of_date: str = "2026-09-14",
    min_hours: float | None = None,
    max_hours: float | None = None,
    split_hours: float | None = None,
) -> dict[str, Any]:
    """
    RULE-DUTY-02: max 60 duty hours in any 7 calendar days. Reads clocks from DB.
    - crew_id + pairing_id: simulate covering that pairing (every day)
    - crew_id only: current 7d hours and headroom as of as_of_date
    - NO crew_id: fleet roster with name, rank, duty_hours_7d
    - split_hours (e.g. 30) without crew_id: returns below / equal / above lists — use this
      for "who is under vs over N hours". Do not loop per crew.
    - min_hours without crew_id: list crew at/above that 7d total
    as_of_date must be a full YYYY-MM-DD (default 2026-09-14).
    """
    return evaluate_duty_7d(
        crew_id=crew_id,
        pairing_id=pairing_id,
        as_of_date=as_of_date,
        min_hours=min_hours,
        max_hours=max_hours,
        split_hours=split_hours,
    )


@tool
def check_flight_28d(
    crew_id: str,
    pairing_id: str | None = None,
    as_of_date: str = "2026-09-14",
) -> dict[str, Any]:
    """
    RULE-FLT-03: max 100 flight hours in any 28 calendar days. Reads clocks from DB.
    Optional pairing_id simulates adding that pairing's block hours.
    """
    return evaluate_flight_28d(crew_id=crew_id, pairing_id=pairing_id, as_of_date=as_of_date)


@tool
def check_rest(
    pairing_id: str | None = None,
    crew_id: str | None = None,
    release_utc: str | None = None,
    next_report_utc: str | None = None,
) -> dict[str, Any]:
    """
    RULE-REST-04: minimum 12h rest between release and next report.
    - release_utc only: returns earliest_report_utc (release + 12h)
    - pairing_id only: inter-day rest gaps on that pairing
    - crew_id + pairing_id: upstream rest and downstream conflict vs that crew's other duties
    """
    return evaluate_rest(
        pairing_id=pairing_id,
        crew_id=crew_id,
        release_utc=release_utc,
        next_report_utc=next_report_utc,
    )


@tool
def check_qualification(
    crew_id: str,
    aircraft_type: str | None = None,
    pairing_id: str | None = None,
    flight_id: str | None = None,
) -> dict[str, Any]:
    """
    RULE-QUAL-05: crew must hold a valid rating for the assigned aircraft type.
    Pass aircraft_type ("A320"/"ATR72") or pairing_id / flight_id to resolve the type.
    """
    return evaluate_qualification(
        crew_id=crew_id,
        aircraft_type=aircraft_type,
        pairing_id=pairing_id,
        flight_id=flight_id,
    )


@tool
def check_certifications(
    crew_id: str,
    duty_date: str,
) -> dict[str, Any]:
    """
    RULE-CERT-06: licence, medical_class1, recurrent_training, and dangerous_goods
    must all be valid on duty_date (valid_from ≤ date ≤ valid_to).
    """
    return evaluate_certifications(crew_id=crew_id, duty_date=duty_date)


@tool
def check_base_positioning(
    crew_id: str,
    pairing_id: str,
) -> dict[str, Any]:
    """
    RULE-BASE-07: same-base callout is clean; another base requires deadhead.
    DEL→BLR uses DX402 (odd dates, arr 08:45Z) or DX589 (even dates, arr 07:45Z).
    New report = deadhead arrival + 15 min. Returns delay_hours, positioning flight,
    reserve-window check against the NEW report, and cost breakdown. Do not add costs yourself.
    """
    return evaluate_base_positioning(crew_id=crew_id, pairing_id=pairing_id)


@tool
def check_cover(
    pairing_id: str,
    crew_id: str | None = None,
    role: str | None = None,
    replace_crew_id: str | None = None,
) -> dict[str, Any]:
    """
    Cover legality for a vacant pairing seat. Rank must match the vacant role
    (First Officer cannot cover Captain). Pass role or replace_crew_id.
    - crew_id set: one candidate. Also checks status (leave is illegal),
      DUTY-02, FLT-03, FDP-01, REST-04, QUAL-05, CERT-06, BASE-07.
    - crew_id omitted: scan every same-rank crew. Returns legal[] and
      excluded[] with real issue strings. Use this for "who can cover".
      Do not loop check_cover per crew. Do not invent QUAL-05.
    """
    if crew_id:
        return evaluate_cover(
            crew_id=crew_id,
            pairing_id=pairing_id,
            role=role,
            replace_crew_id=replace_crew_id,
        )
    return evaluate_cover_candidates(
        pairing_id=pairing_id,
        role=role,
        replace_crew_id=replace_crew_id,
    )


# ---------------------------------------------------------------------------
# Tier 2 Disruption Simulation Tools
# ---------------------------------------------------------------------------

@tool
def simulate_disruption_impact(
    event_type: str,
    crew_id: str | None = None,
    pairing_id: str | None = None,
    station: str | None = None,
    start_utc: str | None = None,
    end_utc: str | None = None,
    aircraft: str | None = None,
    date: str | None = None,
    delay_hours: float | None = None,
    delay_minutes: int | None = None,
) -> dict[str, Any]:
    """
    Simulate the operational consequences and cascading impacts of a disruption event (Tier 2).
    Determines uncrewed flight sectors, passenger seats at risk, multi-day pairing breakage,
    rotational duty delays, and DGCA CAR FDP limit breaches.

    Parameters:
    - event_type: 'SICK_CREW', 'STATION_CLOSURE', 'DELAY', or 'CERT_EXPIRY'
    - crew_id: Affected crew member ID (e.g. 'C-1042', 'C-3231', 'C-5417')
    - pairing_id: Broken pairing ID (e.g. 'P-2291', 'P-2224')
    - station: Airport station closed (e.g. 'BLR', 'DEL', 'HYD')
    - start_utc: Closure window start timestamp or time (e.g. '2026-09-17T08:00:00Z')
    - end_utc: Closure window end timestamp or time (e.g. '2026-09-17T14:00:00Z')
    - aircraft: Delayed aircraft registration (e.g. 'VT-DXA', 'VT-DXB')
    - date: Date of duty 'YYYY-MM-DD' (e.g. '2026-09-16')
    - delay_hours: Duration of delay in hours (e.g. 1.5)
    - delay_minutes: Duration of delay in minutes (e.g. 90)
    """
    payload: dict[str, Any] = {"type": event_type}
    if crew_id:
        payload["crew_id"] = crew_id
    if pairing_id:
        payload["pairing_id"] = pairing_id
    if station:
        payload["station"] = station
    if start_utc or end_utc:
        payload["window_utc"] = {"start": start_utc, "end": end_utc}
    if aircraft:
        payload["aircraft"] = aircraft
    if date:
        payload["date"] = date
    if delay_hours is not None:
        payload["delay_hours"] = float(delay_hours)
    elif delay_minutes is not None:
        payload["delay_hours"] = float(delay_minutes) / 60.0

    return simulate_disruption(payload)


# ---------------------------------------------------------------------------
# Tier 3 Recovery Optimization Tools
# ---------------------------------------------------------------------------

@tool
def optimize_disruption_recovery(
    event_type: str,
    crew_id: str | None = None,
    pairing_id: str | None = None,
    role: str | None = None,
    station: str | None = None,
    aircraft: str | None = None,
    date: str | None = None,
    delay_hours: float | None = None,
) -> dict[str, Any]:
    """
    Generate ranked legal recovery options and cost trade-offs for an operational disruption (Tier 3).
    Evaluates candidate pools (active reserves, day-offs, deadhead positioning) against all 7 DGCA CAR rules,
    computes exact financial costs in INR, identifies excluded candidates with specific rule violation reasons,
    and returns ranked options sorted by delay and cost.

    Parameters:
    - event_type: Disruption type: 'SICK_CREW', 'DELAY', 'CERT_EXPIRY', or 'MULTI_SICK'
    - crew_id: Incapacitated or affected crew ID (e.g. 'C-1042', 'C-3231')
    - pairing_id: Broken pairing ID needing replacement crew (e.g. 'P-2291')
    - role: Rank/role needing cover ('Captain', 'First Officer', 'Senior Cabin Crew', 'Cabin Crew')
    - station: Base station needing coverage (e.g. 'BLR')
    - aircraft: Delayed aircraft registration (e.g. 'VT-DXA')
    - date: Date of duty 'YYYY-MM-DD'
    - delay_hours: Rotational delay duration in hours
    """
    payload: dict[str, Any] = {"type": event_type}
    if crew_id:
        payload["crew_id"] = crew_id
    if pairing_id:
        payload["pairing_id"] = pairing_id
    if role:
        payload["role"] = role
    if station:
        payload["station"] = station
    if aircraft:
        payload["aircraft"] = aircraft
    if date:
        payload["date"] = date
    if delay_hours is not None:
        payload["delay_hours"] = float(delay_hours)

    return optimize_recovery(payload)


@tool
def generate_callout_notification_draft(
    crew_id: str,
    pairing_id: str,
) -> dict[str, Any]:
    """
    Generate an official, structured Crew Operations Dispatch callout notification alert (Tier 3).
    Includes mandatory operational fields: pairing ID, report time, location, flight details,
    overnight layover accommodations, acknowledgement deadline, and dispatch contact details.
    """
    return generate_callout_notification(crew_id=crew_id, pairing_id=pairing_id)


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

TIER2_TOOLS = [
    simulate_disruption_impact,
    query_flight_duty_times,
    query_pairing,
    query_crew_detail,
    query_station_movements,
    query_database,
    query_cost_rates,
    check_fdp_limit,
    check_duty_7d,
    check_flight_28d,
    check_rest,
    check_qualification,
    check_certifications,
    check_base_positioning,
    check_cover,
]

TIER3_TOOLS = [
    optimize_disruption_recovery,
    generate_callout_notification_draft,
]

ALL_TOOLS = TIER1_TOOLS + TIER2_TOOLS + TIER3_TOOLS
TOOL_MAP = {t.name: t for t in ALL_TOOLS}
