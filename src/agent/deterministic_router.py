"""Deterministic routing for operational intents that do not require an LLM."""

import re
from datetime import datetime
from typing import Any

from langchain_core.messages import AIMessage

from src.resolver import cover_options, evaluate_replacement_candidate, expand_sick_call
from src.resolver.data import load_all, pairings
from src.resolver.disruption import expand_delay, expand_station_closure
from src.rules.models import SNAPSHOT_DATE
from src.tier1 import get_connection, query_operations
from .tier1_planner import route_tier1_query


_THRESHOLD_PATTERNS = (
    (r"(?:less than|under|below|fewer than)\s*(\d+(?:\.\d+)?)", "<"),
    (r"(?:at most|no more than)\s*(\d+(?:\.\d+)?)", "<="),
    (r"(?:greater than|over|above|more than)\s*(\d+(?:\.\d+)?)", ">"),
    (r"(?:at least|no less than)\s*(\d+(?:\.\d+)?)", ">="),
)


def _crew_duty_threshold(query: str) -> tuple[str, float] | None:
    normalized = " ".join(query.lower().split())
    has_crew_intent = any(term in normalized for term in ("crew", "captain", "first officer", "cabin"))
    has_duty_intent = "duty" in normalized and any(
        term in normalized for term in ("weekly", "week", "7-day", "7 day")
    )
    if not has_crew_intent or not has_duty_intent:
        return None

    for pattern, operator in _THRESHOLD_PATTERNS:
        match = re.search(pattern, normalized)
        if match:
            return operator, float(match.group(1))
    return None


def _format_number(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)


def _format_crew_duty_response(result: dict[str, Any], operator: str, threshold: float) -> str:
    operator_text = {
        "<": "less than",
        "<=": "at most",
        ">": "greater than",
        ">=": "at least",
    }[operator]
    lines = [
        f"Found **{result['count']} crew members** whose rolling 7-day duty hours are "
        f"{operator_text} {_format_number(threshold)} hours as of {result['as_of_date']}.",
        "",
        "| Crew ID | Name | Rank | Weekly duty hours |",
        "|---|---|---|---:|",
    ]
    lines.extend(
        f"| {row['crew_id']} | {row['name']} | {row['rank']} | {row['duty_hours_7d']:.2f} |"
        for row in result["rows"]
    )
    lines.extend(
        [
            "",
            "Duty hours are calculated deterministically from SQLite duty history using the rolling 7-day window.",
        ]
    )
    return "\n".join(lines)


def _query_date(query: str) -> str | None:
    iso_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", query)
    if iso_match:
        return iso_match.group(1)

    date_match = re.search(
        r"\b(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"(?:\s+(20\d{2}))?\b",
        query,
        re.IGNORECASE,
    )
    if not date_match:
        return None
    day, month_name, year = date_match.groups()
    parsed = datetime.strptime(f"{day} {month_name[:3]} {year or SNAPSHOT_DATE.year}", "%d %b %Y")
    return parsed.date().isoformat()


def _sick_call_entities(query: str) -> tuple[str, str | None, str | None] | None:
    normalized = " ".join(query.upper().split())
    if not any(term in normalized for term in ("SICK", "UNAVAILABLE", "ABSENT")):
        return None
    crew_match = re.search(r"\bC-\d+\b", normalized)
    pairing_match = re.search(r"\bP-\d+\b", normalized)
    event_date = _query_date(query)
    if not crew_match or (not pairing_match and not event_date):
        return None
    pairing_id = pairing_match.group(0) if pairing_match else None
    return crew_match.group(0), pairing_id, event_date


