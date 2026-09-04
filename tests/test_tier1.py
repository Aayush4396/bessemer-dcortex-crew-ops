"""
tests/test_tier1.py
===================
Unit tests for all 16 Tier 1 benchmark questions (Q01-Q16) from data/questions.json.
Validates the 9 deterministic query handlers in src/tier1.py.
Zero LLM involvement — purely deterministic assertions against expected answers.
"""

import json
import sqlite3
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.db.loader import init_db
from src.tier1 import (
    get_reserves_at_station,
    get_crew_duty_balance,
    get_departures,
    get_expiring_certifications,
    get_flights,
    get_flight_schedule_stats,
    get_crew_profile,
    get_pairing_roster,
    get_crew_risk_signal,
)

# Load benchmark questions
_DATA_DIR = Path(__file__).parent.parent / "data"
_QUESTIONS_FILE = _DATA_DIR / "questions.json"
_QUESTIONS = json.loads(_QUESTIONS_FILE.read_text(encoding="utf-8"))
_Q_MAP = {q["question_id"]: q for q in _QUESTIONS}


@pytest.fixture(scope="session")
def conn():
    """In-memory SQLite database initialized with all datasets."""
    return init_db()


def test_q01_reserves_at_blr(conn):
    """Q01: Who is on reserve at BLR on 2026-09-15, and what are their on-call windows?"""
    expected = _Q_MAP["Q01"]["expected_answer"]
    actual = get_reserves_at_station(station="BLR", date="2026-09-15", conn=conn)
    assert len(actual) == len(expected)
    assert actual == expected


def test_q02_c1042_duty_balance(conn):
    """Q02: As of the snapshot, how many duty hours has C-1042 accrued in 7d ending 2026-09-14, and headroom?"""
    expected = _Q_MAP["Q02"]["expected_answer"]
    res = get_crew_duty_balance(crew_id="C-1042", as_of_date="2026-09-14", conn=conn)
    assert res["duty_hours_7d"] == expected["duty_hours_7d"]
    assert res["headroom_hours"] == expected["headroom_hours"]


def test_q03_departures_del(conn):
    """Q03: Which flights depart DEL on 2026-09-15?"""
    expected = _Q_MAP["Q03"]["expected_answer"]
    actual = get_departures(station="DEL", date="2026-09-15", conn=conn)
    assert actual == expected


def test_q04_expiring_certifications(conn):
    """Q04: List all certifications expiring within 30 days of 2026-09-15."""
    expected = _Q_MAP["Q04"]["expected_answer"]
    actual = get_expiring_certifications(as_of_date="2026-09-15", days_ahead=30, conn=conn)
    assert len(actual) == len(expected)
    assert actual == expected


def test_q05_flight_dx412_details(conn):
    """Q05: Which aircraft operates DX412 on 2026-09-15, and how many seats does it have?"""
    expected = _Q_MAP["Q05"]["expected_answer"]
    flights = get_flights(date="2026-09-15", flight_no="DX412", conn=conn)
    assert len(flights) == 1
    f = flights[0]
    assert f["aircraft"] == expected["aircraft"]
    assert f["aircraft_type"] == expected["aircraft_type"]
    assert f["seats"] == expected["seats"]


def test_q06_c3310_reserve_reachability(conn):
    """Q06: What is C-3310's reserve on-call window and reachability?"""
    expected = _Q_MAP["Q06"]["expected_answer"]
    profile = get_crew_profile(crew_id="C-3310", conn=conn)
    assert profile["window"] == expected["window"]
    assert profile["reachability_minutes"] == expected["reachability_minutes"]


def test_q07_c2210_base_rating(conn):
    """Q07: What is C-2210's base and rating?"""
    expected = _Q_MAP["Q07"]["expected_answer"]
    profile = get_crew_profile(crew_id="C-2210", conn=conn)
    assert profile["base"] == expected["base"]
    assert profile["ratings"] == expected["ratings"]


def test_q08_pairing_p2291_roster(conn):
    """Q08: Which crew are assigned to pairing P-2291, and in what roles?"""
    expected = _Q_MAP["Q08"]["expected_answer"]
    actual = get_pairing_roster(pairing_id="P-2291", conn=conn)
    assert len(actual) == len(expected)
    assert actual == expected


def test_q09_flights_blr_bom(conn):
    """Q09: Which flights fly BLR->BOM on 2026-09-17?"""
    expected = _Q_MAP["Q09"]["expected_answer"]
    flights = get_flights(date="2026-09-17", origin="BLR", destination="BOM", conn=conn)
    actual = [f["flight_no"] for f in flights]
    assert actual == expected


