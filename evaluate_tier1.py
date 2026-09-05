#!/usr/bin/env python3
"""
evaluate_tier1.py
=================
Independent evaluation script for all Tier 1 benchmark questions (Q01-Q16).
Does NOT rely on pytest or the tests/ directory.

Usage
-----
    python evaluate_tier1.py                  # Run all 16 deterministic benchmarks
    python evaluate_tier1.py --verbose        # Show full expected vs actual payloads
    python evaluate_tier1.py --agent Q05      # Test LangGraph agent on specific question
    python evaluate_tier1.py --agent-all      # Test LangGraph agent on all 16 questions
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(_ROOT))

from src.db.loader import init_db
from src.tier1 import (
    get_reserves_at_station,
    get_crew_duty_balance,
    get_departures,
    get_expiring_certifications,
    get_flights,
    get_flight_schedule_stats,
    get_crew_profile,
    get_pairing_roster,
    get_crew_risk_signal,
)

# Colors for terminal output
CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BOLD = "\033[1m"
RESET = "\033[0m"


def load_tier1_questions() -> list[dict]:
    """Load Q01-Q16 from data/questions.json."""
    q_file = _ROOT / "data" / "questions.json"
    if not q_file.exists():
        raise FileNotFoundError(f"Could not find questions file at {q_file}")
    with open(q_file, "r", encoding="utf-8") as f:
        all_q = json.load(f)
    return [q for q in all_q if q.get("tier") == 1]


def evaluate_question(q: dict, conn) -> tuple[bool, str, any, any]:
    """
    Execute deterministic query for a benchmark question and compare with expected answer.

    Returns:
        (passed: bool, message: str, actual_output: any, expected_output: any)
    """
    qid = q["question_id"]
    expected = q["expected_answer"]

    if qid == "Q01":
        actual = get_reserves_at_station(station="BLR", date="2026-09-15", conn=conn)
        passed = (actual == expected)
        msg = f"Retrieved {len(actual)} reserves (expected {len(expected)})"

    elif qid == "Q02":
        res = get_crew_duty_balance(crew_id="C-1042", as_of_date="2026-09-14", conn=conn)
        actual = {
            "duty_hours_7d": res.get("duty_hours_7d"),
            "headroom_hours": res.get("headroom_hours"),
        }
        passed = (
            actual["duty_hours_7d"] == expected["duty_hours_7d"] and
            actual["headroom_hours"] == expected["headroom_hours"]
        )
        msg = f"Duty 7d: {actual['duty_hours_7d']}h, Headroom: {actual['headroom_hours']}h"

    elif qid == "Q03":
        actual = get_departures(station="DEL", date="2026-09-15", conn=conn)
        passed = (actual == expected)
        msg = f"Found {len(actual)} DEL departures: {actual}"

    elif qid == "Q04":
        actual = get_expiring_certifications(as_of_date="2026-09-15", days_ahead=30, conn=conn)
        passed = (actual == expected)
        msg = f"Found {len(actual)} expiring certs"

    elif qid == "Q05":
        flights = get_flights(date="2026-09-15", flight_no="DX412", conn=conn)
        if flights:
            f = flights[0]
            actual = {
                "aircraft": f["aircraft"],
                "aircraft_type": f["aircraft_type"],
                "seats": f["seats"],
            }
        else:
            actual = {}
        passed = (
            actual.get("aircraft") == expected["aircraft"] and
            actual.get("aircraft_type") == expected["aircraft_type"] and
            actual.get("seats") == expected["seats"]
        )
        msg = f"Aircraft: {actual.get('aircraft')}, Type: {actual.get('aircraft_type')}, Seats: {actual.get('seats')}"

    elif qid == "Q06":
        profile = get_crew_profile(crew_id="C-3310", conn=conn)
        actual = {
            "window": profile.get("window"),
            "reachability_minutes": profile.get("reachability_minutes"),
        }
        passed = (
            actual.get("window") == expected["window"] and
            actual.get("reachability_minutes") == expected["reachability_minutes"]
        )
        msg = f"Window: {actual.get('window')}, Reachability: {actual.get('reachability_minutes')}m"

    elif qid == "Q07":
        profile = get_crew_profile(crew_id="C-2210", conn=conn)
        actual = {
            "base": profile.get("base"),
            "ratings": profile.get("ratings"),
        }
        passed = (
            actual.get("base") == expected["base"] and
            actual.get("ratings") == expected["ratings"]
        )
        msg = f"Base: {actual.get('base')}, Rating: {actual.get('ratings')}"

    elif qid == "Q08":
        actual = get_pairing_roster(pairing_id="P-2291", conn=conn)
        passed = (actual == expected)
        msg = f"Roster size: {len(actual)} crew members"

    elif qid == "Q09":
        flights = get_flights(date="2026-09-17", origin="BLR", destination="BOM", conn=conn)
        actual = [f["flight_no"] for f in flights]
        passed = (actual == expected)
        msg = f"Flights BLR->BOM: {actual}"

    elif qid == "Q10":
        flights = get_flights(date="2026-09-16", conn=conn)
        actual = len(flights)
        passed = (actual == expected)
        msg = f"Total flights: {actual} (expected {expected})"

    elif qid == "Q11":
        profiles = get_crew_profile(rank="Captain", base="DEL", conn=conn)
        actual = [p["crew_id"] for p in profiles]
        passed = (actual == expected)
        msg = f"DEL Captains: {actual}"

    elif qid == "Q12":
        actual = get_flight_schedule_stats(metric="longest_block", conn=conn)
        passed = (
            actual.get("block_hours") == expected["block_hours"] and
            sorted(actual.get("flights", [])) == sorted(expected["flights"])
        )
        msg = f"Longest block: {actual.get('block_hours')}h, Flights: {actual.get('flights')}"

    elif qid == "Q13":
        res = get_crew_duty_balance(crew_id="C-2087", as_of_date="2026-09-14", conn=conn)
        actual = {
            "rank": res.get("rank"),
            "flight_hours_28d": res.get("flight_hours_28d"),
        }
        passed = (
            actual.get("rank") == expected["rank"] and
            actual.get("flight_hours_28d") == expected["flight_hours_28d"]
        )
        msg = f"Rank: {actual.get('rank')}, 28d Flight Hours: {actual.get('flight_hours_28d')}h"

    elif qid == "Q14":
        actual = get_flights(origin="BLR", distinct_destinations=True, conn=conn)
        passed = (actual == expected)
        msg = f"Nonstop from BLR: {actual}"

    elif qid == "Q15":
        actual = get_pairing_roster(aircraft="VT-DXB", date="2026-09-16", role="Senior Cabin Crew", conn=conn)
        passed = (actual == expected)
        msg = f"Senior Cabin Crew: {actual}"

    elif qid == "Q16":
        actual = get_crew_risk_signal(crew_id="C-1042", conn=conn)
        passed = (
            actual.get("score") == expected["score"] and
            actual.get("drivers") == expected["drivers"]
        )
        msg = f"Risk score: {actual.get('score')}, Drivers: {actual.get('drivers')}"

    else:
        passed = False
        msg = f"Unknown question ID {qid}"
        actual = None

    return passed, msg, actual, expected


def run_deterministic_eval(verbose: bool = False):
    """Run full deterministic evaluation across Q01-Q16."""
    print(f"\n{CYAN}{BOLD}========================================================================{RESET}")
    print(f"{CYAN}{BOLD}   [TEST] dCortex Independent Tier 1 Evaluation (Zero pytest reliance)  {RESET}")
    print(f"{CYAN}{BOLD}========================================================================{RESET}")
    print(f"Loading dataset into SQLite in-memory engine...")

    t0 = time.time()
    conn = init_db()
    load_ms = (time.time() - t0) * 1000
    print(f"{GREEN}[OK] SQLite database initialized in {load_ms:.1f}ms{RESET}\n")

    questions = load_tier1_questions()
    print(f"Found {len(questions)} Tier 1 benchmark questions in data/questions.json\n")
    print(f"{'ID':<6} {'STATUS':<10} {'DETAILS':<55}")
    print("-" * 72)

    passed_count = 0
    failed_count = 0

    for q in questions:
        qid = q["question_id"]
        prompt = q["prompt"]
        t_start = time.time()
        passed, msg, actual, expected = evaluate_question(q, conn)
        elapsed_ms = (time.time() - t_start) * 1000

        if passed:
            status_str = f"{GREEN}[PASS]{RESET}"
            passed_count += 1
        else:
            status_str = f"{RED}[FAIL]{RESET}"
            failed_count += 1

        print(f"{BOLD}{qid:<6}{RESET} {status_str:<19} {msg:<45} ({elapsed_ms:.1f}ms)")

        if verbose or not passed:
            print(f"       {YELLOW}Prompt:{RESET} {prompt}")
            if not passed:
                print(f"       {RED}Expected:{RESET} {json.dumps(expected)}")
                print(f"       {RED}Actual:  {RESET} {json.dumps(actual)}")
            print()

    print("-" * 72)
    total = len(questions)
    percentage = (passed_count / total) * 100

    if failed_count == 0:
        print(f"\n{GREEN}{BOLD}[SUCCESS] ALL {total} TIER 1 BENCHMARK QUESTIONS PASSED ({percentage:.1f}% ACCURACY)!{RESET}")
        print(f"{GREEN}Deterministic query engine verified 100% compliant with questions.json.{RESET}\n")
        return 0
    else:
        print(f"\n{RED}{BOLD}[FAILURE] {failed_count} OF {total} QUESTIONS FAILED.{RESET}\n")
        return 1


def run_agent_eval(target_qid: str | None = None):
    """Run LangGraph Agent against Tier 1 questions using natural language prompts."""
    from src.agent import run_crew_ops_agent

    print(f"\n{CYAN}{BOLD}========================================================================{RESET}")
    print(f"{CYAN}{BOLD}   [AGENT] dCortex LangGraph Agent Live Natural Language Evaluation     {RESET}")
    print(f"{CYAN}{BOLD}========================================================================{RESET}\n")

    questions = load_tier1_questions()
    if target_qid:
        questions = [q for q in questions if q["question_id"].upper() == target_qid.upper()]
        if not questions:
            print(f"{RED}Question {target_qid} not found in Tier 1 questions.{RESET}")
            return 1

    for q in questions:
        qid = q["question_id"]
        prompt = q["prompt"]
        expected = q["expected_answer"]

        print(f"\n{BOLD}------------------------------------------------------------------------{RESET}")
        print(f"{CYAN}[{qid}] Controller Prompt:{RESET} {BOLD}{prompt}{RESET}")
        print(f"Expected Answer Data: {json.dumps(expected, default=str)[:120]}...")

        t_start = time.time()
        try:
            result = run_crew_ops_agent(query=prompt, tier=1)
            duration = time.time() - t_start

            print(f"\n{GREEN}Agent Dispatched Tool Calls ({len(result['tool_calls'])}):{RESET}")
            for tc in result["tool_calls"]:
                print(f"  • {tc['name']}({tc['args']})")

            print(f"\n{GREEN}Agent Synthesized Operational Response ({duration:.2f}s):{RESET}")
            print(f"  \"{result['final_response']}\"")
        except Exception as e:
            print(f"{RED}Agent Execution Error: {e}{RESET}")

    print(f"\n{BOLD}------------------------------------------------------------------------{RESET}\n")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Independent Tier 1 Evaluation Script")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print verbose output with prompts and outputs")
    parser.add_argument("--agent", type=str, help="Evaluate a specific question ID through LangGraph Agent (e.g. Q05)")
    parser.add_argument("--agent-all", action="store_true", help="Evaluate all 16 questions through LangGraph Agent")

    args = parser.parse_args()

    if args.agent:
        sys.exit(run_agent_eval(args.agent))
    elif args.agent_all:
        sys.exit(run_agent_eval())
    else:
        sys.exit(run_deterministic_eval(verbose=args.verbose))
