"""
tests/test_scenarios.py
=======================
Full benchmark regression test suite for questions Q17-Q38 and scenarios S1-S6.
Validates all Tier 2 simulation cascades, Tier 3 recovery optimizations, rule exclusions,
financial costing, and generalizability across all ranks, stations, aircraft, and delay profiles.
"""

import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.db.loader import init_db
from src.rules import check_rest
from src.rules.engine import check_crew_legality_for_pairing
from src.tier1.duty_queries import get_crew_duty_balance
from src.tier1.flight_queries import get_flights
from src.tier2 import simulate_disruption
from src.tier3 import (
    find_cover_options,
    generate_callout_notification,
    optimize_recovery,
    solve_delay_fdp_breach,
    solve_joint_optimization,
)


@pytest.fixture(scope="session")
def conn():
    """In-memory database initialized with datasets."""
    return init_db()


# ---------------------------------------------------------------------------
# Tier 2 Benchmark Questions (Q17 - Q30)
# ---------------------------------------------------------------------------

def test_q17_p2291_sick_cascade(conn):
    """Q17: Captain C-1042 sick on P-2291 (2-day pairing)."""
    event = {
        "type": "SICK_CREW",
        "crew_id": "C-1042",
        "pairing_id": "P-2291",
        "reported_utc": "2026-09-15T05:00:00Z",
    }
    res = simulate_disruption(event, conn=conn)

    assert res["is_multi_day"] is True
    assert len(res["uncovered_flights"]) == 6
    assert len(res["uncovered_flights_day1"]) == 3
    assert len(res["uncovered_flights_day2"]) == 3
    assert res["passengers_at_risk_day1"] == 486
    assert res["passengers_at_risk"] == 972


def test_q18_c2087_p2291_legality(conn):
    """Q18: If Captain C-2087 is assigned to cover P-2291, breaches RULE-DUTY-02 (> 60h/7d)."""
    res = check_crew_legality_for_pairing("C-2087", "P-2291", conn)
    assert res["is_legal"] is False
    assert any(v["rule"] == "RULE-DUTY-02" for v in res["violations"])


def test_q19_blr_station_closure(conn):
    """Q19: BLR closed 08:00-14:00Z on 17 Sep. 13 flights affected."""
    event = {
        "type": "STATION_CLOSURE",
        "station": "BLR",
        "date": "2026-09-17",
        "window_utc": {"start": "08:00", "end": "14:00"},
    }
    res = simulate_disruption(event, conn=conn)
    assert len(res["affected_flights"]) == 13
    flight_nos = {f.split("-")[0] for f in res["affected_flights"]}
    assert "DX402" in flight_nos
    assert "DX422" in flight_nos
    assert "DX462" in flight_nos
    assert "DX588" in flight_nos


def test_q20_vtdxa_delay_breach(conn):
    """Q20: VT-DXA delayed 90 min on 16 Sep. Crew breaches FDP limit on 4-sector duty."""
    event = {
        "type": "DELAY",
        "aircraft": "VT-DXA",
        "date": "2026-09-16",
        "delay_hours": 1.5,
    }
    res = simulate_disruption(event, conn=conn)
    assert res["breach"] is True
    assert res["scheduled_fdp"] == 11.25
    assert res["fdp_after_delay"] == 12.75
    assert res["fdp_limit"] == 12.0


def test_q21_c2210_deadhead_positioning(conn):
    """Q21: C-2210 (DEL base) deadheads to BLR on DX402 to cover P-2291."""
    opts, excluded = find_cover_options(
        pairing_id="P-2291",
        role="Captain",
        sick_crew_id="C-1042",
        conn=conn,
    )
    c2210_opt = next((o for o in opts if o["crew_id"] == "C-2210"), None)
    assert c2210_opt is not None
    assert c2210_opt["legal"] is True
    assert c2210_opt["delay_hours"] == 3.0
    assert c2210_opt["cost_inr"] == 41200
    assert "deadhead from DEL" in c2210_opt["action"]


def test_q22_c5417_cert_expiry(conn):
    """Q22: C-5417 recurrent training expired on 17 Sep; cannot operate on 19 Sep."""
    event = {
        "type": "CERT_EXPIRY",
        "crew_id": "C-5417",
        "date": "2026-09-19",
        "pairing_id": "P-2213",
    }
    res = simulate_disruption(event, conn=conn)
    assert res["disruption_type"] == "CERT_EXPIRY"
    assert res["lapsed_cert"] == "recurrent_training"
    assert res["illegal_assignment"]["crew_id"] == "C-5417"


