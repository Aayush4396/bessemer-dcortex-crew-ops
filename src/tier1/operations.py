"""
Generalized, allowlisted operational query service.

This module accepts a typed query shape from the agent and translates it into
parameterized SQLite queries or existing deterministic duty calculations. It
does not execute caller-provided SQL.
"""

import json
import operator
import sqlite3
from datetime import date
from typing import Any, Callable

from src.rules.config import DUTY_MAX_HOURS, DUTY_WINDOW_DAYS
from src.rules.time_utils import calculate_rolling_sum

from .connection import get_connection

MAX_QUERY_LIMIT = 500

RESOURCE_FIELDS: dict[str, dict[str, str]] = {
    "flights": {
        "flight_id": "f.flight_id",
        "flight_no": "f.flight_no",
        "date": "f.date",
        "origin": "f.dep_station",
        "destination": "f.arr_station",
        "dep_station": "f.dep_station",
        "arr_station": "f.arr_station",
        "dep_utc": "f.dep_utc",
        "arr_utc": "f.arr_utc",
        "block_hours": "f.block_hours",
        "aircraft": "f.aircraft",
        "aircraft_type": "f.aircraft_type",
        "seats": "f.seats",
    },
    "crew": {
        "crew_id": "c.crew_id",
        "name": "c.name",
        "rank": "c.rank",
        "base": "c.base",
        "rating": "c.ratings",
        "status": "c.status",
        "seniority": "c.seniority",
        "reachability_minutes": "c.reachability_minutes",
    },
    "pairings": {
        "pairing_id": "p.pairing_id",
        "aircraft": "p.aircraft",
        "date": "p.date",
        "report_utc": "p.report_utc",
        "release_utc": "p.release_utc",
        "flights_json": "p.flights_json",
    },
    "reserves": {
        "crew_id": "rp.crew_id",
        "name": "c.name",
        "rank": "c.rank",
        "base": "rp.base",
        "date": "rp.date",
        "on_call_start": "rp.on_call_start",
        "on_call_end": "rp.on_call_end",
    },
    "certifications": {
        "crew_id": "cert.crew_id",
        "name": "c.name",
        "rank": "c.rank",
        "cert_type": "cert.cert_type",
        "valid_from": "cert.valid_from",
        "valid_to": "cert.valid_to",
    },
    "risk_signals": {
        "crew_id": "rs.crew_id",
        "name": "c.name",
        "rank": "c.rank",
        "base": "c.base",
        "score": "rs.disruption_risk_score",
        "disruption_risk_score": "rs.disruption_risk_score",
        "as_of_utc": "rs.as_of_utc",
        "drivers": "rs.drivers_json",
    },
}

RESOURCE_TABLES = {
    "flights": ("flights f", ""),
    "crew": ("crew c", ""),
    "pairings": ("pairings p", ""),
    "reserves": ("reserve_pool rp JOIN crew c ON c.crew_id = rp.crew_id", "c.status = 'active'"),
    "certifications": ("certifications cert JOIN crew c ON c.crew_id = cert.crew_id", ""),
    "risk_signals": ("risk_signals rs JOIN crew c ON c.crew_id = rs.crew_id", ""),
}

SORT_FIELDS = {
    field: expression
    for fields in RESOURCE_FIELDS.values()
    for field, expression in fields.items()
}

COMPARATORS: dict[str, Callable[[Any, Any], bool]] = {
    "=": operator.eq,
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


def _validate_resource(resource: str) -> None:
    if resource not in RESOURCE_FIELDS and resource != "crew_duty":
        supported = sorted([*RESOURCE_FIELDS, "crew_duty"])
        raise ValueError(f"Unsupported resource {resource!r}; supported resources: {supported}")


def _validate_limit(limit: int) -> int:
    if limit < 1 or limit > MAX_QUERY_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_QUERY_LIMIT}")
    return limit


def _validate_filters(resource: str, filters: dict[str, Any]) -> None:
    if resource == "crew_duty":
        allowed = {"crew_id", "name", "rank", "base", "rating", "status"}
    else:
        allowed = set(RESOURCE_FIELDS[resource])
    unknown = sorted(set(filters) - allowed)
    if unknown:
        raise ValueError(f"Unsupported {resource} filter field(s): {unknown}")


