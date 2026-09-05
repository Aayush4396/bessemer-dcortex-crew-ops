import { Link } from 'react-router-dom'
import { Avatar } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { hoursLabel, riskBadge } from '@/lib/format'

function ClockBar({ used, max, rule }) {
  if (used == null || max == null) return null
  const pct = Math.min(100, (used / max) * 100)
  const tone = pct >= 90 ? 'bg-rose-500' : pct >= 75 ? 'bg-amber-500' : 'bg-emerald-500'

  return (
    <div>
      <div className="flex items-baseline justify-between gap-2 text-[11px]">
        <p className="font-medium text-slate-700">
          {hoursLabel(used)} / {hoursLabel(max)}
        </p>
        <p className="text-slate-400">{rule}</p>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
        <div className={cn('h-full rounded-full', tone)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export function CrewDetail({ crew }) {
  const badgeVariant = riskBadge[crew.risk_level] || 'low'
  const duty = crew.duty ?? {}

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-5 py-4">
        <div className="flex items-start gap-3">
          <Avatar initials={crew.initials} tone={crew.risk_level} className="h-11 w-11 text-sm" />
          <div>
            <h1 className="text-lg font-semibold text-slate-900">{crew.name}</h1>
            <p className="mt-0.5 text-sm text-slate-500">
              {crew.crew_id} · {crew.rank} · {crew.base}
            </p>
            <p className="text-[11px] text-slate-400">
              {crew.ratings.join(', ')}
              {crew.status ? ` · ${crew.status}` : ''}
            </p>
          </div>
        </div>
        <Badge variant={badgeVariant}>RISK {crew.risk_score.toFixed(2)}</Badge>
      </header>

      {crew.drivers?.length > 0 && (
        <section className="rounded-2xl border border-slate-200 bg-white px-5 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Risk drivers
          </p>
          <ul className="mt-1 space-y-0.5 text-sm text-slate-600">
            {crew.drivers.map((driver) => (
              <li key={driver}>{driver}</li>
            ))}
          </ul>
        </section>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-white px-5 py-4">
          <p className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Duty clocks
          </p>
          <div className="space-y-4">
            <div>
              <p className="text-[11px] text-slate-500">7-day duty</p>
              <ClockBar used={duty.duty_hours_7d} max={duty.duty_max_7d} rule={duty.duty_rule} />
            </div>
            <div>
              <p className="text-[11px] text-slate-500">28-day block</p>
              <ClockBar
                used={duty.flight_hours_28d}
                max={duty.flight_max_28d}
                rule={duty.flight_rule}
              />
            </div>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white px-5 py-4">
          <p className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Certifications
          </p>
          <ul className="space-y-2">
            {crew.certs.map((cert) => (
              <li key={cert.cert_type} className="flex items-center justify-between gap-3 text-sm">
                <span className="text-slate-700">{cert.cert_type}</span>
                <span
                  className={cn(
                    'text-[11px]',
                    cert.status === 'expired'
                      ? 'text-rose-600'
                      : cert.status === 'expiring'
                        ? 'text-amber-600'
                        : 'text-slate-500',
                  )}
                >
                  {cert.valid_to}
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {crew.pairings.map((pairing) => (
        <Link
          key={pairing.pairing_id}
          to={`/pairings/${pairing.pairing_id}`}
          className="block rounded-2xl border border-slate-200 bg-white px-5 py-4 hover:border-emerald-300 hover:bg-emerald-50/30"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="text-sm font-semibold text-slate-800">{pairing.pairing_id}</p>
            <p className="text-[11px] text-slate-500">{pairing.role}</p>
          </div>
          <p className="mt-1 text-xs text-slate-500">{pairing.route.join(' → ')}</p>
        </Link>
      ))}
    </div>
  )
}
