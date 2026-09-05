import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { fetchCrew, fetchCrewList, fetchFlight, fetchPairing, fetchPairings } from '@/lib/api'

export function usePairings({ date, aircraft, risk }) {
  return useQuery({
    queryKey: ['pairings', date, aircraft, risk],
    queryFn: () => fetchPairings({ date, aircraft, risk }),
    placeholderData: keepPreviousData,
  })
}

export function usePairing(pairingId) {
  return useQuery({
    queryKey: ['pairing', pairingId],
    queryFn: () => fetchPairing(pairingId),
    enabled: Boolean(pairingId),
    retry: false,
  })
}

export function useFlight(flightId) {
  return useQuery({
    queryKey: ['flight', flightId],
    queryFn: () => fetchFlight(flightId),
    enabled: Boolean(flightId),
    retry: false,
  })
}

export function useCrew(crewId) {
  return useQuery({
    queryKey: ['crew', crewId],
    queryFn: () => fetchCrew(crewId),
    enabled: Boolean(crewId),
    retry: false,
  })
}

export function useCrewList({ rank, base, risk }) {
  return useQuery({
    queryKey: ['crew-list', rank, base, risk],
    queryFn: () => fetchCrewList({ rank, base, risk }),
    placeholderData: keepPreviousData,
  })
}
