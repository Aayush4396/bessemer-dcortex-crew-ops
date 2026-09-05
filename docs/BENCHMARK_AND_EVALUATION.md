# Comprehensive Benchmark, Testing & Evaluation Guide

This document details the complete **Evaluation & Benchmarking Framework** for the **dCortex Crew Operations Advisor**.

The system is validated across multiple layers:
1. **Automated Pytest Suite**: 92 passing core tests spanning APIs, rules, query handlers, disruption simulators, recovery optimizers, and UI workspace engines.
2. **Operational Benchmark Matrix**: 38 benchmark questions (Q01–Q38) and 6 disruption scenarios (S1–S6) validated against ground-truth data in [`data/questions.json`](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/data/questions.json) and [`data/scenarios.json`](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/data/scenarios.json).
3. **Standalone Evaluation Tools**: Zero-dependency CLI evaluators for rapid auditing without pytest.

---

## 1. Automated Pytest Suite Catalog (92 Tests Passing)

```powershell
.venv\Scripts\pytest.exe tests/test_api.py tests/test_entity_detail.py tests/test_pairings_workspace.py tests/test_router.py tests/test_rules.py tests/test_tier1.py tests/test_tier2.py -v
```

```
============================== 92 passed in 9.40s ==============================
```

| Test Suite Module | Test Count | Domain Responsibilities & Verification Focus |
|:---|:---:|:---|
| [`tests/test_api.py`](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/tests/test_api.py) | | Backend REST endpoints: `/api/health`, `/api/stats`, `/api/chat`, and session lifecycle (CRUD). |
| [`tests/test_entity_detail.py`](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/tests/test_entity_detail.py) | **11** | Entity 360 handlers: flight detail resolution, crew profile assembly, 150-crew directory filtering, and graceful 404 handling. |
| [`tests/test_pairings_workspace.py`](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/tests/test_pairings_workspace.py) | **20** | Tactical pairings workspace: KPI summary parity, 2-day rotation grouping, composite risk scoring, risk band filters, and cert/duty risk elevations. |
| [`tests/test_router.py`](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/tests/test_router.py) | **6** | LangGraph ReAct agent: 13-tool registry mapping, cyclic graph compilation, conditional edge routing, and multi-tier tool execution in `tools_node`. |
| [`tests/test_rules.py`](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/tests/test_rules.py) | **10** | Programmatic CAR legality engine: FDP limits (Table A), 7d duty / 28d flight rolling windows, 12h rest, type ratings, cert validities, base geometry, and multi-day accumulation. |
| [`tests/test_tier1.py`](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/tests/test_tier1.py) | **16** | Deterministic operational queries: Direct ground-truth validation for the 16 Tier 1 benchmark questions (Q01–Q16). |
| [`tests/test_tier2.py`](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/tests/test_tier2.py) | | Rule-check handlers for Q17–Q30: pairing absence, cover legality, duty/FDP/rest, stations, and seat-risk by type. |

---

## 2. The 38 Operational Benchmark Questions (Q01–Q38)

The benchmark dataset ([`data/questions.json`](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/data/questions.json)) tests operational correctness across all 3 tiers:

### Tier 1: Deterministic Lookups (Q01–Q16)
| ID | Inquiry Focus | Target Handler | Expected Ground Truth |
|:---|:---|:---|:---|
| **Q01** | Reserves on call at BLR on 15 Sep | `get_reserves_at_station` | 12 reserves (Captains: C-3305, C-3310, C-3315, etc.) |
| **Q02** | C-1042 7d duty balance & headroom (14 Sep) | `get_crew_duty_balance` | `duty_hours_7d`: **20.93h**, `headroom_hours`: **39.07h** |
| **Q03** | DEL departures on 15 Sep | `get_departures` | 13 flights (DX201, DX203, DX205, etc.) |
| **Q04** | Certifications expiring within 30 days | `get_expiring_certifications` | 24 expiring certs (e.g. C-2087 medical on 22 Sep) |
| **Q05** | Flight DX412 aircraft & seat capacity | `get_flights` | Tail: **VT-DXC**, Fleet: **A320**, Seats: **162** |
| **Q06** | C-3310 reserve reachability & on-call window| `get_crew_profile` | Window: 06:00–18:00 UTC, Reachability: 60 min |
| **Q07** | C-2210 base and aircraft type rating | `get_crew_profile` | Base: **BOM**, Ratings: `["A320"]` |
| **Q08** | Pairing P-2291 crew roster & roles | `get_pairing_roster` | Capt: C-1042, FO: C-2087, SCC: C-3101, CC: C-4112, C-4203 |
| **Q09** | BLR $\to$ BOM flights on 17 Sep | `get_flights` | 4 flights: DX101, DX103, DX105, DX107 |
| **Q10** | Total flights operating on 16 Sep | `get_flights` (count) | **50 scheduled flights** |
| **Q11** | Captains based at DEL | `get_crew_profile` | 10 Captains (C-1002, C-1006, C-1009, etc.) |
| **Q12** | Longest scheduled block time | `get_flight_schedule_stats`| **3.08 hours** (DX581 / DX582 DEL-COK) |
| **Q13** | C-2087 rank & 28-day flight hours | `get_crew_duty_balance` | Rank: **First Officer**, Flight hours: **78.45h** |
| **Q14** | Nonstop destinations from BLR | `get_flights` (distinct) | 7 stations: AMD, BOM, CCU, COK, DEL, HYD, MAA |
| **Q15** | Senior Cabin Crew on VT-DXB on 16 Sep | `get_pairing_roster` | **C-4809** |
| **Q16** | C-1042 disruption risk score & drivers | `get_crew_risk_signal` | Score: **0.78**, Drivers: `["short-rest pattern"]` |

