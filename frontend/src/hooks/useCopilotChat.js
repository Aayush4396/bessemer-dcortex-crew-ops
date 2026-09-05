import { useCallback, useState } from 'react'
import { sendChatQuery } from '@/lib/api'

function timestamp() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const welcomeMessage = {
  id: 'welcome',
  sender: 'assistant',
  text: `**Welcome to the dCortex Crew Operations Control Desk.**\n\nI am your AI Operations Advisor powered by **LangGraph** and **Sarvam-105B**, operating over live flight schedules, crew rosters, and DGCA CAR Section 7 regulations.\n\nAsk me any operational lookup question or click one of the quick inquiry chips below.`,
  timestamp: timestamp(),
}

export function useCopilotChat() {
  const [messages, setMessages] = useState([welcomeMessage])
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId] = useState(() => `web-${crypto.randomUUID()}`)

  const send = useCallback(
    async (query) => {
      const text = query?.trim()
      if (!text || isLoading) return

      setMessages((prev) => [
        ...prev,
        { id: Date.now().toString(), sender: 'user', text, timestamp: timestamp() },
      ])
      setIsLoading(true)

      try {
        const data = await sendChatQuery(text, sessionId)
        setMessages((prev) => [
          ...prev,
          {
            id: `${Date.now()}-assistant`,
            sender: 'assistant',
            text: data.response,
            timestamp: timestamp(),
            reasoningTrace: data.reasoning_trace ?? [],
            toolCalls: data.tool_calls ?? [],
            toolResults: data.tool_results ?? [],
          },
        ])
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          {
            id: `${Date.now()}-error`,
            sender: 'assistant',
            isError: true,
            text: `**Operational connection error:** unable to reach the backend agent. ${err.message}`,
            timestamp: timestamp(),
          },
        ])
      } finally {
        setIsLoading(false)
      }
    },
    [isLoading, sessionId],
  )

  return { messages, isLoading, send }
}
