# dCortex NOC Operations Console (Frontend)

The frontend for the **dCortex Airline Crew Operations Advisor** is an airline Network Operations Control (NOC) console built with **React 19**, **Vite**, **React Router 7**, and **Tailwind CSS**.

---

## 🚀 Key Capabilities

- **Tactical Pairings Workspace (`/`)**: Real-time network health overview with live KPI counters (active pairings, unassigned sectors, elevated risk, crew complement), multi-day rotation grouping, and composite risk scoring (`low`, `elevated`, `high`, `critical`).
- **Tactical Roster Filters**: Instant filtering by calendar date, aircraft tail registration (`VT-DXA` through `VT-DXF`), and risk level.
- **Pairing Detail Drilldown (`/pairings/:pairingId`)**: Multi-day rotation timeline, individual flight segments, operating crew complement, and fatigue/risk breakdown.
- **Flight Sector 360 (`/flights/:flightId`)**: Complete flight information, scheduled UTC/local times, block hours, aircraft type, seat capacity (162 for A320, 72 for ATR72), and reverse link to the assigned pairing.
- **Crew Management & 360 Profile (`/crew`, `/crew/:crewId`)**: Searchable 150-crew directory filtered by rank (Captain, First Officer, Cabin Crew), base station (BLR, BOM, DEL), and risk level. Displays rolling 7d duty / 28d flight hours, DGCA regulatory headroom, valid certifications, and disruption risk drivers.
- **Conversational AI Copilot (`/copilot`)**: Multi-turn operational chat powered by Sarvam-105B with session history management, quick query chips, and collapsible explainability drawers detailing tool dispatches and raw SQLite records.

---

## 🛠️ Technology Stack

- **Framework**: React 19 + Vite 7
- **Routing**: React Router 7 (`react-router-dom`)
- **Styling**: Tailwind CSS with custom NOC dark palette
- **Icons**: Lucide React
- **HTTP Client**: Native browser `fetch` with Vite backend proxy

---

## 📁 Component & Route Architecture

```
frontend/src/
├── components/
│   ├── layout/
│   │   └── AppSidebar.jsx        # Navigation sidebar with active pairing & crew badges
│   ├── copilot/
│   │   ├── ChatConsole.jsx       # Interactive chat message feed with optimistic UI
│   │   └── AuditDrawer.jsx       # Tool call & raw SQL explainability drawer
│   ├── pairings/
│   │   ├── PairingTable.jsx      # Tactical pairings roster with risk badges
│   │   └── PairingFilter.jsx     # Date, aircraft, and risk band filter controls
│   ├── crew/
│   │   └── CrewTable.jsx         # 150-crew directory with rank/base filters
│   ├── flights/
│   │   └── FlightCard.jsx        # Flight schedule & block hour metadata card
│   └── SessionSidebar.jsx        # Conversational session history with search
├── pages/
│   ├── PairingsWorkspace.jsx     # Route: /
│   ├── PairingDetailPage.jsx     # Route: /pairings/:pairingId
│   ├── FlightDetailPage.jsx      # Route: /flights/:flightId
│   ├── CrewManagementPage.jsx    # Route: /crew
│   ├── CrewDetailPage.jsx        # Route: /crew/:crewId
│   └── CopilotPage.jsx           # Route: /copilot
├── hooks/
│   ├── usePairings.js            # SWR-style hook for /api/pairings
│   ├── useCrew.js                # Hook for /api/crew
│   └── useFlight.js              # Hook for /api/flights
├── App.jsx                       # Route coordinator & main layout
└── main.jsx                      # React entrypoint
```

---

## 🌐 API Proxy Configuration

The development server proxies all `/api/*` requests to the FastAPI backend running on port `8000` via [`vite.config.js`](file:///c:/Users/aayus/OneDrive/Desktop/bessemer_dcortex/frontend/vite.config.js):

```javascript
server: {
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true,
    },
  },
}
```

---

## 💻 Local Development

### Prerequisites
- **Node.js 18+** and **npm**

### Install Dependencies
```bash
npm install
```

### Start Development Server
```bash
npm run dev
```
The console will be accessible at **`http://127.0.0.1:5173`**.

### Build for Production
```bash
npm run build
```
Generates production assets in `frontend/dist/`.
