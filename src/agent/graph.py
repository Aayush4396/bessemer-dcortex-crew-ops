"""
src/agent/graph.py
==================
LangGraph StateGraph workflow for dCortex Crew Operations Advisor.
Implements the multi-turn agentic ReAct loop:
  agent (Sarvam-105B) <-> tools (deterministic Python against SQLite) -> END
"""

import json
import re
from typing import Any, Literal

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, START, StateGraph

from src.db.chat_store import get_session_messages, save_message

from .client import get_llm
from .prompts import ROUTER_SYSTEM_PROMPT
from .state import AgentState
from .tool_calls import (
    all_calls_already_run,
    desk_text_from_tools,
    hydrate_tool_calls,
    message_text,
    strip_model_scratch,
    tool_call_signature,
)
from .tools import ALL_TOOLS, TOOL_MAP

MAX_TOOL_HOPS = 8

_GREETING_ONLY = re.compile(
    r"^(hi|hello|hey|thanks|thank you|ok|okay|bye|good morning|good evening)[.!\s]*$",
    re.IGNORECASE,
)


def is_operational_query(query: str) -> bool:
    """True when the desk question must hit SQLite (tools or query_database)."""
    text = (query or "").strip()
    if not text:
        return False
    return _GREETING_ONLY.fullmatch(text) is None


# Parameters that represent temporal/query controls rather than persistent operational entities
IGNORED_PARAMS = {
    "as_of_date",
    "date",
    "start_date",
    "end_date",
    "limit",
    "offset",
    "dry_run",
}

# Explicit core aviation entity keys (supports Tier 1, Tier 2, and Tier 3)
CORE_ENTITY_KEYS = {
    "crew_id",
    "flight_no",
    "aircraft",
    "pairing_id",
    "station",
    "scenario_id",
    "candidate_id",
    "swap_crew_id",
}


def extract_active_entities(
    args: dict[str, Any],
    existing_entities: dict[str, str] | None = None,
) -> dict[str, str]:
    """
    Extracts operational domain entities from tool invocation arguments.
    Works dynamically across Tier 1 (Lookups), Tier 2 (Disruptions), and Tier 3 (Recovery)
    without hardcoding tool-specific branches.
    """
    entities = dict(existing_entities or {})
    if not isinstance(args, dict):
        return entities

    for key, val in args.items():
        if val is None or str(val).strip() == "":
            continue
        # Skip operational query controls like dates or pagination limits
        if key in IGNORED_PARAMS:
            continue
        # Capture domain entity if recognized or follows naming conventions (*_id, *_no, *_code, *_reg)
        if key in CORE_ENTITY_KEYS or key.endswith(("_id", "_no", "_code", "_reg")):
            entities[key] = str(val).strip()

    return entities


def prepare_compact_context(
    messages: list[BaseMessage],
    active_entities: dict[str, str] | None = None,
    max_turns: int = 6,
) -> list[BaseMessage]:
    """
    Deterministic Python Pre-Processor:
    - Binds conversational context to the last `max_turns` turns.
    - Prunes historical ToolMessage raw JSON bodies to compact stubs.
    - Injects active entity registry into system prompt for pronoun resolution.
    """
    if not messages:
        return [SystemMessage(content=ROUTER_SYSTEM_PROMPT)]

    system_text = ROUTER_SYSTEM_PROMPT
    if active_entities:
        entity_bullets = "\n".join(f"  * {k}: {v}" for k, v in active_entities.items() if v)
        if entity_bullets:
            system_text += (
                f"\n\n[Active Operational Context]\n"
                f"{entity_bullets}\n"
                f"(When resolving relative references such as 'his/her', 'that flight', 'the captain', refer to these active entities unless the user specifies a new one)."
            )

    # Slice recent message turns
    recent = messages[-(max_turns * 3):] if len(messages) > (max_turns * 3) else list(messages)

    compacted: list[BaseMessage] = [SystemMessage(content=system_text)]
    for i, msg in enumerate(recent):
        if isinstance(msg, SystemMessage):
            continue
        # If this is a ToolMessage and not in the immediate turn, prune its heavy JSON payload
        if isinstance(msg, ToolMessage) and i < len(recent) - 3:
            compacted.append(
                ToolMessage(
                    content='{"status": "verified", "note": "Data verified and incorporated in prior assistant answer"}',
                    tool_call_id=msg.tool_call_id,
                    name=msg.name,
                )
            )
        else:
            compacted.append(msg)

    return compacted


