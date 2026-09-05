import { useCallback, useEffect, useRef, useState } from 'react'
import {
  createSession as apiCreateSession,
  deleteSession as apiDeleteSession,
  fetchSessionHistory,
  fetchSessions,
  sendChatQuery,
} from '@/lib/api'

function getTimestamp(isoString) {
  if (isoString) {
    try {
      const d = new Date(isoString.replace(' ', 'T'))
      if (!isNaN(d.getTime())) {
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
      return isoString.slice(11, 16)
    } catch {
      return isoString.slice(11, 16)
    }
  }
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const welcomeMessage = {
  id: 'welcome',
  sender: 'assistant',
  text: `**Welcome to the dCortex Crew Operations Control Desk.**\n\nI am your AI Operations Advisor powered by **LangGraph** and **Sarvam-105B**, operating over live flight schedules, crew rosters, and DGCA CAR Section 7 regulations.\n\nAsk me any operational lookup question or click one of the quick inquiry chips below.`,
  timestamp: getTimestamp(),
  reasoningTrace: [
    'Initialized dCortex Crew Operations Control Desk',
    'Connected to SQLite operational database (crew_ops.db)',
  ],
  toolCalls: [],
  toolResults: [],
}

export function useCopilotChat() {
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(() => {
    return localStorage.getItem('dcortex_active_session_id') || 'default'
  })
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  const [isLoadingSessions, setIsLoadingSessions] = useState(false)

  const [messages, setMessages] = useState([welcomeMessage])
  const [isLoading, setIsLoading] = useState(false)
  const activeSessionRef = useRef(activeSessionId)

  useEffect(() => {
    activeSessionRef.current = activeSessionId
  }, [activeSessionId])

  // Load message history for a given session
  const selectSession = useCallback(async (sessionId) => {
    if (!sessionId) return
    setActiveSessionId(sessionId)
    localStorage.setItem('dcortex_active_session_id', sessionId)

    try {
      const data = await fetchSessionHistory(sessionId)
      if (data?.messages && data.messages.length > 0) {
        const mapped = data.messages.map((m, idx) => ({
          id: m.message_id || `msg-${idx}`,
          sender: m.sender,
          text: m.content,
          timestamp: getTimestamp(m.created_at),
          reasoningTrace: m.reasoning_trace ?? [],
          toolCalls: m.tool_calls ?? [],
          toolResults: m.tool_results ?? [],
        }))
        setMessages(mapped)
      } else {
        setMessages([welcomeMessage])
      }
    } catch (err) {
      console.warn(`Failed to load history for session ${sessionId}:`, err)
      setMessages([welcomeMessage])
    }
  }, [])

  // Refresh session list from SQLite
  const refreshSessions = useCallback(async (selectId = null) => {
    try {
      setIsLoadingSessions(true)
      const data = await fetchSessions()
      const list = Array.isArray(data) ? data : []
      setSessions(list)

      if (selectId) {
        await selectSession(selectId)
      } else if (list.length > 0) {
        const currentActive = activeSessionRef.current
        const exists = list.some((s) => s.session_id === currentActive)
        if (!exists) {
          await selectSession(list[0].session_id)
        }
      }
      return list
    } catch (err) {
      console.warn('Failed to fetch sessions:', err)
      return []
    } finally {
      setIsLoadingSessions(false)
    }
  }, [selectSession])

  // Initial load
  useEffect(() => {
    const init = async () => {
      const list = await refreshSessions()
      const stored = localStorage.getItem('dcortex_active_session_id')
      if (stored && list.some((s) => s.session_id === stored)) {
        await selectSession(stored)
      } else if (list.length > 0) {
        await selectSession(list[0].session_id)
      }
    }
    init()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Create a brand new session
  const newSession = useCallback(async () => {
    const newId = `sess_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`
    try {
      const created = await apiCreateSession({
        sessionId: newId,
        title: 'New Operational Inquiry',
      })
      setSessions((prev) => [created, ...prev.filter((s) => s.session_id !== newId)])
      setActiveSessionId(newId)
      localStorage.setItem('dcortex_active_session_id', newId)
      setMessages([welcomeMessage])
    } catch (err) {
      console.warn('Failed to create session on backend, using local session ID:', err)
      setActiveSessionId(newId)
      localStorage.setItem('dcortex_active_session_id', newId)
      setMessages([welcomeMessage])
    }
  }, [])

  // Delete a session
  const deleteSession = useCallback(
    async (sessionId, e) => {
      if (e) e.stopPropagation()
      try {
        await apiDeleteSession(sessionId)
      } catch (err) {
        console.warn(`Failed to delete session ${sessionId}:`, err)
      }

      setSessions((prev) => {
        const updated = prev.filter((s) => s.session_id !== sessionId)
        if (sessionId === activeSessionRef.current) {
          if (updated.length > 0) {
            selectSession(updated[0].session_id)
          } else {
            newSession()
          }
        }
        return updated
      })
    },
    [selectSession, newSession],
  )

  // Send a chat query
  const send = useCallback(
    async (query) => {
      const text = query?.trim()
      if (!text || isLoading) return

      const currentSid = activeSessionRef.current || 'default'

      setMessages((prev) => [
        ...prev,
        { id: Date.now().toString(), sender: 'user', text, timestamp: getTimestamp() },
      ])
      setIsLoading(true)

      try {
        const data = await sendChatQuery(text, currentSid)
        setMessages((prev) => [
          ...prev,
          {
            id: `${Date.now()}-assistant`,
            sender: 'assistant',
            text: data.response,
            timestamp: getTimestamp(),
            reasoningTrace: data.reasoning_trace ?? [],
            toolCalls: data.tool_calls ?? [],
            toolResults: data.tool_results ?? [],
          },
        ])
        // Silently refresh sessions list to reflect new title/timestamps/message count
        fetchSessions().then((res) => {
          if (Array.isArray(res)) setSessions(res)
        }).catch(() => {})
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          {
            id: `${Date.now()}-error`,
            sender: 'assistant',
            isError: true,
            text: `**Operational connection error:** unable to reach the backend agent. ${err.message}`,
            timestamp: getTimestamp(),
          },
        ])
      } finally {
        setIsLoading(false)
      }
    },
    [isLoading],
  )

  return {
    messages,
    isLoading,
    send,
    sessions,
    activeSessionId,
    selectSession,
    newSession,
    deleteSession,
    isSidebarCollapsed,
    setIsSidebarCollapsed,
    isLoadingSessions,
    refreshSessions,
  }
}