def test_q10_flight_count_sep16(conn):
    """Q10: How many flights operate on 2026-09-16 in total?"""
    expected = _Q_MAP["Q10"]["expected_answer"]
    flights = get_flights(date="2026-09-16", conn=conn)
    assert len(flights) == expected


def test_q11_captains_at_del(conn):
    """Q11: How many captains are based at DEL, and who are they?"""
    expected = _Q_MAP["Q11"]["expected_answer"]
    profiles = get_crew_profile(rank="Captain", base="DEL", conn=conn)
    actual = [p["crew_id"] for p in profiles]
    assert actual == expected


def test_q12_longest_block_time(conn):
    """Q12: What is the longest block time in the schedule, and which flights have it?"""
    expected = _Q_MAP["Q12"]["expected_answer"]
    actual = get_flight_schedule_stats(metric="longest_block", conn=conn)
    assert actual["block_hours"] == expected["block_hours"]
    assert sorted(actual["flights"]) == sorted(expected["flights"])


def test_q13_c2087_flight_hours_28d(conn):
    """Q13: What is C-2087's rank, and total flight hours over 28d ending 2026-09-14?"""
    expected = _Q_MAP["Q13"]["expected_answer"]
    res = get_crew_duty_balance(crew_id="C-2087", as_of_date="2026-09-14", conn=conn)
    assert res["rank"] == expected["rank"]
    assert res["flight_hours_28d"] == expected["flight_hours_28d"]


def test_q14_nonstop_from_blr(conn):
    """Q14: Which stations does the network serve nonstop from BLR?"""
    expected = _Q_MAP["Q14"]["expected_answer"]
    actual = get_flights(origin="BLR", distinct_destinations=True, conn=conn)
    assert actual == expected


def test_q15_scc_vt_dxb_sep16(conn):
    """Q15: Who is the Senior Cabin Crew on VT-DXB's pairing on 2026-09-16?"""
    expected = _Q_MAP["Q15"]["expected_answer"]
    actual = get_pairing_roster(aircraft="VT-DXB", date="2026-09-16", role="Senior Cabin Crew", conn=conn)
    assert actual == expected


def test_q16_c1042_risk_signal(conn):
    """Q16: What is the disruption-risk score for C-1042 and what drives it?"""
    expected = _Q_MAP["Q16"]["expected_answer"]
    actual = get_crew_risk_signal(crew_id="C-1042", conn=conn)
    assert actual["score"] == expected["score"]
    assert actual["drivers"] == expected["drivers"]


if __name__ == "__main__":
    db_conn = init_db()
    test_funcs = [
        ("Q01 (BLR reserves)", test_q01_reserves_at_blr),
        ("Q02 (C-1042 7d duty & headroom)", test_q02_c1042_duty_balance),
        ("Q03 (DEL departures)", test_q03_departures_del),
        ("Q04 (Expiring certifications)", test_q04_expiring_certifications),
        ("Q05 (DX412 aircraft & seats)", test_q05_flight_dx412_details),
        ("Q06 (C-3310 reserve reachability)", test_q06_c3310_reserve_reachability),
        ("Q07 (C-2210 base & rating)", test_q07_c2210_base_rating),
        ("Q08 (P-2291 crew roster)", test_q08_pairing_p2291_roster),
        ("Q09 (BLR->BOM flights on Sep 17)", test_q09_flights_blr_bom),
        ("Q10 (Sep 16 total flight count)", test_q10_flight_count_sep16),
        ("Q11 (Captains based at DEL)", test_q11_captains_at_del),
        ("Q12 (Longest block time)", test_q12_longest_block_time),
        ("Q13 (C-2087 rank & 28d flight hours)", test_q13_c2087_flight_hours_28d),
        ("Q14 (Nonstop destinations from BLR)", test_q14_nonstop_from_blr),
        ("Q15 (VT-DXB SCC on Sep 16)", test_q15_scc_vt_dxb_sep16),
        ("Q16 (C-1042 risk score & drivers)", test_q16_c1042_risk_signal),
    ]

    print("=" * 60)
    print("RUNNING TIER 1 BENCHMARK TESTS (Q01-Q16)")
    print("=" * 60)
    passed = 0
    failed = 0
    for name, fn in test_funcs:
        try:
            fn(db_conn)
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1

    print("=" * 60)
    print(f"Result: {passed} PASSED / {failed} FAILED")
    print("=" * 60)
    if failed:
        sys.exit(1)
    print("\nALL 16 TIER 1 BENCHMARK QUESTIONS PASSED!")
