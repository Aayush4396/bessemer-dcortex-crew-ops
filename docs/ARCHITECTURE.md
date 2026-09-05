# dCortex Crew Operations Advisor Architecture

This document describes the current end-to-end architecture of the dCortex Crew Operations Advisor: data ingestion, SQLite storage, deterministic query and legality logic, resolver flows, LangGraph orchestration, FastAPI APIs, React UI, and evaluation.

## 1. System Purpose

The application is a NOC copilot for a fictional airline operating from a BLR hub. It answers crew-control questions using a frozen synthetic operational snapshot:

- Snapshot: `2026-09-14T18:00:00Z`
- Planned operations: `2026-09-15` through `2026-09-20`
- Fleet: A320 and ATR72
- Dataset: 147 flights, 150 crew, 39 pairings, 16 reserves
- Time convention: UTC; rolling duty windows use inclusive calendar dates

The core design rule is that the LLM does not calculate operational values. It identifies the required operation and formats verified results. Python and SQLite perform lookups, time arithmetic, legality checks, disruption analysis, and recovery costing.

## 2. High-Level Architecture

```mermaid
flowchart TB
    Controller[Crew Controller]

    subgraph Browser[React Operations Console :5173]
        Workspace[Pairings Workspace]
        Details[Crew / Flight / Pairing Details]
        Copilot[Copilot Chat]
        Audit[Reasoning and Tool Audit]
    end

    subgraph API[FastAPI Backend :8000]
        ReadAPI[Health, Stats, Pairings, Crew, Flight APIs]
        ChatAPI[POST /api/chat]
        SessionAPI[Session APIs]
        SimAPI[Tier 2 Simulation Endpoint]
        RecoverAPI[Tier 3 Recovery Endpoint]
    end

    subgraph Orchestration[Agent Orchestration]
        Graph[LangGraph StateGraph]
        LLM[Sarvam-105B via OpenAI-compatible client]
        ToolNode[Deterministic Tool Node]
        Memory[Chat Session Memory]
    end

    subgraph Deterministic[Deterministic Domain Layer]
        Tier1[Tier 1 Query Handlers]
        Rules[Rules Engine]
        Resolver[Disruption and Recovery Resolver]
    end

    subgraph Storage[Local Data and Storage]
        SQLite[(crew_ops.db)]
        JSON[data/*.json]
    end

    Controller --> Browser
    Workspace --> ReadAPI
    Details --> ReadAPI
    Copilot --> ChatAPI
    Audit --> ChatAPI
    Browser --> API
    ChatAPI --> Graph
    SessionAPI --> Memory
    Memory --> SQLite
    Graph --> LLM
    Graph --> ToolNode
    ToolNode --> Tier1
    ToolNode --> Rules
    ToolNode --> Resolver
    ReadAPI --> Tier1
    ReadAPI --> SQLite
    SimAPI --> Resolver
    RecoverAPI --> Resolver
    Tier1 --> SQLite
    Rules --> SQLite
    Resolver --> SQLite
    Resolver --> JSON
    JSON --> SQLite
```

### Current implementation boundary

The deterministic resolver and agent tools for Tier 2 and Tier 3 are implemented. `POST /api/simulate` and `POST /api/recover` in `src/api/server.py` still return placeholder responses, so direct UI/API access to those capabilities is not yet connected end to end.

## 3. Source Data and Ingestion

The `data/` directory is the source snapshot. `src/db/loader.py` applies `src/db/schema.sql`, transforms nested JSON structures, and loads an idempotent SQLite database.

```mermaid
flowchart LR
    subgraph Files[data/ JSON sources]
        F[flights.json]
        C[crew.json]
        R[rosters.json]
        D[duty_clocks.json]
        RP[reserve_pool.json]
        CERT[certifications.json]
        RS[risk_signals.json]
        Rules[rules.json]
        Costs[costs.json]
        Scenarios[scenarios.json]
        Questions[questions.json]
    end

    Loader[src/db/loader.py]
    Schema[src/db/schema.sql]
    DB[(SQLite database)]
    Runtime[Python runtime constants]

    F --> Loader
    C --> Loader
    R --> Loader
    D --> Loader
    RP --> Loader
    CERT --> Loader
    RS --> Loader
    Schema --> Loader
    Loader --> DB
    Rules --> Runtime
    Costs --> Runtime
    Scenarios --> Runtime
    Questions --> Runtime
```

