import { Link } from 'react-router-dom'
import { Avatar } from '@/components/ui/avatar'
import { cn } from '@/lib/utils'

export function CrewRow({ member, pairingId }) {
  const to = pairingId ? `/crew/${member.crew_id}?pairing=${pairingId}` : `/crew/${member.crew_id}`

  return (
    <Link
      to={to}
      className="flex items-center gap-2.5 rounded-lg px-2 py-2 hover:bg-slate-50"
    >
      <Avatar initials={member.initials} tone={member.risk_level} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-800">{member.name}</p>
        <p className="truncate text-[11px] text-slate-500">
          {member.crew_id} · {member.role || member.rank}
        </p>
      </div>
      <span
        className={cn(
          'text-xs font-semibold',
          member.risk_level === 'critical'
            ? 'text-rose-600'
            : member.risk_score >= 0.3
              ? 'text-amber-600'
              : 'text-slate-500',
        )}
      >
        {member.risk_score.toFixed(2)}
      </span>
    </Link>
  )
}
