import { cva } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-semibold tracking-wide uppercase',
  {
    variants: {
      variant: {
        default: 'border-slate-200 bg-slate-100 text-slate-600',
        critical: 'border-rose-200 bg-rose-50 text-rose-700',
        elevated: 'border-amber-200 bg-amber-50 text-amber-700',
        low: 'border-emerald-200 bg-emerald-50 text-emerald-700',
        ontime: 'border-emerald-200 bg-emerald-50 text-emerald-700',
        scheduled: 'border-slate-200 bg-slate-50 text-slate-500',
        tight: 'border-amber-200 bg-amber-50 text-amber-700',
        enroute: 'border-sky-200 bg-sky-50 text-sky-700',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
)

export function Badge({ className, variant, ...props }) {
  return <span className={cn(badgeVariants({ variant, className }))} {...props} />
}
