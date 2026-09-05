import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { CrewRow } from '@/components/crew/CrewRow'
import { hoursLabel, riskBadge } from '@/lib/format'
import { cn } from '@/lib/utils'

function DutyBar({ usedPct }) {
  const tone = usedPct >= 90 ? 'bg-rose-500' : usedPct >= 75 ? 'bg-amber-500' : 'bg-emerald-500'
  return (
    <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
      <div className={cn('h-full rounded-full', tone)} style={{ width: `${usedPct}%` }} />
    </div>
  )
}

export function PairingDetail({ pairing }) {
  const badgeVariant = riskBadge[pairing.risk_level] || 'low'
  const firstFlight = pairing.days[0]?.flights[0]
  const roster = pairing.crew ?? []

  return (
    <div className="space-y-6">
      <header className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <div className="flex flex-wrap items-start justify-between gap-4 px-5 py-5">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-semibold tracking-tight text-slate-900">{pairing.pairing_id}</h1>
              <Badge>{pairing.rotation_label}</Badge>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              {pairing.route.map((station, index) => (
                <span key={`${station}-${index}`} className="flex items-center gap-1.5">
                  {index > 0 && <span className="text-slate-300">→</span>}
                  <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-xs font-semibold text-slate-700">
                    {station}
                  </span>
                </span>
              ))}
            </div>
          </div>
          <Badge variant={badgeVariant} className="text-[11px]">
            RISK {pairing.risk_score.toFixed(2)}
          </Badge>
        </div>
        <div className="grid grid-cols-3 divide-x divide-slate-100 border-t border-slate-100 bg-slate-50/70 text-xs">
          <div className="px-5 py-3">
            <p className="uppercase tracking-wide text-slate-400">Aircraft</p>
            <p className="mt-0.5 font-semibold text-slate-800">{pairing.aircraft.tail}</p>
            <p className="text-slate-500">{pairing.aircraft.type}</p>
          </div>
          <div className="px-5 py-3">
            <p className="uppercase tracking-wide text-slate-400">Seats</p>
            <p className="mt-0.5 font-semibold text-slate-800">{firstFlight?.seats ?? '—'}</p>
          </div>
          <div className="px-5 py-3">
            <p className="uppercase tracking-wide text-slate-400">Days</p>
            <p className="mt-0.5 font-semibold text-slate-800">{pairing.rotation_days}</p>
          </div>
        </div>
      </header>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_280px]">
        <div className="space-y-8">
          {pairing.days.map((day) => (
            <section key={day.date}>
              {day.rest_hours != null && (
                <div className="mb-6 flex items-center gap-3">
                  <div className="h-px flex-1 bg-slate-200" />
                  <p className="text-[11px] font-medium text-slate-500">
                    Rest {hoursLabel(day.rest_hours)}
                    {day.rest_min_hours != null ? ` · RULE-REST-04 ${hoursLabel(day.rest_min_hours)}` : ''}
                  </p>
                  <div className="h-px flex-1 bg-slate-200" />
                </div>
              )}

              <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-900">
                    Day {day.day_index} — {day.label}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {day.report_hhmm}Z → {day.release_hhmm}Z ({day.duty_hours.toFixed(1)}h)
                    <span className="ml-2 text-slate-400">
                      {day.sector_count} sectors · max {hoursLabel(day.max_window_hours)}
                    </span>
                  </p>
                </div>
              </div>
              <DutyBar usedPct={day.duty_used_pct} />

              <ol className="mt-4">
                {day.flights.map((flight) => (
                  <li key={flight.flight_id}>
                    {flight.ground_hours != null && (
                      <div className="flex items-center gap-3 py-2 pl-4">
                        <div className="h-6 w-px bg-slate-200" />
                        <p className="text-[10px] uppercase tracking-wide text-slate-400">
                          Ground {hoursLabel(flight.ground_hours)}
                        </p>
                      </div>
                    )}
                    <Link
                      to={`/flights/${flight.flight_id}`}
                      className="flex items-center gap-4 rounded-xl border border-slate-200 bg-white px-4 py-3 transition-colors hover:border-emerald-300 hover:bg-emerald-50/40"
                    >
                      <div className="w-16 shrink-0">
                        <p className="text-sm font-semibold text-slate-900">{flight.flight_no}</p>
                        <p className="text-[11px] text-slate-400">{hoursLabel(flight.block_hours)}</p>
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-3">
                          <div className="text-right">
                            <p className="text-sm font-semibold text-slate-800">{flight.dep_station}</p>
                            <p className="text-[11px] text-slate-400">{flight.dep_hhmm}Z</p>
                          </div>
                          <div className="h-px min-w-[48px] flex-1 bg-slate-200" />
                          <div>
                            <p className="text-sm font-semibold text-slate-800">{flight.arr_station}</p>
                            <p className="text-[11px] text-slate-400">{flight.arr_hhmm}Z</p>
                          </div>
                        </div>
                      </div>
                    </Link>
                  </li>
                ))}
              </ol>
            </section>
          ))}
        </div>

        <aside className="h-fit rounded-2xl border border-slate-200 bg-white xl:sticky xl:top-0">
          <div className="border-b border-slate-100 px-4 py-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Assigned roster
            </p>
            <p className="mt-0.5 text-xs text-slate-500">{roster.length} crew</p>
          </div>
          <div className="divide-y divide-slate-100 px-2 py-1">
            {roster.map((member) => (
              <CrewRow key={member.crew_id} member={member} pairingId={pairing.pairing_id} />
            ))}
          </div>
        </aside>
      </div>
    </div>
  )
}