def _replacement_entities(query: str) -> tuple[str | None, str | None, str | None, str | None] | None:
    normalized = " ".join(query.upper().split())
    if not any(term in normalized for term in ("WHO CAN COVER", "COVER UP", "REPLACEMENT", "REPLACE")):
        return None
    crew_match = re.search(r"\bC-\d+\b", normalized)
    pairing_match = re.search(r"\bP-\d+\b", normalized)
    role = next(
        (candidate for candidate in ("Senior Cabin Crew", "First Officer", "Captain", "Cabin Crew")
         if candidate.upper() in normalized),
        None,
    )
    return (
        crew_match.group(0) if crew_match else None,
        pairing_match.group(0) if pairing_match else None,
        role,
        _query_date(query),
    )


def _legality_check_entities(
    query: str,
    active_entities: dict[str, str],
) -> tuple[str, str, str] | None:
    """Match queries about rule breaches / legality for a crew-pairing assignment."""
    normalized = " ".join(query.upper().split())
    has_legality_intent = any(
        term in normalized
        for term in ("RULE BREACH", "BREACH", "LEGAL", "VIOLAT")
    )
    has_cover_context = "ASSIGNED TO COVER" in normalized or "PROPOSED TO COVER" in normalized
    if not (has_legality_intent or has_cover_context):
        return None
    crew_ids = re.findall(r"\bC-\d+\b", normalized)
    pairing_match = re.search(r"\bP-\d+\b", normalized)
    if not crew_ids or not pairing_match:
        return None
    candidate_id = crew_ids[0]
    pairing_id = pairing_match.group(0)
    unavailable_crew_id = (
        crew_ids[1] if len(crew_ids) > 1
        else active_entities.get("sick_crew_id")
        or _resolve_incumbent(candidate_id, pairing_id)
    )
    if not unavailable_crew_id:
        return None
    return candidate_id, unavailable_crew_id, pairing_id


def _delay_entities(query: str) -> tuple[str, str, float] | None:
    """Match delay impact queries: aircraft + date + delay amount."""
    normalized = " ".join(query.upper().split())
    if "DELAY" not in normalized:
        return None
    aircraft_match = re.search(r"\bVT-[A-Z0-9]+\b", query, re.IGNORECASE)
    if not aircraft_match:
        return None
    delay_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:MINUTE|MIN|HOUR|HR|H\b)", normalized)
    if not delay_match:
        return None
    delay_val = float(delay_match.group(1))
    if "MINUTE" in normalized[delay_match.start():] or "MIN" in normalized[delay_match.start():delay_match.end() + 10]:
        delay_val /= 60.0
    date_str = _query_date(query)
    if not date_str:
        return None
    return aircraft_match.group(0).upper(), date_str, round(delay_val, 4)


def _format_delay_response(result: dict) -> str:
    lines = [
        f"**Delay impact analysis for pairing {result['pairing_id']}**",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Original FDP | {result['original_fdp']}h |",
        f"| FDP after delay | {result['fdp_after_delay']}h |",
        f"| FDP limit ({result['sectors']} sectors) | {result['fdp_limit']}h |",
        f"| Breach | {'**Yes**' if result['breach'] else 'No'} |",
    ]
    if result.get("breach_detail"):
        lines.extend(["", result["breach_detail"]])
    return "\n".join(lines)


def _delay_route(aircraft: str, date_str: str, delay_hours: float) -> dict[str, Any]:
    result = expand_delay(aircraft, date_str, delay_hours)
    tool_args = {"aircraft": aircraft, "date": date_str, "delay_hours": delay_hours}
    response = _format_delay_response(result)
    return {
        "messages": [AIMessage(content=response)],
        "tool_calls": [{"name": "analyze_delay_impact", "args": tool_args, "id": "deterministic_delay"}],
        "tool_results": [{"tool_name": "analyze_delay_impact", "args": tool_args, "result": result}],
        "reasoning_trace": [
            f"Deterministic router matched a delay impact query for {aircraft} on {date_str}",
            f"Applied {delay_hours}h delay across all legs of the duty day",
            f"FDP breach: {result['breach']} ({result['fdp_after_delay']}h vs {result['fdp_limit']}h limit)",
            "Rendered the operational response without an external LLM call",
        ],
        "final_response": response,
    }


