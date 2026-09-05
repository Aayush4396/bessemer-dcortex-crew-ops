"""
tests/test_router.py
====================
Unit tests for the LangGraph agent architecture, state transitions, tool dispatch,
and deterministic execution boundaries.
"""

import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
import pytest

from src.agent.graph import build_crew_ops_graph, should_continue, tools_node
from src.agent.tools import ALL_TOOLS, TIER1_TOOLS, TIER2_TOOLS, TIER3_TOOLS, TOOL_MAP
from src.db.loader import init_db


@pytest.fixture(scope="session")
def conn():
    """In-memory database initialized with datasets."""
    return init_db()


def test_tool_registry_completeness():
    """Verify all Tier 1, 2, and 3 tools are registered with schemas."""
    expected_tier1 = {
        "query_flight_schedule",
        "query_station_departures",
        "query_station_arrivals",
        "query_flight_schedule_stats",
        "query_crew_profile",
        "query_reserve_crew",
        "query_pairing_roster",
        "query_crew_duty_balance",
        "query_expiring_certifications",
        "query_crew_risk_signal",
    }
    assert {t.name for t in TIER1_TOOLS} == expected_tier1
    assert {t.name for t in TIER2_TOOLS} == {"simulate_disruption_impact"}
    assert {t.name for t in TIER3_TOOLS} == {
        "optimize_disruption_recovery",
        "generate_callout_notification_draft",
    }
    assert len(ALL_TOOLS) == 13
    assert len(TOOL_MAP) == 13


def test_graph_compilation():
    """Verify LangGraph StateGraph compiles successfully."""
    app = build_crew_ops_graph()
    assert app is not None


def test_should_continue_logic():
    """Verify conditional edge correctly routes between tools and synthesizer."""
    # Message with tool call -> routes to 'tools'
    ai_with_tool = AIMessage(
        content="",
        tool_calls=[{
            "name": "query_flight_schedule",
            "args": {"flight_no": "DX412"},
            "id": "call_123",
        }],
    )
    state_tools = {"messages": [ai_with_tool]}
    assert should_continue(state_tools) == "tools"

    # Message without tool call -> routes to '__end__'
    ai_plain = AIMessage(content="Flight DX412 departs at 06:00Z.")
    state_plain = {"messages": [ai_plain]}
    assert should_continue(state_plain) == "__end__"


def test_tools_node_execution(conn):
    """Verify tools_node executes tools deterministically and records results."""
    ai_msg = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "query_flight_schedule",
                "args": {"date": "2026-09-15", "flight_no": "DX412"},
                "id": "call_flight_test",
            },
            {
                "name": "query_crew_duty_balance",
                "args": {"crew_id": "C-1042", "as_of_date": "2026-09-14"},
                "id": "call_duty_test",
            },
        ],
    )
    initial_state = {
        "messages": [ai_msg],
        "tool_results": [],
        "reasoning_trace": [],
    }

    result = tools_node(initial_state)

    # Check returned tool messages
    assert len(result["messages"]) == 2
    assert all(isinstance(m, ToolMessage) for m in result["messages"])

    # Check flight tool output
    flight_data = json.loads(result["messages"][0].content)
    assert len(flight_data) == 1
    assert flight_data[0]["flight_no"] == "DX412"
    assert flight_data[0]["aircraft"] == "VT-DXC"

    # Check duty tool output
    duty_data = json.loads(result["messages"][1].content)
    assert duty_data["crew_id"] == "C-1042"
    assert duty_data["duty_hours_7d"] == 20.93
    assert duty_data["headroom_hours"] == 39.07

    # Check reasoning trace logged both executions
    assert len(result["reasoning_trace"]) == 2


def test_tools_node_unknown_tool_handling():
    """Verify tools_node gracefully handles unknown tool requests."""
    ai_msg = AIMessage(
        content="",
        tool_calls=[{
            "name": "non_existent_tool",
            "args": {},
            "id": "call_bad",
        }],
    )
    state = {
        "messages": [ai_msg],
        "tool_results": [],
        "reasoning_trace": [],
    }
    result = tools_node(state)
    assert len(result["messages"]) == 1
    err_data = json.loads(result["messages"][0].content)
    assert "error" in err_data


def test_tools_node_tier2_and_tier3_execution(conn):
    """Verify tools_node executes Tier 2 and Tier 3 tools deterministically."""
    ai_msg = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "simulate_disruption_impact",
                "args": {
                    "event_type": "SICK_CREW",
                    "date": "2026-09-17",
                    "crew_id": "C-1042",
                    "pairing_id": "P-2224",
                },
                "id": "call_sim_test",
            },
            {
                "name": "optimize_disruption_recovery",
                "args": {
                    "event_type": "SICK_CREW",
                    "date": "2026-09-17",
                    "crew_id": "C-1042",
                    "pairing_id": "P-2224",
                    "role": "Captain",
                    "station": "DEL",
                },
                "id": "call_opt_test",
            },
        ],
    )
    state = {
        "messages": [ai_msg],
        "tool_results": [],
        "reasoning_trace": [],
    }
    result = tools_node(state)
    assert len(result["messages"]) == 2

    sim_res = json.loads(result["messages"][0].content)
    assert sim_res["pairing_id"] == "P-2224"
    assert any("DX451" in f for f in sim_res["uncovered_flights"])

    opt_res = json.loads(result["messages"][1].content)
    assert opt_res["expected_choice"]["legal"] is True
    assert opt_res["expected_choice"]["crew_id"] == "C-3315"
    assert opt_res["expected_choice"]["cost_inr"] == 18500
    assert opt_res["expected_choice"]["delay_hours"] == 0.0


