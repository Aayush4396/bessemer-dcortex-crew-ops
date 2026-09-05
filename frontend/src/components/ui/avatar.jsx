import { cn } from '@/lib/utils'

const toneClass = {
  critical: 'border-rose-200 bg-rose-50 text-rose-700',
  elevated: 'border-amber-200 bg-amber-50 text-amber-700',
  low: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  muted: 'border-slate-200 bg-slate-100 text-slate-500',
}

export function Avatar({ initials, tone = 'muted', className }) {
  return (
    <span
      className={cn(
        'inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold',
        toneClass[tone] || toneClass.muted,
        className,
      )}
    >
      {initials}
    </span>
  )
}