def agent_node(state: AgentState) -> dict[str, Any]:
    """
    Reasoning Agent node: Uses Sarvam-105B with bound Tier 1 tools to analyze controller query,
    formulate tool calls, or synthesize final operational responses.
    """
    llm = get_llm(temperature=0.0)
    model_with_tools = llm.bind_tools(ALL_TOOLS)

    # Use compact context pre-processor
    compact_messages = prepare_compact_context(
        state.get("messages", []),
        state.get("active_entities"),
    )

    response: AIMessage = hydrate_tool_calls(model_with_tools.invoke(compact_messages))

    if (
        not response.tool_calls
        and not state.get("tool_results")
        and is_operational_query(state.get("user_query") or "")
    ):
        response = hydrate_tool_calls(
            model_with_tools.invoke(
                compact_messages
                + [
                    SystemMessage(
                        content=(
                            "Airline-operations questions cannot be answered from the "
                            "system prompt or memory. Call a lookup/check tool or "
                            "query_database now. Do not write desk prose yet. "
                            "Do not copy illustration types (B737, Q400, IX, C-99)."
                        )
                    )
                ]
            )
        )

    if response.tool_calls and all_calls_already_run(
        response.tool_calls, state.get("tool_results") or []
    ):
        # Keep tools bound: Sarvam 400s if ToolMessages are in the thread without a tools schema.
        response = hydrate_tool_calls(
            model_with_tools.invoke(
                compact_messages
                + [
                    SystemMessage(
                        content=(
                            "Those rule checks already ran this turn. "
                            "Write the desk answer from passed/detail/issues. "
                            "Do not emit tool markup or <think>."
                        )
                    )
                ]
            )
        )
        if response.tool_calls and all_calls_already_run(
            response.tool_calls, state.get("tool_results") or []
        ):
            response = AIMessage(content=strip_model_scratch(message_text(response.content)))

    trace = list(state.get("reasoning_trace", []))
    if response.tool_calls:
        tool_names = [tc["name"] for tc in response.tool_calls]
        trace.append(f"Agent dispatched {len(response.tool_calls)} tool call(s): {tool_names}")
    else:
        trace.append("Agent synthesized operational response")

    tool_calls_extracted = list(state.get("tool_calls", []))
    for tc in (response.tool_calls or []):
        tool_calls_extracted.append({"name": tc["name"], "args": tc["args"], "id": tc["id"]})

    final_text = strip_model_scratch(message_text(response.content))

    return {
        "messages": [response],
        "tool_calls": tool_calls_extracted,
        "final_response": final_text,
        "reasoning_trace": trace,
    }


def tools_node(state: AgentState) -> dict[str, Any]:
    """
    Deterministic Tool Execution Node:
    Executes tool calls against the SQLite database using Python handlers.
    Strictly zero arithmetic or hallucination by LLM.
    """
    last_message = state["messages"][-1]
    tool_messages: list[BaseMessage] = []
    tool_results: list[dict[str, Any]] = list(state.get("tool_results", []))
    trace = list(state.get("reasoning_trace", []))
    active_entities = dict(state.get("active_entities") or {})

    for tc in getattr(last_message, "tool_calls", []):
        tool_name = tc["name"]
        tool_args = tc.get("args", {})
        tool_id = tc["id"]

        # Track active focus entities dynamically for pronoun resolution
        active_entities = extract_active_entities(tool_args, active_entities)

        prior = next(
            (
                row
                for row in tool_results
                if tool_call_signature(row["tool_name"], row.get("args"))
                == tool_call_signature(tool_name, tool_args)
            ),
            None,
        )
        if prior is not None:
            tool_messages.append(
                ToolMessage(
                    content=json.dumps(prior["result"], default=str),
                    tool_call_id=tool_id,
                    name=tool_name,
                )
            )
            trace.append(f"Reused {tool_name}({tool_args}) from earlier hop this turn")
            continue

        if tool_name not in TOOL_MAP:
            error_msg = f"Unknown tool requested: {tool_name}"
            tool_messages.append(
                ToolMessage(content=json.dumps({"error": error_msg}), tool_call_id=tool_id, name=tool_name)
            )
            trace.append(f"Tool execution failed: {error_msg}")
            continue

        selected_tool = TOOL_MAP[tool_name]
        try:
            raw_result = selected_tool.invoke(tool_args)
            result_json = json.dumps(raw_result, default=str)
            tool_messages.append(
                ToolMessage(content=result_json, tool_call_id=tool_id, name=tool_name)
            )
            tool_results.append({
                "tool_name": tool_name,
                "args": tool_args,
                "result": raw_result,
            })
            item_count = len(raw_result) if isinstance(raw_result, (list, dict)) else 1
            trace.append(f"Executed {tool_name}({tool_args}) -> retrieved {item_count} record(s)")
        except Exception as e:
            err_json = json.dumps({"error": str(e)})
            tool_messages.append(
                ToolMessage(content=err_json, tool_call_id=tool_id, name=tool_name)
            )
            trace.append(f"Execution error on {tool_name}: {e}")

    return {
        "messages": tool_messages,
        "tool_results": tool_results,
        "reasoning_trace": trace,
        "active_entities": active_entities,
        "tool_hops": state.get("tool_hops", 0) + 1,
    }


