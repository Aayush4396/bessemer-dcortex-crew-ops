"""
src/tier2
=========
Deterministic Tier 2 entity lookups and per-rule legality checks.
"""

from .entities import (
    get_cost_rates,
    get_crew_entity,
    get_flight_duty_times,
    get_pairing_entity,
    get_station_movements,
    load_pairing_days,
)
from .sql import execute_readonly_sql
from .rules import (
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
)

__all__ = [
    "get_pairing_entity",
    "get_flight_duty_times",
    "get_crew_entity",
    "get_station_movements",
    "get_cost_rates",
    "load_pairing_days",
    "evaluate_fdp_limit",
    "evaluate_duty_7d",
    "evaluate_flight_28d",
    "evaluate_rest",
    "evaluate_qualification",
    "evaluate_certifications",
    "evaluate_base_positioning",
    "evaluate_reserve_callout",
    "evaluate_cover",
    "evaluate_cover_candidates",
    "execute_readonly_sql",
]