def _station_closure_entities(query: str) -> tuple[str, str, str, str] | None:
    """Match station closure queries: station + date + time window."""
    normalized = " ".join(query.lower().split())
    if not any(term in normalized for term in ("closed", "closure", "closes")):
        return None
    station = None
    for alias, code in {
        "blr": "BLR", "bengaluru": "BLR", "bangalore": "BLR",
        "bom": "BOM", "mumbai": "BOM",
        "del": "DEL", "delhi": "DEL",
        "hyd": "HYD", "hyderabad": "HYD",
        "maa": "MAA", "chennai": "MAA",
    }.items():
        if re.search(rf"\b{re.escape(alias)}\b", normalized):
            station = code
            break
    if not station:
        return None
    date_str = _query_date(query)
    if not date_str:
        return None
    time_range = re.search(r"(\d{1,2}:\d{2})\s*[–—-]\s*(\d{1,2}:\d{2})\s*Z?\b", query)
    if not time_range:
        return None
    start_time, end_time = time_range.group(1), time_range.group(2)
    window_start = f"{date_str}T{start_time.zfill(5)}:00Z"
    window_end = f"{date_str}T{end_time.zfill(5)}:00Z"
    return station, date_str, window_start, window_end


def _format_station_closure_response(station: str, date_str: str, result: dict) -> str:
    affected = result["affected_flights"]
    assessments = result["per_flight_assessment"]
    lines = [
        f"**{station} closure on {date_str}** affects **{len(affected)} flights**.",
        "",
        "| Flight | Pairing | Min delay (h) | New FDP (h) | FDP limit (h) | Action |",
        "|---|---|---:|---:|---:|---|",
    ]
    for a in assessments:
        lines.append(
            f"| {a['flight_id']} | {a['pairing_id']} | {a['min_delay_hours']} | "
            f"{a['crew_fdp_after_delay']} | {a['fdp_limit']} | {a['action']} |"
        )
    return "\n".join(lines)


def _station_closure_route(station: str, date_str: str, window_start: str, window_end: str) -> dict[str, Any]:
    result = expand_station_closure(station, date_str, window_start, window_end)
    tool_args = {"station": station, "date": date_str, "window_start": window_start, "window_end": window_end}
    response = _format_station_closure_response(station, date_str, result)
    return {
        "messages": [AIMessage(content=response)],
        "tool_calls": [{"name": "analyze_station_closure", "args": tool_args, "id": "deterministic_closure"}],
        "tool_results": [{"tool_name": "analyze_station_closure", "args": tool_args, "result": result}],
        "reasoning_trace": [
            f"Deterministic router matched a station closure query for {station} on {date_str}",
            f"Scanned flights for {station} departures/arrivals during closure window",
            f"Found {len(result['affected_flights'])} affected flights with per-flight FDP assessment",
            "Rendered the operational response without an external LLM call",
        ],
        "final_response": response,
    }


def _resolve_aircraft_to_pairing(aircraft: str, date_str: str) -> str | None:
    """Resolve VT-XXX aircraft + date to a pairing_id."""
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT pairing_id FROM pairings WHERE aircraft = ? AND date = ? ORDER BY pairing_id",
            (aircraft, date_str),
        ).fetchone()
        return row["pairing_id"] if row else None
    finally:
        connection.close()


def _resolve_role_incumbent(pairing_id: str, role: str) -> str | None:
    """Find the crew member assigned to a specific role on a pairing."""
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT crew_id FROM pairing_crew WHERE pairing_id = ? AND role = ? ORDER BY crew_id",
            (pairing_id, role),
        ).fetchone()
        return row["crew_id"] if row else None
    finally:
        connection.close()


