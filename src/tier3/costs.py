"""
src/tier3/costs.py
==================
Cost configuration loader and financial evaluation helpers for Tier 3.
Loads financial parameters from `data/costs.json`.
"""

import json
from pathlib import Path
from typing import Any

# Default root path for dataset
_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_COSTS_FILE = _DATA_DIR / "costs.json"

_DEFAULT_COSTS = {
    "currency": "INR",
    "reserve_callout_pilot": 18500,
    "reserve_callout_cabin": 9500,
    "dayoff_callout_pilot": 24000,
    "dayoff_callout_cabin": 12500,
    "deadhead_positioning": 6500,
    "delay_cost_per_duty_hour": 5400,
    "cancellation_per_flight": 250000,
    "hotel_overnight": 4200,
}


def load_costs() -> dict[str, Any]:
    """Loads operational cost parameters from costs.json."""
    if _COSTS_FILE.exists():
        try:
            with open(_COSTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return dict(_DEFAULT_COSTS)
    return dict(_DEFAULT_COSTS)


COSTS = load_costs()


def compute_callout_cost(
    is_reserve: bool,
    is_pilot: bool,
    has_deadhead: bool = False,
    delay_hours: float = 0.0,
) -> int:
    """
    Computes total INR cost for a crew assignment according to costs.json:
    Cost = Callout Fee + Deadhead Positioning (if applicable) + (Delay Hours * Hourly Delay Rate)
    """
    costs = load_costs()
    if is_reserve:
        base_fee = costs["reserve_callout_pilot"] if is_pilot else costs["reserve_callout_cabin"]
    else:
        base_fee = costs["dayoff_callout_pilot"] if is_pilot else costs["dayoff_callout_cabin"]

    total = base_fee
    if has_deadhead:
        total += costs["deadhead_positioning"]
        total += int(round(delay_hours * costs["delay_cost_per_duty_hour"]))

    return int(round(total))


def compute_cancellation_cost(flight_count: int) -> int:
    """Computes total cost of cancelling flight legs."""
    costs = load_costs()
    return int(costs["cancellation_per_flight"] * flight_count)
