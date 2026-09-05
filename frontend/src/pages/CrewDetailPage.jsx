import { useParams, useSearchParams } from 'react-router-dom'
import { BackLink, PageShell, StatusPanel } from '@/components/layout/PageShell'
import { CrewDetail } from '@/components/crew/CrewDetail'
import { useCrew } from '@/hooks/usePairings'

export function CrewDetailPage() {
  const { crewId } = useParams()
  const [params] = useSearchParams()
  const { data: crew, isPending, isError, error } = useCrew(crewId)
  const fromPairing = params.get('pairing')

  return (
    <PageShell>
      <BackLink to={fromPairing ? `/pairings/${fromPairing}` : '/crew'}>
        {fromPairing ? `Pairing ${fromPairing}` : 'Crew'}
      </BackLink>
      {isPending && <StatusPanel>Loading {crewId}…</StatusPanel>}
      {isError && <StatusPanel tone="error">{error.message}</StatusPanel>}
      {crew && <CrewDetail crew={crew} />}
    </PageShell>
  )
}
