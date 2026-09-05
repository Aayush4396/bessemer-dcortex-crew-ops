"""
tests/test_tier3.py
===================
Unit tests for Tier 3 Recovery Optimizer against operational scenarios S1-S6,
held-out benchmark scenarios H1, and questions Q31-Q37.
"""

import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.db.loader import init_db
from src.tier3 import (
    find_cover_options,
    generate_callout_notification,
    optimize_recovery,
    solve_delay_fdp_breach,
    solve_joint_optimization,
)


@pytest.fixture(scope="session")
def conn():
    """In-memory or connection to initialized crew_ops database."""
    return init_db()


def test_scenario_s1_atr_captain_recovery(conn):
    """S1: ATR captain C-3231 sick call recovery."""
    event = {
        "type": "SICK_CREW",
        "crew_id": "C-3231",
        "pairing_id": "P-2224",
        "reported_utc": "2026-09-16T01:30:00Z",
    }
    res = optimize_recovery(event, conn=conn)

    assert len(res["options"]) == 7
    assert res["expected_choice"]["crew_id"] == "C-3315"
    assert res["expected_choice"]["cost_inr"] == 18500
    assert res["expected_choice"]["rank"] == 1
    assert "reserve callout" in res["expected_choice"]["action"]

    # Fallback option is pairing cancellation
    assert res["options"][-1]["crew_id"] is None
    assert res["options"][-1]["cost_inr"] == 1000000


def test_scenario_s2_flagship_captain_recovery_multiday(conn):
    """S2: Flagship captain C-1042 sick call for 2-day pairing P-2291."""
    event = {
        "type": "SICK_CREW",
        "crew_id": "C-1042",
        "pairing_id": "P-2291",
        "reported_utc": "2026-09-15T05:00:00Z",
    }
    res = optimize_recovery(event, conn=conn)

    assert len(res["options"]) == 6
    assert res["expected_choice"]["crew_id"] == "C-3310"
    assert res["expected_choice"]["cost_inr"] == 18500

    # Verify deadhead positioning candidate C-2210 from DEL
    dh_opt = next(o for o in res["options"] if o["crew_id"] == "C-2210")
    assert dh_opt["cost_inr"] == 41200
    assert dh_opt["delay_hours"] == 3.0
    assert "deadhead from DEL" in dh_opt["action"]

    # Verify excluded candidates
    exc_map = {e["crew_id"]: e["reason"] for e in res["excluded_candidates"]}
    assert "C-2087" in exc_map
    assert "RULE-DUTY-02" in exc_map["C-2087"]
    assert "C-3305" in exc_map
    assert "reserve on-call window" in exc_map["C-3305"]
    assert "C-2091" in exc_map
    assert "RULE-QUAL-05" in exc_map["C-2091"]


def test_scenario_s4_delay_fdp_breach_recovery(conn):
    """S4: Tech delay causes FDP breach on 4th leg; reserve set operates tail leg."""
    event = {
        "type": "DELAY",
        "aircraft": "VT-DXA",
        "date": "2026-09-16",
        "delay_hours": 1.5,
    }
    res = optimize_recovery(event, conn=conn)

    assert len(res["options"]) == 2
    top = res["expected_choice"]
    assert top["rank"] == 1
    assert top["cost_inr"] == 75000
    assert "DX404" in top["action"]

    # Rank 2 is cancellation of tail leg
    cancel_opt = res["options"][1]
    assert cancel_opt["cost_inr"] == 250000


def test_scenario_s5_cert_expiry_recovery(conn):
    """S5: Cabin crew C-5417 cert lapse on VT-DXB 19 Sep."""
    event = {
        "type": "CERT_EXPIRY",
        "crew_id": "C-5417",
        "pairing_id": "P-2213",
        "reported_utc": "2026-09-18T10:00:00Z",
    }
    res = optimize_recovery(event, conn=conn)

    assert len(res["options"]) == 43
    assert res["expected_choice"]["crew_id"] == "C-4809"
    assert res["expected_choice"]["cost_inr"] == 9500


def test_scenario_s6_joint_multi_sick_optimization(conn):
    """S6: Two captains sick simultaneously (VT-DXA and VT-DXB on 18 Sep)."""
    event = {
        "type": "MULTI_SICK",
        "events": [
            {"crew_id": "C-3940", "pairing_id": "P-2205", "reported_utc": "2026-09-18T00:30:00Z"},
            {"crew_id": "C-1938", "pairing_id": "P-2212", "reported_utc": "2026-09-18T00:30:00Z"},
        ],
    }
    res = optimize_recovery(event, conn=conn)

    joint_plan = res["optimal_joint_plan"]
    assert joint_plan["total_cost_inr"] == 42500
    assert joint_plan["assign_dxa"]["crew_id"] != joint_plan["assign_dxb"]["crew_id"]
    # One reserve (18500) + one day-off (24000)
    costs = {joint_plan["assign_dxa"]["cost_inr"], joint_plan["assign_dxb"]["cost_inr"]}
    assert costs == {18500, 24000}


def test_held_out_h1_first_officer_generalization(conn):
    """H1: ATR First Officer sick call recovery on 16 Sep."""
    p_row = conn.execute("SELECT pairing_id FROM pairings WHERE date = '2026-09-16' AND aircraft = 'VT-DXE'").fetchone()
    fo_id = conn.execute("SELECT crew_id FROM pairing_crew WHERE pairing_id = ? AND role = 'First Officer'", (p_row['pairing_id'],)).fetchone()['crew_id']

    event = {
        "type": "SICK_CREW",
        "crew_id": fo_id,
        "pairing_id": p_row['pairing_id'],
        "role": "First Officer",
        "reported_utc": "2026-09-16T02:00:00Z",
    }
    res = optimize_recovery(event, conn=conn)

    assert res["expected_choice"]["crew_id"] == "C-3316"
    assert res["expected_choice"]["cost_inr"] == 18500


def test_senior_cabin_crew_recovery_generalization(conn):
    """Generalization: SCC recovery for 02:00Z report when no reserves on call early -> falls back to day-off."""
    p_scc = conn.execute("SELECT pairing_id FROM pairings WHERE date = '2026-09-15' AND aircraft = 'VT-DXB'").fetchone()
    scc_id = conn.execute("SELECT crew_id FROM pairing_crew WHERE pairing_id = ? AND role = 'Senior Cabin Crew'", (p_scc['pairing_id'],)).fetchone()['crew_id']

    event = {
        "type": "SICK_CREW",
        "crew_id": scc_id,
        "pairing_id": p_scc['pairing_id'],
        "role": "Senior Cabin Crew",
        "reported_utc": "2026-09-15T02:00:00Z",
    }
    res = optimize_recovery(event, conn=conn)

    # Day-off callout rate is 12500 for cabin
    assert res["expected_choice"]["cost_inr"] == 12500
    assert "day-off callout" in res["expected_choice"]["action"]


def test_callout_notification_generation_q36(conn):
    """Q36: Complete and compliant dispatch callout notification."""
    notif = generate_callout_notification("C-3310", "P-2291", conn=conn)

    assert len(notif["must_include"]) >= 5
    text = notif["message_text"]
    assert "C-3310" in text
    assert "P-2291" in text
    assert "06:00Z" in text
    assert "DX412" in text
    assert "Radisson Blu" in text
    assert "05:15Z" in text  # deadline