### JSON-to-SQLite transformations

| JSON source | SQLite destination | Transformation |
|---|---|---|
| `flights.json` | `flights` | One row per flight leg |
| `crew.json` | `crew` | `ratings` array serialized as JSON text |
| `rosters.json` | `pairings`, `pairing_crew` | Pairing days and crew assignments are decomposed into relational records |
| `duty_clocks.json` | `duty_clocks`, `duty_clock_history` | Snapshot totals are separated from 28 daily history rows |
| `reserve_pool.json` | `reserve_pool` | Nested dates are expanded to one row per crew/date |
| `certifications.json` | `certifications` | One row per crew/certification type |
| `risk_signals.json` | `risk_signals` | `drivers` array serialized as JSON text |
| `rules.json` | Python configuration | Loaded by `src/rules/config.py`; not stored in SQLite |
| `costs.json` | Resolver runtime configuration | Loaded by `src/resolver/data.py`; not stored in SQLite |
| `scenarios.json`, `questions.json` | Evaluation/runtime fixtures | Used by evaluators and scenario specifications |

The loader enables SQLite WAL mode, foreign keys, indexes, and `sqlite3.Row` results. The default application database is `crew_ops.db`; tests and evaluators normally use an in-memory database.

## 4. Relational Data Model

```mermaid
erDiagram
    CREW ||--o{ PAIRING_CREW : assigned_to
    PAIRINGS ||--o{ PAIRING_CREW : contains
    CREW ||--|| DUTY_CLOCKS : snapshot
    CREW ||--o{ DUTY_CLOCK_HISTORY : history
    CREW ||--o{ RESERVE_POOL : reserve
    CREW ||--o{ CERTIFICATIONS : holds
    CREW ||--|| RISK_SIGNALS : risk

    FLIGHTS {
        string flight_id PK
        string flight_no
        string date
        string dep_station
        string arr_station
        string dep_utc
        string arr_utc
        float block_hours
        string aircraft
        string aircraft_type
        int seats
    }

    CREW {
        string crew_id PK
        string name
        string rank
        string base
        json ratings
        int seniority
        int reachability_minutes
        string status
    }

    PAIRINGS {
        int id PK
        string pairing_id
        string aircraft
        string date
        string report_utc
        string release_utc
        json flights_json
    }

    PAIRING_CREW {
        string pairing_id PK
        string crew_id PK
        string role
    }

    DUTY_CLOCKS {
        string crew_id PK
        string as_of_utc
        float duty_hours_7d
        float flight_hours_28d
        string last_rest_ended
    }

    DUTY_CLOCK_HISTORY {
        string crew_id PK
        string date PK
        float duty_hours
        float flight_hours
    }

    RESERVE_POOL {
        int id PK
        string crew_id
        string base
        string date
        string on_call_start
        string on_call_end
    }

    CERTIFICATIONS {
        int id PK
        string crew_id
        string cert_type
        string valid_from
        string valid_to
    }

    RISK_SIGNALS {
        string crew_id PK
        string as_of_utc
        float disruption_risk_score
        json drivers_json
    }
```

`rosters.json` is the source roster model. SQLite has no table named `rosters`; a roster is reconstructed by joining `pairings` with `pairing_crew`. The `flagged_exceptions` array in `rosters.json` remains source metadata and is not loaded as a separate table.

Chat persistence adds `chat_sessions` and `chat_messages` at runtime through `src/db/chat_store.py`. These store conversational turns, tool calls, tool results, and reasoning traces for auditability.

## 5. Application Startup

