"""
tests/test_api.py
=================
Unit and integration tests for FastAPI backend server endpoints.
"""

import sys
from pathlib import Path
from unittest.mock import patch

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
import pytest

from src.api.server import app

client = TestClient(app)


def test_health_endpoint():
    """Verify GET /api/health returns healthy status and engine information."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "Sarvam" in data["engine"]
    assert data["snapshot_date"] == "2026-09-14"


def test_stats_endpoint():
    """Verify GET /api/stats returns accurate database metrics."""
    res = client.get("/api/stats")
    assert res.status_code == 200
    data = res.json()
    assert data["flights"] == 147
    assert data["crew"] == 150
    assert data["pairings"] == 42
    assert data["reserves"] == 112
    assert "BLR" in data["active_stations"]


def test_simulate_placeholder():
    """Verify POST /api/simulate returns Tier 2 placeholder info."""
    res = client.post("/api/simulate")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "placeholder"
    assert data["tier"] == 2
    assert len(data["scenarios"]) == 6


def test_recover_placeholder():
    """Verify POST /api/recover returns Tier 3 placeholder info."""
    res = client.post("/api/recover")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "placeholder"
    assert data["tier"] == 3
    assert len(data["capabilities"]) == 4


def test_chat_empty_query():
    """Verify POST /api/chat rejects empty query with 400."""
    res = client.post("/api/chat", json={"query": "   ", "tier": 1})
    assert res.status_code == 400


def test_chat_endpoint_mock():
    """Verify POST /api/chat formats LangGraph agent output into response model."""
    mock_agent_output = {
        "final_response": "Flight DX412 is operated by VT-DXC (A320).",
        "tool_calls": [{"name": "query_flight_schedule", "args": {"flight_no": "DX412"}, "id": "c1"}],
        "tool_results": [{"tool_name": "query_flight_schedule", "result": [{"flight_no": "DX412"}]}],
        "reasoning_trace": ["Dispatched query_flight_schedule", "Synthesized response"],
    }
    with patch("src.api.server.run_crew_ops_agent", return_value=mock_agent_output):
        res = client.post("/api/chat", json={"query": "Details for DX412", "tier": 1})
        assert res.status_code == 200
        data = res.json()
        assert data["response"] == "Flight DX412 is operated by VT-DXC (A320)."
        assert len(data["tool_calls"]) == 1
        assert len(data["reasoning_trace"]) == 2
