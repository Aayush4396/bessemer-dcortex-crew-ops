"""
src/api/server.py
=================
FastAPI backend server for the dCortex Crew Operations Advisor.
Exposes REST endpoints for conversational AI chat, live database statistics,
and placeholder endpoints for Tier 2 (Disruption Simulator) and Tier 3 (Recovery Optimizer).
"""

import os
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.agent import run_crew_ops_agent
from src.db.loader import init_db
from src.rules.models import SNAPSHOT_DATE

app = FastAPI(
    title="dCortex Crew Operations Advisor API",
    description="Airline Operations Control Assistant powered by LangGraph, Sarvam-105B, and DGCA CAR Rules Engine.",
    version="1.0.0",
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared in-process or on-disk database connection
_db_conn = None


def get_db():
    global _db_conn
    if _db_conn is None:
        db_path = os.getenv("DB_PATH", ":memory:")
        _db_conn = init_db(db_path=db_path)
    return _db_conn


# ---------------------------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    query: str = Field(..., description="Operational question from the Crew Controller")
    tier: int = Field(default=1, description="Context tier (1: Lookup, 2: Disruption, 3: Recovery)")


class ChatResponse(BaseModel):
    response: str
    tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    reasoning_trace: list[str]
    tier: int


class StatsResponse(BaseModel):
    flights: int
    crew: int
    pairings: int
    reserves: int
    snapshot_date: str
    active_stations: list[str]
    fleet_types: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "dcortex-crew-ops-backend",
        "engine": "LangGraph + Sarvam-105B",
        "snapshot_date": str(SNAPSHOT_DATE),
    }


@app.get("/api/stats", response_model=StatsResponse)
def get_fleet_stats():
    """Fetch live counts and operational metadata from SQLite."""
    conn = get_db()
    flights_count = conn.execute("SELECT COUNT(*) FROM flights").fetchone()[0]
    crew_count = conn.execute("SELECT COUNT(*) FROM crew").fetchone()[0]
    pairings_count = conn.execute("SELECT COUNT(*) FROM pairings").fetchone()[0]
    reserves_count = conn.execute("SELECT COUNT(*) FROM reserve_pool").fetchone()[0]

    return StatsResponse(
        flights=flights_count,
        crew=crew_count,
        pairings=pairings_count,
        reserves=reserves_count,
        snapshot_date=str(SNAPSHOT_DATE),
        active_stations=["BLR", "BOM", "DEL"],
        fleet_types=["A320 (162 seats)", "ATR72 (72 seats)"],
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    """
    Execute natural language operational query via LangGraph agent.
    Routes to deterministic Python query tools, verifies data, and synthesizes response.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        result = run_crew_ops_agent(query=req.query, tier=req.tier)
        return ChatResponse(
            response=result.get("final_response", ""),
            tool_calls=result.get("tool_calls", []),
            tool_results=result.get("tool_results", []),
            reasoning_trace=result.get("reasoning_trace", []),
            tier=req.tier,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution error: {str(e)}")


@app.post("/api/simulate")
def simulate_disruption_placeholder(payload: dict[str, Any] | None = None):
    """
    Placeholder endpoint for Tier 2 Disruption Consequence Simulator.
    """
    return {
        "status": "placeholder",
        "tier": 2,
        "title": "Tier 2: Disruption Consequence Simulator",
        "message": "Tier 2 Impact Simulator is scheduled for implementation in Step 5.",
        "scenarios": [
            {
                "id": "S1",
                "title": "Unscheduled Sick Call (Capt C-1042 on DX412)",
                "impact": "Grounds flight DX412 unless reserve replacement is dispatched.",
            },
            {
                "id": "S2",
                "title": "Rolling 2h Technical Delay",
                "impact": "Triggers downstream FDP extension breach on pairing P-2291.",
            },
            {
                "id": "S3",
                "title": "Station Weather Closure (BOM Dense Fog)",
                "impact": "Diversions and groundings cascading across network pairings.",
            },
            {
                "id": "S4",
                "title": "In-Flight Pressurization Snag Diversion",
                "impact": "Strands crew at non-base station, requiring duty clock resets.",
            },
            {
                "id": "S5",
                "title": "Medical Divert on DX588",
                "impact": "Breaches maximum allowable daily flight duty period.",
            },
            {
                "id": "S6",
                "title": "Mid-Roster Certification Expiration",
                "impact": "First Officer C-2087 medical expires mid-rotation.",
            },
        ],
    }


@app.post("/api/recover")
def recovery_optimizer_placeholder(payload: dict[str, Any] | None = None):
    """
    Placeholder endpoint for Tier 3 Recovery Candidate Ranker.
    """
    return {
        "status": "placeholder",
        "tier": 3,
        "title": "Tier 3: Recovery Candidate Ranker & Cost Optimizer",
        "message": "Tier 3 Recovery Optimizer is scheduled for implementation in Step 6.",
        "capabilities": [
            "Candidate Pool Generation from Active Reserves, Home Base Standbys, and Off-Duty Crew",
            "Deterministic DGCA CAR Legality Pre-Filter (FDP, Rest, 7d/28d Headroom, Type Ratings)",
            "Exact Multi-Variable Cost Optimization in INR (Callout Fee + Deadhead + Delay Penalty)",
            "Automated Multi-Channel Notification Drafter (WhatsApp / SMS / Crew App Alert)",
        ],
    }