def _where_clause(resource: str, filters: dict[str, Any]) -> tuple[str, list[Any]]:
    fields = RESOURCE_FIELDS[resource]
    clauses: list[str] = []
    params: list[Any] = []

    for field, value in filters.items():
        expression = fields[field]
        if field == "rating":
            values = value if isinstance(value, list) else [value]
            for rating in values:
                clauses.append(f'{expression} LIKE ?')
                params.append(f'%"{rating}"%')
            continue
        if isinstance(value, list):
            if not value:
                clauses.append("1 = 0")
                continue
            placeholders = ",".join("?" for _ in value)
            clauses.append(f"{expression} IN ({placeholders})")
            params.extend(value)
        else:
            clauses.append(f"{expression} = ?")
            params.append(value)

    return (" AND ".join(clauses), params)


def _select_fields(resource: str, fields: list[str] | None) -> list[str]:
    available = RESOURCE_FIELDS[resource]
    selected = fields or list(available)
    unknown = sorted(set(selected) - set(available))
    if unknown:
        raise ValueError(f"Unsupported {resource} field(s): {unknown}")
    return selected


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _row_value(row: sqlite3.Row, field: str) -> Any:
    value = row[field]
    if field in {"rating", "ratings", "drivers", "drivers_json", "flights_json"}:
        return _json_value(value)
    if field in {"block_hours", "score", "disruption_risk_score"} and value is not None:
        return float(value)
    return value


def _query_rows(
    resource: str,
    filters: dict[str, Any],
    fields: list[str] | None,
    sort: list[str] | None,
    limit: int,
    conn: sqlite3.Connection,
) -> list[dict[str, Any]]:
    selected = _select_fields(resource, fields)
    table, base_condition = RESOURCE_TABLES[resource]
    select_sql = ", ".join(f"{RESOURCE_FIELDS[resource][field]} AS {field}" for field in selected)
    where, params = _where_clause(resource, filters)
    conditions = [condition for condition in (base_condition, where) if condition]
    where_sql = f" WHERE {' AND '.join(conditions)}" if conditions else ""

    order_fields = sort or [selected[0]]
    order_sql_parts = []
    for item in order_fields:
        descending = item.startswith("-")
        field = item[1:] if descending else item
        if field not in RESOURCE_FIELDS[resource]:
            raise ValueError(f"Unsupported {resource} sort field {field!r}")
        order_sql_parts.append(f"{RESOURCE_FIELDS[resource][field]} {'DESC' if descending else 'ASC'}")
    order_sql = ", ".join(order_sql_parts)

    rows = conn.execute(
        f"SELECT {select_sql} FROM {table}{where_sql} ORDER BY {order_sql} LIMIT ?",
        (*params, limit),
    ).fetchall()
    return [{field: _row_value(row, field) for field in selected} for row in rows]


def _aggregate_rows(
    rows: list[dict[str, Any]],
    aggregation: dict[str, Any],
) -> dict[str, Any]:
    function = aggregation.get("function", aggregation.get("op"))
    field = aggregation.get("field")
    if function == "count":
        return {"function": "count", "field": field, "value": len(rows)}
    if function == "distinct":
        if not field:
            raise ValueError("distinct aggregation requires a field")
        values = list(dict.fromkeys(row[field] for row in rows))
        return {"function": "distinct", "field": field, "value": values, "count": len(values)}
    if function in {"sum", "min", "max", "avg", "average"}:
        if not field:
            raise ValueError(f"{function} aggregation requires a field")
        values = [row[field] for row in rows if row[field] is not None]
        if not values:
            value = None
        elif function == "sum":
            value = sum(values)
        elif function == "min":
            value = min(values)
        elif function == "max":
            value = max(values)
        else:
            value = sum(values) / len(values)
        return {"function": function, "field": field, "value": value, "count": len(values)}
    raise ValueError("aggregation function must be count, distinct, sum, min, max, or avg")


