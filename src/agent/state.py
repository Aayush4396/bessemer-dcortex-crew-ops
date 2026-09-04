"""
src/agent/state.py
==================
State definition for the LangGraph Crew Operations reasoning agent.
"""

from typing import Annotated, Any, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    Comprehensive state tracking conversation history, operational tier,
    tool execution artifacts, audit trail, and formatted user responses.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    user_query: str
    tier: int
    tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    reasoning_trace: list[str]
    final_response: str
