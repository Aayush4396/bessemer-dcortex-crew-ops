import { Card } from '@/components/ui/card'
import { ChatComposer } from '@/components/copilot/ChatComposer'
import { ChatThread } from '@/components/copilot/ChatThread'
import { QuickPrompts } from '@/components/copilot/QuickPrompts'
import SessionSidebar from '@/components/SessionSidebar'
import { useCopilotChat } from '@/hooks/useCopilotChat'

export function CopilotPage() {
  const {
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
  } = useCopilotChat()

  return (
    <div className="flex h-full min-h-0 w-full overflow-hidden">
      <SessionSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={selectSession}
        onNewSession={newSession}
        onDeleteSession={deleteSession}
        isCollapsed={isSidebarCollapsed}
        setIsCollapsed={setIsSidebarCollapsed}
        isLoadingSessions={isLoadingSessions}
      />

      <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-4 p-6 overflow-hidden">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-slate-900">Tactical Copilot</h1>
            <p className="text-sm text-slate-500">
              Multi-turn operational lookups over live schedules and rosters with SQLite persistence.
            </p>
          </div>
        </div>

        <Card className="flex min-h-0 flex-1 flex-col overflow-hidden p-0">
          <QuickPrompts onSelect={send} disabled={isLoading} />
          <ChatThread messages={messages} isLoading={isLoading} />
          <ChatComposer onSend={send} disabled={isLoading} />
        </Card>
      </div>
    </div>
  )
}
