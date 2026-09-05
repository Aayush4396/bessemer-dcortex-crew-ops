"""Schema-aware deterministic planner for generalized Tier 1 questions."""

import json
import re
from datetime import datetime
from typing import Any

from langchain_core.messages import AIMessage

from src.rules.models import SNAPSHOT_DATE
from src.tier1 import query_operations


STATION_ALIASES = {
    "blr": "BLR",
    "bengaluru": "BLR",
    "bangalore": "BLR",
    "bom": "BOM",
    "mumbai": "BOM",
    "del": "DEL",
    "delhi": "DEL",
    "maa": "MAA",
    "chennai": "MAA",
    "hyd": "HYD",
    "hyderabad": "HYD",
    "ccu": "CCU",
    "kolkata": "CCU",
    "cok": "COK",
    "kochi": "COK",
    "goi": "GOI",
    "goa": "GOI",
}

RANK_TERMS = (
    ("senior cabin crew", "Senior Cabin Crew"),
    ("first officer", "First Officer"),
    ("captain", "Captain"),
    ("cabin crew", "Cabin Crew"),
)

THRESHOLD_PATTERNS = (
    (r"(?:less than|under|below|fewer than)\s*(\d+(?:\.\d+)?)", "<"),
    (r"(?:at most|no more than)\s*(\d+(?:\.\d+)?)", "<="),
    (r"(?:at least|at or above|no less than)\s*(\d+(?:\.\d+)?)", ">="),
    (r"(?:greater than|over|above|more than)\s*(\d+(?:\.\d+)?)", ">"),
)


def _date_from_query(query: str) -> str | None:
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


def _station_after(normalized: str, prefixes: tuple[str, ...]) -> str | None:
    for alias, code in STATION_ALIASES.items():
        if any(f"{prefix} {alias}" in normalized for prefix in prefixes):
            return code
    return None


def _mentioned_station(normalized: str) -> str | None:
    for alias, code in STATION_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", normalized):
            return code
    return None


def _rank(normalized: str) -> str | None:
    for term, rank in RANK_TERMS:
        if term in normalized:
            return rank
    return None


def _status(normalized: str) -> str | None:
    if "active" in normalized:
        return "active"
    if "on leave" in normalized or "leave status" in normalized:
        return "leave"
    if "training status" in normalized:
        return "training"
    return None


def _top_limit(normalized: str) -> int | None:
    digit_match = re.search(r"\b(?:top|first)\s+(\d+)\b", normalized)
    if digit_match:
        return int(digit_match.group(1))
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ten": 10}
    for word, value in words.items():
        if f"{word} " in normalized and any(term in normalized for term in ("highest", "longest", "shortest", "quickest")):
            return value
    return None


def _threshold(normalized: str) -> tuple[str, float] | None:
    for pattern, operator in THRESHOLD_PATTERNS:
        match = re.search(pattern, normalized)
        if match:
            return operator, float(match.group(1))
    return None


def _base_filters(normalized: str) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    status = _status(normalized)
    rank = _rank(normalized)
    if status:
        filters["status"] = status
    if rank:
        filters["rank"] = rank
    return filters


