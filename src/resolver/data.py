"""
src/resolver/data.py
====================
Loads SQLite + JSON data into in-memory dicts matching generate.py's structures.
Cached on first call so repeated resolver invocations don't re-query.
"""

import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from src.tier1.connection import get_connection

_DATA_DIR = Path(__file__).parent.parent.parent / "data"

# Module-level caches (populated by load_all)
crew: dict = {}
week_duties: dict = {}
history: dict = {}
CERT: dict = {}
FBY: dict = {}
costs: dict = {}
reserve_pool: list = []
RESERVE_IDS: set = set()
pairings: list = []
flights_list: list = []

ODD = [date(2026, 9, d) for d in (15, 17, 19)]
EVEN = [date(2026, 9, d) for d in (14, 16, 18, 20)]

_loaded = False


def _parse_dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


def _hrs(td: timedelta) -> float:
    return round(td.total_seconds() / 3600.0, 2)


def load_all(conn: sqlite3.Connection | None = None):
    """Load all data structures needed by the resolver. Idempotent."""
    global _loaded
    if _loaded:
        return
    conn = get_connection(conn)
    _load_crew(conn)
    _load_flights(conn)
    _load_pairings_and_duties(conn)
    _load_history(conn)
    _load_certifications(conn)
    _load_reserve_pool(conn)
    _load_costs()
    _loaded = True


def _load_crew(conn: sqlite3.Connection):
    global crew
    rows = conn.execute("SELECT * FROM crew").fetchall()
    for r in rows:
        crew[r["crew_id"]] = {
            "crew_id": r["crew_id"],
            "name": r["name"],
            "rank": r["rank"],
            "base": r["base"],
            "ratings": json.loads(r["ratings"]),
            "seniority": r["seniority"],
            "reachability_minutes": r["reachability_minutes"],
            "status": r["status"],
        }


def _load_flights(conn: sqlite3.Connection):
    rows = conn.execute("SELECT * FROM flights").fetchall()
    flights_list.clear()
    for r in rows:
        f = {
            "flight_id": r["flight_id"],
            "flight_no": r["flight_no"],
            "date": r["date"],
            "dep_station": r["dep_station"],
            "arr_station": r["arr_station"],
            "dep_utc": r["dep_utc"],
            "arr_utc": r["arr_utc"],
            "block_hours": r["block_hours"],
            "aircraft": r["aircraft"],
            "aircraft_type": r["aircraft_type"],
            "seats": r["seats"],
        }
        flights_list.append(f)
        FBY[r["flight_id"]] = f


def _load_pairings_and_duties(conn: sqlite3.Connection):
    """Load pairings from SQLite and build week_duties index."""
    day_rows = conn.execute(
        "SELECT pairing_id, aircraft, date, report_utc, release_utc, flights_json FROM pairings ORDER BY pairing_id, date"
    ).fetchall()
    crew_rows = conn.execute(
        "SELECT pairing_id, crew_id, role FROM pairing_crew"
    ).fetchall()

    crew_by_pairing: dict[str, list[dict]] = {}
    for r in crew_rows:
        crew_by_pairing.setdefault(r["pairing_id"], []).append(
            {"crew_id": r["crew_id"], "role": r["role"]}
        )

    pairing_map: dict[str, dict] = {}
    for r in day_rows:
        pid = r["pairing_id"]
        if pid not in pairing_map:
            pairing_map[pid] = {
                "pairing_id": pid,
                "aircraft": r["aircraft"],
                "days": [],
                "crew": crew_by_pairing.get(pid, []),
            }
        pairing_map[pid]["days"].append({
            "date": r["date"],
            "flights": json.loads(r["flights_json"]),
            "report_utc": r["report_utc"],
            "release_utc": r["release_utc"],
        })
    pairings.clear()
    pairings.extend(pairing_map.values())

    week_duties.clear()
    for cid in crew:
        week_duties[cid] = []
    for p in pairings:
        for day in p["days"]:
            d = date.fromisoformat(day["date"])
            rep = _parse_dt(day["report_utc"])
            rel = _parse_dt(day["release_utc"])
            fh = sum(FBY[fid]["block_hours"] for fid in day["flights"])
            for m in p["crew"]:
                cid = m["crew_id"]
                if cid in week_duties:
                    week_duties[cid].append(
                        (d, rep, rel, _hrs(rel - rep), round(fh, 2), p["pairing_id"])
                    )
    for v in week_duties.values():
        v.sort(key=lambda x: x[0])


def _load_history(conn: sqlite3.Connection):
    global history
    rows = conn.execute("SELECT * FROM duty_clock_history").fetchall()
    for r in rows:
        cid = r["crew_id"]
        d = date.fromisoformat(r["date"])
        history.setdefault(cid, {})[d] = (r["duty_hours"], r["flight_hours"])


def _load_certifications(conn: sqlite3.Connection):
    global CERT
    rows = conn.execute("SELECT crew_id, cert_type, valid_to FROM certifications").fetchall()
    for r in rows:
        CERT.setdefault(r["crew_id"], {})[r["cert_type"]] = date.fromisoformat(r["valid_to"])


def _load_reserve_pool(conn: sqlite3.Connection):
    rows = conn.execute(
        "SELECT crew_id, base, date, on_call_start, on_call_end FROM reserve_pool ORDER BY crew_id, date"
    ).fetchall()

    by_crew: dict[str, dict] = {}
    for r in rows:
        cid = r["crew_id"]
        if cid not in by_crew:
            by_crew[cid] = {
                "crew_id": cid,
                "base": r["base"],
                "dates": [],
                "oncall_window_utc": {"start": r["on_call_start"], "end": r["on_call_end"]},
            }
        by_crew[cid]["dates"].append(r["date"])
    reserve_pool.clear()
    reserve_pool.extend(by_crew.values())
    RESERVE_IDS.clear()
    RESERVE_IDS.update(r["crew_id"] for r in reserve_pool)


def _load_costs():
    with open(_DATA_DIR / "costs.json", encoding="utf-8") as f:
        costs.update(json.load(f))
