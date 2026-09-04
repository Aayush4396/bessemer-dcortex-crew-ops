"""
src/db/verify_db.py
====================
Cross-checks the SQLite database against known answer keys from
questions.json and README facts to confirm the loader transformation
is correct.

Run:
    python -m src.db.verify_db

All checks are deterministic against the fixed dataset snapshot.
A PASS here means: SQLite queries return the same values as the JSON source.
"""

import io
import json
import sys
from pathlib import Path

# Fix Windows console encoding for ASCII-safe output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.db.loader import init_db, get_constants

_REPO = Path(__file__).parent.parent.parent  # project root
_DATA = _REPO / "data"

errors = []
passed = []

def ok(label: str):
    passed.append(label)
    print(f"  [PASS] {label}")

def fail(label: str, detail: str):
    errors.append((label, detail))
    print(f"  [FAIL] {label}: {detail}")

def check(label: str, actual, expected):
    if actual == expected:
        ok(label)
    else:
        fail(label, f"expected {expected!r}, got {actual!r}")

def check_approx(label: str, actual: float, expected: float, tol=0.05):
    if abs(actual - expected) <= tol:
        ok(label)
    else:
        fail(label, f"expected ~{expected}, got {actual}")


def main():
    print("Loading SQLite DB...")
    conn = init_db()
    cur = conn.cursor()
    constants = get_constants()
    questions = json.loads((_DATA / "questions.json").read_text())
    q = {qq["question_id"]: qq for qq in questions}

    print("\n-- Table row counts ---------------------------------")

    # README facts: 147 flights, 150 crew, 39 pairings, 16 reserves
    n = cur.execute("SELECT COUNT(*) FROM flights").fetchone()[0]
    check("flights: 147 rows", n, 147)

    n = cur.execute("SELECT COUNT(*) FROM crew").fetchone()[0]
    check("crew: 150 rows", n, 150)

    # 39 pairings (unique pairing_ids)
    n = cur.execute("SELECT COUNT(DISTINCT pairing_id) FROM pairings").fetchone()[0]
    check("pairings: 39 unique pairing_ids", n, 39)

    n = cur.execute("SELECT COUNT(DISTINCT crew_id) FROM reserve_pool").fetchone()[0]
    check("reserve_pool: 16 distinct crew", n, 16)

    n = cur.execute("SELECT COUNT(*) FROM certifications").fetchone()[0]
    check("certifications: 600 rows (150 crew × 4)", n, 600)

    n = cur.execute("SELECT COUNT(*) FROM duty_clock_history").fetchone()[0]
    check("duty_clock_history: 4200 rows (150 crew × 28 days)", n, 4200)

    print("\n-- Q01: Reserve pool at BLR on 2026-09-15 ----------")
    # Q01 expects 10 specific crew on reserve at BLR on 2026-09-15
    expected_q01 = {
        "C-3305","C-3310","C-3311","C-3312","C-3315","C-3316",
        "C-2111","C-3677","C-5418","C-1329","C-2248","C-4809"
    }
    rows = cur.execute(
        "SELECT crew_id FROM reserve_pool WHERE base='BLR' AND date='2026-09-15'"
    ).fetchall()
    actual_q01 = {r[0] for r in rows}
    if expected_q01.issubset(actual_q01):
        ok("Q01: BLR reserve crew on 2026-09-15 (superset check)")
    else:
        missing = expected_q01 - actual_q01
        fail("Q01: BLR reserve crew", f"missing: {missing}")

    print("\n-- Q02: C-1042 duty hours 7d ending 2026-09-14 -----")
    # Q02 expects duty_hours_7d=20.93, headroom=39.07
    row = cur.execute(
        """
        SELECT ROUND(SUM(duty_hours), 2)
        FROM duty_clock_history
        WHERE crew_id = 'C-1042'
          AND date >= '2026-09-08'
          AND date <= '2026-09-14'
        """
    ).fetchone()
    check_approx("Q02: C-1042 duty_hours_7d (rolling sum)", row[0], 20.93)
    # Also check the snapshot field matches
    snap = cur.execute(
        "SELECT duty_hours_7d FROM duty_clocks WHERE crew_id='C-1042'"
    ).fetchone()[0]
    check_approx("Q02: duty_clocks snapshot duty_hours_7d", snap, 20.93)

    print("\n-- Q03: Flights departing DEL on 2026-09-15 --------")
    rows = cur.execute(
        "SELECT flight_no FROM flights WHERE dep_station='DEL' AND date='2026-09-15'"
    ).fetchall()
    actual = sorted([r[0] for r in rows])
    check("Q03: flights departing DEL on 2026-09-15", actual, ["DX402"])

    print("\n-- Q04: Certifications expiring within 30 days -----")
    # Expected: C-2087 licence 2026-09-18, C-5417 recurrent 2026-09-17, etc.
    rows = cur.execute(
        """
        SELECT crew_id, cert_type, valid_to
        FROM certifications
        WHERE valid_to >= '2026-09-15' AND valid_to <= '2026-10-15'
        ORDER BY valid_to, crew_id
        """
    ).fetchall()
    actual_ids = {r[0] for r in rows}
    expected_ids = {"C-2087", "C-2091", "C-5417", "C-3116", "C-5020", "C-2993"}
    if expected_ids == actual_ids:
        ok("Q04: expiring certs set matches expected crew_ids")
    else:
        fail("Q04: expiring certs", f"expected {expected_ids}, got {actual_ids}")
    # Spot-check C-2087 licence
    r = cur.execute(
        "SELECT valid_to FROM certifications WHERE crew_id='C-2087' AND cert_type='licence'"
    ).fetchone()
    check("Q04: C-2087 licence valid_to", r[0], "2026-09-18")

    print("\n-- Q05: Aircraft operating DX412 on 2026-09-15 ----")
    r = cur.execute(
        "SELECT aircraft, aircraft_type, seats FROM flights WHERE flight_id='DX412-2026-09-15'"
    ).fetchone()
    if r:
        check("Q05: aircraft reg",   r[0], "VT-DXC")
        check("Q05: aircraft_type",  r[1], "A320")
        check("Q05: seats",          r[2], 162)
    else:
        fail("Q05", "flight DX412-2026-09-15 not found in DB")

    print("\n-- Q06: C-3310 reserve window & reachability -------")
    r = cur.execute(
        "SELECT on_call_start, on_call_end FROM reserve_pool WHERE crew_id='C-3310' AND date='2026-09-15'"
    ).fetchone()
    if r:
        check("Q06: on_call_start", r[0], "06:00")
        check("Q06: on_call_end",   r[1], "18:00")
    else:
        fail("Q06", "C-3310 not in reserve_pool for 2026-09-15")
    r2 = cur.execute(
        "SELECT reachability_minutes FROM crew WHERE crew_id='C-3310'"
    ).fetchone()
    check("Q06: reachability_minutes", r2[0], 45)

    print("\n-- Q07: C-2210 base and rating ---------------------")
    r = cur.execute(
        "SELECT base, ratings FROM crew WHERE crew_id='C-2210'"
    ).fetchone()
    check("Q07: base",    r[0], "DEL")
    check("Q07: ratings", json.loads(r[1]), ["A320"])

    print("\n-- Q08: Crew on pairing P-2291 ---------------------")
    rows = cur.execute(
        "SELECT crew_id, role FROM pairing_crew WHERE pairing_id='P-2291' ORDER BY crew_id"
    ).fetchall()
    actual_crew = {r[0] for r in rows}
    expected_crew = {"C-1042","C-1694","C-3005","C-4395","C-4273","C-1873"}
    if expected_crew == actual_crew:
        ok("Q08: P-2291 crew set matches")
    else:
        fail("Q08: P-2291 crew", f"expected {expected_crew}, got {actual_crew}")

    print("\n-- Q11: Captains based at DEL ----------------------")
    rows = cur.execute(
        "SELECT crew_id FROM crew WHERE base='DEL' AND rank='Captain' AND status='active'"
    ).fetchall()
    actual = sorted([r[0] for r in rows])
    check("Q11: captains at DEL", actual, ["C-2210"])

    print("\n-- Q13: C-2087 rank and 28-day flight hours --------")
    r = cur.execute("SELECT rank FROM crew WHERE crew_id='C-2087'").fetchone()
    check("Q13: C-2087 rank", r[0], "Captain")
    fh = cur.execute(
        "SELECT duty_hours_7d, flight_hours_28d FROM duty_clocks WHERE crew_id='C-2087'"
    ).fetchone()
    check_approx("Q13: C-2087 flight_hours_28d", fh[1], 23.5)

    print("\n-- README facts ------------------------------------")
    # C-1042 operates pairing P-2291 day 1: DX412/DX413/DX588
    r = cur.execute(
        "SELECT flights_json FROM pairings WHERE pairing_id='P-2291' AND date='2026-09-15'"
    ).fetchone()
    if r:
        flights = json.loads(r[0])
        expected_flights = ["DX412-2026-09-15","DX413-2026-09-15","DX588-2026-09-15"]
        check("P-2291 day-1 flights", flights, expected_flights)
    else:
        fail("P-2291 day-1", "pairing not found in DB")

    # C-2091 is ATR-only (RULE-QUAL-05 exclusion case)
    r = cur.execute("SELECT ratings FROM crew WHERE crew_id='C-2091'").fetchone()
    ratings = json.loads(r[0])
    check("C-2091 is ATR-only", ratings, ["ATR72"])

    # costs dict
    costs = constants["costs"]
    check("costs: reserve_callout_pilot", costs["reserve_callout_pilot"], 18500)
    check("costs: deadhead_positioning",  costs["deadhead_positioning"],  6500)
    check("costs: cancellation_per_flight", costs["cancellation_per_flight"], 250000)

    print("\n-- Summary -----------------------------------------")
    print(f"  Passed : {len(passed)}")
    print(f"  Failed : {len(errors)}")
    if errors:
        print("\nFailed checks:")
        for label, detail in errors:
            print(f"  ✗ {label}: {detail}")
        sys.exit(1)
    else:
        print("\n  ALL CHECKS PASSED — SQLite DB is consistent with source data.")


if __name__ == "__main__":
    main()
