"""
src/rules/validators/qualification.py
=====================================
RULE-QUAL-05: Aircraft type rating validation.
RULE-CERT-06: Medical and line check certification validity on duty date.
"""

import sqlite3
from datetime import date

from ..models import RuleResult


def check_qualification(crew_ratings: list[str], aircraft_type: str) -> RuleResult:
    """
    Verifies crew member holds a valid type rating for the aircraft type.

    Parameters
    ----------
    crew_ratings : list[str]
        List of ratings held by crew, e.g. ["A320"].
    aircraft_type : str
        Aircraft type of the flight, e.g. "A320" or "ATR72".

    Returns
    -------
    RuleResult
        Evaluation verdict with breach=1.0 if not rated.
    """
    if aircraft_type in crew_ratings:
        return RuleResult(
            rule_id="RULE-QUAL-05",
            passed=True,
            detail=f"Crew holds {aircraft_type} rating",
        )

    return RuleResult(
        rule_id="RULE-QUAL-05",
        passed=False,
        detail=f"RULE-QUAL-05: no {aircraft_type} rating (holds: {crew_ratings})",
        breach=1.0,
    )


def check_certifications(
    conn: sqlite3.Connection,
    crew_id: str,
    duty_date: date,
) -> RuleResult:
    """
    Verifies all certifications (medical, line check, etc.) are valid on the duty date.
    Validity is evaluated as: valid_to >= duty_date.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active DB connection.
    crew_id : str
        Crew identifier, e.g. "C-1042".
    duty_date : date
        Date of the duty assignment.

    Returns
    -------
    RuleResult
        Evaluation verdict with list of expired certifications if any.
    """
    rows = conn.execute(
        """
        SELECT cert_type, valid_to
        FROM certifications
        WHERE crew_id = ?
        """,
        (crew_id,),
    ).fetchall()

    expired = []
    for cert_type, valid_to_str in rows:
        valid_to = date.fromisoformat(valid_to_str)
        if valid_to < duty_date:
            expired.append(f"{cert_type} expired {valid_to_str}")

    if expired:
        return RuleResult(
            rule_id="RULE-CERT-06",
            passed=False,
            detail=f"RULE-CERT-06: {', '.join(expired)}",
            breach=float(len(expired)),
        )

    return RuleResult(
        rule_id="RULE-CERT-06",
        passed=True,
        detail=f"All certifications valid on {duty_date}",
    )
