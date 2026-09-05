-- =============================================================================
-- dCortex Crew Ops Advisor — SQLite Schema
-- =============================================================================
-- Run order matters (FK logical dependency, though SQLite doesn't enforce FKs
-- by default). Recreate by running:  sqlite3 crew_ops.db < schema.sql
--
-- Tables sourced from JSON:
--   flights, crew, pairings, pairing_crew, duty_clocks,
--   duty_clock_history, reserve_pool, certifications, risk_signals
--
-- NOT in SQLite (kept as Python dicts loaded at import time):
--   rules.json, costs.json, scenarios.json
-- =============================================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- 1. flights
--    147 legs, 8 stations, 6 aircraft (4x A320-162, 2x ATR72-72)
--    PK: flight_id  e.g. "DX401-2026-09-14"
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS flights (
    flight_id     TEXT PRIMARY KEY,        -- "DX401-2026-09-14"
    flight_no     TEXT NOT NULL,           -- "DX401"
    date          TEXT NOT NULL,           -- "2026-09-14"  (UTC calendar date)
    dep_station   TEXT NOT NULL,           -- IATA: BLR, DEL, BOM, CCU, COK, HYD, MAA, AMD
    arr_station   TEXT NOT NULL,
    dep_utc       TEXT NOT NULL,           -- ISO-8601 datetime string
    arr_utc       TEXT NOT NULL,
    block_hours   REAL NOT NULL,
    aircraft      TEXT NOT NULL,           -- tail reg: "VT-DXA"
    aircraft_type TEXT NOT NULL,           -- "A320" | "ATR72"
    seats         INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_flights_date        ON flights(date);
CREATE INDEX IF NOT EXISTS idx_flights_dep_station ON flights(dep_station, date);
CREATE INDEX IF NOT EXISTS idx_flights_aircraft    ON flights(aircraft);

-- ---------------------------------------------------------------------------
-- 2. crew
--    150 crew members - pilots (Captain/FO) + cabin crew
--    ratings stored as JSON text array  e.g. '["A320","ATR72"]'
--    status: "active" | "leave" | "training"  - ALWAYS filter on status='active'
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS crew (
    crew_id              TEXT PRIMARY KEY,   -- "C-1042"
    name                 TEXT NOT NULL,
    rank                 TEXT NOT NULL,      -- "Captain" | "First Officer" | "Senior Cabin Crew" | "Cabin Crew"
    base                 TEXT NOT NULL,      -- IATA station
    ratings              TEXT NOT NULL,      -- JSON array e.g. '["A320"]'
    seniority            INTEGER,
    reachability_minutes INTEGER,
    status               TEXT NOT NULL       -- "active" | "leave" | "training"
        CHECK(status IN ('active','leave','training'))
);

CREATE INDEX IF NOT EXISTS idx_crew_base   ON crew(base);
CREATE INDEX IF NOT EXISTS idx_crew_rank   ON crew(rank);
CREATE INDEX IF NOT EXISTS idx_crew_status ON crew(status);

-- ---------------------------------------------------------------------------
-- 3. pairings
--    One row per (pairing, day). A multi-day pairing produces multiple rows.
--    flights_json is the ordered JSON array of flight_ids for that day.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pairings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    pairing_id   TEXT NOT NULL,             -- "P-2291"
    aircraft     TEXT NOT NULL,             -- tail reg "VT-DXC"
    date         TEXT NOT NULL,             -- "2026-09-15"
    report_utc   TEXT NOT NULL,             -- "2026-09-15T02:00:00Z"
    release_utc  TEXT NOT NULL,             -- "2026-09-15T12:45:00Z"
    flights_json TEXT NOT NULL              -- JSON array of flight_ids (ordered)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_pairings_pid_date ON pairings(pairing_id, date);
CREATE INDEX        IF NOT EXISTS idx_pairings_date     ON pairings(date);

-- ---------------------------------------------------------------------------
-- 4. pairing_crew
--    Many-to-many: which crew member is on which pairing, in what role.
--    One row per (pairing, crew_member). role repeats the rank for this duty.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pairing_crew (
    pairing_id  TEXT NOT NULL,
    crew_id     TEXT NOT NULL,
    role        TEXT NOT NULL,  -- "Captain" | "First Officer" | "Senior Cabin Crew" | "Cabin Crew"
    PRIMARY KEY (pairing_id, crew_id)
);

CREATE INDEX IF NOT EXISTS idx_pc_crew_id    ON pairing_crew(crew_id);
CREATE INDEX IF NOT EXISTS idx_pc_pairing_id ON pairing_crew(pairing_id);

-- ---------------------------------------------------------------------------
-- 5. duty_clocks
--    Per-crew snapshot totals valid as of 2026-09-14T18:00:00Z.
--    NOTE: these pre-aggregated fields are ONLY valid at snapshot time.
--    For on-the-fly window calculations always use duty_clock_history.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS duty_clocks (
    crew_id           TEXT PRIMARY KEY,
    as_of_utc         TEXT NOT NULL,
    duty_hours_7d     REAL NOT NULL,
    flight_hours_28d  REAL NOT NULL,
    last_rest_ended   TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- 6. duty_clock_history
--    28 rows per crew (2026-08-18 to 2026-09-14), total ~4,200 rows.
--    This is the source of truth for rolling-window rule checks.
--    Use: SELECT SUM(duty_hours) WHERE crew_id=? AND date BETWEEN ? AND ?
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS duty_clock_history (
    crew_id      TEXT NOT NULL,
    date         TEXT NOT NULL,          -- "2026-08-18"  (UTC calendar date)
    duty_hours   REAL NOT NULL DEFAULT 0.0,
    flight_hours REAL NOT NULL DEFAULT 0.0,
    PRIMARY KEY (crew_id, date)
);

CREATE INDEX IF NOT EXISTS idx_dch_date ON duty_clock_history(date);

-- ---------------------------------------------------------------------------
-- 7. reserve_pool
--    16 reserves x 7 dates = up to 112 rows (one row per crew x date).
--    on_call_start/end are UTC time strings "HH:MM".
--    A reserve is callable when the required REPORT time falls inside window.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reserve_pool (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    crew_id       TEXT NOT NULL,
    base          TEXT NOT NULL,
    date          TEXT NOT NULL,          -- "2026-09-14"
    on_call_start TEXT NOT NULL,          -- "06:00"
    on_call_end   TEXT NOT NULL           -- "18:00"
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_rp_crew_date ON reserve_pool(crew_id, date);
CREATE INDEX        IF NOT EXISTS idx_rp_base_date ON reserve_pool(base, date);

-- ---------------------------------------------------------------------------
-- 8. certifications
--    4 cert types per crew -> ~600 rows total.
--    cert_type: "licence" | "medical_class1" | "recurrent_training" | "dangerous_goods"
--    RULE-CERT-06: all certs must be valid (valid_to >= duty_date)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS certifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    crew_id    TEXT NOT NULL,
    cert_type  TEXT NOT NULL,   -- "licence" | "medical_class1" | "recurrent_training" | "dangerous_goods"
    valid_from TEXT NOT NULL,   -- "YYYY-MM-DD"
    valid_to   TEXT NOT NULL    -- "YYYY-MM-DD"
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_cert_crew_type ON certifications(crew_id, cert_type);
CREATE INDEX        IF NOT EXISTS idx_cert_valid_to  ON certifications(valid_to);

-- ---------------------------------------------------------------------------
-- 9. risk_signals
--    Pre-computed disruption risk scores. Do NOT recompute - treat as input.
--    drivers_json is a JSON text array of driver description strings.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS risk_signals (
    crew_id               TEXT PRIMARY KEY,
    as_of_utc             TEXT NOT NULL,
    disruption_risk_score REAL NOT NULL,
    drivers_json          TEXT NOT NULL    -- JSON array e.g. '["short-rest pattern"]'
);

-- ---------------------------------------------------------------------------
-- 10. chat_sessions
--     Tracks multi-turn operational conversation sessions.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id  TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    tier        INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cs_updated_at ON chat_sessions(updated_at DESC);

-- ---------------------------------------------------------------------------
-- 11. chat_messages
--     Full uncompacted audit log of all user prompts, assistant answers,
--     tool calls, and SQLite results.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_messages (
    message_id      TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    sender          TEXT NOT NULL,          -- 'user' | 'assistant'
    content         TEXT NOT NULL,
    tier_used       INTEGER NOT NULL DEFAULT 1,
    tool_calls      TEXT,                   -- JSON array string
    tool_results    TEXT,                   -- JSON array string
    reasoning_trace TEXT,                   -- JSON array string
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cm_session_created ON chat_messages(session_id, created_at ASC);