def _flight_plan(query: str, normalized: str) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    query_date = _date_from_query(query)
    if query_date:
        filters["date"] = query_date
    origin = _station_after(normalized, ("from", "departing"))
    if origin is None:
        for alias, code in STATION_ALIASES.items():
            if f"{alias} departures" in normalized:
                origin = code
                break
    destination = _station_after(normalized, ("to",))
    if origin is None:
        route_match = re.search(r"\b([a-z]+)\s+to\s+([a-z]+)\b", normalized)
        if route_match:
            origin = STATION_ALIASES.get(route_match.group(1))
            destination = STATION_ALIASES.get(route_match.group(2))
    if origin:
        filters["origin"] = origin
    if destination:
        filters["destination"] = destination
    aircraft_type = re.search(r"\b(A320|ATR72)\b", query, re.IGNORECASE)
    tail = re.search(r"\bVT-[A-Z0-9]+\b", query, re.IGNORECASE)
    if aircraft_type:
        filters["aircraft_type"] = aircraft_type.group(1).upper()
    if tail:
        filters["aircraft"] = tail.group(0).upper()

    if "distinct destination" in normalized or "unique arrival station" in normalized:
        return {
            "resource": "flights", "filters": filters, "fields": ["destination"],
            "aggregation": {"function": "distinct", "field": "destination"},
            "sort": ["destination"], "limit": 500,
        }
    if "average block" in normalized or "mean scheduled block" in normalized:
        return {
            "resource": "flights", "filters": filters, "fields": ["block_hours"],
            "aggregation": {"function": "avg", "field": "block_hours"}, "limit": 500,
        }
    if "total seat capacity" in normalized or "sum the seats" in normalized:
        return {
            "resource": "flights", "filters": filters, "fields": ["seats"],
            "aggregation": {"function": "sum", "field": "seats"}, "limit": 500,
        }
    top_limit = _top_limit(normalized)
    if "longest" in normalized or "by block hour" in normalized:
        return {
            "resource": "flights", "filters": filters, "fields": ["flight_no", "block_hours"],
            "sort": ["-block_hours", "flight_no"], "limit": top_limit or 5,
        }
    if "how many" in normalized or "count" in normalized or "total number" in normalized:
        return {
            "resource": "flights", "filters": filters, "fields": ["flight_id"],
            "aggregation": {"function": "count"}, "limit": 500,
        }
    if tail:
        return {
            "resource": "flights", "filters": filters,
            "fields": ["flight_id", "origin", "destination"], "sort": ["flight_id"], "limit": 500,
        }
    return {
        "resource": "flights", "filters": filters,
        "fields": ["flight_id", "flight_no", "dep_utc"], "sort": ["dep_utc"], "limit": 500,
    }


def _crew_plan(normalized: str) -> dict[str, Any]:
    filters = _base_filters(normalized)
    station = _mentioned_station(normalized)
    if station:
        filters["base"] = station
    rating = re.search(r"\b(A320|ATR72)\b", normalized, re.IGNORECASE)
    if rating and any(term in normalized for term in ("rating", "rated", "qualified on")):
        filters["rating"] = rating.group(1).upper()
    if "distinct" in normalized or "unique base" in normalized:
        return {
            "resource": "crew", "filters": filters, "fields": ["base"],
            "aggregation": {"function": "distinct", "field": "base"}, "sort": ["base"], "limit": 500,
        }
    if "average seniority" in normalized or "mean seniority" in normalized:
        return {
            "resource": "crew", "filters": filters, "fields": ["seniority"],
            "aggregation": {"function": "avg", "field": "seniority"}, "limit": 500,
        }
    top_limit = _top_limit(normalized)
    if "shortest reachability" in normalized or "quickest" in normalized:
        return {
            "resource": "crew", "filters": filters,
            "fields": ["crew_id", "name", "rank", "reachability_minutes"],
            "sort": ["reachability_minutes", "name"], "limit": top_limit or 5,
        }
    fields = ["crew_id", "name"] if _rank(normalized) else ["crew_id", "name", "rank", "base"]
    plan: dict[str, Any] = {
        "resource": "crew", "filters": filters, "fields": fields, "sort": ["name"], "limit": 500,
    }
    if "how many" in normalized or "count" in normalized:
        if "rating" in filters:
            plan["fields"] = ["crew_id", "name", "rank"]
            plan["sort"] = ["rank", "name"]
        plan["aggregation"] = {"function": "count"}
    if filters.get("status") == "leave":
        plan["fields"] = ["crew_id", "name", "rank", "base"]
        plan["sort"] = ["base", "rank", "name"]
    return plan


def _pairing_plan(query: str, normalized: str) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    query_date = _date_from_query(query)
    pairing = re.search(r"\bP-\d+\b", query, re.IGNORECASE)
    tail = re.search(r"\bVT-[A-Z0-9]+\b", query, re.IGNORECASE)
    if query_date:
        filters["date"] = query_date
    if pairing:
        filters["pairing_id"] = pairing.group(0).upper()
    if tail:
        filters["aircraft"] = tail.group(0).upper()
    if "how many" in normalized or "count" in normalized:
        return {
            "resource": "pairings", "filters": filters, "fields": ["pairing_id"],
            "aggregation": {"function": "count"}, "sort": ["pairing_id"], "limit": 500,
        }
    if pairing:
        fields = ["pairing_id", "date", "report_utc", "release_utc", "flights_json"]
    else:
        fields = ["pairing_id", "date", "flights_json"]
    return {"resource": "pairings", "filters": filters, "fields": fields, "sort": ["date"], "limit": 500}


