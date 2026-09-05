#!/usr/bin/env python3
"""
evaluate_tier2.py
=================
Independent evaluation of Tier 2 handlers against Q17–Q30.
Does not call the LLM — proves the tools are sufficient before composition.
"""

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(_ROOT))

from src.db.loader import init_db
from src.tier1 import get_flights, get_flight_schedule_stats
from src.tier2 import (
    evaluate_base_positioning,
    evaluate_certifications,
    evaluate_duty_7d,
    evaluate_fdp_limit,
    evaluate_reserve_callout,
    evaluate_rest,
    get_cost_rates,
    get_pairing_entity,
    get_station_movements,
)

CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BOLD = "\033[1m"
RESET = "\033[0m"


def load_tier2_questions() -> list[dict]:
    all_q = json.loads((_ROOT / "data" / "questions.json").read_text(encoding="utf-8"))
    return [q for q in all_q if q.get("tier") == 2]


def evaluate_question(q: dict, conn) -> tuple[bool, str, object]:
    qid = q["question_id"]
    expected = q["expected_answer"]

    if qid == "Q17":
        pairing = get_pairing_entity("P-2291", conn=conn)
        actual = {
            "day1": pairing["days"][0]["flight_ids"],
            "day2_also_at_risk": pairing["days"][1]["flight_ids"],
            "passengers_day1": pairing["passengers_day1"],
        }
        return actual == expected, "uncrewed pairing legs", actual

    if qid == "Q18":
        actual = evaluate_duty_7d(crew_id="C-2087", pairing_id="P-2291", conn=conn)
        passed = actual["legal"] is False and actual["issues"] == expected["issues"]
        return passed, f"issues={len(actual.get('issues', []))}", actual

    if qid == "Q19":
        actual = get_station_movements("BLR", "2026-09-17", "08:00", "14:00", conn=conn)
        return actual == expected, f"{len(actual)} affected", actual

    if qid == "Q20":
        actual = evaluate_fdp_limit(aircraft="VT-DXA", date="2026-09-16", delay_hours=1.5, conn=conn)
        passed = (
            actual["breach"] is True
            and actual["fdp_after_delay"] == expected["fdp_after_delay"]
            and actual["fdp_limit"] == expected["fdp_limit"]
        )
        return passed, f"FDP {actual.get('fdp_after_delay')}/{actual.get('fdp_limit')}", actual

    if qid == "Q21":
        pos = evaluate_base_positioning("C-2210", "P-2291", conn=conn)
        actual = {"legal": pos["legal"], "consequence": pos.get("consequence")}
        return actual == expected, pos.get("consequence", ""), actual

    if qid == "Q22":
        result = evaluate_certifications("C-5417", "2026-09-19", conn=conn)
        actual = {"legal": result["legal"], "rule": result["rule"], "detail": result["detail"]}
        return actual == expected, result["detail"], actual

    if qid == "Q23":
        actual = evaluate_rest(release_utc="2026-09-16T15:30:00Z")["earliest_report_utc"]
        return actual == expected, actual, actual

    if qid == "Q24":
        actual = evaluate_duty_7d(crew_id="C-3305", pairing_id="P-2291", conn=conn)
        passed = actual["legal"] is False and actual["issues"] == expected["issues"]
        return passed, f"issues={actual.get('issues')}", actual

    if qid == "Q25":
        flights = get_flights(date="2026-09-16", flight_no="DX404", conn=conn)
        costs = get_cost_rates()
        actual = {"passengers": flights[0]["seats"], "cost_inr": costs["cancellation_per_flight"]}
        return actual == expected, str(actual), actual

    if qid == "Q26":
        actual = evaluate_duty_7d(as_of_date="2026-09-15", min_hours=45, conn=conn)["crew"]
        return actual == expected, f"{len(actual)} crew", actual

    if qid == "Q27":
        result = evaluate_reserve_callout(
            date="2026-09-16",
            rank="Captain",
            required_report_utc="2026-09-16T03:00:00Z",
            aircraft_type="ATR72",
            conn=conn,
        )
        excluded = {e["crew_id"]: e["reason"] for e in result["excluded"]}
        passed = result["eligible"] == expected["eligible"] and all(
            excluded.get(ex["crew_id"]) == ex["reason"] for ex in expected["excluded_examples"]
        )
        actual = {"eligible": result["eligible"], "excluded_examples": expected["excluded_examples"]}
        return passed, f"eligible={result['eligible']}", actual

    if qid == "Q28":
        actual = evaluate_rest(crew_id="C-5837", pairing_id="P-2291", conn=conn)
        passed = actual["legal"] is False and actual["issues"] == expected["issues"]
        return passed, str(actual.get("issues")), actual

    if qid == "Q29":
        actual = get_station_movements("HYD", "2026-09-19", "05:00", "09:00", conn=conn)
        return actual == expected, str(actual), actual

    if qid == "Q30":
        actual = get_flight_schedule_stats(metric="max_seats", conn=conn)
        return actual == expected, str(actual), actual

    return False, f"Unknown {qid}", None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    print(f"\n{CYAN}{BOLD}========================================================================{RESET}")
    print(f"{CYAN}{BOLD}   [TEST] dCortex Independent Tier 2 Evaluation                         {RESET}")
    print(f"{CYAN}{BOLD}========================================================================{RESET}")

    conn = init_db()
    questions = load_tier2_questions()
    print(f"Found {len(questions)} Tier 2 questions\n")
    print(f"{'ID':<6} {'STATUS':<10} {'DETAILS'}")
    print("-" * 72)

    passed_count = 0
    failed_count = 0
    for q in questions:
        passed, msg, actual = evaluate_question(q, conn)
        if passed:
            print(f"{BOLD}{q['question_id']:<6}{RESET} {GREEN}[PASS]{RESET}    {msg}")
            passed_count += 1
        else:
            print(f"{BOLD}{q['question_id']:<6}{RESET} {RED}[FAIL]{RESET}    {msg}")
            if args.verbose or True:
                print(f"       {YELLOW}Expected:{RESET} {json.dumps(q['expected_answer'])}")
                print(f"       {RED}Actual:{RESET}   {json.dumps(actual, default=str)}")
            failed_count += 1

    print("-" * 72)
    if failed_count == 0:
        print(f"\n{GREEN}{BOLD}[SUCCESS] ALL {len(questions)} TIER 2 HANDLERS PASSED{RESET}\n")
        return 0
    print(f"\n{RED}{BOLD}[FAILURE] {failed_count} OF {len(questions)} FAILED{RESET}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