def _cover_options_entities(query: str) -> tuple[str | None, str | None, str | None, str | None] | None:
    """Match T3 ranked replacement option queries."""
    normalized = " ".join(query.upper().split())
    if not any(term in normalized for term in (
        "RANKED", "RESOLUTION OPTION", "CHEAPEST LEGAL", "OPTIMAL",
        "CREWING PLAN", "RECOVERY PLAN",
    )):
        return None
    crew_match = re.search(r"\bC-\d+\b", normalized)
    pairing_match = re.search(r"\bP-\d+\b", normalized)
    aircraft_match = re.search(r"\bVT-[A-Z0-9]+\b", query, re.IGNORECASE)
    role = next(
        (candidate for candidate in ("Senior Cabin Crew", "First Officer", "Captain", "Cabin Crew")
         if candidate.upper() in normalized),
        None,
    )
    crew_id = crew_match.group(0) if crew_match else None
    pairing_id = pairing_match.group(0) if pairing_match else None
    event_date = _query_date(query)

    if pairing_id is None and aircraft_match and event_date:
        pairing_id = _resolve_aircraft_to_pairing(aircraft_match.group(0).upper(), event_date)

    if crew_id is None and pairing_id and role:
        crew_id = _resolve_role_incumbent(pairing_id, role)

    return (crew_id, pairing_id, role, event_date)


def _requires_llm_prose(query: str) -> bool:
    """Queries that need LLM generation, not deterministic routing."""
    normalized = " ".join(query.lower().split())
    return any(term in normalized for term in (
        "draft", "write", "compose", "notify", "notification message",
        "morning briefing", "surface and why", "data points",
    ))


def _resolve_incumbent(candidate_id: str, pairing_id: str) -> str | None:
    """Find the current incumbent for the same role on the pairing."""
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT crew_id FROM pairing_crew WHERE pairing_id = ? AND role = "
            "(SELECT rank FROM crew WHERE crew_id = ?) AND crew_id != ? ORDER BY crew_id",
            (pairing_id, candidate_id, candidate_id),
        ).fetchone()
        if row:
            return row["crew_id"]
        fallback = connection.execute(
            "SELECT crew_id FROM pairing_crew WHERE pairing_id = ? AND crew_id != ? ORDER BY crew_id",
            (pairing_id, candidate_id),
        ).fetchone()
        return fallback["crew_id"] if fallback else None
    finally:
        connection.close()


def _candidate_cover_entities(
    query: str,
    active_entities: dict[str, str],
) -> tuple[str, str, str] | None:
    normalized = " ".join(query.upper().split())
    if "WHO CAN" in normalized:
        return None
    if not ("CAN " in normalized or "WHAT ABOUT" in normalized):
        return None
    if not any(term in normalized for term in ("REPLACE", "COVER")):
        return None
    crew_ids = re.findall(r"\bC-\d+\b", normalized)
    if not crew_ids:
        return None
    candidate_id = crew_ids[0]
    pairing_match = re.search(r"\bP-\d+\b", normalized)
    pairing_id = pairing_match.group(0) if pairing_match else active_entities.get("pairing_id")
    if not pairing_id:
        return None
    unavailable_crew_id = (
        crew_ids[1] if len(crew_ids) > 1
        else active_entities.get("sick_crew_id")
        or _resolve_incumbent(candidate_id, pairing_id)
    )
    if not unavailable_crew_id:
        return None
    return candidate_id, unavailable_crew_id, pairing_id


def _flight_parts(flight_id: str) -> tuple[str, str]:
    match = re.match(r"^(.+)-(\d{4}-\d{2}-\d{2})$", flight_id)
    return (match.group(1), match.group(2)) if match else (flight_id, "")


def _format_flight_table(flight_ids: list[str], status: str) -> list[str]:
    rows = ["| Flight | Date | Status |", "|---|---|---|"]
    for flight_id in flight_ids:
        flight_no, flight_date = _flight_parts(flight_id)
        rows.append(f"| {flight_no} | {flight_date} | {status} |")
    return rows