```mermaid
sequenceDiagram
    participant Start as start.ps1 / start.sh
    participant DB as src.db.loader
    participant API as Uvicorn + FastAPI
    participant UI as Vite + React

    Start->>Start: Select project Python environment
    Start->>Start: Create .env if absent
    Start->>DB: Initialize crew_ops.db if absent
    DB->>DB: Apply schema and load data/*.json
    Start->>API: Start on 127.0.0.1:8000
    Start->>UI: Start Vite on 127.0.0.1:5173
    UI->>API: Requests through Vite /api proxy
```

## 6. Chat Request Flow

```mermaid
sequenceDiagram
    actor Controller
    participant React
    participant API as FastAPI /api/chat
    participant Graph as LangGraph
    participant LLM as Sarvam-105B
    participant Tools as Deterministic tools
    participant DB as SQLite
    participant Store as Chat store

    Controller->>React: Submit natural-language question
    React->>API: POST /api/chat {query, tier, session_id}
    API->>Graph: run_crew_ops_agent(query, session_id, tier)
    Graph->>Store: Load prior session messages
    Graph->>Graph: Build frozen-clock and active-entity context
    Graph->>LLM: Send prompt and tool schemas
    LLM-->>Graph: Tool call or final response
    alt Tool call returned
        Graph->>Tools: Execute selected Python tool
        Tools->>DB: Run deterministic query/calculation
        DB-->>Tools: Verified records
        Tools-->>Graph: Tool result + audit trace
        Graph->>LLM: Send tool result
        LLM-->>Graph: Final operational response
    end
    Graph->>Store: Persist user message, response, tools, trace
    Graph-->>API: Response and audit payloads
    API-->>React: JSON response
    React-->>Controller: Answer and expandable audit trail
```

The graph has two nodes:

1. `agent`: invokes the LLM with all registered tool schemas.
2. `tools`: executes requested tools and appends `ToolMessage` results.

The conditional edge loops back to `agent` when tool calls exist and ends after a final response. A six-tool-call safety limit prevents runaway loops. Historical tool payloads are compacted before later turns, while active aviation entities such as crew, flight, aircraft, and pairing IDs are retained for pronoun resolution.

The LLM is therefore responsible for intent interpretation, parameter selection, and response wording. It is not trusted for database facts or arithmetic.

## 7. Tier 1 Deterministic Query Layer

Tier 1 handlers live in `src/tier1/`. Each handler accepts explicit parameters, obtains a thread-safe SQLite connection, executes parameterized SQL, and returns JSON-compatible dictionaries/lists.

```mermaid
flowchart TD
    Q[Natural-language question]
    Router[LLM chooses tool and arguments]
    T[LangChain tool wrapper]
    H[Tier 1 query handler]
    SQL[Parameterized SQL]
    DB[(SQLite)]
    Result[Exact records]
    Synthesis[LLM formats verified answer]

    Q --> Router --> T --> H --> SQL --> DB --> Result --> Synthesis
```

Available lookup capabilities:

- Flight schedule, route, aircraft, seat, count, and distinct destinations
- Station departures and arrivals
- Longest/shortest block-time statistics
- Crew profile, rank, base, rating, status, reserve window, and reachability
- Reserve availability by station/date/rank
- Pairing roster and reverse crew schedule lookup
- Duty and flight-hour balance
- Expiring certifications
- Precomputed risk signals

Tier 1 benchmark coverage is `Q01`–`Q16`. `evaluate_tier1.py` independently executes all 16 deterministic benchmark paths.

## 8. Time and Duty Calculations

All timestamps are parsed as UTC strings using `src/rules/time_utils.py` and resolver equivalents.

### Duty period / FDP

For a duty day:

```text
report = first departure - 60 minutes
release = last arrival + 30 minutes
FDP hours = release - report
```

For example, if the first departure is `02:00Z` and the last arrival is `12:15Z`:

```text
report  = 01:00Z
release = 12:45Z
FDP     = 11.75 hours
```

### FDP limit

`RULE-FDP-01` is read from `data/rules.json`:

```text
limit = base_fdp_hours - reduction_per_extra_sector_hours
        * max(0, sectors - free_sectors)
```

With the current parameters:

