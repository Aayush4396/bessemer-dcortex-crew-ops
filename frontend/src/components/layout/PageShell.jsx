import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { cn } from '@/lib/utils'

export function PageShell({ children, className }) {
  return (
    <div className={cn('h-full min-h-0 overflow-y-auto bg-[#eef1f5] p-6 text-slate-800', className)}>
      {children}
    </div>
  )
}

export function PageHeader({ title, subtitle }) {
  return (
    <div>
      <h1 className="text-lg font-semibold text-slate-900">{title}</h1>
      {subtitle ? <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p> : null}
    </div>
  )
}

export function BackLink({ to, children }) {
  return (
    <Link
      to={to}
      className="mb-4 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-emerald-700"
    >
      <ArrowLeft className="h-4 w-4" />
      {children}
    </Link>
  )
}

export function StatusPanel({ tone = 'muted', children }) {
  return (
    <div
      className={cn(
        'rounded-xl border px-4 py-10 text-center text-sm',
        tone === 'error'
          ? 'border-rose-200 bg-rose-50 text-rose-700'
          : 'border-dashed border-slate-200 bg-white text-slate-500',
      )}
    >
      {children}
    </div>
  )
}