def _format_sick_call_response(result: dict[str, Any]) -> str:
    day1 = result["uncovered_flights_day1"]
    day2 = result.get("uncovered_flights_day2", [])
    lines = [
        f"When {result['role']} {result['sick_crew_id']} is unavailable for pairing "
        f"{result['pairing_id']}, **{len(day1)} Day 1 flights are immediately uncrewed**.",
        "",
        "### Immediately uncrewed",
        "",
        *_format_flight_table(day1, "Uncrewed"),
    ]
    if day2:
        lines.extend(
            [
                "",
                "### Downstream flights also at risk",
                "",
                *_format_flight_table(day2, "At risk"),
            ]
        )
    lines.extend(
        [
            "",
            f"Day 1 passenger impact: **{result['passengers_at_risk_day1']} passengers at risk**.",
            "",
            f"Immediate action: arrange a replacement {result['role']} for pairing {result['pairing_id']}.",
        ]
    )
    return "\n".join(lines)


def _sick_call_route(crew_id: str, pairing_id: str | None, event_date: str | None) -> dict[str, Any]:
    result = expand_sick_call(crew_id, pairing_id, event_date)
    tool_args = {"crew_id": crew_id, "pairing_id": result["pairing_id"]}
    if event_date:
        tool_args["event_date"] = event_date
    response = _format_sick_call_response(result)
    return {
        "messages": [AIMessage(content=response)],
        "tool_calls": [{"name": "analyze_sick_call", "args": tool_args, "id": "deterministic_sick_call"}],
        "tool_results": [{"tool_name": "analyze_sick_call", "args": tool_args, "result": result}],
        "reasoning_trace": [
            "Deterministic router matched a crew sick-call disruption query",
            f"Resolved {crew_id} to pairing {result['pairing_id']} for the sick-call event",
            f"Executed analyze_sick_call for {crew_id} on {result['pairing_id']}",
            f"Retrieved {len(result['uncovered_flights_day1'])} immediately uncovered flights from SQLite",
            "Calculated Day 1 passenger exposure from SQLite aircraft seat counts",
            "Rendered the operational response without an external LLM call",
        ],
        "final_response": response,
    }


def _resolve_replacement_context(
    crew_id: str | None,
    pairing_id: str | None,
    role: str | None,
    event_date: str | None,
) -> tuple[str, str, str]:
    if pairing_id is None and crew_id and event_date:
        pairing_id = expand_sick_call(crew_id, event_date=event_date)["pairing_id"]
    if pairing_id is None:
        raise ValueError("A pairing ID, or a crew ID with duty date, is required to find replacements")

    connection = get_connection()
    try:
        if crew_id:
            assignment = connection.execute(
                "SELECT role FROM pairing_crew WHERE pairing_id = ? AND crew_id = ?",
                (pairing_id, crew_id),
            ).fetchone()
            if assignment is None:
                raise ValueError(f"Crew {crew_id} is not assigned to pairing {pairing_id}")
            role = role or assignment["role"]
        if role is None:
            raise ValueError("The replacement role is required when the unavailable crew member is not specified")
        if crew_id is None:
            incumbents = connection.execute(
                "SELECT crew_id FROM pairing_crew WHERE pairing_id = ? AND role = ? ORDER BY crew_id",
                (pairing_id, role),
            ).fetchall()
            if len(incumbents) != 1:
                ids = [row["crew_id"] for row in incumbents]
                raise ValueError(f"Expected one {role} on {pairing_id}, found {ids}")
            crew_id = incumbents[0]["crew_id"]
    finally:
        connection.close()
    return crew_id, pairing_id, role


