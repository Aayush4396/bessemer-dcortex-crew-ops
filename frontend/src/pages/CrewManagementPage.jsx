import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Avatar } from '@/components/ui/avatar'
import { PageHeader, PageShell, StatusPanel } from '@/components/layout/PageShell'
import { cn } from '@/lib/utils'
import { useCrewList } from '@/hooks/usePairings'

const riskOptions = [
  { id: 'all', label: 'All' },
  { id: 'high', label: 'High' },
  { id: 'elevated', label: 'Elevated' },
  { id: 'low', label: 'Low' },
]

export function CrewManagementPage() {
  const [rank, setRank] = useState(null)
  const [base, setBase] = useState(null)
  const [risk, setRisk] = useState('all')
  const [query, setQuery] = useState('')

  const { data, isPending, isError, error } = useCrewList({ rank, base, risk })
  const crew = useMemo(() => {
    const rows = data?.crew ?? []
    const q = query.trim().toLowerCase()
    if (!q) return rows
    return rows.filter(
      (member) =>
        member.name.toLowerCase().includes(q) || member.crew_id.toLowerCase().includes(q),
    )
  }, [data, query])

  return (
    <PageShell className="space-y-4">
      <PageHeader
        title="Crew Management"
        subtitle={`${data?.kpis?.crew_total ?? '—'} crew · ${data?.kpis?.high_risk_crew ?? '—'} high risk`}
      />

      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-3">
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search name or id"
          className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none placeholder:text-slate-400 focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/20"
        />
        <select
          value={rank || ''}
          onChange={(event) => setRank(event.target.value || null)}
          className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none focus:border-emerald-400"
        >
          <option value="">All ranks</option>
          {(data?.ranks ?? []).map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
        <select
          value={base || ''}
          onChange={(event) => setBase(event.target.value || null)}
          className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none focus:border-emerald-400"
        >
          <option value="">All bases</option>
          {(data?.bases ?? []).map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
        <div className="ml-auto flex gap-1">
          {riskOptions.map((option) => (
            <button
              key={option.id}
              type="button"
              onClick={() => setRisk(option.id)}
              className={cn(
                'h-9 rounded-lg px-3 text-xs font-semibold',
                risk === option.id
                  ? 'bg-emerald-600 text-white'
                  : 'border border-slate-200 bg-white text-slate-500 hover:bg-slate-50 hover:text-slate-800',
              )}
            >
              {option.label}
              {data?.risk_counts?.[option.id] != null ? ` ${data.risk_counts[option.id]}` : ''}
            </button>
          ))}
        </div>
      </div>

      {isPending && <StatusPanel>Loading crew from SQLite…</StatusPanel>}
      {isError && <StatusPanel tone="error">{error.message}</StatusPanel>}

      {!isPending && !isError && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <div className="grid grid-cols-[1fr_8rem_4rem_5rem_4.5rem] gap-3 border-b border-slate-100 px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            <p>Crew</p>
            <p>Rank</p>
            <p>Base</p>
            <p>Status</p>
            <p className="text-right">Risk</p>
          </div>
          {crew.length === 0 && (
            <p className="px-4 py-10 text-center text-sm text-slate-500">No crew match these filters.</p>
          )}
          <div className="divide-y divide-slate-100">
            {crew.map((member) => (
              <Link
                key={member.crew_id}
                to={`/crew/${member.crew_id}`}
                className="grid grid-cols-[1fr_8rem_4rem_5rem_4.5rem] items-center gap-3 px-4 py-2.5 hover:bg-emerald-50/40"
              >
                <div className="flex min-w-0 items-center gap-2.5">
                  <Avatar initials={member.initials} tone={member.risk_level} />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-900">{member.name}</p>
                    <p className="text-[11px] text-slate-400">{member.crew_id}</p>
                  </div>
                </div>
                <p className="truncate text-xs text-slate-600">{member.rank}</p>
                <p className="text-xs text-slate-600">{member.base}</p>
                <p className="text-xs text-slate-500">{member.status}</p>
                <p
                  className={cn(
                    'text-right text-xs font-semibold',
                    member.risk_level === 'critical'
                      ? 'text-rose-600'
                      : member.risk_score >= 0.3
                        ? 'text-amber-600'
                        : 'text-slate-500',
                  )}
                >
                  {member.risk_score.toFixed(2)}
                </p>
              </Link>
            ))}
          </div>
        </div>
      )}
    </PageShell>
  )
}
