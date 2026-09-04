"""
src/rules/validators/base.py
============================
RULE-BASE-07: Reserve callout base alignment and deadhead cost flag.
Cross-base assignment is allowed in ops recovery but triggers deadhead + delay cost.
"""

from ..models import RuleResult


def check_base(crew_base: str, flight_dep_station: str) -> RuleResult:
    """
    Evaluates whether flight departure station matches crew domicile.

    RULE-BASE-07 is an informational cost flag in ops recovery:
    - If bases match: passed=True, no deadhead required.
    - If cross-base: passed=False with breach=0.0 (signals cost penalty in Tier 3,
      not an outright disqualification for legality).

    Parameters
    ----------
    crew_base : str
        Home domicile of the crew member, e.g. "BOM".
    flight_dep_station : str
        Departure airport of the duty, e.g. "DEL".

    Returns
    -------
    RuleResult
        Evaluation verdict with breach=0.0 on cross-base.
    """
    if crew_base == flight_dep_station:
        return RuleResult(
            rule_id="RULE-BASE-07",
            passed=True,
            detail=f"Crew based at {crew_base} — same as departure station",
        )

    return RuleResult(
        rule_id="RULE-BASE-07",
        passed=False,
        detail=(
            f"Crew based at {crew_base}, flight departs {flight_dep_station} — "
            f"deadhead positioning required (cost applies)"
        ),
        breach=0.0,
    )