| Sectors | Limit |
|---:|---:|
| 1–2 | 13.0h |
| 3 | 12.5h |
| 4 | 12.0h |
| 5 | 11.5h |

### Rolling windows

The rolling window is calendar-day based and inclusive:

```text
window_start = window_end - (window_days - 1)
```

For `RULE-DUTY-02`:

```text
duty_7d = SUM(duty_clock_history.duty_hours in window)
          + planned pairing duty hours in window
          + simulated cover duty hours in window

legal if duty_7d <= 60.0h
headroom = 60.0h - duty_7d
```

For `RULE-FLT-03`, the same process sums flight block hours over 28 calendar days and checks the 100-hour cap.

The engine combines historical rows, future published pairing rows, and prior days of a simulated multi-day cover. When swapping a crew member, the replaced pairing is excluded before adding the proposed cover.

### Rest

`RULE-REST-04` checks both directions:

```text
upstream rest   = proposed report - previous release
downstream rest = next scheduled report - proposed release
```

The assignment is legal only when each applicable rest interval is at least 12 hours. Multi-day pairings pass the prior day release into the next day evaluation.

## 9. Legality Engine

`src/rules/engine.py` is the centralized legality orchestrator. It fetches the crew record, rejects non-active crew, evaluates all configured rules, and returns a structured legality report.

```mermaid
flowchart TD
    Input[Proposed crew assignment]
    Lookup[Load crew profile from SQLite]
    Active{status == active?}
    Parse[Parse date, timestamps, sectors, block hours]
    FDP[check_fdp]
    Duty[check_duty_7d]
    Flight[check_flight_28d]
    Rest[check_rest + downstream rest]
    Qual[check_qualification]
    Cert[check_certifications]
    Base[check_base]
    Ops[overlap + reserve window checks]
    Report[Legality report]

    Input --> Lookup --> Active
    Active -- No --> Report
    Active -- Yes --> Parse
    Parse --> FDP
    Parse --> Duty
    Parse --> Flight
    Parse --> Rest
    Parse --> Qual
    Parse --> Cert
    Parse --> Base
    Parse --> Ops
    FDP --> Report
    Duty --> Report
    Flight --> Report
    Rest --> Report
    Qual --> Report
    Cert --> Report
    Base --> Report
    Ops --> Report
```

The seven configured rules are:

| Rule | Deterministic check | Result |
|---|---|---|
| `RULE-FDP-01` | Daily FDP against sector-based cap | Violation if over limit |
| `RULE-DUTY-02` | 7-day calendar duty sum ≤ 60h | Violation if exceeded |
| `RULE-FLT-03` | 28-day block-hour sum ≤ 100h | Violation if exceeded |
| `RULE-REST-04` | Upstream/downstream rest ≥ 12h | Violation if insufficient |
| `RULE-QUAL-05` | Assigned aircraft type in crew ratings | Violation if absent |
| `RULE-CERT-06` | Every certification `valid_to` covers duty date | Violation if expired |
| `RULE-BASE-07` | Base matches departure station | Advisory when positioning/deadhead is required |

Operational constraints add double-booking and reserve-window checks. The engine does not short-circuit the rule list, allowing the audit response to show all discovered violations.

`check_crew_legality_for_pairing` evaluates each day in chronological order, carries forward prior cover duty and release time, and treats the overnight station as the departure point on later days of a multi-day pairing.

## 10. Tier 2 Disruption Analysis

Tier 2 resolver functions are in `src/resolver/disruption.py` and are exposed to the agent through `src/agent/tools.py`.

```mermaid
flowchart TD
    Event[Structured disruption event]
    Sick[expand_sick_call]
    Closure[expand_station_closure]
    Delay[expand_delay]
    Roster[Pairings and flights]
    DutyCalc[FDP and delay arithmetic]
    Impact[Impact report]

    Event --> Sick
    Event --> Closure
    Event --> Delay
    Sick --> Roster
    Closure --> Roster
    Delay --> Roster
    Closure --> DutyCalc
    Delay --> DutyCalc
    Sick --> Impact
    Closure --> Impact
    Delay --> Impact
```

Current deterministic operations:

