import { Clock3, Plane } from 'lucide-react'
import { Card } from '@/components/ui/card'

export function KpiBar({ kpis }) {
  const cards = [
    {
      label: 'Active Cycle Load',
      value: kpis?.active_pairings ?? '—',
      hint: 'pairings scheduled',
      icon: Clock3,
    },
    {
      label: 'Flight Legs',
      value: kpis?.flight_legs ?? '—',
      hint: `${kpis?.legs_covered_pct ?? 0}% covered`,
      icon: Plane,
    },
  ]

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {cards.map((card) => {
        const Icon = card.icon
        return (
          <Card key={card.label} className="px-4 py-3">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                  {card.label}
                </p>
                <p className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">{card.value}</p>
                {card.hint ? <p className="mt-0.5 text-xs text-slate-500">{card.hint}</p> : null}
              </div>
              <Icon className="h-4 w-4 text-slate-400" />
            </div>
          </Card>
        )
      })}
    </div>
  )
}
