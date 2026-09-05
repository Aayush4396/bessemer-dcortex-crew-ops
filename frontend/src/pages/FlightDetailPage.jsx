import { Link, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { FlightDetail } from '@/components/flights/FlightDetail'
import { useFlight } from '@/hooks/usePairings'

export function FlightDetailPage() {
  const { flightId } = useParams()
  const { data: flight, isPending, isError, error } = useFlight(flightId)
  const pairingId = flight?.pairing?.pairing_id

  return (
    <div className="h-full min-h-0 overflow-y-auto p-6">
      <Link
        to={pairingId ? `/pairings/${pairingId}` : '/'}
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800"
      >
        <ArrowLeft className="h-4 w-4" />
        {pairingId ? `Pairing ${pairingId}` : 'Pairings'}
      </Link>

      {isPending && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-10 text-center text-sm text-slate-500">
          Loading {flightId}…
        </div>
      )}

      {isError && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-6 text-sm text-rose-700">
          {error.message}
        </div>
      )}

      {flight && <FlightDetail flight={flight} />}
    </div>
  )
}