def test_q23_rest_window(conn):
    """Q23: Crew released at 15:30Z on 16 Sep; earliest next report is 03:30Z on 17 Sep (12h)."""
    res_pass = check_rest(
        last_release_utc="2026-09-16T15:30:00Z",
        next_report_utc="2026-09-17T03:30:00Z",
    )
    assert res_pass.passed is True

    # 11 hours rest breaches
    res_fail = check_rest(
        last_release_utc="2026-09-16T15:30:00Z",
        next_report_utc="2026-09-17T02:30:00Z",
    )
    assert res_fail.passed is False


def test_q24_c3305_p2291_rolling_window(conn):
    """Q24: Reserve C-3305 cannot cover full 2-day P-2291 because 7d duty breaches on day 2."""
    res = check_crew_legality_for_pairing("C-3305", "P-2291", conn)
    assert res["is_legal"] is False
    assert any(v["rule"] == "RULE-DUTY-02" for v in res["violations"])


def test_q25_flight_cancellation_cost_and_seats(conn):
    """Q25: Cancelling DX404 on 16 Sep affects 162 seats and costs ₹250,000."""
    flights = get_flights(flight_no="DX404", date="2026-09-16", conn=conn)
    assert len(flights) == 1
    assert flights[0]["seats"] == 162

    res = solve_delay_fdp_breach(
        aircraft="VT-DXA",
        date="2026-09-16",
        delay_hours=1.5,
        conn=conn,
    )
    cancel_opt = next(o for o in res["options"] if o["rank"] == 2)
    assert cancel_opt["cost_inr"] == 250000


def test_q26_duty_hours_high_headroom_risk(conn):
    """Q26: C-2087 and C-3305 have >= 45h duty in 7d ending 2026-09-15."""
    c2087_bal = get_crew_duty_balance("C-2087", "2026-09-15", conn)
    c3305_bal = get_crew_duty_balance("C-3305", "2026-09-15", conn)

    assert c2087_bal["duty_hours_7d"] >= 45.0
    assert c3305_bal["duty_hours_7d"] >= 45.0


def test_q27_vtdxe_atr_reserve_cover(conn):
    """Q27: VT-DXE ATR captain sick callout at 01:30Z. C-3315 is eligible; C-3305/C-3310 excluded."""
    res = optimize_recovery({
        "type": "SICK_CREW",
        "crew_id": "C-3231",
        "pairing_id": "P-2224",
        "reported_utc": "2026-09-16T01:30:00Z",
    }, conn=conn)

    assert res["expected_choice"]["crew_id"] == "C-3315"
    excluded_map = {e["crew_id"]: e["reason"] for e in res["excluded_candidates"]}
    assert "C-3305" in excluded_map
    assert "RULE-QUAL-05" in excluded_map["C-3305"]
    assert "C-3310" in excluded_map
    assert "RULE-QUAL-05" in excluded_map["C-3310"]


def test_q28_c5837_downstream_rest_conflict(conn):
    """Q28: C-5837 covering P-2291 has downstream rest conflict before P-2204 on 17 Sep."""
    res = check_crew_legality_for_pairing("C-5837", "P-2291", conn)
    assert res["is_legal"] is False
    assert any(v["rule"] == "RULE-REST-04" for v in res["violations"])


def test_q29_hyd_station_closure(conn):
    """Q29: HYD closure 05:00-09:00Z on 19 Sep affects DX461 and DX462."""
    event = {
        "type": "STATION_CLOSURE",
        "station": "HYD",
        "date": "2026-09-19",
        "window_utc": {"start": "05:00", "end": "09:00"},
    }
    res = simulate_disruption(event, conn=conn)
    assert len(res["affected_flights"]) == 2
    flight_nos = {f.split("-")[0] for f in res["affected_flights"]}
    assert flight_nos == {"DX461", "DX462"}


# ---------------------------------------------------------------------------
# Tier 3 Benchmark Questions (Q31 - Q37)
# ---------------------------------------------------------------------------

