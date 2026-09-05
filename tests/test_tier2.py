"""
tests/test_tier2.py
===================
Deterministic handler tests for Tier 2 questions Q17–Q30.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.loader import init_db
from src.tier1 import get_flight_schedule_stats, get_flights
from src.tier2 import (
    execute_readonly_sql,
    evaluate_base_positioning,
    evaluate_certifications,
    evaluate_cover,
    evaluate_cover_candidates,
    evaluate_duty_7d,
    evaluate_fdp_limit,
    evaluate_qualification,
    evaluate_reserve_callout,
    evaluate_rest,
    get_cost_rates,
    get_crew_entity,
    get_flight_duty_times,
    get_pairing_entity,
    get_station_movements,
)
from src.tier2.entities import _absence_impact

_QUESTIONS = json.loads((Path(__file__).parent.parent / "data" / "questions.json").read_text(encoding="utf-8"))
_Q = {q["question_id"]: q for q in _QUESTIONS}


@pytest.fixture(scope="session")
def conn():
    return init_db()


def test_q17_uncrewed_pairing(conn):
    expected = _Q["Q17"]["expected_answer"]
    pairing = get_pairing_entity("P-2291", conn=conn)
    assert pairing["days"][0]["flight_ids"] == expected["day1"]
    assert pairing["days"][1]["flight_ids"] == expected["day2_also_at_risk"]
    assert pairing["passengers_day1"] == expected["passengers_day1"]
    assert pairing["rotation_days"] == 2
    impact = pairing["absence_impact"]
    assert [d["date"] for d in impact["days"]] == [d["date"] for d in pairing["days"]]
    assert impact["immediately_uncrewed"] == expected["day1"]
    assert impact["subsequent_at_risk"] == expected["day2_also_at_risk"]
    assert impact["days"][0]["impact"] == "immediately_uncrewed"
    assert impact["days"][1]["impact"] == "at_risk"
    assert impact["passengers_immediately_uncrewed"] == expected["passengers_day1"]
    assert impact["day1"] == expected["day1"]
    assert impact["day2_also_at_risk"] == expected["day2_also_at_risk"]
    assert impact["passengers_day1"] == expected["passengers_day1"]

    day2 = get_pairing_entity("P-2291", conn=conn, as_of_date="2026-09-16")
    late = day2["absence_impact"]
    assert late["already_operated"] == expected["day1"]
    assert late["immediately_uncrewed"] == expected["day2_also_at_risk"]
    assert late["subsequent_at_risk"] == []


def test_absence_impact_lists_every_later_day():
    days = [
        {
            "day_index": i,
            "date": f"2026-09-{14 + i:02d}",
            "flight_ids": [f"DX{i}00"],
            "passengers": 100 * i,
            "dep_station": "BLR",
        }
        for i in (1, 2, 3)
    ]
    impact = _absence_impact(days, "2026-09-15")
    assert [d["impact"] for d in impact["days"]] == [
        "immediately_uncrewed",
        "at_risk",
        "at_risk",
    ]
    assert impact["immediately_uncrewed"] == ["DX100"]
    assert impact["subsequent_at_risk"] == ["DX200", "DX300"]
    assert impact["already_operated"] == []


def test_q18_duty_cover_c2087(conn):
    expected = _Q["Q18"]["expected_answer"]
    result = evaluate_duty_7d(crew_id="C-2087", pairing_id="P-2291", conn=conn)
    assert result["legal"] is False
    assert result["issues"] == expected["issues"]
    cover = evaluate_cover(crew_id="C-2087", pairing_id="P-2291", conn=conn)
    assert cover["legal"] is False
    assert cover["issues"] == expected["issues"]


def test_q19_blr_closure(conn):
    expected = _Q["Q19"]["expected_answer"]
    actual = get_station_movements("BLR", "2026-09-17", "08:00", "14:00", conn=conn)
    assert actual == expected


def test_q20_fdp_delay(conn):
    expected = _Q["Q20"]["expected_answer"]
    result = evaluate_fdp_limit(
        aircraft="VT-DXA",
        date="2026-09-16",
        delay_hours=1.5,
        conn=conn,
    )
    assert result["breach"] is True
    assert result["fdp_after_delay"] == expected["fdp_after_delay"]
    assert result["fdp_limit"] == expected["fdp_limit"]


def test_q21_deadhead_c2210(conn):
    expected = _Q["Q21"]["expected_answer"]
    pos = evaluate_base_positioning("C-2210", "P-2291", conn=conn)
    assert pos["legal"] is True
    assert pos["needs_deadhead"] is True
    assert pos["delay_hours"] == 3.0
    assert pos["cost_inr"] == 41200
    assert pos["consequence"] == expected["consequence"]
    cover = evaluate_cover(crew_id="C-2210", pairing_id="P-2291", conn=conn)
    assert cover["legal"] is True
    assert cover["issues"] == []
    assert cover["consequence"] == expected["consequence"]
    rest = evaluate_rest(crew_id="C-2210", pairing_id="P-2291", conn=conn)
    duty = evaluate_duty_7d(crew_id="C-2210", pairing_id="P-2291", conn=conn)
    qual = evaluate_qualification(crew_id="C-2210", pairing_id="P-2291", conn=conn)
    assert rest["legal"] is True
    assert duty["legal"] is True
    assert qual["passed"] is True


def test_q22_cert_c5417(conn):
    expected = _Q["Q22"]["expected_answer"]
    result = evaluate_certifications("C-5417", "2026-09-19", conn=conn)
    assert result["legal"] is False
    assert result["rule"] == expected["rule"]
    assert result["detail"] == expected["detail"]


def test_q23_earliest_report():
    expected = _Q["Q23"]["expected_answer"]
    result = evaluate_rest(release_utc="2026-09-16T15:30:00Z")
    assert result["earliest_report_utc"] == expected


def test_q24_duty_cover_c3305(conn):
    expected = _Q["Q24"]["expected_answer"]
    result = evaluate_duty_7d(crew_id="C-3305", pairing_id="P-2291", conn=conn)
    assert result["legal"] is False
    assert result["issues"] == expected["issues"]
    cover = evaluate_cover(crew_id="C-3305", pairing_id="P-2291", conn=conn)
    assert cover["legal"] is False
    assert cover["issues"] == expected["issues"]


def test_q25_cancellation_cost(conn):
    expected = _Q["Q25"]["expected_answer"]
    flights = get_flights(date="2026-09-16", flight_no="DX404", conn=conn)
    costs = get_cost_rates()
    assert flights[0]["seats"] == expected["passengers"]
    assert costs["cancellation_per_flight"] == expected["cost_inr"]


def test_q26_near_duty_cap(conn):
    expected = _Q["Q26"]["expected_answer"]
    result = evaluate_duty_7d(as_of_date="2026-09-15", min_hours=45, conn=conn)
    assert result["crew"] == expected


def test_query_database_weekly_and_monthly(conn):
    weekly = execute_readonly_sql(
        """
        SELECT c.crew_id, c.name, c.rank, d.duty_hours_7d
        FROM crew c
        JOIN duty_clocks d ON d.crew_id = c.crew_id
        WHERE d.duty_hours_7d < 30
        ORDER BY d.duty_hours_7d ASC
        """,
        conn=conn,
    )
    assert "error" not in weekly
    assert weekly["row_count"] > 0
    assert {"crew_id", "name", "rank", "duty_hours_7d"} <= set(weekly["columns"])
    assert all(row["duty_hours_7d"] < 30 for row in weekly["rows"])

    monthly = execute_readonly_sql(
        """
        SELECT c.crew_id, c.name, c.rank, d.flight_hours_28d
        FROM crew c
        JOIN duty_clocks d ON d.crew_id = c.crew_id
        WHERE d.flight_hours_28d >= 0
        ORDER BY d.flight_hours_28d DESC
        LIMIT 5
        """,
        conn=conn,
    )
    assert monthly["row_count"] == 5
    assert "flight_hours_28d" in monthly["columns"]


def test_query_database_rejects_writes(conn):
    blocked = execute_readonly_sql("DELETE FROM crew", conn=conn)
    assert "error" in blocked
    chat = execute_readonly_sql("SELECT * FROM chat_messages", conn=conn)
    assert "error" in chat


def test_query_database_is_sqlite_dialect(conn):
    pg = execute_readonly_sql(
        "SELECT crew_id FROM crew WHERE 'A320' = ANY(ratings)",
        conn=conn,
    )
    assert "error" in pg
    assert "SQLite" in pg["error"]
    ok = execute_readonly_sql(
        """
        SELECT c.crew_id FROM crew c
        WHERE c.rank = 'Captain'
          AND EXISTS (SELECT 1 FROM json_each(c.ratings) WHERE value = 'A320')
        LIMIT 3
        """,
        conn=conn,
    )
    assert "error" not in ok
    assert ok["row_count"] >= 1


def test_duty_split_lists_include_name_rank(conn):
    result = evaluate_duty_7d(as_of_date="2026-09-14", split_hours=30, conn=conn)
    assert result["below"] and result["above"]
    sample = result["below"][0]
    assert {"crew_id", "name", "rank", "duty_hours_7d"} <= set(sample)
    assert all(r["duty_hours_7d"] < 30 for r in result["below"])
    assert all(r["duty_hours_7d"] > 30 for r in result["above"])
    counted = len(result["below"]) + len(result["equal"]) + len(result["above"])
    roster = evaluate_duty_7d(as_of_date="2026-09-14", conn=conn)
    assert counted == len(roster["crew"])


def test_q27_reserve_callout(conn):
    expected = _Q["Q27"]["expected_answer"]
    result = evaluate_reserve_callout(
        date="2026-09-16",
        rank="Captain",
        required_report_utc="2026-09-16T03:00:00Z",
        aircraft_type="ATR72",
        conn=conn,
    )
    assert result["eligible"] == expected["eligible"]
    excluded_by_id = {e["crew_id"]: e["reason"] for e in result["excluded"]}
    for example in expected["excluded_examples"]:
        assert excluded_by_id[example["crew_id"]] == example["reason"]


def test_q28_downstream_rest(conn):
    expected = _Q["Q28"]["expected_answer"]
    result = evaluate_rest(crew_id="C-5837", pairing_id="P-2291", conn=conn)
    assert result["legal"] is False
    assert result["issues"] == expected["issues"]
    cover = evaluate_cover(crew_id="C-5837", pairing_id="P-2291", conn=conn)
    assert cover["legal"] is False
    assert cover["issues"] == expected["issues"]


def test_cover_rejects_first_officer_for_captain_seat(conn):
    fo_as_captain = evaluate_cover(
        crew_id="C-1694",
        pairing_id="P-2291",
        role="Captain",
        conn=conn,
    )
    assert fo_as_captain["legal"] is False
    assert fo_as_captain["required_role"] == "Captain"
    assert fo_as_captain["candidate_rank"] == "First Officer"
    assert any("Rank mismatch" in issue for issue in fo_as_captain["issues"])

    inferred = evaluate_cover(
        crew_id="C-1694",
        pairing_id="P-2291",
        replace_crew_id="C-1042",
        conn=conn,
    )
    assert any("vacant seat is Captain" in issue for issue in inferred["issues"])

    fo_for_fo = evaluate_cover(
        crew_id="C-1694",
        pairing_id="P-2291",
        role="First Officer",
        conn=conn,
    )
    assert not any("Rank mismatch" in issue for issue in fo_for_fo["issues"])


def test_cover_candidates_use_real_issues_not_invented_qual(conn):
    result = evaluate_cover_candidates(
        pairing_id="P-2291",
        role="Captain",
        replace_crew_id="C-1042",
        conn=conn,
    )
    legal_ids = {row["crew_id"] for row in result["legal"]}
    excluded_by_id = {row["crew_id"]: row["issues"] for row in result["excluded"]}
    assert "C-1042" not in legal_ids
    assert {"C-3310", "C-1526", "C-3983", "C-5566"} <= legal_ids
    assert "C-2442" in excluded_by_id
    assert any("leave" in issue for issue in excluded_by_id["C-2442"])
    assert not any("A320 rating" in issue for issue in excluded_by_id.get("C-1526", []))
    assert not any("A320 rating" in issue for issue in excluded_by_id.get("C-1017", []))
    leave = evaluate_cover(crew_id="C-2442", pairing_id="P-2291", role="Captain", conn=conn)
    assert leave["legal"] is False
    assert any("leave" in issue for issue in leave["issues"])


def test_q29_hyd_closure(conn):
    expected = _Q["Q29"]["expected_answer"]
    actual = get_station_movements("HYD", "2026-09-19", "05:00", "09:00", conn=conn)
    assert actual == expected


def test_q30_max_seats(conn):
    a320 = get_flights(aircraft_type="A320", date="2026-09-15", conn=conn)
    atr = get_flights(aircraft_type="ATR72", date="2026-09-15", conn=conn)
    assert a320[0]["seats"] == 162
    assert atr[0]["seats"] == 72
    seats = get_flight_schedule_stats(metric="max_seats", conn=conn)
    assert seats == _Q["Q30"]["expected_answer"]


def test_flight_duty_times_join(conn):
    duty = get_flight_duty_times(flight_id="DX412-2026-09-15", conn=conn)
    assert duty["pairing_id"] == "P-2291"
    assert duty["report_utc"] == "2026-09-15T06:00:00Z"
    assert duty["release_utc"] == "2026-09-15T15:30:00Z"
    assert any(m["crew_id"] == "C-1042" for m in duty["crew"])


def test_crew_detail_join(conn):
    crew = get_crew_entity("C-1042", conn=conn)
    assert crew["crew_id"] == "C-1042"
    assert any(p["pairing_id"] == "P-2291" for p in crew["pairings"])
    assert crew["certs"]