def _format_replacement_response(result: dict[str, Any]) -> str:
    legal_options = [option for option in result["options"] if option["crew_id"]]
    cancellation = next((option for option in result["options"] if option["crew_id"] is None), None)
    lines = [
        f"Found **{len(legal_options)} legal replacement {result['role']} options** for pairing "
        f"{result['pairing_id']}. The unavailable incumbent is {result['sick_crew_id']}.",
        "",
        "| Rank | Crew ID | Action | Cost (INR) | Delay hours |",
        "|---:|---|---|---:|---:|",
    ]
    lines.extend(
        f"| {option['rank']} | {option['crew_id']} | {option['action']} | {option['cost_inr']} | {option['delay_hours']} |"
        for option in legal_options
    )
    best = legal_options[0]
    lines.extend(
        [
            "",
            f"Recommended first option: **{best['crew_id']}** at **INR {best['cost_inr']}**, "
            f"with {best['delay_hours']} hours of modeled delay.",
            f"The legality engine excluded **{len(result['excluded_candidates'])} candidates** with recorded reasons.",
        ]
    )
    if cancellation:
        lines.append(f"Cancellation remains the last-resort option at INR {cancellation['cost_inr']}.")
    return "\n".join(lines)


def _replacement_route(
    crew_id: str | None,
    pairing_id: str | None,
    role: str | None,
    event_date: str | None,
) -> dict[str, Any]:
    crew_id, pairing_id, role = _resolve_replacement_context(crew_id, pairing_id, role, event_date)
    load_all()
    pairing = next((item for item in pairings if item["pairing_id"] == pairing_id), None)
    if pairing is None:
        raise ValueError(f"Pairing {pairing_id} was not found")
    callout_time = datetime.strptime(pairing["days"][0]["report_utc"], "%Y-%m-%dT%H:%M:%SZ")
    options, excluded = cover_options(pairing["days"], role, crew_id, pairing_id, callout_time)
    result = {
        "pairing_id": pairing_id,
        "role": role,
        "sick_crew_id": crew_id,
        "options": options,
        "excluded_candidates": excluded,
    }
    tool_args = {"pairing_id": pairing_id, "role": role, "sick_crew_id": crew_id}
    response = _format_replacement_response(result)
    return {
        "messages": [AIMessage(content=response)],
        "tool_calls": [{"name": "get_cover_options", "args": tool_args, "id": "deterministic_cover_options"}],
        "tool_results": [{"tool_name": "get_cover_options", "args": tool_args, "result": result}],
        "reasoning_trace": [
            f"Resolved the unavailable {role} as {crew_id} on pairing {pairing_id}",
            "Executed deterministic legality checks for every replacement candidate",
            f"Ranked {len(options)} recovery options by modeled cost and crew ID tie-break",
            "Preserved excluded candidates and exact legality reasons in the audit payload",
            "Rendered the operational response without an external LLM call",
        ],
        "final_response": response,
    }


def _candidate_cover_route(candidate_id: str, unavailable_crew_id: str, pairing_id: str) -> dict[str, Any]:
    result = evaluate_replacement_candidate(candidate_id, pairing_id, unavailable_crew_id)
    tool_args = {
        "crew_id": candidate_id,
        "pairing_id": pairing_id,
        "replaces_crew_id": unavailable_crew_id,
    }
    if result["legal"]:
        response = (
            f"Yes. **{candidate_id}** can legally replace {unavailable_crew_id} as "
            f"{result['required_role']} on pairing {pairing_id}."
        )
        consequence = result.get("operational_consequence")
        if consequence:
            response += f"\n\n**Operational consequence:** {consequence['consequence']}"
    else:
        response = (
            f"No. **{candidate_id} cannot replace {unavailable_crew_id}** as {result['required_role']} "
            f"on pairing {pairing_id}.\n\nReason: " + "; ".join(result["issues"])
        )
    return {
        "messages": [AIMessage(content=response)],
        "tool_calls": [{"name": "check_crew_cover_legality", "args": tool_args, "id": "deterministic_candidate_cover"}],
        "tool_results": [{"tool_name": "check_crew_cover_legality", "args": tool_args, "result": result}],
        "reasoning_trace": [
            f"Resolved prior conversation context to pairing {pairing_id}",
            f"Compared candidate {candidate_id} with the {result['required_role']} role held by {unavailable_crew_id}",
            "Executed candidate-specific status, role, qualification, duty, FDP, and rest checks",
            f"Candidate legality result: {result['legal']}",
            "Rendered the operational response without an external LLM call",
        ],
        "final_response": response,
    }