def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    """
    Conditional routing edge from agent:
    If tool calls are present and under the hop limit, transition to tools node;
    otherwise terminate at END. Hops (agent↔tools cycles) are counted, not
    total tool calls, so one turn can emit several parallel rule checks.
    """
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        if state.get("tool_hops", 0) < MAX_TOOL_HOPS:
            return "tools"
    return "__end__"


def build_crew_ops_graph():
    """
    Constructs and compiles the complete multi-turn LangGraph StateGraph workflow.
    """
    workflow = StateGraph(AgentState)

    # Register nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tools_node)

    # Define edges
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "__end__": END,
        },
    )
    # Loop tools back to agent for multi-turn reasoning
    workflow.add_edge("tools", "agent")

    return workflow.compile()


def run_crew_ops_agent(query: str, session_id: str = "default", tier: int = 1) -> dict[str, Any]:
    """
    High-level entry point to execute a natural language query through the LangGraph workflow.
    Loads historical session context, runs the agent, and persists the completed turn.

    Parameters
    ----------
    query : str
        Operational question from the Crew Controller.
    session_id : str, optional
        Unique session / thread identifier (default 'default').
    tier : int, optional
        Target tier context (default 1).

    Returns
    -------
    dict with keys:
        - final_response: str
        - tool_calls: list[dict]
        - tool_results: list[dict]
        - reasoning_trace: list[str]
        - session_id: str
        - tier: int
        - messages: list[BaseMessage]
    """
    app = build_crew_ops_graph()

    # 1. Fetch prior messages from SQLite
    past_records = get_session_messages(session_id)
    historical_messages: list[BaseMessage] = []
    active_entities: dict[str, str] = {}

    for rec in past_records:
        if rec["sender"] == "user":
            historical_messages.append(HumanMessage(content=rec["content"]))
        elif rec["sender"] == "assistant":
            historical_messages.append(AIMessage(content=rec["content"]))
            # Seed active entities from past tool calls dynamically
            for tc in (rec.get("tool_calls") or []):
                active_entities = extract_active_entities(tc.get("args") or {}, active_entities)

    # 2. Build initial state with history + new user prompt
    initial_state: AgentState = {
        "messages": historical_messages + [HumanMessage(content=query)],
        "user_query": query,
        "tier": tier,
        "session_id": session_id,
        "active_entities": active_entities,
        "tool_calls": [],
        "tool_results": [],
        "tool_hops": 0,
        "reasoning_trace": [f"Received Controller Query: '{query}'"],
        "final_response": "",
    }

    result = app.invoke(initial_state)

    # 3. Desk text: strip scratch, then recover if the model returned only tools/think
    final_text = strip_model_scratch(message_text(result.get("final_response", "") or ""))
    if not final_text:
        for msg in reversed(result.get("messages", [])):
            if isinstance(msg, AIMessage) and msg.content:
                cleaned = strip_model_scratch(message_text(msg.content))
                if cleaned:
                    final_text = cleaned
                    break

    tool_results = result.get("tool_results", [])
    if not final_text and tool_results:
        forced = get_llm(temperature=0.0).bind_tools(ALL_TOOLS).invoke(
            prepare_compact_context(
                result.get("messages", []),
                result.get("active_entities"),
            )
            + [
                SystemMessage(
                    content=(
                        "The tool results are already in this thread. "
                        "Write the controller-facing desk answer now in plain text. "
                        "No tool markup, no <think>, no JSON fence."
                    )
                )
            ]
        )
        final_text = strip_model_scratch(message_text(getattr(forced, "content", "")))
    if not final_text and tool_results:
        final_text = desk_text_from_tools(tool_results)

    # 4. Persist completed turn to SQLite
    tool_calls = result.get("tool_calls", [])
    tool_results = result.get("tool_results", [])
    reasoning_trace = result.get("reasoning_trace", [])

    save_message(
        session_id=session_id,
        sender="user",
        content=query,
        tier_used=tier,
    )
    save_message(
        session_id=session_id,
        sender="assistant",
        content=final_text,
        tool_calls=tool_calls,
        tool_results=tool_results,
        reasoning_trace=reasoning_trace,
        tier_used=tier,
    )

    return {
        "final_response": final_text,
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "reasoning_trace": reasoning_trace,
        "session_id": session_id,
        "tier": tier,
        "messages": result.get("messages", []),
    }
