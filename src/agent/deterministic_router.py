"""Deterministic routing for operational intents that do not require an LLM."""

import re
from typing import Any

from langchain_core.messages import AIMessage

from src.rules.models import SNAPSHOT_DATE
from src.tier1 import query_operations


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


def route_deterministic_query(query: str) -> dict[str, Any] | None:
    """Return a complete graph-state update when a deterministic intent matches."""
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