- `expand_sick_call`: finds the affected pairing, lists day-one/day-two uncovered flights, and sums seats for passengers at risk.
- `expand_station_closure`: finds flights departing from or arriving at a station during the closure window, calculates minimum delay, recalculates crew FDP, and recommends delay, re-crew, or cancellation.
- `expand_delay`: shifts a pairing FDP by the technical delay and compares it against the sector-based FDP cap.
- `compute_duty_window`: calculates historical plus planned duty/flight hours for an arbitrary calendar window.

These functions use read-only base data and calculate results in memory. They do not modify the published roster or SQLite snapshot.

## 11. Tier 3 Recovery and Costing

Recovery logic is in `src/resolver/cover.py`. It follows the candidate rules encoded by `generate.py` and validated by `evaluate_tier2_tier3.py`.

```mermaid
flowchart TD
    Need[Pairing, role, unavailable crew]
    Pool[All crew records]
    Filter[Active + correct role + not unavailable]
    Position[Base and deadhead check]
    Reserve[Reserve on-call window check]
    Legal[Multi-day legality check]
    Cost[Cost calculation]
    Rank[Sort by cost, then crew_id]
    Cancel[Append cancellation fallback]
    Output[Options + excluded candidates]

    Need --> Pool --> Filter --> Position
    Position --> Reserve
    Reserve --> Legal
    Legal --> Cost
    Cost --> Rank --> Cancel --> Output
```

### Candidate filtering

For every candidate, the resolver checks:

1. Crew status is `active`.
2. Rank matches the required role.
3. Aircraft type is present in `ratings`.
4. Existing pairing is excluded when evaluating a swap.
5. Schedule overlap is absent.
6. Upstream and downstream rest are legal.
7. 7-day duty and 28-day flight limits remain legal.
8. All certifications are valid on every covered duty date.
9. Reserve window covers the required report time.
10. Cross-base positioning is available when needed.

Rejected candidates are retained with rule-oriented reasons such as `RULE-QUAL-05`, `RULE-DUTY-02`, `RULE-REST-04`, or `RULE-BASE-07`.

### Deadhead calculation

The synthetic dataset supports DEL-to-BLR positioning only:

- Odd dates use `DX402`, arriving at `08:45Z`.
- Even dates use `DX589`, arriving at `07:45Z`.
- The positioned crew requires 15 minutes transit, then the normal 60-minute report buffer.
- The resulting first-departure delay is charged to the recovery cost.

Other cross-base directions are excluded because no same-day positioning flight exists.

### Cost calculation

```text
reserve candidate = reserve callout fee
day-off candidate = day-off callout fee
deadhead candidate += positioning fee
deadhead candidate += delay_hours * delay_cost_per_duty_hour
cancellation = cancellation_per_flight * number_of_legs
```

Options are sorted by `(cost_inr, crew_id)`. Cancellation is appended after crew options as the fallback. The current implementation supports single-pairing candidate ranking; joint simultaneous assignment is assembled in the Tier 3 evaluator for the existing S6 benchmark rather than exposed as a dedicated resolver service.

## 12. Agent Tool Registry

```mermaid
flowchart LR
    Agent[LangGraph agent]
    All[ALL_TOOLS]
    T1[TIER1_TOOLS: 10 lookup tools]
    T23[TIER2_TOOLS: legality, disruption, recovery tools]
    DB[(SQLite)]
    Resolver[Resolver modules]

    Agent --> All
    All --> T1
    All --> T23
    T1 --> DB
    T23 --> DB
    T23 --> Resolver
```

Current tool groups:

- Tier 1: 10 schedule, crew, reserve, roster, duty, certification, and risk tools.
- Tier 2/3 group: `check_crew_cover_legality`, `get_cover_options`, `analyze_sick_call`, `analyze_station_closure`, `analyze_delay_impact`, and `compute_duty_window`.

The agent currently binds `ALL_TOOLS`. The `tier` request value is returned and persisted, but tool availability is not yet isolated into separate Tier 1, Tier 2, and Tier 3 registries.

## 13. REST and Frontend Flow

