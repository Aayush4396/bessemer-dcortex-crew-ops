"""
tests/test_rules.py
====================
Unit tests for the modular deterministic legality rules engine.

All test cases use known facts from:
  - data/scenarios.json answer keys
  - README engineered facts
  - data/questions.json expected answers

Run:
    python -m pytest tests/test_rules.py -v
    # or without pytest:
    python tests/test_rules.py
"""

import json
import sys
from datetime import date
from pathlib import Path

# Make sure src/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.loader import init_db
from src.rules.engine import check_crew_legality, check_crew_legality_for_pairing
from src.rules.models import ALL_RULE_IDS, SNAPSHOT_DATE, LegalityReport, RuleResult
from src.rules.operational import check_reserve_window, check_schedule_overlap
from src.rules.time_utils import calculate_duty_period, calculate_rolling_sum, parse_date, parse_utc
from src.rules.validators import (
    check_base,
    check_certifications,
    check_downstream_rest,
    check_duty_7d,
    check_fdp,
    check_flight_28d,
    check_qualification,
    check_rest,
)


def test_fdp_limits():
    """RULE-FDP-01: Flight Duty Period limits based on number of sectors."""
    # 1-2 sectors: limit 13h
    r = check_fdp(sectors=2, fdp_hours=12.9)
    assert r.passed
    assert "13.0" in r.detail

    r = check_fdp(sectors=2, fdp_hours=13.1)
    assert not r.passed
    assert abs(r.breach - 0.1) <= 0.01

    # 3 sectors: limit 12.5h
    r = check_fdp(sectors=3, fdp_hours=12.5)
    assert r.passed

    r = check_fdp(sectors=3, fdp_hours=12.6)
    assert not r.passed

    # 4 sectors: limit 12.0h
    r = check_fdp(sectors=4, fdp_hours=12.0)
    assert r.passed

    r = check_fdp(sectors=4, fdp_hours=12.01)
    assert not r.passed

    # 5 sectors: limit 11.5h
    r = check_fdp(sectors=5, fdp_hours=11.5)
    assert r.passed

    # P-2201 (VT-DXA, 4 flights): report 01:30Z, release 12:45Z -> FDP = 11.25h
    r = check_fdp(sectors=4, fdp_hours=11.25)
    assert r.passed


def test_duty_7d_limits():
    """RULE-DUTY-02: 60h max in any 7 consecutive calendar days."""
    conn = init_db()

    # C-2087 covering P-2291 -> RULE-DUTY-02 breach by 1h20m (61.33h total)
    r = check_duty_7d(conn, "C-2087", 10.75, date(2026, 9, 15))
    assert not r.passed
    assert r.breach > 0

    # C-3310 covering P-2291: should PASS
    r = check_duty_7d(conn, "C-3310", 10.75, date(2026, 9, 15))
    assert r.passed

    # C-1042 snapshot rolling 7d sum = 20.93h
    h7 = calculate_rolling_sum(conn, "C-1042", date(2026, 9, 14), 7, "duty_hours")
    assert abs(h7 - 20.93) <= 0.05


def test_flight_28d_limits():
    """RULE-FLT-03: 100h max flight hours in 28 consecutive calendar days."""
    conn = init_db()

    # C-1042 flight_hours_28d snapshot = 64.27. Adding 40h should fail (104.27h > 100h)
    r = check_flight_28d(conn, "C-1042", 40.0, date(2026, 9, 14))
    assert not r.passed

    # Adding 5h should pass (69.27h < 100h)
    r = check_flight_28d(conn, "C-1042", 5.0, date(2026, 9, 14))
    assert r.passed


def test_rest_limits():
    """RULE-REST-04: Minimum 12h rest between release and next report."""
    # 48h rest -> PASS
    r = check_rest("2026-09-13T02:00:00Z", "2026-09-15T02:00:00Z")
    assert r.passed

    # 11h rest -> FAIL
    r = check_rest("2026-09-15T01:00:00Z", "2026-09-15T12:00:00Z")
    assert not r.passed
    assert abs(r.breach - 1.0) <= 0.05

    # Exactly 12h -> PASS
    r = check_rest("2026-09-15T00:00:00Z", "2026-09-15T12:00:00Z")
    assert r.passed

    # No prior rest record -> PASS
    r = check_rest(None, "2026-09-15T06:00:00Z")
    assert r.passed


def test_qualification_limits():
    """RULE-QUAL-05: Aircraft type rating validation."""
    # C-1042 is A320-rated -> can fly A320
    r = check_qualification(["A320"], "A320")
    assert r.passed

    # C-2091 is ATR72-only -> cannot fly A320
    r = check_qualification(["ATR72"], "A320")
    assert not r.passed
    assert "A320" in r.detail

    # A320-only on ATR72 -> FAIL
    r = check_qualification(["A320"], "ATR72")
    assert not r.passed

    # Dual-rated crew -> PASS
    r = check_qualification(["A320", "ATR72"], "ATR72")
    assert r.passed

    # S1 exclusion case: C-1042 on ATR72 -> FAIL
    r = check_qualification(["A320"], "ATR72")
    assert not r.passed


def test_certifications_limits():
    """RULE-CERT-06: All certifications valid on duty date."""
    conn = init_db()

    # C-1042: all certs valid well past 2026-09-15
    r = check_certifications(conn, "C-1042", date(2026, 9, 15))
    assert r.passed

    # C-2087: licence expires 2026-09-18. On 2026-09-15 -> still valid
    r = check_certifications(conn, "C-2087", date(2026, 9, 15))
    assert r.passed

    # C-2087 on 2026-09-19 -> FAIL
    r = check_certifications(conn, "C-2087", date(2026, 9, 19))
    assert not r.passed
    assert "licence" in r.detail

    # C-5417: recurrent_training expires 2026-09-17. On expiry day -> PASS
    r = check_certifications(conn, "C-5417", date(2026, 9, 17))
    assert r.passed

    # C-5417 on 2026-09-18 -> FAIL
    r = check_certifications(conn, "C-5417", date(2026, 9, 18))
    assert not r.passed


