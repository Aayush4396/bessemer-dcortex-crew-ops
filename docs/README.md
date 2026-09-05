# dCortex Crew Operations Advisor — Documentation Hub

Welcome to the technical documentation repository for the **dCortex & Bessemer Tech Catalyst — Airline Crew Operations Advisor (NOC AI Copilot)**.

---

## 📚 Complete Technical Documentation Index

| # | Document | Area | Contents & Architectural Focus |
|:---:|:---|:---:|:---|
| **1** | **[Database Pipeline & Ingestion](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/docs/DATABASE_PIPELINE.md)** | `src/db/` | 11-table normalized SQLite schema, raw JSON ETL loader, WAL mode concurrency pragmas, and session store. |
| **2** | **[DGCA CAR Legality Rules Engine](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/docs/RULES_ENGINE.md)** | `src/rules/` | Deterministic compliance engine for DGCA CAR Sec 7 Ser J: Table A/B FDP caps, 7d/28d rolling windows, 12h rest, ratings, certs, and base geometry. |
| **3** | **[Tier 1 Operational Query Engine](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/docs/TIER1_QUERY_ENGINE.md)** | `src/tier1/` | Domain-driven queries for flight schedules, crew profiles, standby reserve pools, duty balances, and Q01–Q16 ground-truth benchmarks. |
| **4** | **[Pairings Workspace & Entity 360](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/docs/PAIRINGS_WORKSPACE_AND_ENTITIES.md)** | `src/tier1/` & UI | Tactical pairing roster engine, network KPI calculations, composite risk models (`low` to `critical`), multi-day rotation grouping, and Flight/Crew 360 profiles. |
| **5** | **[LangGraph Agent & Memory](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/docs/LANGGRAPH_AGENT.md)** | `src/agent/` | StateGraph ReAct loop powered by Sarvam-105B, bound lookup and rule-check tools, Option A deterministic payload compaction, and multi-turn pronoun resolution. |
| **6** | **[Full-Stack App: API & Console](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/docs/FULLSTACK_APP.md)** | `src/api/` & `frontend/` | FastAPI REST service, React 19 Operations Desk with React Router, session history, and explainability audit drawers. |
| **7** | **[Benchmark Matrix & Evaluation](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/docs/BENCHMARK_AND_EVALUATION.md)** | `tests/` & root | Test suite catalog, Q01–Q38 ground truth matrix, and standalone CLI evaluators. |

---

## 🏗️ System Architecture Overview

```
                               ┌──────────────────────────────────────────────────────────┐
                               │       React 19 NOC Operations Console (Port 5173)        │
                               │   (PairingsWorkspace, DetailPages, Copilot, AuditDrawer) │
                               └────────────────────────────┬─────────────────────────────┘
                                                            │ HTTP / Vite Proxy
                               ┌────────────────────────────▼─────────────────────────────┐
                               │              FastAPI Backend Server (Port 8000)          │
                               │   (/api/pairings, /api/crew, /api/flights, /api/chat,    │
                               │    /api/simulate, /api/recover, /api/sessions)           │
                               └─────────────┬──────────────────────────────┬─────────────┘
                                             │                              │
                    ┌────────────────────────▼─────┐               ┌────────▼─────────────┐
                    │  LangGraph ReAct Loop Agent  │               │ Tactical Workspace & │
                    │   (Sarvam-105B + 13 Tools)   │               │  Entity 360 Engines  │
                    └──────────────┬───────────────┘               └────────┬─────────────┘
                                   │                                        │
           ┌───────────────────────┴────────────────────────┐               │
           │                                                │               │
┌──────────▼───────────┐ ┌────────────────────┐ ┌───────────▼────────────┐  │
│  Tier 1 Query Engine │ │   Tier 2 Simulator │ │     Tier 3 Optimizer   │  │
│ (10 Python Handlers) │ │ (Disruption Impact)│ │ (Candidate Rank & Cost)│  │
└──────────┬───────────┘ └──────────┬─────────┘ └───────────┬────────────┘  │
           │                        │                       │               │
           │                        └───────────┬───────────┘               │
           │                                    │                           │
           │                        ┌───────────▼────────────┐              │
           │                        │ DGCA CAR Rules Engine  │              │
           │                        │ (7 Programmatic Rules) │              │
           │                        └───────────┬────────────┘              │
           │                                    │                           │
           └────────────────────────────────────┼───────────────────────────┘
                                                │
                               ┌────────────────▼─────────────────────────┐
                               │         crew_ops.db (SQLite WAL Mode)    │
                               │  (flights, crew, pairings, duty_clocks,  │
                               │   reserve_pool, certs, risk, chat_store) │
                               └──────────────────────────────────────────┘
```

---

## ⚡ Quick Start

### 1. Launch Backend & Frontend with One Script
```powershell
# Windows PowerShell
.\start.ps1

# Linux / macOS Bash
./start.sh
```

### 2. Verify Complete Automated Test Suite
```powershell
# Run all 92 automated core tests
.venv\Scripts\pytest.exe tests/test_api.py tests/test_entity_detail.py tests/test_pairings_workspace.py tests/test_router.py tests/test_rules.py tests/test_tier1.py tests/test_tier2.py -v
