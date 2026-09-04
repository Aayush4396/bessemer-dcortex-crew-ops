"""
src/db/loader.py
================
Loads all dCortex JSON dataset files into SQLite (in-memory or on-disk).

Usage
-----
    from src.db.loader import init_db

    conn = init_db()                       # in-memory (default)
    conn = init_db(db_path="crew_ops.db")  # on-disk persistent file

The function is idempotent — tables use CREATE IF NOT EXISTS and inserts
use INSERT OR IGNORE, so re-running never produces duplicate rows.

What goes into SQLite (7 JSON files -> 9 tables):
    flights.json        -> flights
    crew.json           -> crew
    rosters.json        -> pairings + pairing_crew
    duty_clocks.json    -> duty_clocks + duty_clock_history
    reserve_pool.json   -> reserve_pool
    certifications.json -> certifications
    risk_signals.json   -> risk_signals

What stays as Python dicts (loaded by get_constants()):
    rules.json          -> RULES   (7 rule entries, static)
    costs.json          -> COSTS   (9 rate entries, static)
    scenarios.json      -> not loaded here (test fixture only)
"""

import json
import sqlite3
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE     = Path(__file__).parent          # src/db/
_SCHEMA   = _HERE / "schema.sql"
_REPO     = _HERE.parent.parent            # project root
_DATA_DIR = _REPO / "data"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_db(
    data_dir: str | Path = None,
    db_path: str = ":memory:",
) -> sqlite3.Connection:
    """
    Create all tables (from schema.sql) and load all JSON data.

    Parameters
    ----------
    data_dir : path to the data/ directory (default: auto-detected)
    db_path  : SQLite path. Use ":memory:" for in-process (default) or a
               file path like "crew_ops.db" for a persistent on-disk DB.

    Returns
    -------
    sqlite3.Connection  — ready to query, row_factory set to sqlite3.Row
    """
    data_dir = Path(data_dir) if data_dir else _DATA_DIR

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")

    _apply_schema(conn)

    _load_flights(conn, data_dir / "flights.json")
    _load_crew(conn, data_dir / "crew.json")
    _load_rosters(conn, data_dir / "rosters.json")
    _load_duty_clocks(conn, data_dir / "duty_clocks.json")
    _load_reserve_pool(conn, data_dir / "reserve_pool.json")
    _load_certifications(conn, data_dir / "certifications.json")
    _load_risk_signals(conn, data_dir / "risk_signals.json")

    conn.commit()
    return conn


