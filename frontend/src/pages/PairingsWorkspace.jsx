import { useMemo, useState } from 'react'
import { FilterBar } from '@/components/pairings/FilterBar'
import { KpiBar } from '@/components/pairings/KpiBar'
import { PairingCard } from '@/components/pairings/PairingCard'
import { PageHeader, PageShell, StatusPanel } from '@/components/layout/PageShell'
import { usePairings } from '@/hooks/usePairings'

export function PairingsWorkspace() {
  const [date, setDate] = useState(null)
  const [aircraft, setAircraft] = useState(null)
  const [risk, setRisk] = useState('all')

  const { data, isPending, isError, error } = usePairings({ date, aircraft, risk })
  const pairings = useMemo(() => data?.pairings ?? [], [data])

  return (
    <PageShell className="space-y-4">
      <PageHeader
        title="Tactical Pairings Roster"
        subtitle="One row per pairing-day. At-risk crew are expanded; legal complement is collapsed."
      />

      <KpiBar kpis={data?.kpis} />

      <FilterBar
        weekDays={data?.week?.days ?? []}
        date={date}
        aircraft={aircraft}
        risk={risk}
        riskCounts={data?.risk_counts ?? {}}
        tails={data?.tails ?? []}
        onChange={(next) => {
          if ('date' in next) setDate(next.date)
          if ('aircraft' in next) setAircraft(next.aircraft)
          if ('risk' in next) setRisk(next.risk)
        }}
      />

      {isPending && <StatusPanel>Loading pairings from SQLite…</StatusPanel>}

      {isError && <StatusPanel tone="error">{error.message}</StatusPanel>}

      {!isPending && !isError && pairings.length === 0 && (
        <StatusPanel>No pairings match this day, tail, or risk filter.</StatusPanel>
      )}

      <div className="space-y-3">
        {pairings.map((pairing) => (
          <PairingCard key={pairing.pairing_id} pairing={pairing} />
        ))}
      </div>
    </PageShell>
  )
}
