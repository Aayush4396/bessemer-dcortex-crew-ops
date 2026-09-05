import { CalendarDays, Plane } from 'lucide-react'
import { cn } from '@/lib/utils'

const riskOptions = [
  { id: 'all', label: 'All', swatch: 'bg-slate-400' },
  { id: 'high', label: 'High', swatch: 'bg-rose-500' },
  { id: 'elevated', label: 'Elevated', swatch: 'bg-amber-500' },
  { id: 'low', label: 'Low', swatch: 'bg-emerald-500' },
]

export function FilterBar({ weekDays = [], date, aircraft, risk, tails = [], riskCounts = {}, onChange }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04),0_8px_24px_rgba(15,23,42,0.04)]">
      <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 bg-gradient-to-r from-slate-50/80 to-white px-4 py-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            onClick={() => onChange({ date: null })}
            className={cn(
              'h-12 rounded-xl px-3 text-xs font-semibold transition-all',
              !date
                ? 'bg-emerald-600 text-white shadow-sm shadow-emerald-600/25'
                : 'bg-white text-slate-500 ring-1 ring-slate-200 hover:bg-slate-50 hover:text-slate-800',
            )}
          >
            All week
          </button>
          {weekDays.map((day) => {
            const selected = day.date === date
            const dayNumber = day.date.slice(8, 10)
            return (
              <button
                key={day.date}
                type="button"
                onClick={() => onChange({ date: day.date })}
                className={cn(
                  'flex h-12 w-12 flex-col items-center justify-center rounded-xl transition-all',
                  selected
                    ? 'bg-emerald-600 text-white shadow-sm shadow-emerald-600/25'
                    : 'bg-white text-slate-500 ring-1 ring-slate-200 hover:bg-slate-50 hover:text-slate-800',
                )}
              >
                <span className={cn('text-[10px] font-medium uppercase', selected ? 'text-emerald-100' : 'text-slate-400')}>
                  {day.weekday}
                </span>
                <span className="text-sm font-semibold leading-none">{Number(dayNumber)}</span>
              </button>
            )
          })}
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          <label className="relative flex h-10 items-center gap-2 rounded-xl bg-white px-3 ring-1 ring-slate-200 transition-shadow hover:ring-emerald-300 focus-within:ring-2 focus-within:ring-emerald-500">
            <CalendarDays className="h-4 w-4 shrink-0 text-emerald-600" />
            <input
              type="date"
              value={date || ''}
              onChange={(event) => onChange({ date: event.target.value || null })}
              className="w-[8.75rem] bg-transparent text-sm font-medium text-slate-700 outline-none [&::-webkit-calendar-picker-indicator]:absolute [&::-webkit-calendar-picker-indicator]:inset-0 [&::-webkit-calendar-picker-indicator]:h-full [&::-webkit-calendar-picker-indicator]:w-full [&::-webkit-calendar-picker-indicator]:cursor-pointer [&::-webkit-calendar-picker-indicator]:opacity-0"
              aria-label="Filter by date"
            />
          </label>

          <div className="relative">
            <Plane className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
            <select
              value={aircraft || ''}
              onChange={(event) => onChange({ aircraft: event.target.value || null })}
              className="h-10 appearance-none rounded-xl bg-white pl-9 pr-8 text-sm font-medium text-slate-700 ring-1 ring-slate-200 outline-none transition-shadow hover:ring-emerald-300 focus:ring-2 focus:ring-emerald-500"
            >
              <option value="">All tails · {tails.length}</option>
              {tails.map((tail) => (
                <option key={tail.tail} value={tail.tail}>
                  {tail.tail} · {tail.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 px-4 py-2.5">
        <span className="mr-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
          Risk
        </span>
        {riskOptions.map((option) => {
          const selected = risk === option.id
          return (
            <button
              key={option.id}
              type="button"
              onClick={() => onChange({ risk: option.id })}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold transition-all',
                selected
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'bg-slate-100 text-slate-500 hover:bg-slate-200 hover:text-slate-800',
              )}
            >
              <span className={cn('h-1.5 w-1.5 rounded-full', option.swatch, selected && 'ring-2 ring-white/40')} />
              {option.label}
              <span className={selected ? 'text-white/70' : 'text-slate-400'}>
                {riskCounts[option.id] ?? 0}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
