"""
tests/test_tier2.py
===================
Unit tests for Tier 2 Disruption Simulator against operational scenarios S1-S6
and Tier 2 benchmark questions from questions.json.
"""

import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.db.loader import init_db
from src.tier2 import (
    simulate_cert_expiry,
    simulate_disruption,
    simulate_flight_delay,
    simulate_sick_crew,
    simulate_station_closure,
)


@pytest.fixture(scope="session")
def conn():
    """In-memory or connection to initialized crew_ops database."""
    return init_db()


def test_scenario_s1_atr_captain_sick(conn):
    """S1: ATR captain C-3231 sick call on 16 Sep for P-2224."""
    event = {
        "type": "SICK_CREW",
        "crew_id": "C-3231",
        "pairing_id": "P-2224",
        "reported_utc": "2026-09-16T01:30:00Z",
    }
    res = simulate_disruption(event, conn=conn)

    assert res["disruption_type"] == "SICK_CREW"
    assert res["crew_id"] == "C-3231"
    assert res["role"] == "Captain"
    assert res["aircraft_type"] == "ATR72"
    assert res["uncovered_flights"] == [
        "DX451-2026-09-16",
        "DX452-2026-09-16",
        "DX453-2026-09-16",
        "DX454-2026-09-16",
    ]
    # ATR72 is 72 seats * 4 legs = 288 seats
    assert res["passengers_at_risk"] == 288


def test_scenario_s2_flagship_captain_sick_multiday(conn):
    """S2: Flagship captain C-1042 sick call for 2-day pairing P-2291."""
    event = {
        "type": "SICK_CREW",
        "crew_id": "C-1042",
        "pairing_id": "P-2291",
        "reported_utc": "2026-09-15T05:00:00Z",
    }
    res = simulate_disruption(event, conn=conn)

    assert res["disruption_type"] == "SICK_CREW"
    assert res["crew_id"] == "C-1042"
    assert res["is_multi_day"] is True
    assert res["uncovered_flights_day1"] == [
        "DX412-2026-09-15",
        "DX413-2026-09-15",
        "DX588-2026-09-15",
    ]
    assert res["uncovered_flights_day2"] == [
        "DX589-2026-09-16",
        "DX590-2026-09-16",
        "DX591-2026-09-16",
    ]
    # Day 1 has 3 A320 flights (162 seats * 3 = 486 seats)
    assert res["passengers_at_risk_day1"] == 486


def test_scenario_s3_blr_station_closure(conn):
    """S3: BLR closed 08:00-14:00Z on 17 Sep (13 flights affected)."""
    event = {
        "type": "STATION_CLOSURE",
        "station": "BLR",
        "window_utc": {
            "start": "2026-09-17T08:00:00Z",
            "end": "2026-09-17T14:00:00Z",
        },
    }
    res = simulate_disruption(event, conn=conn)

    expected_flights = [
        "DX402-2026-09-17",
        "DX422-2026-09-17",
        "DX462-2026-09-17",
        "DX453-2026-09-17",
        "DX433-2026-09-17",
        "DX403-2026-09-17",
        "DX413-2026-09-17",
        "DX423-2026-09-17",
        "DX454-2026-09-17",
        "DX434-2026-09-17",
        "DX404-2026-09-17",
        "DX424-2026-09-17",
        "DX588-2026-09-17",
    ]
    assert res["affected_flights"] == expected_flights
    assert len(res["per_flight_assessment"]) == 13

    # Check DX402: 5.75h delay, 17.0h crew FDP, exceeds 12.0h limit
    dx402 = next(a for a in res["per_flight_assessment"] if a["flight_id"] == "DX402-2026-09-17")
    assert dx402["min_delay_hours"] == 5.75
    assert dx402["crew_fdp_after_delay"] == 17.0
    assert dx402["fdp_limit"] == 12.0
    assert "re-crew tail legs" in dx402["action"]

    # Check DX462: 2 sectors (limit 13h), 11.0h crew FDP -> legal
    dx462 = next(a for a in res["per_flight_assessment"] if a["flight_id"] == "DX462-2026-09-17")
    assert dx462["crew_fdp_after_delay"] == 11.0
    assert dx462["fdp_limit"] == 13.0
    assert "crew legal" in dx462["action"]


def test_scenario_s4_flight_delay_fdp_breach(conn):
    """S4: VT-DXA 90-minute delay before DX401 on 16 Sep causes FDP breach."""
    event = {
        "type": "DELAY",
        "aircraft": "VT-DXA",
        "date": "2026-09-16",
        "delay_hours": 1.5,
    }
    res = simulate_disruption(event, conn=conn)

    assert res["aircraft"] == "VT-DXA"
    assert res["fdp_after_delay"] == 12.75
    assert res["fdp_limit"] == 12.0
    assert res["breach"] is True
    assert "delayed duty runs 12.75h vs 12.0h limit" in res["breach_detail"]
    assert "DX404" in res["breach_detail"]


def test_scenario_s5_cert_expiry_preflight(conn):
    """S5: C-5417 recurrent training lapsed before 19 Sep duty."""
    event = {
        "type": "CERT_EXPIRY",
        "crew_id": "C-5417",
        "pairing_id": "P-2213",
        "reported_utc": "2026-09-18T10:00:00Z",
    }
    res = simulate_disruption(event, conn=conn)

    assert res["crew_id"] == "C-5417"
    assert res["role"] == "Cabin Crew"
    assert res["date"] == "2026-09-19"
    assert res["lapsed_cert"] == "recurrent_training"
    assert res["illegal_assignment"] == {
        "crew_id": "C-5417",
        "date": "2026-09-19",
        "rule": "RULE-CERT-06",
    }