def test_q31_p2291_ranked_recovery_options(conn):
    """Q31: Ranked resolution options for P-2291 with costs and reasoning."""
    res = optimize_recovery({
        "type": "SICK_CREW",
        "crew_id": "C-1042",
        "pairing_id": "P-2291",
        "reported_utc": "2026-09-15T05:00:00Z",
    }, conn=conn)

    assert len(res["options"]) == 6
    assert res["options"][0]["crew_id"] == "C-3310"
    assert res["options"][0]["cost_inr"] == 18500
    assert res["options"][0]["delay_hours"] == 0.0

    # Day-off options
    assert res["options"][1]["cost_inr"] == 24000
    assert res["options"][2]["cost_inr"] == 24000
    assert res["options"][3]["cost_inr"] == 24000

    # Deadhead option
    assert res["options"][4]["crew_id"] == "C-2210"
    assert res["options"][4]["cost_inr"] == 41200
    assert res["options"][4]["delay_hours"] == 3.0

    # Cancellation fallback
    assert res["options"][5]["crew_id"] is None
    assert res["options"][5]["cost_inr"] == 1500000


def test_q32_s6_joint_combinatorial_optimization(conn):
    """Q32: S6 joint optimization for VT-DXA and VT-DXB sick captains."""
    events = [
        {"crew_id": "C-3940", "pairing_id": "P-2205", "reported_utc": "2026-09-18T00:30:00Z"},
        {"crew_id": "C-1938", "pairing_id": "P-2212", "reported_utc": "2026-09-18T00:30:00Z"},
    ]
    res = solve_joint_optimization(events, conn=conn)
    joint_plan = res["optimal_joint_plan"]
    assert joint_plan["total_cost_inr"] == 42500
    assert joint_plan["assign_dxa"]["crew_id"] != joint_plan["assign_dxb"]["crew_id"]
    costs = {joint_plan["assign_dxa"]["cost_inr"], joint_plan["assign_dxb"]["cost_inr"]}
    assert costs == {18500, 24000}


def test_q33_s4_delay_recovery_tradeoff(conn):
    """Q33: VT-DXA 90-min delay recovery trade-off (Reserve set @ ₹75k vs Cancel @ ₹250k)."""
    res = solve_delay_fdp_breach("VT-DXA", "2026-09-16", 1.5, conn=conn)
    assert len(res["options"]) == 2
    assert res["options"][0]["cost_inr"] == 75000
    assert res["options"][0]["rank"] == 1
    assert res["options"][1]["cost_inr"] == 250000
    assert res["options"][1]["rank"] == 2


def test_q34_s5_cert_expiry_recovery(conn):
    """Q34: C-5417 cert expiry recovery. C-4809 cabin reserve callout @ ₹9,500."""
    res = optimize_recovery({
        "type": "CERT_EXPIRY",
        "crew_id": "C-5417",
        "pairing_id": "P-2213",
        "date": "2026-09-19",
    }, conn=conn)

    assert res["expected_choice"]["crew_id"] == "C-4809"
    assert res["expected_choice"]["cost_inr"] == 9500
    assert res["expected_choice"]["delay_hours"] == 0.0


def test_q35_s3_station_closure_impact_assessment(conn):
    """Q35: BLR station closure recovery assessment across 13 flights."""
    res = simulate_disruption({
        "type": "STATION_CLOSURE",
        "station": "BLR",
        "date": "2026-09-17",
        "window_utc": {"start": "08:00", "end": "14:00"},
    }, conn=conn)

    assessments = res["per_flight_assessment"]
    assert len(assessments) == 13
    assert all("min_delay_hours" in a for a in assessments)
    assert all("crew_fdp_after_delay" in a for a in assessments)
    assert all("action" in a for a in assessments)


def test_q36_callout_notification_generation(conn):
    """Q36: Structured dispatch notification to C-3310 for covering P-2291."""
    notif = generate_callout_notification("C-3310", "P-2291", conn)
    assert len(notif["must_include"]) >= 5
    text = notif["message_text"]
    assert "C-3310" in text
    assert "P-2291" in text
    assert "06:00Z" in text
    assert "DX412" in text
    assert "Radisson Blu" in text
    assert "05:15Z" in text


def test_q37_vtdxf_first_officer_generalization(conn):
    """Q37: VT-DXF First Officer sick call on 20 Sep. C-3316 ATR FO reserve @ ₹18,500."""
    res = optimize_recovery({
        "type": "SICK_CREW",
        "role": "First Officer",
        "pairing_id": "P-2235",
        "reported_utc": "2026-09-20T03:30:00Z",
    }, conn=conn)

    assert res["expected_choice"]["crew_id"] == "C-3316"
    assert res["expected_choice"]["cost_inr"] == 18500
    assert res["expected_choice"]["delay_hours"] == 0.0
