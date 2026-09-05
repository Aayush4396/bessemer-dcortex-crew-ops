import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { tableFeatures, useTable } from '@tanstack/react-table'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { AssignedRoster } from '@/components/pairings/AssignedRoster'
import { cn } from '@/lib/utils'

const tableFeatureSet = tableFeatures({})

const riskBadge = {
  critical: 'critical',
  elevated: 'elevated',
  low: 'low',
}

const accent = {
  critical: 'border-l-rose-500',
  elevated: 'border-l-amber-500',
  low: 'border-l-emerald-500',
}

function DutyCell({ day, aircraft, isFirst }) {
  const barTone =
    day.duty_used_pct >= 90 ? 'bg-rose-500' : day.duty_used_pct >= 75 ? 'bg-amber-500' : 'bg-emerald-500'

  return (
    <div className="min-w-[220px] space-y-2">
      {isFirst && (
        <div>
          <p className="text-sm font-semibold text-slate-900">{aircraft.tail}</p>
          <p className="text-[11px] text-slate-500">{aircraft.label}</p>
        </div>
      )}
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Duty Cycle</p>
        <p className="text-xs font-medium text-slate-700">
          {day.report_hhmm}Z → {day.release_hhmm}Z
          <span className="ml-1.5 font-semibold text-slate-900">({day.duty_hours.toFixed(1)}h)</span>
        </p>
        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
          <div className={cn('h-full rounded-full', barTone)} style={{ width: `${day.duty_used_pct}%` }} />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-500">
        <div>
          <p className="uppercase tracking-wide text-slate-400">Report</p>
          <p className="font-medium text-slate-700">{day.report_hhmm}Z</p>
        </div>
        <div>
          <p className="uppercase tracking-wide text-slate-400">Max Window</p>
          <p className="font-medium text-slate-700">{day.max_window_hours.toFixed(1)}h</p>
        </div>
      </div>
    </div>
  )
}

function FlightsCell({ day }) {
  return (
    <div className="min-w-0">
      <p className="mb-2 text-[11px] font-semibold text-slate-500">
        Day {day.day_index} — {day.label}
      </p>
      <div className="flex flex-wrap gap-2">
        {day.flights.map((flight) => (
          <div
            key={flight.flight_id}
            className="min-w-[132px] rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-2"
          >
            <p className="text-xs font-semibold text-slate-800">{flight.flight_no}</p>
            <p className="mt-1 text-[11px] text-slate-600">
              {flight.dep_station} → {flight.arr_station}
            </p>
            <p className="text-[11px] text-slate-400">
              {flight.dep_hhmm}Z – {flight.arr_hhmm}Z
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}

export function PairingCard({ pairing }) {
  const columns = useMemo(
    () => [
      {
        id: 'duty',
        header: 'Aircraft / Duty',
        cell: ({ row }) => (
          <DutyCell
            day={row.original}
            aircraft={pairing.aircraft}
            isFirst={row.index === 0}
          />
        ),
      },
      {
        id: 'flights',
        header: 'Flight Legs',
        cell: ({ row }) => <FlightsCell day={row.original} />,
      },
    ],
    [pairing],
  )

  const table = useTable({
    features: tableFeatureSet,
    columns,
    data: pairing.days,
  })

  const badgeVariant = riskBadge[pairing.risk_level] || 'low'

  return (
    <Link to={`/pairings/${pairing.pairing_id}`} className="block">
    <Card
      className={cn(
        'overflow-hidden border-l-4 text-left transition-shadow hover:shadow-md',
        accent[pairing.risk_level] || accent.low,
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-semibold text-slate-900">{pairing.pairing_id}</p>
          <Badge>{pairing.rotation_label}</Badge>
          <p className="text-xs text-slate-500">{pairing.route.join(' → ')}</p>
        </div>
        <Badge variant={badgeVariant}>RISK {pairing.risk_score.toFixed(2)}</Badge>
      </div>

      <div className="flex gap-4 px-4 py-4">
        <div className="min-w-0 flex-1 overflow-x-auto">
          <table className="w-full border-separate border-spacing-y-3">
            <tbody>
              {table.getRowModel().rows.map((row, index) => (
                <tr key={row.id} className={index > 0 ? 'border-t border-slate-100' : undefined}>
                  {row.getAllCells().map((cell) => (
                    <td
                      key={cell.id}
                      className={cell.column.id === 'duty' ? 'w-[240px] align-top pr-4' : 'align-top'}
                    >
                      <table.FlexRender cell={cell} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <AssignedRoster roster={pairing.roster} />
      </div>
    </Card>
    </Link>
  )
}
