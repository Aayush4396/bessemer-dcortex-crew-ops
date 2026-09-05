# dCortex Crew Operations Advisor — Documentation Hub

Welcome to the technical documentation repository for the **dCortex & Bessemer Tech Catalyst — Airline Crew Operations Advisor (NOC AI Copilot)**.

---

## 📚 Documentation Index

| Document | Area | Contents & Architectural Focus |
|:---|:---|:---|
| **[0. Complete System Architecture](ARCHITECTURE.md)** | Entire system | End-to-end flow from JSON ingestion through SQLite, deterministic engines, LangGraph, FastAPI, React, and evaluation. |
| **[1. Database Pipeline & Ingestion](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/docs/DATABASE_PIPELINE.md)** | `src/db/` | SQLite schema, relational normalization of raw JSON, WAL mode, indexing strategy, and thread-safe session store. |
| **[2. DGCA CAR Rules Engine](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/docs/RULES_ENGINE.md)** | `src/rules/` | Deterministic compliance engine for DGCA CAR Section 7 Series J: FDP limits, 7d/28d rolling windows, 12h rest, ratings, certs, and operational overlap constraints. |
| **[3. Tier 1 Query Engine & Benchmarks](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/docs/TIER1_QUERY_ENGINE.md)** | `src/tier1/` | Domain-driven query handlers for flights, crew profiles, standby reserves, rosters, duty balances, and the 16 benchmark questions (Q01–Q16). |
| **[4. LangGraph Agent & Memory](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/docs/LANGGRAPH_AGENT.md)** | `src/agent/` | StateGraph ReAct loop powered by Sarvam-105B, Option A deterministic payload compaction (<0.1ms), dynamic domain entity extraction, and multi-turn pronoun resolution. |
| **[5. Full-Stack App: API & UI](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/docs/FULLSTACK_APP.md)** | `src/api/` & `frontend/` | FastAPI REST endpoints, React 19 + Tailwind console, multi-session inquiry history sidebar, live fleet metrics, and interactive explainability audit drawers. |

---

## 🏗️ System Architecture Overview

```
                               ┌──────────────────────────────────────────────┐
                               │   React 19 NOC Operations Console (5173)     │
                               │   (SessionSidebar, ChatConsole, AuditDrawer) │
                               └──────────────────────┬───────────────────────┘
                                                      │ HTTP / Vite Proxy
                               ┌──────────────────────▼───────────────────────┐
                               │       FastAPI Backend Server (8000)          │
                               │    (Health, Stats, Chat, Sessions Endpoints) │
                               └───────────┬──────────────────────┬───────────┘
                                           │                      │
                   ┌───────────────────────▼──────┐      ┌────────▼──────────────┐
                   │  LangGraph StateGraph Agent  │      │  SQLite CRUD Store    │
                   │  (Sarvam-105B ReAct Loop)    │      │  (chat_store.py)      │
                   └───────────────┬──────────────┘      └────────┬──────────────┘
                                   │                              │
                   ┌───────────────▼──────────────┐               │
                   │   Deterministic Tools Node   │               │
                   │  (11 Tier 1 Python Handlers) │               │
                   └───────────────┬──────────────┘               │
                                   │                              │
                   ┌───────────────▼──────────────────────────────▼───────────┐
                   │                     crew_ops.db (SQLite WAL)             │
                   │  (flights, crew, pairings, duty_clocks, history, chat)   │
                   └──────────────────────────────────────────────────────────┘
```

---

## ⚡ Quick Start

### 1. Launch Everything with One Script
```powershell
# Windows PowerShell
.\start.ps1

# Linux / macOS Bash
./start.sh
```

### 2. Verify Complete Test Suite
```powershell
# Run all 39 automated tests
.venv\Scripts\pytest.exe tests/ -v
```
Output:
- `tests/test_api.py`: **8/8 PASSED**
- `tests/test_router.py`: **5/5 PASSED**
- `tests/test_rules.py`: **10/10 PASSED**
- `tests/test_tier1.py`: **16/16 PASSED**