def get_constants(data_dir: str | Path = None) -> dict:
    """
    Load the small static files that stay as Python dicts (not in SQLite).

    Returns
    -------
    {
        "rules": {...},    # from rules.json
        "costs": {...},    # from costs.json
    }
    """
    data_dir = Path(data_dir) if data_dir else _DATA_DIR
    return {
        "rules": _read_json(data_dir / "rules.json"),
        "costs": _read_json(data_dir / "costs.json"),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> dict | list:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _apply_schema(conn: sqlite3.Connection) -> None:
    """Execute schema.sql to create all tables and indexes."""
    sql = _SCHEMA.read_text(encoding="utf-8")
    # SQLite's executescript commits any open transaction first
    conn.executescript(sql)


# ---------------------------------------------------------------------------
# 1. flights  (147 rows)
# ---------------------------------------------------------------------------
def _load_flights(conn: sqlite3.Connection, path: Path) -> None:
    rows = _read_json(path)
    conn.executemany(
        """
        INSERT OR IGNORE INTO flights
            (flight_id, flight_no, date, dep_station, arr_station,
             dep_utc, arr_utc, block_hours, aircraft, aircraft_type, seats)
        VALUES
            (:flight_id, :flight_no, :date, :dep_station, :arr_station,
             :dep_utc, :arr_utc, :block_hours, :aircraft, :aircraft_type, :seats)
        """,
        rows,
    )


# ---------------------------------------------------------------------------
# 2. crew  (150 rows)
# ---------------------------------------------------------------------------
def _load_crew(conn: sqlite3.Connection, path: Path) -> None:
    rows = _read_json(path)
    conn.executemany(
        """
        INSERT OR IGNORE INTO crew
            (crew_id, name, rank, base, ratings, seniority,
             reachability_minutes, status)
        VALUES
            (:crew_id, :name, :rank, :base, :ratings, :seniority,
             :reachability_minutes, :status)
        """,
        [
            {**r, "ratings": json.dumps(r.get("ratings", []))}
            for r in rows
        ],
    )


# ---------------------------------------------------------------------------
# 3. rosters  -> pairings + pairing_crew
#    rosters.json structure:
#      { "pairings": [ { pairing_id, aircraft, days: [...], crew: [...] } ] }
#    days[]:  { date, flights: [...], report_utc, release_utc }
#    crew[]:  { crew_id, role }
# ---------------------------------------------------------------------------
def _load_rosters(conn: sqlite3.Connection, path: Path) -> None:
    data = _read_json(path)
    pairings_rows   = []
    pairing_crew_rows = []

    for p in data["pairings"]:
        pid      = p["pairing_id"]
        aircraft = p["aircraft"]

        # One pairings row per pairing-day
        for day in p["days"]:
            pairings_rows.append({
                "pairing_id":   pid,
                "aircraft":     aircraft,
                "date":         day["date"],
                "report_utc":   day["report_utc"],
                "release_utc":  day["release_utc"],
                "flights_json": json.dumps(day["flights"]),
            })

        # pairing_crew rows (one per crew member per pairing, not per day)
        for member in p["crew"]:
            pairing_crew_rows.append({
                "pairing_id": pid,
                "crew_id":    member["crew_id"],
                "role":       member["role"],
            })

    conn.executemany(
        """
        INSERT OR IGNORE INTO pairings
            (pairing_id, aircraft, date, report_utc, release_utc, flights_json)
        VALUES
            (:pairing_id, :aircraft, :date, :report_utc, :release_utc, :flights_json)
        """,
        pairings_rows,
    )
    conn.executemany(
        """
        INSERT OR IGNORE INTO pairing_crew (pairing_id, crew_id, role)
        VALUES (:pairing_id, :crew_id, :role)
        """,
        pairing_crew_rows,
    )


# ---------------------------------------------------------------------------
# 4. duty_clocks  -> duty_clocks (snapshot) + duty_clock_history (28-day rows)
#    JSON structure per crew:
#      { crew_id, as_of_utc, duty_hours_7d, flight_hours_28d,
#        last_rest_ended, daily_history: [{date, duty_hours, flight_hours}] }
# ---------------------------------------------------------------------------
def _load_duty_clocks(conn: sqlite3.Connection, path: Path) -> None:
    rows = _read_json(path)
    snapshot_rows = []
    history_rows  = []

    for c in rows:
        snapshot_rows.append({
            "crew_id":          c["crew_id"],
            "as_of_utc":        c["as_of_utc"],
            "duty_hours_7d":    c["duty_hours_7d"],
            "flight_hours_28d": c["flight_hours_28d"],
            "last_rest_ended":  c["last_rest_ended"],
        })
        for day in c.get("daily_history", []):
            history_rows.append({
                "crew_id":      c["crew_id"],
                "date":         day["date"],
                "duty_hours":   day["duty_hours"],
                "flight_hours": day["flight_hours"],
            })

    conn.executemany(
        """
        INSERT OR IGNORE INTO duty_clocks
            (crew_id, as_of_utc, duty_hours_7d, flight_hours_28d, last_rest_ended)
        VALUES
            (:crew_id, :as_of_utc, :duty_hours_7d, :flight_hours_28d, :last_rest_ended)
        """,
        snapshot_rows,
    )
    conn.executemany(
        """
        INSERT OR IGNORE INTO duty_clock_history
            (crew_id, date, duty_hours, flight_hours)
        VALUES
            (:crew_id, :date, :duty_hours, :flight_hours)
        """,
        history_rows,
    )


# ---------------------------------------------------------------------------
# 5. reserve_pool  -> reserve_pool (one row per crew x date)
#    JSON structure per entry:
#      { crew_id, base, dates: [...], oncall_window_utc: {start, end} }
# ---------------------------------------------------------------------------
def _load_reserve_pool(conn: sqlite3.Connection, path: Path) -> None:
    rows = _read_json(path)
    reserve_rows = []
    for r in rows:
        start = r["oncall_window_utc"]["start"]
        end   = r["oncall_window_utc"]["end"]
        for date in r["dates"]:
            reserve_rows.append({
                "crew_id":       r["crew_id"],
                "base":          r["base"],
                "date":          date,
                "on_call_start": start,
                "on_call_end":   end,
            })

    conn.executemany(
        """
        INSERT OR IGNORE INTO reserve_pool
            (crew_id, base, date, on_call_start, on_call_end)
        VALUES
            (:crew_id, :base, :date, :on_call_start, :on_call_end)
        """,
        reserve_rows,
    )


# ---------------------------------------------------------------------------
# 6. certifications  (~600 rows, 4 per crew)
# ---------------------------------------------------------------------------
def _load_certifications(conn: sqlite3.Connection, path: Path) -> None:
    rows = _read_json(path)
    conn.executemany(
        """
        INSERT OR IGNORE INTO certifications
            (crew_id, cert_type, valid_from, valid_to)
        VALUES
            (:crew_id, :cert_type, :valid_from, :valid_to)
        """,
        rows,
    )


# ---------------------------------------------------------------------------
# 7. risk_signals  (one row per crew, pre-computed)
# ---------------------------------------------------------------------------
def _load_risk_signals(conn: sqlite3.Connection, path: Path) -> None:
    rows = _read_json(path)
    conn.executemany(
        """
        INSERT OR IGNORE INTO risk_signals
            (crew_id, as_of_utc, disruption_risk_score, drivers_json)
        VALUES
            (:crew_id, :as_of_utc, :disruption_risk_score, :drivers_json)
        """,
        [
            {**r, "drivers_json": json.dumps(r.get("drivers", []))}
            for r in rows
        ],
    )


# ---------------------------------------------------------------------------
# CLI: python -m src.db.loader  (quick smoke-test)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    data_dir = sys.argv[1] if len(sys.argv) > 1 else None
    print("Loading data into in-memory SQLite...")
    conn = init_db(data_dir=data_dir)
    cur = conn.cursor()

    tables = [
        "flights", "crew", "pairings", "pairing_crew",
        "duty_clocks", "duty_clock_history",
        "reserve_pool", "certifications", "risk_signals",
    ]
    print("\nRow counts:")
    for t in tables:
        n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:<25} {n:>6} rows")

    constants = get_constants(data_dir)
    print(f"\n  rules (dict keys)  : {list(constants['rules'].keys())}")
    print(f"  costs (dict keys)  : {list(constants['costs'].keys())}")
    print("\nDone — SQLite loaded successfully.")
