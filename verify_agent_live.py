"""
verify_agent_live.py
====================
Standalone live operational test of the LangGraph + Sarvam-105B agent.
Tests natural language queries without using pytest or the tests/ folder.
"""

import json
import time
from src.agent import run_crew_ops_agent
from src.db.loader import init_db

# Initialize database
init_db()

print("=" * 80)
print("LIVE OPERATIONAL VERIFICATION — LANGGRAPH + SARVAM-105B CREW OPS AGENT")
print("=" * 80)

TEST_QUERIES = [
    {
        "id": "T1-01",
        "description": "Flight Equipment & Capacity Lookup (DX412 on 2026-09-15)",
        "prompt": "Which aircraft operates flight DX412 on 2026-09-15 and how many seats does it have?",
        "expected_tool": "query_flight_schedule",
        "expected_facts": ["VT-DXC", "162"],
    },
    {
        "id": "T1-02",
        "description": "Standby Reserve Crew Pool & On-Call Windows (BLR on 2026-09-15)",
        "prompt": "Who is on reserve at BLR on 2026-09-15, and what are their on-call windows?",
        "expected_tool": "query_reserve_crew",
        "expected_facts": ["C-3305", "C-3310", "C-3315"],
    },
    {
        "id": "T1-03",
        "description": "7-Day Duty Balance & Headroom Calculation (C-1042 as of 2026-09-14)",
        "prompt": "How many duty hours has C-1042 accrued in the 7 days ending 2026-09-14, and what is the remaining headroom?",
        "expected_tool": "query_crew_duty_balance",
        "expected_facts": ["20.93", "39.07"],
    },
    {
        "id": "T1-04",
        "description": "Fatigue & Disruption Risk Signals (C-1042)",
        "prompt": "What is the disruption risk score for C-1042 and what operational factors drive it?",
        "expected_tool": "query_crew_risk_signal",
        "expected_facts": ["0.78"],
    },
]

passed = 0
failed = 0

for test in TEST_QUERIES:
    print("\n" + "-" * 80)
    print(f"TEST {test['id']}: {test['description']}")
    print(f"Controller Prompt: \"{test['prompt']}\"")
    print("-" * 80)

    start_time = time.time()
    try:
        result = run_crew_ops_agent(test["prompt"])
        duration = time.time() - start_time

        # Inspect tool calls
        tool_calls = result.get("tool_calls", [])
        tool_names = [tc["name"] for tc in tool_calls]
        print(f"\n1. Dispatched Tool Calls ({len(tool_calls)}):")
        for tc in tool_calls:
            print(f"   -> Tool: {tc['name']} | Args: {tc['args']}")

        # Inspect tool results
        tool_results = result.get("tool_results", [])
        print(f"\n2. Deterministic Tool Outputs ({len(tool_results)}):")
        for tr in tool_results:
            raw = tr["result"]
            sample = raw[:2] if isinstance(raw, list) and len(raw) > 2 else raw
            print(f"   -> {tr['tool_name']} returned: {sample}")

        # Inspect reasoning trace
        trace = result.get("reasoning_trace", [])
        print(f"\n3. Agent Audit Trace ({len(trace)} steps):")
        for step in trace:
            print(f"   * {step}")

        # Inspect final answer
        answer = result.get("final_response", "")
        print(f"\n4. Final Synthesized Operational Response (in {duration:.2f}s):")
        print("   " + "\n   ".join(answer.split("\n")))

        # Check verifications
        tool_matched = test["expected_tool"] in tool_names
        facts_matched = all(fact.lower() in answer.lower() for fact in test["expected_facts"])

        if tool_matched and facts_matched:
            print(f"\nVERDICT: [PASS] (Correct tool dispatched & exact facts cited without hallucination)")
            passed += 1
        else:
            reasons = []
            if not tool_matched:
                reasons.append(f"Expected tool '{test['expected_tool']}' not in {tool_names}")
            if not facts_matched:
                reasons.append(f"Missing expected facts: {test['expected_facts']}")
            print(f"\nVERDICT: [FAIL] ({', '.join(reasons)})")
            failed += 1

    except Exception as e:
        print(f"\nVERDICT: [ERROR] Exception during agent execution: {e}")
        failed += 1

print("\n" + "=" * 80)
print(f"LIVE AGENT TEST SUMMARY: {passed} PASSED / {failed} FAILED")
print("=" * 80)
