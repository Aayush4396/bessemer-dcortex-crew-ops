"""
src/rules/validators/fdp.py
===========================
RULE-FDP-01: Flight Duty Period limits.
Max FDP = 13h - 0.5h per sector beyond the 2nd sector.
"""

from ..config import FDP_BASE_HOURS, FDP_FREE_SECTORS, FDP_REDUCTION_PER_EXTRA_SECTOR
from ..models import RuleResult


def check_fdp(sectors: int, fdp_hours: float) -> RuleResult:
    """
    Evaluates Flight Duty Period limit against number of sectors flown.
    Sectors 1-2: 13h | 3: 12.5h | 4: 12h | 5: 11.5h | ...

    Parameters
    ----------
    sectors : int
        Number of flight legs in this duty period.
    fdp_hours : float
        Elapsed duty time in hours (release_utc - report_utc).

    Returns
    -------
    RuleResult
        Evaluation verdict with breach magnitude and detailed explanation.
    """
    extra_sectors = max(0, sectors - FDP_FREE_SECTORS)
    limit = FDP_BASE_HOURS - FDP_REDUCTION_PER_EXTRA_SECTOR * extra_sectors
    breach = round(fdp_hours - limit, 4)

    if breach > 1e-6:
        return RuleResult(
            rule_id="RULE-FDP-01",
            passed=False,
            detail=f"FDP {fdp_hours:.2f}h exceeds {sectors}-sector limit {limit:.1f}h by {breach:.2f}h",
            breach=breach,
        )

    return RuleResult(
        rule_id="RULE-FDP-01",
        passed=True,
        detail=f"FDP {fdp_hours:.2f}h within {sectors}-sector limit {limit:.1f}h",
    )
