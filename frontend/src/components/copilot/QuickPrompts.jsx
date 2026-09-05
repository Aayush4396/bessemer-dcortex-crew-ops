import { Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'

const quickPrompts = [
  { label: 'DX412 Aircraft & Seats', query: 'Which aircraft operates flight DX412 on 2026-09-15 and how many seats does it have?' },
  { label: 'BLR Reserves (Sep 15)', query: 'Who is on reserve at BLR on 2026-09-15, and what are their on-call windows?' },
  { label: 'C-1042 7d Duty & Headroom', query: 'How many duty hours has C-1042 accrued in the 7 days ending 2026-09-14, and what is the remaining headroom?' },
  { label: 'Simulate S1 (C-3231 Sick)', query: 'Simulate the disruption impact if ATR Captain C-3231 calls in sick for pairing P-2224 on 2026-09-16. What flights and passengers are affected?' },
  { label: 'Simulate S3 (BLR Closure)', query: 'Simulate impact if BLR station closes between 08:00Z and 14:00Z on 2026-09-17. Which flights are affected?' },
  { label: 'Simulate S4 (VT-DXA 90m Delay)', query: 'Simulate disruption if aircraft VT-DXA is delayed by 1.5 hours on 2026-09-16. Does the crew breach FDP limits?' },
  { label: 'Optimize S1 Recovery', query: 'Optimize recovery options for ATR Captain C-3231 calling sick on pairing P-2224 on 2026-09-16. What is the lowest-cost legal cover?' },
  { label: 'Optimize S6 Joint Crewing', query: 'Both A320 captains for VT-DXA (P-2205) and VT-DXB (P-2212) called in sick on 2026-09-18. Find the optimal joint recovery plan.' },
  { label: 'Draft Callout Draft (Q36)', query: 'Draft the callout dispatch notification for reserve Captain C-3310 covering pairing P-2291.' },
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
