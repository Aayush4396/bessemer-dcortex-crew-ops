import { cn } from '@/lib/utils'

export function Card({ className, ...props }) {
  return (
    <div
      className={cn(
        'rounded-xl border border-slate-200 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04),0_8px_24px_rgba(15,23,42,0.04)]',
        className,
      )}
      {...props}
    />
  )
}

export function CardHeader({ className, ...props }) {
  return <div className={cn('flex items-center justify-between gap-3 px-4 py-3', className)} {...props} />
}

export function CardContent({ className, ...props }) {
  return <div className={cn('px-4 pb-4', className)} {...props} />
}
