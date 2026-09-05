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
    is_operational_query,
    should_continue,
    tools_node,
)
from src.agent.tool_calls import (
    all_calls_already_run,
    desk_text_from_tools,
    hydrate_tool_calls,
    message_text,
    parse_sarvam_tool_markup,
    strip_model_scratch,
)
from src.agent.tools import ALL_TOOLS, TIER1_TOOLS, TIER2_TOOLS, TIER3_TOOLS, TOOL_MAP
from src.db.loader import init_db


@pytest.fixture(scope="session")
def conn():
    """In-memory database initialized with datasets."""
    return init_db()


def test_tool_registry_completeness():
    """Verify all 10 Tier 1 tools are registered with schemas."""
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
    }
    registered = {t.name for t in TIER1_TOOLS}
    assert registered == expected_tools
    tier2_names = {
        "simulate_disruption_impact",
        "query_flight_duty_times",
        "query_pairing",
        "query_crew_detail",
        "query_station_movements",
        "query_database",
        "query_cost_rates",
        "check_fdp_limit",
        "check_duty_7d",
        "check_flight_28d",
        "check_rest",
        "check_qualification",
        "check_certifications",
        "check_base_positioning",
        "check_cover",
    }
    assert {t.name for t in TIER2_TOOLS} == tier2_names
    assert {t.name for t in TIER3_TOOLS} == {
        "optimize_disruption_recovery",
        "generate_callout_notification_draft",
    }
    assert len(TOOL_MAP) == len(ALL_TOOLS)
    assert set(TOOL_MAP) == {t.name for t in ALL_TOOLS}


def test_graph_compilation():
    """Verify LangGraph StateGraph compiles successfully."""
    app = build_crew_ops_graph()
    assert app is not None


def test_operational_query_requires_tools():
    assert is_operational_query("Which single flight leg has the most seats at risk if cancelled, and why?")
    assert is_operational_query("Who can cover P-2291?")
    assert not is_operational_query("hello")
    assert not is_operational_query("Thanks!")
    assert not is_operational_query("")


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


def test_sarvam_markup_parsed_and_routed():
    leaked = (
        "<|tool_calls_section_begin|>"
        '<|tool_call_begin|>functions.query_pairing:0|<tool_call_argument_begin|>{"pairing_id":"P-2291"}<|tool_call_end|>'
        '<|tool_call_begin|>functions.query_crew_detail:1|<tool_call_argument_begin|>{"crew_id":"C-2087"}<|tool_call_end|>'
        "<|tool_calls_section_end|>"
    )
    leaked_pipe_token = (
        "<|tool_calls_section_begin|>"
        '<|tool_call_begin|>functions.query_pairing:0<|tool_call_argument_begin|>{"pairing_id":"P-2291"}<|tool_call_end|>'
        "<|tool_calls_section_end|>"
    )
    parsed = parse_sarvam_tool_markup(leaked)
    assert [c["name"] for c in parsed] == ["query_pairing", "query_crew_detail"]
    assert parsed[0]["args"] == {"pairing_id": "P-2291"}
    assert parsed[1]["args"] == {"crew_id": "C-2087"}
    assert parse_sarvam_tool_markup(leaked_pipe_token)[0]["args"] == {"pairing_id": "P-2291"}

    hydrated = hydrate_tool_calls(AIMessage(content=leaked))
    assert hydrated.content == ""
    assert len(hydrated.tool_calls) == 2
    assert should_continue({"messages": [hydrated], "tool_hops": 0}) == "tools"

    already = AIMessage(
        content="",
        tool_calls=[{"name": "check_duty_7d", "args": {"crew_id": "C-2087"}, "id": "x"}],
    )
    assert hydrate_tool_calls(already).tool_calls[0]["name"] == "check_duty_7d"


def test_xml_tool_call_markup_parsed():
    leaked = """<tool_call>
query_pairing
<arg_key>pairing_id</arg_key>
<arg_value>P-2291</arg_value>
</tool_call>
<tool_call>
check_duty_7d
<arg_key>crew_id</arg_key>
<arg_value>C-2087</arg_value>
<arg_key>pairing_id</arg_key>
<arg_value>P-2291</arg_value>
</tool_call>"""
    parsed = parse_sarvam_tool_markup(leaked)
    assert [c["name"] for c in parsed] == ["query_pairing", "check_duty_7d"]
    assert parsed[0]["args"] == {"pairing_id": "P-2291"}
    assert parsed[1]["args"] == {"crew_id": "C-2087", "pairing_id": "P-2291"}

    truncated = """<tool_call>
query_pairing
<arg_key>pairing_id</arg_key>
<arg_value>P-2291"""
    assert parse_sarvam_tool_markup(truncated)[0]["args"] == {"pairing_id": "P-2291"}

    hermes = '<tool_call>{"name": "check_flight_28d", "arguments": {"crew_id": "C-2087", "pairing_id": "P-2291"}}</tool_call>'
    assert parse_sarvam_tool_markup(hermes)[0] == {
        "name": "check_flight_28d",
        "args": {"crew_id": "C-2087", "pairing_id": "P-2291"},
        "id": "sarvam_0",
        "type": "tool_call",
    }

    hydrated = hydrate_tool_calls(AIMessage(content=leaked))
    assert hydrated.content == ""
    assert should_continue({"messages": [hydrated], "tool_hops": 0}) == "tools"


def test_empty_synthesis_falls_back_to_tool_prose():
    assert message_text([{"type": "text", "text": "Eligible: C-9910."}]) == "Eligible: C-9910."
    prose = desk_text_from_tools(
        [
            {
                "tool_name": "query_reserve_crew",
                "args": {},
                "result": {
                    "eligible": ["C-3315"],
                    "excluded": [
                        {"crew_id": "C-3305", "reason": "RULE-QUAL-05: no ATR72 rating"},
                    ],
                },
            }
        ]
    )
    assert "C-3315" in prose
    assert "C-3305" in prose
    seats = desk_text_from_tools(
        [
            {
                "tool_name": "query_flight_schedule_stats",
                "args": {"metric": "max_seats"},
                "result": {
                    "by_type": [
                        {"aircraft_type": "A320", "max_seats": 162},
                        {"aircraft_type": "ATR72", "max_seats": 72},
                    ],
                },
            }
        ]
    )
    assert "A320" in seats
    assert "162" in seats
    assert strip_model_scratch("<think>calling tools</think>") == ""


def test_think_and_duplicate_calls_are_dropped():
    assert strip_model_scratch(
        "<think>I need to run the actual rule checks.</think>\nYes, DUTY-02 breaches."
    ) == "Yes, DUTY-02 breaches."
    thought = hydrate_tool_calls(
        AIMessage(
            content="<think>call them correctly</think>",
            tool_calls=[{"name": "check_duty_7d", "args": {"crew_id": "C-2087"}, "id": "x"}],
        )
    )
    assert thought.content == ""
    assert thought.tool_calls[0]["name"] == "check_duty_7d"

    prior = [
        {
            "tool_name": "check_duty_7d",
            "args": {"crew_id": "C-2087", "pairing_id": "P-2291"},
            "result": {"legal": False},
        }
    ]
    assert all_calls_already_run(
        [{"name": "check_duty_7d", "args": {"crew_id": "C-2087", "pairing_id": "P-2291"}}],
        prior,
    )
    assert not all_calls_already_run(
        [{"name": "check_flight_28d", "args": {"crew_id": "C-2087", "pairing_id": "P-2291"}}],
        prior,
    )


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
