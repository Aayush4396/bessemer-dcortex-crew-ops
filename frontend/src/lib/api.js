export async function fetchFlight(flightId) {
  const response = await fetch(`/api/flights/${encodeURIComponent(flightId)}`)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || 'Failed to load flight')
  }
  return response.json()
}

export async function fetchCrewList({ rank, base, risk } = {}) {
  const params = new URLSearchParams()
  if (rank) params.set('rank', rank)
  if (base) params.set('base', base)
  if (risk && risk !== 'all') params.set('risk', risk)

  const response = await fetch(`/api/crew?${params.toString()}`)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || 'Failed to load crew roster')
  }
  return response.json()
}

export async function fetchCrew(crewId) {
  const response = await fetch(`/api/crew/${encodeURIComponent(crewId)}`)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || 'Failed to load crew')
  }
  return response.json()
}

export async function fetchPairing(pairingId) {
  const response = await fetch(`/api/pairings/${encodeURIComponent(pairingId)}`)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || 'Failed to load pairing')
  }
  return response.json()
}

export async function fetchPairings({ date, aircraft, risk } = {}) {
  const params = new URLSearchParams()
  if (date) params.set('date', date)
  if (aircraft) params.set('aircraft', aircraft)
  if (risk && risk !== 'all') params.set('risk', risk)

  const response = await fetch(`/api/pairings?${params.toString()}`)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || 'Failed to load pairings workspace')
  }
  return response.json()
}

export async function fetchSessions() {
  const response = await fetch('/api/sessions')
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || 'Failed to load sessions')
  }
  return response.json()
}

export async function createSession({ sessionId, title } = {}) {
  const response = await fetch('/api/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId || undefined,
      title: title || 'New Operational Inquiry',
    }),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || 'Failed to create session')
  }
  return response.json()
}

export async function fetchSessionHistory(sessionId) {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || 'Failed to load session history')
  }
  return response.json()
}

export async function deleteSession(sessionId) {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || 'Failed to delete session')
  }
  return response.json()
}

export async function sendChatQuery(query, sessionId = 'default') {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, tier: 1, session_id: sessionId }),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Copilot request failed (HTTP ${response.status})`)
  }
  return response.json()
}

