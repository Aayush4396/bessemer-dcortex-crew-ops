"""
src/rules/__init__.py
=====================
Deterministic legality rules engine for dCortex Crew Ops Advisor.
"""

from .engine import check_crew_legality, check_crew_legality_for_pairing
from .models import ALL_RULE_IDS, SNAPSHOT_DATE, LegalityReport, RuleResult
from .validators import (
    check_base,
    check_certifications,
    check_downstream_rest,
    check_duty_7d,
    check_fdp,
    check_flight_28d,
    check_qualification,
    check_rest,
)

__all__ = [
    "check_crew_legality",
    "check_crew_legality_for_pairing",
    "RuleResult",
    "LegalityReport",
    "ALL_RULE_IDS",
    "SNAPSHOT_DATE",
    "check_fdp",
    "check_duty_7d",
    "check_flight_28d",
    "check_rest",
    "check_downstream_rest",
    "check_qualification",
    "check_certifications",
    "check_base",
]
