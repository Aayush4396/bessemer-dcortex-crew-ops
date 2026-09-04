"""
src/rules/models.py
===================
Core domain data models and constants for the legality rules engine.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

SNAPSHOT_DATE = date(2026, 9, 14)

ALL_RULE_IDS = [
    "RULE-FDP-01",
    "RULE-DUTY-02",
    "RULE-FLT-03",
    "RULE-REST-04",
    "RULE-QUAL-05",
    "RULE-CERT-06",
    "RULE-BASE-07",
]


@dataclass
class RuleResult:
    """Individual rule evaluation verdict."""
    rule_id: str
    passed: bool
    detail: str
    breach: float = 0.0  # Amount by which limit was exceeded (0.0 if passed or cost flag)


@dataclass
class LegalityReport:
    """Full legality evaluation report for a proposed crew assignment."""
    crew_id: str
    is_legal: bool
    rules_checked: list[str] = field(default_factory=list)
    violations: list[dict[str, Any]] = field(default_factory=list)
    advisories: list[dict[str, Any]] = field(default_factory=list)
    rule_results: list[RuleResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical dict shape for LLM routing and explainability schemas."""
        return {
            "crew_id": self.crew_id,
            "is_legal": self.is_legal,
            "rules_checked": self.rules_checked,
            "violations": self.violations,
            "advisories": self.advisories,
        }
