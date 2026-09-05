#!/usr/bin/env bash
# ==============================================================================
# start.sh — dCortex Crew Operations Advisor Startup Script
# Starts both FastAPI Backend (Port 8000) and React Vite Frontend (Port 5173).
# Compatible with Git Bash (Windows), Linux, macOS, and WSL.
# ==============================================================================

set -e

# ANSI Color Codes
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo -e "${CYAN}${BOLD}"
echo "================================================================="
echo "   ✈️  dCortex Crew Operations Advisor (NOC AI Copilot)          "
echo "================================================================="
echo -e "${NC}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# ------------------------------------------------------------------------------
# 1. Virtual Environment Activation
# ------------------------------------------------------------------------------
echo -e "${YELLOW}[1/4] Checking Python environment...${NC}"

if [ -f "$ROOT_DIR/.venv/Scripts/activate" ]; then
    # Windows / Git Bash
    source "$ROOT_DIR/.venv/Scripts/activate"
    echo -e "${GREEN}✓ Activated Windows virtual environment (.venv/Scripts/activate)${NC}"
elif [ -f "$ROOT_DIR/.venv/bin/activate" ]; then
    # Linux / macOS / WSL
    source "$ROOT_DIR/.venv/bin/activate"
    echo -e "${GREEN}✓ Activated Unix virtual environment (.venv/bin/activate)${NC}"
else
    echo -e "${RED}Virtual environment not found at .venv!${NC}"
    echo "Creating virtual environment and installing dependencies..."
    python -m venv .venv
    if [ -f "$ROOT_DIR/.venv/Scripts/activate" ]; then
        source "$ROOT_DIR/.venv/Scripts/activate"
    else
        source "$ROOT_DIR/.venv/bin/activate"
    fi
    pip install -r requirements.txt
fi

# ------------------------------------------------------------------------------
# 2. Environment Variables & Database Check
# ------------------------------------------------------------------------------
echo -e "${YELLOW}[2/4] Verifying configuration and database...${NC}"

if [ ! -f "$ROOT_DIR/.env" ]; then
    if [ -f "$ROOT_DIR/.env.example" ]; then
        cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
        echo -e "${YELLOW}! Created .env from .env.example. Please ensure SARVAM_API_KEY is set.${NC}"
    fi
fi

if [ ! -f "$ROOT_DIR/crew_ops.db" ]; then
    echo -e "${YELLOW}Database not found. Loading datasets into SQLite (crew_ops.db)...${NC}"
    python -m src.db.loader
    echo -e "${GREEN}✓ Database initialized successfully.${NC}"
else
    echo -e "${GREEN}✓ SQLite database detected (crew_ops.db).${NC}"
fi

# ------------------------------------------------------------------------------
# 3. Graceful Shutdown Handler (Ctrl+C)
# ------------------------------------------------------------------------------
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down dCortex services...${NC}"
    if [ -n "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    echo -e "${GREEN}All processes terminated cleanly. Goodbye!${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# ------------------------------------------------------------------------------
# 4. Launch FastAPI Backend
# ------------------------------------------------------------------------------
echo -e "${YELLOW}[3/4] Starting FastAPI backend on http://127.0.0.1:8000...${NC}"

python -m uvicorn src.api.server:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

sleep 2

# ------------------------------------------------------------------------------
# 5. Launch React + Vite Frontend
# ------------------------------------------------------------------------------
echo -e "${YELLOW}[4/4] Starting React frontend on http://127.0.0.1:5173...${NC}"

cd "$ROOT_DIR/frontend"

if [ ! -d "node_modules" ]; then
    echo "Installing frontend npm dependencies..."
    npm install
fi

npm run dev &
FRONTEND_PID=$!

cd "$ROOT_DIR"

# ------------------------------------------------------------------------------
# Ready Banner
# ------------------------------------------------------------------------------
echo ""
echo -e "${GREEN}${BOLD}=================================================================${NC}"
echo -e "${GREEN}${BOLD}   🚀 dCortex NOC AI Copilot is LIVE!                            ${NC}"
echo -e "${GREEN}${BOLD}=================================================================${NC}"
echo -e "   • Frontend Console : ${CYAN}${BOLD}http://127.0.0.1:5173${NC}"
echo -e "   • Backend API      : ${CYAN}${BOLD}http://127.0.0.1:8000${NC}"
echo -e "   • Swagger Docs     : ${CYAN}${BOLD}http://127.0.0.1:8000/docs${NC}"
echo -e "${BOLD}Press Ctrl+C to gracefully stop all services.${NC}"
echo ""

# Wait on background processes
wait
