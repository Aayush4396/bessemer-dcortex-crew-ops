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

from src.agent.graph import (
    build_crew_ops_graph,
    deterministic_router_node,
    route_initial_query,
    should_continue,
    tools_node,
)
from src.agent.tools import TIER1_TOOLS, TOOL_MAP
from src.db.loader import init_db


@pytest.fixture(scope="session")
def conn():
    """In-memory database initialized with datasets."""
    return init_db()


def test_tool_registry_completeness():
    """Verify all Tier 1 tools are registered with schemas."""
    expected_tools = {
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
        "query_operations",
    }
    registered = {t.name for t in TIER1_TOOLS}
    assert registered == expected_tools
    assert len(TOOL_MAP) == 17


def test_graph_compilation():
    """Verify LangGraph StateGraph compiles successfully."""
    app = build_crew_ops_graph()
    assert app is not None


def test_deterministic_router_handles_roster_wide_weekly_duty_query():
    state = {
        "user_query": "give me all crew members name and rank whose weekly duty hours is less than 60 hours.",
        "reasoning_trace": ["Received Controller Query"],
    }

    result = deterministic_router_node(state)

    assert route_initial_query(result) == "__end__"
    assert result["tool_calls"][0]["name"] == "query_operations"
    assert result["tool_results"][0]["result"]["count"] == 150
    assert "Found **150 crew members**" in result["final_response"]
    assert "Rendered the operational response without an external LLM call" in result["reasoning_trace"]


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
