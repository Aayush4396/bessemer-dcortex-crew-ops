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
from src.db.chat_store import (
    create_session,
    delete_session,
    get_session,
    get_session_messages,
    list_sessions,
)
from src.rules.models import SNAPSHOT_DATE
from src.tier1.connection import get_connection
from src.tier1.entity_detail import get_crew_detail, get_flight_detail, list_crew
from src.tier1.pairings_workspace import get_pairing, get_pairings_workspace

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


# ---------------------------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    query: str = Field(..., description="Operational question from the Crew Controller")
    tier: int = Field(default=1, description="Context tier (1: Lookup, 2: Disruption, 3: Recovery)")
    session_id: str = Field(default="default", description="Session identifier for multi-turn conversational context")


class ChatResponse(BaseModel):
    response: str
    tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    reasoning_trace: list[str]
    tier: int
    session_id: str = "default"


class CreateSessionRequest(BaseModel):
    session_id: str | None = Field(default=None, description="Optional custom session ID; auto-generated if omitted")
    title: str = Field(default="New Session", description="Display title for the session")


class SessionItem(BaseModel):
    session_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


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
    conn = get_connection()
    try:
        flights_count = conn.execute("SELECT COUNT(*) FROM flights").fetchone()[0]
        crew_count = conn.execute("SELECT COUNT(*) FROM crew").fetchone()[0]
        pairings_count = conn.execute("SELECT COUNT(*) FROM pairings").fetchone()[0]
        reserves_count = conn.execute("SELECT COUNT(*) FROM reserve_pool").fetchone()[0]
    finally:
        conn.close()

    return StatsResponse(
        flights=flights_count,
        crew=crew_count,
        pairings=pairings_count,
        reserves=reserves_count,
        snapshot_date=str(SNAPSHOT_DATE),
        active_stations=["BLR", "BOM", "DEL"],
        fleet_types=["A320 (162 seats)", "ATR72 (72 seats)"],
    )


@app.get("/api/pairings")
def list_pairings_workspace(
    date: str | None = None,
    aircraft: str | None = None,
    risk: str | None = "all",
):
    """
    Tactical Pairings Roster payload for the Pairings Workspace UI.

    Joins pairings → flights → pairing_crew → crew → risk_signals and
    derives pairing risk as the max assigned-crew disruption score.
    """
    allowed_risk = {None, "", "all", "high", "elevated", "low"}
    if risk not in allowed_risk:
        raise HTTPException(status_code=400, detail="risk must be all, high, elevated, or low")

    try:
        return get_pairings_workspace(
            date_filter=date,
            aircraft=aircraft,
            risk=None if risk in (None, "", "all") else risk,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pairings query error: {exc}") from exc


@app.get("/api/pairings/{pairing_id}")
def get_pairing_detail(pairing_id: str):
    """Full pairing payload for the pairing detail page."""
    try:
        pairing = get_pairing(pairing_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pairings query error: {exc}") from exc
    if pairing is None:
        raise HTTPException(status_code=404, detail=f"Pairing {pairing_id} not found")
    return pairing


@app.get("/api/crew")
def list_crew_endpoint(
    rank: str | None = None,
    base: str | None = None,
    risk: str | None = "all",
):
    """Crew Management roster."""
    allowed_risk = {None, "", "all", "high", "elevated", "low"}
    if risk not in allowed_risk:
        raise HTTPException(status_code=400, detail="risk must be all, high, elevated, or low")
    try:
        return list_crew(
            rank=rank,
            base=base,
            risk=None if risk in (None, "", "all") else risk,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Crew query error: {exc}") from exc


@app.get("/api/flights/{flight_id}")
def get_flight_detail_endpoint(flight_id: str):
    """Full flight payload for the flight detail page."""
    try:
        flight = get_flight_detail(flight_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Flight query error: {exc}") from exc
    if flight is None:
        raise HTTPException(status_code=404, detail=f"Flight {flight_id} not found")
    return flight


@app.get("/api/crew/{crew_id}")
def get_crew_detail_endpoint(crew_id: str):
    """Full crew payload for the crew detail page."""
    try:
        crew = get_crew_detail(crew_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Crew query error: {exc}") from exc
    if crew is None:
        raise HTTPException(status_code=404, detail=f"Crew {crew_id} not found")
    return crew


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    """
    Execute natural language operational query via LangGraph agent.
    Routes to deterministic Python query tools, verifies data, and synthesizes response.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        result = run_crew_ops_agent(query=req.query, session_id=req.session_id, tier=req.tier)
        return ChatResponse(
            response=result.get("final_response", ""),
            tool_calls=result.get("tool_calls", []),
            tool_results=result.get("tool_results", []),
            reasoning_trace=result.get("reasoning_trace", []),
            tier=req.tier,
            session_id=req.session_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution error: {str(e)}")


@app.get("/api/sessions", response_model=list[SessionItem])
def get_sessions():
    """List all chat sessions ordered by most recently updated."""
    return list_sessions()


@app.post("/api/sessions", response_model=SessionItem)
def create_new_session(req: CreateSessionRequest | None = None):
    """Create a new chat session."""
    session_id = req.session_id if req and req.session_id else None
    title = req.title if req and req.title else "New Session"
    sess = create_session(session_id=session_id, title=title)
    return sess


@app.get("/api/sessions/{session_id}")
def get_session_history(session_id: str):
    """Fetch all messages and audit payloads for a given session."""
    messages = get_session_messages(session_id)
    session_meta = get_session(session_id)
    return {
        "session_id": session_id,
        "session": session_meta,
        "messages": messages,
    }


@app.delete("/api/sessions/{session_id}")
def remove_session(session_id: str):
    """Delete a session and all its associated messages."""
    delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


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
