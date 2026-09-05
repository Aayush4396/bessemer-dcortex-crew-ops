"""
src/tier2/models.py
===================
Data models and schemas for Tier 2 Disruption Simulation.
"""

from typing import Any, Literal
from pydantic import BaseModel, Field


DisruptionType = Literal["SICK_CREW", "STATION_CLOSURE", "DELAY", "CERT_EXPIRY", "MULTI_SICK"]


class FlightAssessment(BaseModel):
    """Impact assessment for an individual flight affected by disruption."""
    flight_id: str
    pairing_id: str | None = None
    min_delay_hours: float = 0.0
    crew_fdp_after_delay: float | None = None
    fdp_limit: float | None = None
    action: str = ""


class SickCrewImpact(BaseModel):
    """Impact result for a crew incapacitation or sick call."""
    disruption_type: Literal["SICK_CREW"] = "SICK_CREW"
    crew_id: str
    pairing_id: str
    reported_utc: str
    role: str
    rank: str
    aircraft_type: str
    is_multi_day: bool = False
    uncovered_flights: list[str] = Field(default_factory=list)
    uncovered_flights_day1: list[str] = Field(default_factory=list)
    uncovered_flights_day2: list[str] = Field(default_factory=list)
    passengers_at_risk: int = 0
    passengers_at_risk_day1: int = 0
    details: dict[str, Any] = Field(default_factory=dict)


class StationClosureImpact(BaseModel):
    """Impact result for an airport station closure."""
    disruption_type: Literal["STATION_CLOSURE"] = "STATION_CLOSURE"
    station: str
    window_utc: dict[str, str]
    affected_flights: list[str] = Field(default_factory=list)
    per_flight_assessment: list[dict[str, Any]] = Field(default_factory=list)
    note: str = ""


class FlightDelayImpact(BaseModel):
    """Impact result for a flight/aircraft technical delay."""
    disruption_type: Literal["DELAY"] = "DELAY"
    aircraft: str
    date: str
    delay_hours: float
    flight_no: str | None = None
    affected_legs: list[str] = Field(default_factory=list)
    scheduled_fdp: float = 0.0
    fdp_after_delay: float = 0.0
    fdp_limit: float = 12.0
    breach: bool = False
    breach_detail: str = ""


class CertExpiryImpact(BaseModel):
    """Impact result for an expired qualification or certification."""
    disruption_type: Literal["CERT_EXPIRY"] = "CERT_EXPIRY"
    crew_id: str
    pairing_id: str
    reported_utc: str
    role: str
    rank: str
    date: str
    lapsed_cert: str
    illegal_assignment: dict[str, Any] = Field(default_factory=dict)
    uncovered_flights: list[str] = Field(default_factory=list)
    passengers_at_risk: int = 0


class MultiSickImpact(BaseModel):
    """Impact result for multiple concurrent sick crew calls."""
    disruption_type: Literal["MULTI_SICK"] = "MULTI_SICK"
    events: list[dict[str, Any]]
    sub_impacts: list[dict[str, Any]]
    uncovered_flights_total: list[str] = Field(default_factory=list)
    passengers_at_risk_total: int = 0
