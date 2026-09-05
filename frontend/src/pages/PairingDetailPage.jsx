import { useParams } from 'react-router-dom'
import { BackLink, PageShell, StatusPanel } from '@/components/layout/PageShell'
import { PairingDetail } from '@/components/pairings/PairingDetail'
import { usePairing } from '@/hooks/usePairings'

export function PairingDetailPage() {
  const { pairingId } = useParams()
  const { data: pairing, isPending, isError, error } = usePairing(pairingId)

  return (
    <PageShell>
      <BackLink to="/">Pairings</BackLink>
      {isPending && <StatusPanel>Loading {pairingId}…</StatusPanel>}
      {isError && <StatusPanel tone="error">{error.message}</StatusPanel>}
      {pairing && <PairingDetail pairing={pairing} />}
    </PageShell>
  )
}
