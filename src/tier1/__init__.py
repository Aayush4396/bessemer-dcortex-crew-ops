"""
src/tier1/__init__.py
=====================
Clean public domain export of Tier 1 deterministic query handlers.
"""

from .cert_queries import get_expiring_certifications
from .connection import get_connection
from .crew_queries import get_crew_profile, get_reserves_at_station
from .duty_queries import get_crew_duty_balance
from .flight_queries import (
    get_arrivals,
    get_departures,
    get_flight_schedule_stats,
    get_flights,
)
from .risk_queries import get_crew_risk_signal
from .entity_detail import get_crew_detail, get_flight_detail, list_crew
from .pairings_workspace import get_pairing, get_pairings_workspace
from .roster_queries import get_pairing_roster
from .operations import query_operations

__all__ = [
    "get_flights",
    "get_departures",
    "get_arrivals",
    "get_flight_schedule_stats",
    "get_crew_profile",
    "get_reserves_at_station",
    "get_pairing_roster",
    "get_pairings_workspace",
    "get_pairing",
    "get_flight_detail",
    "get_crew_detail",
    "list_crew",
    "get_crew_duty_balance",
    "get_expiring_certifications",
    "get_crew_risk_signal",
    "query_operations",
    "get_connection",
]
