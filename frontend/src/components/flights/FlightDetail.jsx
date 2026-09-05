import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { CrewRow } from '@/components/crew/CrewRow'
import { hoursLabel, riskBadge } from '@/lib/format'

export function FlightDetail({ flight }) {
  const pairing = flight.pairing
  const badgeVariant = riskBadge[pairing?.risk_level] || 'low'

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">{flight.flight_no}</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            {flight.dep_station} → {flight.arr_station} · {flight.date}
          </p>
          <p className="text-xs text-slate-400">{flight.flight_id}</p>
        </div>
        {pairing && <Badge variant={badgeVariant}>RISK {pairing.risk_score.toFixed(2)}</Badge>}
      </div>

      <section className="grid grid-cols-2 gap-4 rounded-xl border border-slate-200 bg-white px-4 py-3 text-xs sm:grid-cols-4">
        <div>
          <p className="uppercase tracking-wide text-slate-400">Depart</p>
          <p className="mt-0.5 font-medium text-slate-800">{flight.dep_hhmm}Z</p>
          <p className="text-slate-500">{flight.dep_station}</p>
        </div>
        <div>
          <p className="uppercase tracking-wide text-slate-400">Arrive</p>
          <p className="mt-0.5 font-medium text-slate-800">{flight.arr_hhmm}Z</p>
          <p className="text-slate-500">{flight.arr_station}</p>
        </div>
        <div>
          <p className="uppercase tracking-wide text-slate-400">Block</p>
          <p className="mt-0.5 font-medium text-slate-800">{hoursLabel(flight.block_hours)}</p>
        </div>
        <div>
          <p className="uppercase tracking-wide text-slate-400">Aircraft</p>
          <p className="mt-0.5 font-medium text-slate-800">{flight.aircraft}</p>
          <p className="text-slate-500">
            {flight.aircraft_type} · {flight.seats} seats
          </p>
        </div>
      </section>

      {pairing && (
        <section className="rounded-xl border border-slate-200 bg-white px-4 py-4">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <Link
              to={`/pairings/${pairing.pairing_id}`}
              className="text-sm font-semibold text-slate-800 hover:text-emerald-800"
            >
              Pairing {pairing.pairing_id}
            </Link>
            <p className="text-[11px] text-slate-500">{pairing.rotation_label}</p>
          </div>
          <p className="mt-1 text-xs text-slate-500">{pairing.route.join(' → ')}</p>
          {pairing.day && (
            <p className="mt-1 text-[11px] text-slate-500">
              Day {pairing.day.day_index} — {pairing.day.label} · Report {pairing.day.report_hhmm}Z →
              Release {pairing.day.release_hhmm}Z · Duty {hoursLabel(pairing.day.duty_hours)} / max{' '}
              {hoursLabel(pairing.day.max_window_hours)} · {pairing.day.sector_count} sectors
            </p>
          )}

          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {pairing.previous && (
              <Link
                to={`/flights/${pairing.previous.flight_id}`}
                className="rounded-lg border border-slate-200 px-3 py-2 hover:bg-slate-50"
              >
                <p className="text-[10px] uppercase tracking-wide text-slate-400">Previous</p>
                <p className="text-xs font-semibold text-slate-800">{pairing.previous.flight_no}</p>
                <p className="text-[11px] text-slate-500">
                  {pairing.previous.dep_station} → {pairing.previous.arr_station}
                </p>
              </Link>
            )}
            {pairing.ground_hours != null && (
              <div className="rounded-lg border border-slate-200 px-3 py-2">
                <p className="text-[10px] uppercase tracking-wide text-slate-400">Ground</p>
                <p className="text-xs font-semibold text-slate-800">{hoursLabel(pairing.ground_hours)}</p>
              </div>
            )}
            {pairing.next && (
              <Link
                to={`/flights/${pairing.next.flight_id}`}
                className="rounded-lg border border-slate-200 px-3 py-2 hover:bg-slate-50"
              >
                <p className="text-[10px] uppercase tracking-wide text-slate-400">Next</p>
                <p className="text-xs font-semibold text-slate-800">{pairing.next.flight_no}</p>
                <p className="text-[11px] text-slate-500">
                  {pairing.next.dep_station} → {pairing.next.arr_station}
                </p>
              </Link>
            )}
          </div>
        </section>
      )}

      {pairing?.crew?.length > 0 && (
        <section className="rounded-2xl border border-slate-200 bg-white">
          <div className="border-b border-slate-100 px-4 py-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Assigned roster
            </p>
          </div>
          <div className="divide-y divide-slate-100 px-2 py-1">
            {pairing.crew.map((member) => (
              <CrewRow key={member.crew_id} member={member} pairingId={pairing.pairing_id} />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