def _combine_routes(*routes: dict[str, Any]) -> dict[str, Any]:
    return {
        "messages": [AIMessage(content="\n\n".join(route["final_response"] for route in routes))],
        "tool_calls": [call for route in routes for call in route["tool_calls"]],
        "tool_results": [result for route in routes for result in route["tool_results"]],
        "reasoning_trace": [step for route in routes for step in route["reasoning_trace"]],
        "final_response": "\n\n".join(route["final_response"] for route in routes),
    }


def route_deterministic_query(
    query: str,
    active_entities: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Return a complete graph-state update when a deterministic intent matches."""
    if _requires_llm_prose(query):
        return None
    context = dict(active_entities or {})
    legality_check = _legality_check_entities(query, context)
    if legality_check is not None:
        return _candidate_cover_route(*legality_check)
    candidate_cover = _candidate_cover_entities(query, context)
    if candidate_cover is not None:
        return _candidate_cover_route(*candidate_cover)
    sick_call = _sick_call_entities(query)
    replacement = _replacement_entities(query)
    if sick_call is not None and replacement is not None:
        sick_route = _sick_call_route(*sick_call)
        replacement_crew, replacement_pairing, replacement_role, replacement_date = replacement
        replacement_route = _replacement_route(
            replacement_crew or sick_call[0],
            replacement_pairing or sick_route["tool_results"][0]["result"]["pairing_id"],
            replacement_role or sick_route["tool_results"][0]["result"]["role"],
            replacement_date or sick_call[2],
        )
        return _combine_routes(sick_route, replacement_route)
    if sick_call is not None:
        return _sick_call_route(*sick_call)
    if replacement is not None:
        return _replacement_route(*replacement)

    delay = _delay_entities(query)
    if delay is not None:
        return _delay_route(*delay)

    closure = _station_closure_entities(query)
    if closure is not None:
        return _station_closure_route(*closure)

    cover_opts = _cover_options_entities(query)
    if cover_opts is not None:
        return _replacement_route(*cover_opts)

    tier1_result = route_tier1_query(query)
    if tier1_result is not None:
        return tier1_result

    threshold = _crew_duty_threshold(query)
    if threshold is None:
        return None

    operator, value = threshold
    tool_args = {
        "resource": "crew_duty",
        "fields": ["crew_id", "name", "rank", "duty_hours_7d"],
        "aggregation": {"metric": "duty_hours_7d", "operator": operator, "value": value},
        "sort": ["duty_hours_7d", "name"],
        "limit": 500,
        "as_of_date": SNAPSHOT_DATE.isoformat(),
        "window_days": 7,
    }
    result = query_operations(**tool_args)
    tool_call = {"name": "query_operations", "args": tool_args, "id": "deterministic_crew_duty"}
    tool_result = {"tool_name": "query_operations", "args": tool_args, "result": result}
    response = _format_crew_duty_response(result, operator, value)

    return {
        "messages": [AIMessage(content=response)],
        "tool_calls": [tool_call],
        "tool_results": [tool_result],
        "reasoning_trace": [
            "Deterministic router matched a roster-wide rolling duty threshold query",
            f"Executed query_operations with a 7-day duty threshold of {operator} {_format_number(value)} hours",
            f"Retrieved {result['count']} grounded crew records from SQLite",
            "Rendered the operational response without an external LLM call",
        ],
        "final_response": response,
    }
