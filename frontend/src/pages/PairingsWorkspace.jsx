import { useMemo, useState } from 'react'
import { FilterBar } from '@/components/pairings/FilterBar'
import { KpiBar } from '@/components/pairings/KpiBar'
import { PairingCard } from '@/components/pairings/PairingCard'
import { usePairings } from '@/hooks/usePairings'

export function PairingsWorkspace() {
  const [date, setDate] = useState(null)
  const [aircraft, setAircraft] = useState(null)
  const [risk, setRisk] = useState('all')

  const { data, isPending, isError, error } = usePairings({ date, aircraft, risk })
  const pairings = useMemo(() => data?.pairings ?? [], [data])

  return (
    <div className="h-full min-h-0 space-y-4 overflow-y-auto p-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">Tactical Pairings Roster</h1>
        <p className="text-sm text-slate-500">
          One row per pairing-day. At-risk crew are expanded; legal complement is collapsed.
        </p>
      </div>

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

      {isPending && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-10 text-center text-sm text-slate-500">
          Loading pairings from SQLite…
        </div>
      )}

      {isError && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-6 text-sm text-rose-700">
          {error.message}
        </div>
      )}

      {!isPending && !isError && pairings.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-10 text-center text-sm text-slate-500">
          No pairings match this day, tail, or risk filter.
        </div>
      )}

      <div className="space-y-3">
        {pairings.map((pairing) => (
          <PairingCard key={pairing.pairing_id} pairing={pairing} />
        ))}
      </div>
    </div>
  )
}