### Backend endpoints

| Endpoint | Current behavior |
|---|---|
| `GET /api/health` | Service status and frozen snapshot date |
| `GET /api/stats` | Flight, crew, pairing, reserve, station, and fleet metrics |
| `GET /api/pairings` | Pairings workspace data with date/aircraft/risk filters |
| `GET /api/pairings/{pairing_id}` | Pairing detail |
| `GET /api/flights/{flight_id}` | Flight detail |
| `GET /api/crew` | Crew list with rank/base/risk filters |
| `GET /api/crew/{crew_id}` | Crew detail |
| `POST /api/chat` | LangGraph chat request with audit payload |
| `GET/POST/DELETE /api/sessions...` | Persistent chat sessions and history |
| `POST /api/simulate` | Placeholder response; not wired to resolver |
| `POST /api/recover` | Placeholder response; not wired to resolver |

```mermaid
flowchart TD
    App[React App router]
    Pairings[PairingsWorkspace]
    Detail[Pairing / Flight / Crew pages]
    Chat[CopilotPage]
    API[frontend/src/lib/api.js]
    Proxy[Vite /api proxy]
    FastAPI[FastAPI routes]

    App --> Pairings
    App --> Detail
    App --> Chat
    Pairings --> API
    Detail --> API
    Chat --> API
    API --> Proxy --> FastAPI
```

The UI displays deterministic records directly for workspace/detail views. Chat responses include `response`, `tool_calls`, `tool_results`, `reasoning_trace`, `tier`, and `session_id`; the copilot renders the answer and exposes the audit trail.

## 14. Evaluation and Verification

```mermaid
flowchart LR
    Data[data/questions.json and data/scenarios.json]
    T1[evaluate_tier1.py]
    T23[evaluate_tier2_tier3.py]
    Unit[pytest tests/]
    Validator[validate.py]
    Result[Pass/fail reports]

    Data --> T1 --> Result
    Data --> T23 --> Result
    Data --> Unit --> Result
    Data --> Validator --> Result
```

Current verified results:

- Tier 1 evaluator: `Q01`–`Q16`, 16/16 passed.
- Tier 2/3 evaluator: 19/19 testable questions passed; Q30, Q36, and Q38 are rubric-graded skips.
- Scenario evaluator: S1–S6, 6/6 passed.
- Dataset validator: internally consistent.
- The local `.venv/bin/python.exe` environment currently lacks `pytest`; the evaluator scripts run successfully without pytest.

The benchmark fixtures are the grading specification. In particular, `generate.py` defines the expected candidate enumeration and costing semantics; the broader regulatory descriptions in `README.md` should not be treated as implemented behavior when they differ from `data/rules.json` and the answer keys.

## 15. Operational Invariants

The following invariants should be preserved when extending the system:

1. Never allow the LLM to calculate hours, costs, limits, or passenger counts.
2. Treat SQLite and the JSON dataset as the immutable base snapshot.
3. Apply disruptions in memory; do not mutate the published roster for a simulation.
4. Evaluate every applicable legality rule and preserve exact rule IDs in audit output.
5. Use UTC timestamps and inclusive calendar-day windows.
6. Evaluate every day of a multi-day pairing, including downstream rest effects.
7. Keep legal options and excluded candidates in the recovery response.
8. Preserve deterministic ordering and cost tie-breaks.
9. Keep scenario answer keys independent; scenarios do not chain state.
10. Expose tool arguments, raw results, and reasoning traces for explainability.

## 16. Next Integration Work

The remaining work to make the architecture fully end to end is concentrated at the API boundary:

1. Add typed request/response models for disruption and recovery operations.
2. Route `/api/simulate` to `expand_sick_call`, `expand_station_closure`, and `expand_delay`.
3. Route `/api/recover` to `cover_options` and add a dedicated joint optimizer for simultaneous absences.
4. Add explicit Tier 2/Tier 3 prompt guidance and tier-specific tool binding.
5. Connect the frontend recovery/simulation screens to the new endpoints.
6. Add API integration tests for the resolver outputs and scenario payloads.
