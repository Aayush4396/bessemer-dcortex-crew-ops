import { useParams } from 'react-router-dom'
import { BackLink, PageShell, StatusPanel } from '@/components/layout/PageShell'
import { FlightDetail } from '@/components/flights/FlightDetail'
import { useFlight } from '@/hooks/usePairings'

export function FlightDetailPage() {
  const { flightId } = useParams()
  const { data: flight, isPending, isError, error } = useFlight(flightId)
  const pairingId = flight?.pairing?.pairing_id

  return (
    <PageShell>
      <BackLink to={pairingId ? `/pairings/${pairingId}` : '/'}>
        {pairingId ? `Pairing ${pairingId}` : 'Pairings'}
      </BackLink>
      {isPending && <StatusPanel>Loading {flightId}…</StatusPanel>}
      {isError && <StatusPanel tone="error">{error.message}</StatusPanel>}
      {flight && <FlightDetail flight={flight} />}
    </PageShell>
  )
}
