import { Navigate, Route, Routes } from 'react-router-dom'
import { AppSidebar } from '@/components/layout/AppSidebar'
import { usePairings } from '@/hooks/usePairings'
import { CopilotPage } from '@/pages/CopilotPage'
import { CrewDetailPage } from '@/pages/CrewDetailPage'
import { CrewManagementPage } from '@/pages/CrewManagementPage'
import { FlightDetailPage } from '@/pages/FlightDetailPage'
import { PairingDetailPage } from '@/pages/PairingDetailPage'
import { PairingsWorkspace } from '@/pages/PairingsWorkspace'

export default function App() {
  const { data } = usePairings({ date: '2026-09-15', risk: 'all' })

  return (
    <div className="flex h-full min-h-0 bg-[#eef1f5]">
      <AppSidebar
        pairingCount={data?.kpis?.active_pairings ?? 0}
        crewCount={data?.kpis?.crew_complement ?? 0}
      />
      <main className="min-h-0 min-w-0 flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<PairingsWorkspace />} />
          <Route path="/pairings/:pairingId" element={<PairingDetailPage />} />
          <Route path="/flights/:flightId" element={<FlightDetailPage />} />
          <Route path="/crew" element={<CrewManagementPage />} />
          <Route path="/crew/:crewId" element={<CrewDetailPage />} />
          <Route path="/copilot" element={<CopilotPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
