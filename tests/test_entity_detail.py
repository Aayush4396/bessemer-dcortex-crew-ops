"""
tests/test_entity_detail.py
===========================
Flight and crew detail pages — only fields that exist in SQLite / rules.json.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.server import app
from src.db.loader import init_db
from src.tier1.entity_detail import get_crew_detail, get_flight_detail, list_crew

client = TestClient(app)


@pytest.fixture(scope="module")
def conn():
    return init_db()


def test_flight_detail_dx412(conn):
    flight = get_flight_detail("DX412-2026-09-15", conn=conn)
    assert flight is not None
    assert flight["flight_no"] == "DX412"
    assert flight["dep_station"] == "BLR"
    assert flight["arr_station"] == "BOM"
    assert flight["seats"] == 162
    assert flight["aircraft"] == "VT-DXC"
    assert flight["pairing"]["pairing_id"] == "P-2291"
    assert flight["pairing"]["next"]["flight_no"] == "DX413"
    assert {c["crew_id"] for c in flight["pairing"]["crew"]} >= {"C-1042"}


def test_flight_detail_unknown(conn):
    assert get_flight_detail("DX000-2026-09-15", conn=conn) is None


def test_crew_detail_c1042(conn):
    crew = get_crew_detail("C-1042", conn=conn)
    assert crew is not None
    assert crew["name"] == "A. Nair"
    assert crew["rank"] == "Captain"
    assert crew["base"] == "BLR"
    assert crew["seniority"] == 22
    assert crew["reachability_minutes"] == 90
    assert crew["status"] == "active"
    assert crew["risk_score"] == 0.78
    assert "short-rest pattern over last 14 days" in crew["drivers"]
    assert crew["duty"]["duty_hours_7d"] == 20.93
    assert crew["duty"]["duty_max_7d"] == 60.0
    assert crew["duty"]["duty_rule"] == "RULE-DUTY-02"
    assert crew["duty"]["flight_hours_28d"] == 64.27
    assert crew["duty"]["flight_max_28d"] == 100.0
    assert crew["duty"]["last_rest_ended"] == "2026-09-13T02:00:00Z"
    assert {c["cert_type"] for c in crew["certs"]} == {
        "licence",
        "medical_class1",
        "recurrent_training",
        "dangerous_goods",
    }
    assert any(p["pairing_id"] == "P-2291" for p in crew["pairings"])
    nair_teammates = next(p["crew"] for p in crew["pairings"] if p["pairing_id"] == "P-2291")
    assert all(m["crew_id"] != "C-1042" for m in nair_teammates)


def test_crew_detail_unknown(conn):
    assert get_crew_detail("C-0000", conn=conn) is None


def test_flight_detail_api():
    with patch("src.api.server.get_flight_detail", return_value={"flight_id": "DX412-2026-09-15"}):
        res = client.get("/api/flights/DX412-2026-09-15")
    assert res.status_code == 200
    assert res.json()["flight_id"] == "DX412-2026-09-15"


def test_flight_detail_api_404():
    with patch("src.api.server.get_flight_detail", return_value=None):
        res = client.get("/api/flights/DX000-2026-09-15")
    assert res.status_code == 404


def test_crew_detail_api():
    with patch("src.api.server.get_crew_detail", return_value={"crew_id": "C-1042"}):
        res = client.get("/api/crew/C-1042")
    assert res.status_code == 200
    assert res.json()["crew_id"] == "C-1042"


def test_crew_detail_api_404():
    with patch("src.api.server.get_crew_detail", return_value=None):
        res = client.get("/api/crew/C-0000")
    assert res.status_code == 404


def test_list_crew_covers_dataset(conn):
    payload = list_crew(conn=conn)
    assert payload["kpis"]["crew_total"] == 150
    assert payload["risk_counts"]["all"] == 150
    nair = next(m for m in payload["crew"] if m["crew_id"] == "C-1042")
    assert nair["risk_score"] == 0.78
    assert nair["rank"] == "Captain"
    assert "Captain" in payload["ranks"]
    assert "BLR" in payload["bases"]


def test_list_crew_rank_filter(conn):
    payload = list_crew(rank="Captain", conn=conn)
    assert payload["crew"]
    assert all(m["rank"] == "Captain" for m in payload["crew"])


def test_list_crew_api():
    with patch("src.api.server.list_crew", return_value={"crew": [], "kpis": {"crew_total": 0}}):
        res = client.get("/api/crew", params={"risk": "all"})
    assert res.status_code == 200
