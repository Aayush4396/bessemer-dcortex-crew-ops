"""
src/agent/graph.py
==================
LangGraph StateGraph workflow for dCortex Crew Operations Advisor.
Orchestrates:
  Router (Sarvam-105B) -> Deterministic Tools (Tier 1) -> Synthesizer (Sarvam-105B)
"""

import json
from typing import Any, Literal

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, START, StateGraph

from .client import get_llm
from .prompts import ROUTER_SYSTEM_PROMPT, SYNTHESIZER_SYSTEM_PROMPT
from .state import AgentState
from .tools import TIER1_TOOLS, TOOL_MAP


def router_node(state: AgentState) -> dict[str, Any]:
    """
    Router node: Uses Sarvam-105B with bound Tier 1 tools to analyze controller query
    and formulate structured deterministic tool calls.
    """
    llm = get_llm(temperature=0.0)
    model_with_tools = llm.bind_tools(TIER1_TOOLS)

    # Ensure system prompt is first message
    messages = list(state["messages"])
    if not messages or not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=ROUTER_SYSTEM_PROMPT))

    response: AIMessage = model_with_tools.invoke(messages)

    trace_entry = f"Router analyzed query: '{state.get('user_query', '')}'"
    if response.tool_calls:
        tool_names = [tc["name"] for tc in response.tool_calls]
        trace_entry += f" -> Dispatched {len(response.tool_calls)} tool call(s): {tool_names}"
    else:
        trace_entry += " -> No tool calls required (direct response)"

    current_trace = list(state.get("reasoning_trace", []))
    current_trace.append(trace_entry)

    tool_calls_extracted = [
        {"name": tc["name"], "args": tc["args"], "id": tc["id"]}
        for tc in (response.tool_calls or [])
    ]

    return {
        "messages": [response],
        "tool_calls": tool_calls_extracted,
        "reasoning_trace": current_trace,
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

    for tc in getattr(last_message, "tool_calls", []):
        tool_name = tc["name"]
        tool_args = tc.get("args", {})
        tool_id = tc["id"]

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
    }


def synthesizer_node(state: AgentState) -> dict[str, Any]:
    """
    Synthesizer Node:
    Formulates a clear, professional operational response from verified tool outputs.
    Strictly quotes numbers and verdicts without calculating arithmetic.
    """
    # Sarvam API requires tools parameter to be present when ToolMessages are in history
    llm = get_llm(temperature=0.0).bind_tools(TIER1_TOOLS)

    # Build synthesis message history
    synthesis_messages: list[BaseMessage] = [SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT)]
    for msg in state["messages"]:
        if isinstance(msg, SystemMessage):
            continue
        synthesis_messages.append(msg)

    response = llm.invoke(synthesis_messages)
    final_text = str(response.content)

    trace = list(state.get("reasoning_trace", []))
    trace.append("Synthesizer produced final operational response with verified data citations")

    return {
        "messages": [response],
        "final_response": final_text,
        "reasoning_trace": trace,
    }


def should_continue(state: AgentState) -> Literal["tools", "synthesizer"]:
    """
    Conditional routing edge from router:
    If tool calls are present, transition to tools node; otherwise go to synthesizer.
    """
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "synthesizer"


def build_crew_ops_graph():
    """
    Constructs and compiles the complete LangGraph StateGraph workflow.
    """
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("router", router_node)
    graph.add_node("tools", tools_node)
    graph.add_node("synthesizer", synthesizer_node)

    # Define edges
    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        should_continue,
        {
            "tools": "tools",
            "synthesizer": "synthesizer",
        },
    )
    graph.add_edge("tools", "synthesizer")
    graph.add_edge("synthesizer", END)

    return graph.compile()


def run_crew_ops_agent(query: str, tier: int = 1) -> dict[str, Any]:
    """
    High-level entry point to execute a natural language query through the LangGraph workflow.

    Parameters
    ----------
    query : str
        Operational question from the Crew Controller.
    tier : int, optional
        Target tier context (default 1).

    Returns
    -------
    dict with keys:
        - final_response: str
        - tool_calls: list[dict]
        - tool_results: list[dict]
        - reasoning_trace: list[str]
        - messages: list[BaseMessage]
    """
    app = build_crew_ops_graph()
    initial_state: AgentState = {
        "messages": [HumanMessage(content=query)],
        "user_query": query,
        "tier": tier,
        "tool_calls": [],
        "tool_results": [],
        "reasoning_trace": [f"Received Controller Query: '{query}'"],
        "final_response": "",
    }

    result = app.invoke(initial_state)
    return {
        "final_response": result.get("final_response", ""),
        "tool_calls": result.get("tool_calls", []),
        "tool_results": result.get("tool_results", []),
        "reasoning_trace": result.get("reasoning_trace", []),
        "messages": result.get("messages", []),
    }