def test_base_geometry():
    """RULE-BASE-07: Base geometry and deadhead advisory."""
    # Same base -> PASS (no deadhead)
    r = check_base("BLR", "BLR")
    assert r.passed

    # Cross-base -> FAIL with breach=0.0 (cost flag)
    r = check_base("DEL", "BLR")
    assert not r.passed
    assert r.breach == 0.0
    assert "deadhead" in r.detail.lower()


def test_operational_constraints():
    """Operational constraints: schedule overlap, downstream rest, reserve window."""
    conn = init_db()

    # Overlap check
    overlap_r = check_schedule_overlap(conn, "C-1042", "2026-09-15T05:00:00Z", "2026-09-15T09:00:00Z")
    assert overlap_r is not None and not overlap_r.passed

    no_overlap_r = check_schedule_overlap(conn, "C-1042", "2026-09-17T08:00:00Z", "2026-09-17T12:00:00Z")
    assert no_overlap_r is None

    # Downstream rest
    downstream_r = check_downstream_rest(conn, "C-1042", "2026-09-15T23:00:00Z")
    assert downstream_r is not None and not downstream_r.passed

    # Reserve window
    res_win_none = check_reserve_window(conn, "C-1042", "2026-09-15T05:00:00Z", "2026-09-15")
    assert res_win_none is None


def test_legality_integration():
    """check_crew_legality() pipeline integration tests."""
    conn = init_db()

    p2291_day1 = {
        "pairing_id": "P-2291",
        "duty_date": "2026-09-15",
        "report_utc": "2026-09-15T02:00:00Z",
        "release_utc": "2026-09-15T12:45:00Z",
        "sectors": 3,
        "block_hours": 8.25,
        "aircraft_type": "A320",
        "dep_station": "BLR",
    }

    # C-2087 on P-2291 -> is_legal=False (RULE-DUTY-02 breach)
    res_2087 = check_crew_legality("C-2087", p2291_day1, conn)
    assert not res_2087["is_legal"]
    assert any(v["rule"] == "RULE-DUTY-02" for v in res_2087["violations"])
    assert len(res_2087["rules_checked"]) == 7

    # C-3310 on P-2291 -> is_legal=True
    res_3310 = check_crew_legality("C-3310", p2291_day1, conn)
    assert res_3310["is_legal"]
    assert len(res_3310["rules_checked"]) == 7
    assert len(res_3310["violations"]) == 0

    # C-2091 (ATR72-only) on P-2291 (A320) -> FAIL QUAL-05
    res_2091 = check_crew_legality("C-2091", p2291_day1, conn)
    assert not res_2091["is_legal"]
    assert any(v["rule"] == "RULE-QUAL-05" for v in res_2091["violations"])

    # C-3315 on P-2224 (ATR72) -> is_legal=True
    p2224_day1 = {
        "pairing_id": "P-2224",
        "duty_date": "2026-09-16",
        "report_utc": "2026-09-16T01:30:00Z",
        "release_utc": "2026-09-16T12:45:00Z",
        "sectors": 4,
        "block_hours": 6.5,
        "aircraft_type": "ATR72",
        "dep_station": "BLR",
    }
    res_3315 = check_crew_legality("C-3315", p2224_day1, conn)
    assert res_3315["is_legal"]


def test_multiday_pairings():
    """check_crew_legality_for_pairing() multi-day evaluation tests."""
    conn = init_db()

    # C-3310 covering full 2-day P-2291 -> is_legal=True
    res_3310 = check_crew_legality_for_pairing("C-3310", "P-2291", conn)
    assert res_3310["is_legal"]
    assert len(res_3310["violations"]) == 0

    # C-2087 covering full 2-day P-2291 -> is_legal=False
    res_2087 = check_crew_legality_for_pairing("C-2087", "P-2291", conn)
    assert not res_2087["is_legal"]
    assert len(res_2087["violations"]) > 0

    # Q24 benchmark: C-3305 Day 1 alone -> LEGAL; full 2-day -> FAILS Day 2
    res_3305_d1 = check_crew_legality_for_pairing("C-3305", "P-2291", conn, duty_date="2026-09-15")
    assert res_3305_d1["is_legal"]

    res_3305_full = check_crew_legality_for_pairing("C-3305", "P-2291", conn)
    assert not res_3305_full["is_legal"]
    d2_breach = [
        v for v in res_3305_full["violations"]
        if "2026-09-16" in v.get("date", "") or "2026-09-16" in v.get("detail", "")
    ]
    assert any(v["rule"] == "RULE-DUTY-02" for v in d2_breach)


if __name__ == "__main__":
    test_fdp_limits()
    print("  [PASS] test_fdp_limits")
    test_duty_7d_limits()
    print("  [PASS] test_duty_7d_limits")
    test_flight_28d_limits()
    print("  [PASS] test_flight_28d_limits")
    test_rest_limits()
    print("  [PASS] test_rest_limits")
    test_qualification_limits()
    print("  [PASS] test_qualification_limits")
    test_certifications_limits()
    print("  [PASS] test_certifications_limits")
    test_base_geometry()
    print("  [PASS] test_base_geometry")
    test_operational_constraints()
    print("  [PASS] test_operational_constraints")
    test_legality_integration()
    print("  [PASS] test_legality_integration")
    test_multiday_pairings()
    print("  [PASS] test_multiday_pairings")
    print("\nALL RULE ENGINE TESTS PASSED")