def _reserve_plan(query: str, normalized: str) -> dict[str, Any]:
    filters = _base_filters(normalized)
    filters.pop("status", None)
    query_date = _date_from_query(query)
    station = _mentioned_station(normalized)
    if query_date:
        filters["date"] = query_date
    if station:
        filters["base"] = station
    if "unique" in normalized or "which bases" in normalized:
        return {
            "resource": "reserves", "filters": filters, "fields": ["base"],
            "aggregation": {"function": "distinct", "field": "base"}, "sort": ["base"], "limit": 500,
        }
    fields = ["crew_id", "name", "on_call_start", "on_call_end"] if _rank(normalized) else [
        "crew_id", "name", "rank", "on_call_start", "on_call_end"
    ]
    plan: dict[str, Any] = {
        "resource": "reserves", "filters": filters, "fields": fields,
        "sort": ["on_call_start", "crew_id"], "limit": 500,
    }
    if "how many" in normalized or "count" in normalized:
        plan["aggregation"] = {"function": "count"}
    return plan


def _certification_plan(query: str, normalized: str) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    crew = re.search(r"\bC-\d+\b", query, re.IGNORECASE)
    if crew:
        filters["crew_id"] = crew.group(0).upper()
    plan: dict[str, Any] = {
        "resource": "certifications", "filters": filters,
        "fields": ["cert_type", "valid_to"], "sort": ["cert_type"], "limit": 500,
    }
    plan["aggregation"] = {"function": "count"}
    return plan


def _risk_plan(normalized: str) -> dict[str, Any]:
    if ("maximum" in normalized or "highest" in normalized) and _top_limit(normalized) is None:
        return {
            "resource": "risk_signals", "fields": ["score"],
            "aggregation": {"function": "max", "field": "score"}, "limit": 500,
        }
    return {
        "resource": "risk_signals", "fields": ["crew_id", "name", "rank", "base", "score"],
        "sort": ["-score", "crew_id"], "limit": _top_limit(normalized) or 5,
    }


def _duty_plan(normalized: str) -> dict[str, Any]:
    filters = _base_filters(normalized)
    station = _mentioned_station(normalized)
    if station:
        filters["base"] = station
    if "average" in normalized or "mean" in normalized:
        return {
            "resource": "crew_duty", "filters": filters, "fields": ["duty_hours_7d"],
            "aggregation": {"function": "avg", "field": "duty_hours_7d"},
            "sort": ["duty_hours_7d"], "limit": 500,
            "as_of_date": SNAPSHOT_DATE.isoformat(), "window_days": 7,
        }
    plan: dict[str, Any] = {
        "resource": "crew_duty", "filters": filters,
        "fields": ["crew_id", "name", "rank", "duty_hours_7d"],
        "sort": ["duty_hours_7d", "name"], "limit": 500,
        "as_of_date": SNAPSHOT_DATE.isoformat(), "window_days": 7,
    }
    threshold = _threshold(normalized)
    if threshold:
        operator, value = threshold
        plan["aggregation"] = {"metric": "duty_hours_7d", "operator": operator, "value": value}
        if operator in (">", ">="):
            plan["sort"] = ["-duty_hours_7d"]
    if "highest" in normalized or "top" in normalized:
        plan["sort"] = ["-duty_hours_7d", "name"]
        plan["limit"] = _top_limit(normalized) or 5
    return plan


