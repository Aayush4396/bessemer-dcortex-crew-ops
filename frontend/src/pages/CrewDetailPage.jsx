import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { CrewDetail } from '@/components/crew/CrewDetail'
import { useCrew } from '@/hooks/usePairings'

export function CrewDetailPage() {
  const { crewId } = useParams()
  const [params] = useSearchParams()
  const { data: crew, isPending, isError, error } = useCrew(crewId)
  const fromPairing = params.get('pairing')

  return (
    <div className="h-full min-h-0 overflow-y-auto p-6">
      <Link
        to={fromPairing ? `/pairings/${fromPairing}` : '/crew'}
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800"
      >
        <ArrowLeft className="h-4 w-4" />
        {fromPairing ? `Pairing ${fromPairing}` : 'Crew'}
      </Link>

      {isPending && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-10 text-center text-sm text-slate-500">
          Loading {crewId}…
        </div>
      )}

      {isError && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-6 text-sm text-rose-700">
          {error.message}
        </div>
      )}

      {crew && <CrewDetail crew={crew} />}
    </div>
  )
}