---

### Tier 2: Disruption Simulation Scenarios (S1–S6 / Q17–Q30)
| Scenario | Disruption Event | Simulation Focus | Ground Truth Consequence |
|:---:|:---|:---|:---|
| **S1** | ATR Captain C-3231 Sick Call | `simulate_sick_crew` | Grounds 4 legs on `P-2224` (DX451-DX454); **288 passenger seats at risk**. |
| **S2** | Flagship Captain C-1042 Sick Call | `simulate_sick_crew` | 2-day pairing `P-2291` broken across BLR & DEL; **972 passenger seats at risk** (486 Day 1 / 486 Day 2). |
| **S3** | BLR Station Fog Closure (08:00–14:00Z)| `simulate_station_closure` | 13 flights affected; delays measured to reopen + 30m turn; tail legs require reserve re-crewing due to FDP limits. |
| **S4** | VT-DXA 90-Minute Rotational Delay | `simulate_flight_delay` | 4-sector duty extended to 12.75h; breaches 12.0h FDP cap (`RULE-FDP-01`); crew cannot operate DX404. |
| **S5** | C-5417 Expired Recurrent Training | `simulate_cert_expiry` | Expired on 17 Sep; flagged as non-compliant for 19 Sep rotation (`RULE-CERT-06`). |
| **S6** | Simultaneous Dual Captain Sick Calls | `simulate_disruption` (MULTI) | Concurrent Captain incapacitations across VT-DXA and VT-DXB; flight legs deduplicated; joint impact analyzed. |

---

### Tier 3: Recovery Optimization & Callout Drafting (Q31–Q38)
| ID | Recovery Problem | Optimizer Focus | Ground Truth Solution |
|:---|:---|:---|:---|
| **Q31** | S1 ATR Captain Recovery | `optimize_recovery` | Rank 1: Reserve Captain `C-3315` (0 delay, ₹18,500); Day-off callout `C-1600` (₹24,000); Fallback cancellation (₹1,000,000). |
| **Q32** | S6 Joint Multi-Disruption | `solve_joint_optimization` | Global combinatorial matching avoiding double-allocation of reserve Captains across VT-DXA and VT-DXB rotations. |
| **Q33** | S2 Deadhead Positioning Option | `find_cover_options` | Captain `C-2210` deadheads from DEL to BLR on DX402 (3.0h delay, ₹41,200 total cost). |
| **Q34** | S4 Rotational Delay Recovery | `solve_delay_fdp_breach` | Fresh reserve callout to take over uncrewed sector DX404 while original crew rests. |
| **Q35** | S3 Station Closure Tactical Action | `simulate_station_closure` | Delay-to-reopen where crew FDP holds; re-crew or cancel tail legs where duty limits breach. |
| **Q36** | Dispatch Callout Drafting | `generate_callout_notification`| Structured callout to `C-3310` with report time, flight legs, overnight DEL hotel, deadline, and dispatch contact. |
| **Q37** | First Officer Sick Call Recovery | `optimize_recovery` | ATR-rated FO reserve `C-3316` assigned clean cover at ₹18,500. |
| **Q38** | Tactical Morning Briefing Rubric | Operational Synthesis | Surfaces 7d duty headroom, reserve availability by window, and active risk signals per aircraft line. |

---

## 3. Standalone Evaluation Scripts

For environments without pytest or for rapid operational validation, the repository provides 3 standalone tools:

### A. Standalone Tier 1 Evaluator ([`evaluate_tier1.py`](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/evaluate_tier1.py))
Executes all 16 Tier 1 benchmark queries directly against SQLite and prints an ASCII compliance matrix:
```powershell
.venv\Scripts\python.exe evaluate_tier1.py
```
```
============================================================
RUNNING TIER 1 BENCHMARK TESTS (Q01-Q16)
============================================================
  [PASS] Q01 (BLR reserves)
  [PASS] Q02 (C-1042 7d duty & headroom)
  [PASS] Q03 (DEL departures)
  ...
============================================================
Result: 16 PASSED / 0 FAILED
============================================================
```

### B. Independent Dataset Consistency Validator ([`validate.py`](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/validate.py))
Performs independent sanity checks directly on raw JSON files (zero shared code with engines):
```powershell
.venv\Scripts\python.exe validate.py
```
- Schedule continuity: Ensures aircraft arrive at the station from which they next depart.
- Crew complement checks: Verifies minimum staffing (1 Captain, 1 FO, 1 SCC, 3 CC on A320; 1 Captain, 1 FO, 1 SCC, 1 CC on ATR72).
- Duty clock integrity: Verifies rolling sums match historical records.

### C. Database Parity Verifier ([`src/db/verify_db.py`](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/src/db/verify_db.py))
Validates SQLite database table row counts, indexes, and ground-truth values:
```powershell
.venv\Scripts\python.exe -m src.db.verify_db
```
Verifies:
- Table counts (147 flights, 150 crew, 42 pairings, 112 reserves, 600 certs, 4,200 clock history rows).
- WAL mode active and foreign key integrity verified.