def plan_tier1_query(query: str) -> dict[str, Any] | None:
    """Translate a supported Tier 1 question into an allowlisted query plan."""
    normalized = " ".join(query.lower().replace("-based", " based").split())
    if "duty" in normalized and any(term in normalized for term in ("week", "weekly", "seven-day", "7-day", "rolling")):
        return _duty_plan(normalized)
    if "reserve" in normalized:
        return _reserve_plan(query, normalized)
    if any(term in normalized for term in ("certification", "certifications", "certificate")):
        return _certification_plan(query, normalized)
    if "risk" in normalized:
        return _risk_plan(normalized)
    if "pairing" in normalized or re.search(r"\bP-\d+\b", query, re.IGNORECASE):
        return _pairing_plan(query, normalized)
    if "crew" in normalized or any(term in normalized for term, _ in RANK_TERMS):
        return _crew_plan(normalized)
    if any(term in normalized for term in ("flight", "sector", "departure", "destination", "arrival station", "seat capacity", "block time", "block hour")):
        return _flight_plan(query, normalized)
    return None


def _unsupported_reason(query: str) -> str | None:
    normalized = " ".join(query.lower().split())
    if any(term in normalized for term in ("predict", "forecast")):
        return "The snapshot contains current risk signals but no validated future-absence forecasting model."
    if "not assigned" in normalized or "without a pairing" in normalized:
        return "The current Tier 1 query plan does not support anti-joins between crew and pairing assignments."
    if re.search(r"\bgroup\b.*\bby\b", normalized) or "grouped" in normalized or ("compare" in normalized and "average" in normalized):
        return "The current Tier 1 query plan does not support grouped or cross-group comparative aggregation."
    if "between" in normalized or re.search(r"\b(?:more|less|greater) than\s+\d+\s+seats?\b", normalized):
        return "The current Tier 1 query plan supports exact flight filters, but not date ranges or numeric flight comparisons."
    return None


def _display_value(value: Any) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, separators=(",", ":"))
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def _render_result(query: str, result: dict[str, Any]) -> str:
    aggregation = result.get("aggregation")
    if result["resource"] == "crew_duty" and not aggregation:
        summary = f"Found **{result['count']} crew members** matching the rolling duty criteria."
    elif aggregation:
        function = aggregation["function"]
        value = aggregation["value"]
        if function == "count":
            summary = f"Found **{value} matching records**."
        elif function == "distinct":
            summary = f"Found **{aggregation['count']} distinct values**: {_display_value(value)}."
        else:
            summary = f"The **{function} {aggregation['field']}** is **{_display_value(value)}**."
    else:
        summary = f"Found **{result['count']} matching records**."

    show_rows = not aggregation or any(term in query.lower() for term in ("list", "show", "which", "who"))
    rows = result["rows"] if show_rows else []
    if not rows:
        return summary + "\n\nResult calculated deterministically from SQLite."

    fields = list(rows[0])
    lines = [summary, "", "| " + " | ".join(field.replace("_", " ").title() for field in fields) + " |"]
    lines.append("|" + "|".join("---" for _ in fields) + "|")
    lines.extend("| " + " | ".join(_display_value(row[field]) for field in fields) + " |" for row in rows)
    lines.extend(["", "Result calculated deterministically from SQLite."])
    return "\n".join(lines)


def route_tier1_query(query: str) -> dict[str, Any] | None:
    """Plan, execute, and render a generalized Tier 1 query without an LLM."""
    unsupported_reason = _unsupported_reason(query)
    if unsupported_reason:
        response = f"I cannot answer that query with the current deterministic Tier 1 plan. {unsupported_reason}"
        return {
            "messages": [AIMessage(content=response)],
            "tool_calls": [],
            "tool_results": [],
            "reasoning_trace": [
                "Deterministic Tier 1 planner identified an unsupported query operation",
                unsupported_reason,
                "Returned an explicit limitation without querying partial data or inventing a result",
            ],
            "final_response": response,
        }
    plan = plan_tier1_query(query)
    if plan is None:
        return None
    result = query_operations(**plan)
    response = _render_result(query, result)
    return {
        "messages": [AIMessage(content=response)],
        "tool_calls": [{"name": "query_operations", "args": plan, "id": "deterministic_tier1_plan"}],
        "tool_results": [{"tool_name": "query_operations", "args": plan, "result": result}],
        "reasoning_trace": [
            f"Deterministic Tier 1 planner selected the {result['resource']} resource",
            "Validated fields, filters, aggregation, sorting, and row limit against the allowlist",
            f"Executed query_operations and retrieved {result['count']} SQLite record(s)",
            "Rendered the operational response without an external LLM call",
        ],
        "final_response": response,
    }