def _crew_duty_rows(
    filters: dict[str, Any],
    fields: list[str] | None,
    aggregation: dict[str, Any] | None,
    sort: list[str] | None,
    limit: int,
    as_of_date: str,
    window_days: int,
    conn: sqlite3.Connection,
) -> list[dict[str, Any]]:
    _validate_filters("crew_duty", filters)
    selected = fields or ["crew_id", "name", "rank", "base", "duty_hours_7d", "headroom_hours"]
    allowed_fields = {
        "crew_id", "name", "rank", "base", "status", "duty_hours_7d", "headroom_hours",
        "flight_hours", "flight_headroom_hours",
    }
    unknown = sorted(set(selected) - allowed_fields)
    if unknown:
        raise ValueError(f"Unsupported crew_duty field(s): {unknown}")
    if window_days not in (DUTY_WINDOW_DAYS, 28):
        raise ValueError("crew_duty window_days must be 7 or 28")

    crew_where, params = _where_clause("crew", filters)
    conditions = f" WHERE {crew_where}" if crew_where else ""
    crew_rows = conn.execute(
        f"SELECT c.crew_id, c.name, c.rank, c.base, c.status FROM crew c{conditions} ORDER BY c.crew_id ASC",
        tuple(params),
    ).fetchall()

    end_date = date.fromisoformat(as_of_date)
    result: list[dict[str, Any]] = []
    for row in crew_rows:
        duty_hours = round(
            calculate_rolling_sum(
                conn,
                row["crew_id"],
                end_date,
                DUTY_WINDOW_DAYS,
                "duty_hours",
            ),
            2,
        )
        flight_hours = round(
            calculate_rolling_sum(conn, row["crew_id"], end_date, 28, "flight_hours"),
            2,
        )
        values = {
            "crew_id": row["crew_id"],
            "name": row["name"],
            "rank": row["rank"],
            "base": row["base"],
            "status": row["status"],
            "duty_hours_7d": duty_hours,
            "headroom_hours": round(DUTY_MAX_HOURS - duty_hours, 2),
            "flight_hours": flight_hours,
            "flight_headroom_hours": round(100.0 - flight_hours, 2),
        }
        if aggregation and "function" not in aggregation and "op" not in aggregation:
            metric = aggregation.get("metric", "duty_hours_7d")
            comparison = aggregation.get("operator", "=")
            threshold = aggregation.get("value")
            if metric not in values or comparison not in COMPARATORS or threshold is None:
                raise ValueError("aggregation requires a valid metric, operator, and value")
            if not COMPARATORS[comparison](values[metric], threshold):
                continue
        result.append({field: values[field] for field in selected})

    order_fields = sort or ["crew_id"]
    for item in reversed(order_fields):
        descending = item.startswith("-")
        field = item[1:] if descending else item
        if field not in allowed_fields:
            raise ValueError(f"Unsupported crew_duty sort field {field!r}")
        result.sort(key=lambda record: (record[field] is None, record[field]), reverse=descending)
    return result[:limit]


def query_operations(
    resource: str,
    filters: dict[str, Any] | None = None,
    fields: list[str] | None = None,
    aggregation: dict[str, Any] | None = None,
    sort: list[str] | None = None,
    limit: int = 100,
    as_of_date: str = "2026-09-14",
    window_days: int = 7,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Execute an allowlisted generalized operational query.

    Filters use equality or list membership. Aggregation supports threshold
    filtering with ``metric``, ``operator``, and ``value``. Sort fields use
    normal names for ascending order and a ``-`` prefix for descending order.
    """
    _validate_resource(resource)
    filters = filters or {}
    limit = _validate_limit(limit)
    c = get_connection(conn)

    aggregate_result = None
    if resource == "crew_duty":
        threshold_aggregation = (
            aggregation
            if aggregation and "function" not in aggregation and "op" not in aggregation
            else None
        )
        rows = _crew_duty_rows(filters, fields, threshold_aggregation, sort, limit, as_of_date, window_days, c)
        if aggregation and ("function" in aggregation or "op" in aggregation):
            aggregate_result = _aggregate_rows(rows, aggregation)
    else:
        _validate_filters(resource, filters)
        rows = _query_rows(resource, filters, fields, sort, limit, c)
        if aggregation:
            aggregate_result = _aggregate_rows(rows, aggregation)

    return {
        "resource": resource,
        "as_of_date": as_of_date,
        "window_days": window_days if resource == "crew_duty" else None,
        "filters": filters,
        "count": len(rows),
        "rows": rows,
        "aggregation": aggregate_result,
    }
