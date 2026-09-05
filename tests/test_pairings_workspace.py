"""
tests/test_pairings_workspace.py
================================
Deterministic tests for the Tactical Pairings Roster assembly layer.
Uses an in-memory SQLite database loaded from data/.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.server import app
from src.db.loader import init_db
from src.tier1.pairings_workspace import _cert_for_schedule, _duty_risk, get_pairing, get_pairings_workspace

client = TestClient(app)


@pytest.fixture(scope="module")
def conn():
    return init_db()


def test_workspace_kpis_match_dataset(conn):
    payload = get_pairings_workspace(conn=conn)
    kpis = payload["kpis"]
    assert kpis["active_pairings"] == 39
    assert kpis["flight_legs"] == 147
    assert kpis["legs_covered_pct"] == 100
    assert kpis["crew_complement"] == 150
    assert kpis["high_risk_crew"] == 3
    assert kpis["certs_expiring_30d"] == 6


def test_p2291_is_two_day_rotation_with_highlighted_captain(conn):
    payload = get_pairings_workspace(date_filter="2026-09-15", conn=conn)
    pairing = next(p for p in payload["pairings"] if p["pairing_id"] == "P-2291")

    assert pairing["rotation_days"] == 2
    assert pairing["aircraft"]["tail"] == "VT-DXC"
    assert pairing["route"][0] == "BLR"
    assert len(pairing["days"]) == 2
    assert pairing["days"][0]["day_index"] == 1
    assert pairing["days"][1]["day_index"] == 2
    assert [f["flight_no"] for f in pairing["days"][0]["flights"]] == ["DX412", "DX413", "DX588"]
    assert [f["flight_no"] for f in pairing["days"][1]["flights"]] == ["DX589", "DX590", "DX591"]
    assert pairing["days"][0]["flights"][0]["seats"] == 162
    assert pairing["days"][0]["flights"][1]["ground_hours"] == 0.75
    assert pairing["days"][1]["rest_hours"] == 12.5
    assert pairing["days"][1]["rest_min_hours"] == 12.0
    nair = next(c for c in pairing["crew"] if c["crew_id"] == "C-1042")
    assert nair["base"] == "BLR"
    assert nair["certs"]

    highlighted_ids = {c["crew_id"] for c in pairing["roster"]["highlighted"]}
    assert "C-1042" in highlighted_ids
    assert pairing["roster"]["collapsed_count"] >= 1
    assert pairing["risk_score"] == 0.78
    assert pairing["risk_level"] == "critical"


def test_date_filter_keeps_full_multi_day_pairing(conn):
    payload = get_pairings_workspace(date_filter="2026-09-15", conn=conn)
    pairing = next(p for p in payload["pairings"] if p["pairing_id"] == "P-2291")
    assert [d["date"] for d in pairing["days"]] == ["2026-09-15", "2026-09-16"]


def test_high_risk_filter_excludes_low_pairings(conn):
    payload = get_pairings_workspace(risk="high", conn=conn)
    assert payload["pairings"]
    assert all(p["risk_score"] >= 0.70 for p in payload["pairings"])


def test_elevated_risk_filter_is_exclusive_band(conn):
    payload = get_pairings_workspace(risk="elevated", conn=conn)
    assert payload["pairings"]
    assert all(0.30 <= p["risk_score"] < 0.70 for p in payload["pairings"])


def test_low_risk_filter(conn):
    payload = get_pairings_workspace(risk="low", conn=conn)
    assert payload["pairings"]
    assert all(p["risk_score"] < 0.30 for p in payload["pairings"])


def test_risk_counts_cover_all_pairings(conn):
    payload = get_pairings_workspace(conn=conn)
    counts = payload["risk_counts"]
    assert counts["all"] == 39
    assert counts["high"] + counts["elevated"] + counts["low"] == counts["all"]


def test_only_elevated_or_higher_crew_are_highlighted(conn):
    payload = get_pairings_workspace(conn=conn)
    for pairing in payload["pairings"]:
        for member in pairing["roster"]["highlighted"]:
            assert member["risk_score"] >= 0.30


def test_cert_risk_expired_and_same_day_and_ignored():
    certs = [{"cert_type": "recurrent_training", "valid_to": "2026-09-17"}]
    expired = _cert_for_schedule(certs, ["2026-09-19"])
    assert expired["status"] == "expired"
    assert expired["risk"] == 1.0

    same_day = _cert_for_schedule(certs, ["2026-09-17"])
    assert same_day["status"] == "expiring"
    assert same_day["risk"] == 0.65

    ignored = _cert_for_schedule(certs, ["2026-09-16"])
    assert ignored["status"] == "valid"
    assert ignored["risk"] == 0.0


def test_expired_cert_sets_pairing_risk_to_one(conn):
    payload = get_pairings_workspace(conn=conn)
    pairing = next(p for p in payload["pairings"] if p["pairing_id"] == "P-2213")
    member = next(c for c in pairing["roster"]["highlighted"] if c["crew_id"] == "C-5417")
    assert member["cert_status"] == "expired"
    assert member["risk_score"] == 1.0
    assert pairing["risk_score"] == 1.0


def test_duty_risk_matches_bar_bands():
    assert _duty_risk(12.5, 12.0) == 1.0
    assert _duty_risk(12.0, 12.0) == 0.9
    assert _duty_risk(11.25, 12.0) == 0.9
    assert _duty_risk(10.8, 12.5) == 0.65
    assert _duty_risk(8.0, 12.0) == 0.0


def test_near_limit_duty_raises_pairing_risk(conn):
    payload = get_pairings_workspace(conn=conn)
    pairing = next(p for p in payload["pairings"] if p["pairing_id"] == "P-2201")
    assert pairing["days"][0]["duty_hours"] == 11.25
    assert pairing["days"][0]["max_window_hours"] == 12.0
    assert pairing["risk_score"] == 0.9


def test_cert_more_than_one_day_out_is_ignored(conn):
    payload = get_pairings_workspace(conn=conn)
    pairing = next(p for p in payload["pairings"] if p["pairing_id"] == "P-2210")
    member = next(c for c in pairing["roster"]["highlighted"] if c["crew_id"] == "C-5417")
    assert member["cert_status"] == "valid"
    assert member["risk_score"] == 0.64


def test_pairings_api_endpoint_shape():
    mock_payload = {
        "snapshot_utc": "2026-09-14T18:00:00Z",
        "kpis": {"active_pairings": 39},
        "pairings": [],
        "tails": [],
    }
    with patch("src.api.server.get_pairings_workspace", return_value=mock_payload):
        res = client.get("/api/pairings", params={"date": "2026-09-15", "risk": "all"})
    assert res.status_code == 200
    assert res.json()["kpis"]["active_pairings"] == 39


def test_pairings_api_rejects_unknown_risk():
    res = client.get("/api/pairings", params={"risk": "extreme"})
    assert res.status_code == 400


def test_pairings_api_accepts_low_risk():
    mock_payload = {
        "snapshot_utc": "2026-09-14T18:00:00Z",
        "kpis": {"active_pairings": 39},
        "pairings": [],
        "tails": [],
        "risk_counts": {"all": 0, "high": 0, "elevated": 0, "low": 0},
    }
    with patch("src.api.server.get_pairings_workspace", return_value=mock_payload):
        res = client.get("/api/pairings", params={"risk": "low"})
    assert res.status_code == 200


def test_get_pairing_returns_full_p2291(conn):
    pairing = get_pairing("P-2291", conn=conn)
    assert pairing is not None
    assert pairing["pairing_id"] == "P-2291"
    assert pairing["days"][0]["flights"][0]["seats"] == 162
    assert {c["crew_id"] for c in pairing["crew"]} >= {"C-1042"}


def test_get_pairing_unknown_is_none(conn):
    assert get_pairing("P-0000", conn=conn) is None


def test_pairing_detail_api():
    with patch("src.api.server.get_pairing", return_value={"pairing_id": "P-2291"}):
        res = client.get("/api/pairings/P-2291")
    assert res.status_code == 200
    assert res.json()["pairing_id"] == "P-2291"


def test_pairing_detail_api_404():
    with patch("src.api.server.get_pairing", return_value=None):
        res = client.get("/api/pairings/P-0000")
    assert res.status_code == 404