def test_scenario_s6_multi_sick(conn):
    """S6: Multi-crew sick calls on 18 Sep."""
    event = {
        "type": "MULTI_SICK",
        "events": [
            {"crew_id": "C-3940", "pairing_id": "P-2205", "reported_utc": "2026-09-18T00:30:00Z"},
            {"crew_id": "C-1938", "pairing_id": "P-2212", "reported_utc": "2026-09-18T00:30:00Z"},
        ],
    }
    res = simulate_disruption(event, conn=conn)

    assert res["disruption_type"] == "MULTI_SICK"
    assert len(res["sub_impacts"]) == 2
    assert res["sub_impacts"][0]["crew_id"] == "C-3940"
    assert res["sub_impacts"][1]["crew_id"] == "C-1938"
    assert len(res["uncovered_flights_total"]) == 8


def test_generalizability_hyd_closure(conn):
    """Q29: HYD station closure 05:00-09:00Z on 19 Sep."""
    event = {
        "type": "STATION_CLOSURE",
        "station": "HYD",
        "window_utc": {
            "start": "2026-09-19T05:00:00Z",
            "end": "2026-09-19T09:00:00Z",
        },
    }
    res = simulate_station_closure(
        station="HYD",
        start_utc="2026-09-19T05:00:00Z",
        end_utc="2026-09-19T09:00:00Z",
        conn=conn,
    )
    assert res["station"] == "HYD"
    assert len(res["affected_flights"]) > 0
    # Every affected flight must touch HYD
    for fid in res["affected_flights"]:
        f_row = conn.execute("SELECT dep_station, arr_station FROM flights WHERE flight_id = ?", (fid,)).fetchone()
        assert "HYD" in (f_row["dep_station"], f_row["arr_station"])


def test_held_out_h1_atr_fo_sick(conn):
    """H1: ATR First Officer sick call on 16 Sep (P-2224)."""
    p_row = conn.execute("SELECT pairing_id FROM pairings WHERE date = '2026-09-16' AND aircraft = 'VT-DXE'").fetchone()
    fo_row = conn.execute("SELECT pc.crew_id FROM pairing_crew pc WHERE pc.pairing_id = ? AND pc.role = 'First Officer'", (p_row['pairing_id'],)).fetchone()
    res = simulate_disruption({
        "type": "SICK_CREW",
        "crew_id": fo_row['crew_id'],
        "pairing_id": p_row['pairing_id'],
        "reported_utc": "2026-09-16T02:00:00Z",
    }, conn=conn)
    assert res["role"] == "First Officer"
    assert res["aircraft_type"] == "ATR72"
    assert res["passengers_at_risk"] == 288
    assert len(res["uncovered_flights"]) == 4


def test_station_closure_del_fog(conn):
    """Generalization: DEL hub closure 02:00-08:00Z on 15 Sep (dense fog)."""
    res = simulate_station_closure(
        station="DEL",
        start_utc="2026-09-15T02:00:00Z",
        end_utc="2026-09-15T08:00:00Z",
        conn=conn,
    )
    assert res["station"] == "DEL"
    assert len(res["affected_flights"]) == 2
    for a in res["per_flight_assessment"]:
        assert "delay exceeds crew FDP" in a["action"]


def test_delay_sensitivity_spectrum(conn):
    """Generalization: 30m buffer vs 60m/90m FDP breach on 4-sector line."""
    # 30m delay absorbed
    res_30 = simulate_flight_delay(aircraft="VT-DXA", date="2026-09-16", delay_hours=0.5, conn=conn)
    assert res_30["breach"] is False
    assert res_30["fdp_after_delay"] <= res_30["fdp_limit"]

    # 60m delay breaches
    res_60 = simulate_flight_delay(aircraft="VT-DXA", date="2026-09-16", delay_hours=1.0, conn=conn)
    assert res_60["breach"] is True
    assert res_60["fdp_after_delay"] > res_60["fdp_limit"]


def test_dual_cockpit_incapacitation_deduplication(conn):
    """Generalization: Captain + FO sick on same flight does not duplicate seats/flights."""
    p_row = conn.execute("SELECT pairing_id FROM pairings WHERE date = '2026-09-15' AND aircraft = 'VT-DXD'").fetchone()
    cpt = conn.execute("SELECT crew_id FROM pairing_crew WHERE pairing_id = ? AND role = 'Captain'", (p_row['pairing_id'],)).fetchone()['crew_id']
    fo = conn.execute("SELECT crew_id FROM pairing_crew WHERE pairing_id = ? AND role = 'First Officer'", (p_row['pairing_id'],)).fetchone()['crew_id']

    res = simulate_disruption({
        "type": "MULTI_SICK",
        "events": [
            {"crew_id": cpt, "pairing_id": p_row['pairing_id'], "reported_utc": "2026-09-15T02:00:00Z"},
            {"crew_id": fo, "pairing_id": p_row['pairing_id'], "reported_utc": "2026-09-15T02:00:00Z"},
        ],
    }, conn=conn)
    # Both positions incapacitated, 4 unique flights, 648 seats (162 * 4) without duplicate counting
    assert len(res["sub_impacts"]) == 2
    assert len(res["uncovered_flights_total"]) == 4
    assert res["passengers_at_risk_total"] == 648

