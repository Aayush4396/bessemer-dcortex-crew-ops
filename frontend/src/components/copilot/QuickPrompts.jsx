import { Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'

const quickPrompts = [
  { label: 'DX412 Aircraft & Seats', query: 'Which aircraft operates flight DX412 on 2026-09-15 and how many seats does it have?' },
  { label: 'BLR Reserves (Sep 15)', query: 'Who is on reserve at BLR on 2026-09-15, and what are their on-call windows?' },
  { label: 'C-1042 7d Duty & Headroom', query: 'How many duty hours has C-1042 accrued in the 7 days ending 2026-09-14, and what is the remaining headroom?' },
  { label: 'C-1042 Risk Score & Drivers', query: 'What is the disruption risk score for C-1042 and what operational factors drive it?' },
  { label: 'Expiring Certifications (30d)', query: 'List all crew certifications expiring within 30 days of 2026-09-15.' },
  { label: 'DEL Departures (Sep 15)', query: 'Which flights depart DEL on 2026-09-15?' },
]

export function QuickPrompts({ onSelect, disabled = false }) {
  return (
    <div className="flex items-center gap-2 overflow-x-auto border-b border-slate-100 bg-slate-50/60 px-4 py-2.5">
      <span className="mr-1 flex shrink-0 items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
        <Sparkles className="h-3.5 w-3.5 text-emerald-600" />
        Quick inquiries
      </span>
      {quickPrompts.map((prompt) => (
        <Button
          key={prompt.label}
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={() => onSelect(prompt.query)}
          className="shrink-0 rounded-full text-xs font-medium text-slate-600 hover:border-emerald-300 hover:text-emerald-700"
        >
          {prompt.label}
        </Button>
      ))}
    </div>
  )
}
