import { Avatar } from '@/components/ui/avatar'

export function AssignedRoster({ roster }) {
  if (!roster) return null

  const hasRisk = roster.highlighted.length > 0

  return (
    <div className="min-w-[220px] border-l border-slate-100 pl-4">
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
        Assigned Roster
      </p>

      {hasRisk ? (
        <div className="space-y-2.5">
          {roster.highlighted.map((member) => (
            <div key={member.crew_id} className="flex items-start gap-2">
              <Avatar initials={member.initials} tone={member.risk_level} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-sm font-semibold text-slate-800">{member.name}</p>
                  <span
                    className={
                      member.risk_level === 'critical'
                        ? 'text-xs font-semibold text-rose-600'
                        : member.risk_score >= 0.3
                          ? 'text-xs font-semibold text-amber-600'
                          : 'text-xs font-semibold text-slate-500'
                    }
                  >
                    {member.risk_score.toFixed(2)}
                  </span>
                </div>
                <p className="text-[11px] text-slate-500">{member.role}</p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <div className="flex -space-x-1.5">
            {roster.captain_initials && <Avatar initials={roster.captain_initials} tone="low" />}
            {roster.collapsed_initials.slice(0, 2).map((initials) => (
              <Avatar key={initials} initials={initials} />
            ))}
            {roster.collapsed_count > 2 && (
              <Avatar initials={`+${roster.collapsed_count - 2}`} />
            )}
          </div>
          <p className="text-xs text-slate-600">{roster.summary}</p>
        </div>
      )}

      {hasRisk && roster.collapsed_count > 0 && (
        <div className="mt-3 flex items-center gap-1.5">
          <div className="flex -space-x-1.5">
            {roster.collapsed_initials.map((initials) => (
              <Avatar key={initials} initials={initials} className="h-6 w-6 text-[9px]" />
            ))}
          </div>
          <p className="text-[11px] text-slate-500">+{roster.collapsed_count} complement</p>
        </div>
      )}
    </div>
  )
}
