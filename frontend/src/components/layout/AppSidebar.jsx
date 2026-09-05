import { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { Bot, ChevronLeft, ChevronRight, Flame, Plane, Sparkles, Users } from 'lucide-react'
import { cn } from '@/lib/utils'

const items = [
  { to: '/', label: 'Pairings Control', icon: Plane, badgeKey: 'pairings' },
  { to: '/crew', label: 'Crew Management', icon: Users, badgeKey: 'crew' },
  { to: '/copilot', label: 'Tactical Copilot', icon: Bot },
  { to: '/simulator', label: 'Disruption Simulator', icon: Flame },
  { to: '/recovery', label: 'Recovery Optimizer', icon: Sparkles },
]

export function AppSidebar({ pairingCount = 0, crewCount = 0 }) {
  const [collapsed, setCollapsed] = useState(false)
  const location = useLocation()
  const pairingsActive =
    location.pathname === '/' ||
    location.pathname.startsWith('/pairings/') ||
    location.pathname.startsWith('/flights/')
  const crewActive = location.pathname.startsWith('/crew')
  const counts = { pairings: pairingCount, crew: crewCount }

  return (
    <aside
      className={cn(
        'relative flex shrink-0 flex-col border-r border-slate-200 bg-[#f7f8fa] transition-[width] duration-200',
        collapsed ? 'w-[68px]' : 'w-64',
      )}
    >
      <button
        type="button"
        onClick={() => setCollapsed((open) => !open)}
        className="absolute -right-3 top-7 z-20 flex h-6 w-6 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-sm hover:border-slate-300 hover:text-slate-800 hover:shadow"
        aria-expanded={!collapsed}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
      </button>

      <div className={cn('border-b border-slate-200', collapsed ? 'px-2 py-5' : 'px-5 py-5')}>
        <div className={cn('flex items-center gap-2', collapsed && 'justify-center')}>
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-600 text-sm font-bold text-white">
            dC
          </div>
          {!collapsed && (
            <div>
              <p className="text-sm font-semibold tracking-tight text-slate-900">dCortex</p>
              <p className="text-[11px] text-slate-500">Air Operations</p>
            </div>
          )}
        </div>
      </div>

      <nav className={cn('space-y-1 py-4', collapsed ? 'px-2' : 'px-3')}>
        {items.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              title={item.label}
              aria-label={item.label}
              className={({ isActive }) =>
                cn(
                  'flex items-center rounded-lg py-2 text-sm',
                  collapsed ? 'justify-center px-0' : 'justify-between px-3',
                  (item.to === '/' ? pairingsActive : item.to === '/crew' ? crewActive : isActive)
                    ? 'bg-emerald-50 font-semibold text-emerald-600'
                    : 'text-slate-700 hover:bg-slate-100',
                )
              }
            >
              <span className={cn('flex items-center', collapsed ? 'relative' : 'gap-2.5')}>
                <Icon className="h-4 w-4" />
                {!collapsed && item.label}
                {collapsed && item.badgeKey && counts[item.badgeKey] > 0 && (
                  <span className="absolute -right-2 -top-2 rounded-full bg-emerald-100 px-1 text-[9px] font-semibold text-emerald-700">
                    {counts[item.badgeKey]}
                  </span>
                )}
              </span>
              {!collapsed && item.badgeKey && counts[item.badgeKey] > 0 && (
                <span className="rounded-full bg-emerald-100 px-1.5 text-[10px] font-semibold text-emerald-700">
                  {counts[item.badgeKey]}
                </span>
              )}
            </NavLink>
          )
        })}
      </nav>
    </aside>
  )
}
