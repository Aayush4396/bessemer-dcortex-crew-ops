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


def test_tier2_route_is_unified_under_chat():
    """Tier 2 has no separate REST endpoint; it uses POST /api/chat."""
    res = client.post("/api/simulate")
    assert res.status_code == 404


def test_tier3_route_is_unified_under_chat():
    """Tier 3 has no separate REST endpoint; it uses POST /api/chat."""
    res = client.post("/api/recover")
    assert res.status_code == 404


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
        assert data["session_id"] == "default"


def test_chat_endpoint_with_session_id():
    """Verify POST /api/chat propagates session_id to run_crew_ops_agent and response."""
    mock_agent_output = {
        "final_response": "Test response",
        "tool_calls": [],
        "tool_results": [],
        "reasoning_trace": ["Trace 1"],
    }
    with patch("src.api.server.run_crew_ops_agent", return_value=mock_agent_output) as mock_run:
        res = client.post(
            "/api/chat",
            json={"query": "Who operates DX412?", "tier": 1, "session_id": "session-test-42"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["session_id"] == "session-test-42"
        mock_run.assert_called_once_with(
            query="Who operates DX412?",
            session_id="session-test-42",
            tier=1,
        )


def test_chat_weekly_duty_query_does_not_require_external_model():
    query = "give me all crew members name and rank whose weekly duty hours is less than 60 hours."
    with patch("src.agent.graph.get_llm", side_effect=AssertionError("LLM must not be called")):
        res = client.post(
            "/api/chat",
            json={"query": query, "tier": 1, "session_id": "session-duty-offline-test"},
        )

    assert res.status_code == 200
    data = res.json()
    assert "Found **150 crew members**" in data["response"]
    assert data["tool_calls"][0]["name"] == "query_operations"
    assert data["tool_results"][0]["result"]["count"] == 150


def test_chat_sick_call_query_does_not_require_external_model():
    query = "Captain C-1042 calls in sick at 05:00Z on 15 Sep for pairing P-2291. Which flights are immediately uncrewed?"
    with patch("src.agent.graph.get_llm", side_effect=AssertionError("LLM must not be called")):
        res = client.post(
            "/api/chat",
            json={"query": query, "tier": 2, "session_id": "session-sick-call-offline-test"},
        )

    assert res.status_code == 200
    data = res.json()
    assert data["tool_calls"][0]["name"] == "analyze_sick_call"
    assert data["tool_results"][0]["result"]["passengers_at_risk_day1"] == 486
    assert "DX412" in data["response"]


def test_chat_sick_call_resolves_pairing_when_omitted():
    query = "Captain C-1042 calls in unavailable at 05:00Z on 15 Sep. Which flights are immediately uncrewed?"
    with patch("src.agent.graph.get_llm", side_effect=AssertionError("LLM must not be called")):
        res = client.post(
            "/api/chat",
            json={"query": query, "tier": 2, "session_id": "session-sick-call-inference-test"},
        )

    assert res.status_code == 200
    data = res.json()
    assert data["tool_calls"][0]["args"]["pairing_id"] == "P-2291"
    assert "DX412" in data["response"]


def test_chat_replacement_query_does_not_require_external_model():
    query = "who can be the replacement captain for pairing P-2291?"
    with patch("src.agent.graph.get_llm", side_effect=AssertionError("LLM must not be called")):
        res = client.post(
            "/api/chat",
            json={"query": query, "tier": 3, "session_id": "session-replacement-offline-test"},
        )

    assert res.status_code == 200
    data = res.json()
    assert data["tool_calls"][0]["name"] == "get_cover_options"
    assert data["tool_results"][0]["result"]["options"][0]["crew_id"] == "C-3310"


def test_chat_candidate_follow_up_uses_persisted_session_context():
    session_id = "session-contextual-candidate-test"
    with patch("src.agent.graph.get_llm", side_effect=AssertionError("LLM must not be called")):
        first = client.post(
            "/api/chat",
            json={
                "query": "who can be the replacement captain for pairing P-2291?",
                "tier": 3,
                "session_id": session_id,
            },
        )
        follow_up = client.post(
            "/api/chat",
            json={
                "query": "can C-3311 replace for C-1042?",
                "tier": 3,
                "session_id": session_id,
            },
        )

    assert first.status_code == 200
    assert follow_up.status_code == 200
    data = follow_up.json()
    assert data["tool_results"][0]["result"]["legal"] is False
    assert "First Officer" in data["response"]
    assert "Captain" in data["response"]


def test_sessions_lifecycle():
    """Verify full CRUD lifecycle of session REST endpoints."""
    # 1. Create session
    create_res = client.post("/api/sessions", json={"title": "NOC Flight DX412 Investigation"})
    assert create_res.status_code == 200
    create_data = create_res.json()
    assert "session_id" in create_data
    session_id = create_data["session_id"]
    assert create_data["title"] == "NOC Flight DX412 Investigation"

    # 2. List sessions
    list_res = client.get("/api/sessions")
    assert list_res.status_code == 200
    sessions = list_res.json()
    assert any(s["session_id"] == session_id for s in sessions)

    # 3. Get session details & history
    get_res = client.get(f"/api/sessions/{session_id}")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["session_id"] == session_id
    assert get_data["session"]["title"] == "NOC Flight DX412 Investigation"
    assert isinstance(get_data["messages"], list)

    # 4. Delete session
    del_res = client.delete(f"/api/sessions/{session_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # 5. Confirm deletion from list
    list_after = client.get("/api/sessions").json()
    assert not any(s["session_id"] == session_id for s in list_after)

