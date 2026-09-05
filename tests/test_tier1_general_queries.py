"""Corpus-driven tests for generalized deterministic Tier 1 query planning."""

import json
from pathlib import Path

import pytest

from src.agent.tier1_planner import route_tier1_query


CORPUS_PATH = Path(__file__).parent.parent / "data" / "tier1_general_query_examples.json"
CORPUS = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
SUPPORTED_PROMPTS = [
    pytest.param(case, prompt, id=f"{case['id']}-{index}")
    for case in CORPUS["supported_cases"]
    for index, prompt in enumerate(case["prompts"], start=1)
]


@pytest.mark.parametrize(("case", "prompt"), SUPPORTED_PROMPTS)
def test_supported_general_query(case, prompt):
    routed = route_tier1_query(prompt)

    assert routed is not None
    assert routed["tool_calls"][0]["name"] == case["expected_tool"]
    result = routed["tool_results"][0]["result"]
    expected = case["expected"]

    if "count" in expected:
        assert result["count"] == expected["count"]
    if "aggregation_value" in expected:
        assert result["aggregation"]["value"] == pytest.approx(expected["aggregation_value"])
    if "aggregation_count" in expected:
        assert result["aggregation"]["count"] == expected["aggregation_count"]


@pytest.mark.parametrize("case", CORPUS["unsupported_boundary_cases"], ids=lambda case: case["id"])
def test_boundary_query_returns_explicit_limitation(case):
    routed = route_tier1_query(case["prompt"])

    assert routed is not None
    assert routed["tool_calls"] == []
    assert routed["tool_results"] == []
    assert "cannot answer" in routed["final_response"].lower()
    assert "without querying partial data or inventing a result" in routed["reasoning_trace"][-1]
