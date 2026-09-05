import { Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'

const quickPrompts = [
  { label: 'DX412 Aircraft & Seats', query: 'Which aircraft operates flight DX412 on 2026-09-15 and how many seats does it have?' },
  { label: 'BLR Reserves (Sep 15)', query: 'Who is on reserve at BLR on 2026-09-15, and what are their on-call windows?' },
  { label: 'C-1042 7d Duty & Headroom', query: 'How many duty hours has C-1042 accrued in the 7 days ending 2026-09-14, and what is the remaining headroom?' },
  { label: 'P-2291 Uncrewed Legs', query: 'Captain C-1042 is a no-show for pairing P-2291. Which flights are immediately uncrewed and which later days stay at risk?' },
  { label: 'Who Can Cover P-2291', query: 'Who can legally cover pairing P-2291 for Captain C-1042?' },
  { label: 'Most Seats at Risk', query: 'Which single flight leg has the most seats at risk if cancelled, and why?' },
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
          className="shrink-0 rounded-full text-xs font-medium"
        >
          {prompt.label}
        </Button>
      ))}
    </div>
  )
}
