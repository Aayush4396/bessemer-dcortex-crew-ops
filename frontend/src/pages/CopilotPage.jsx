import { Card } from '@/components/ui/card'
import { ChatComposer } from '@/components/copilot/ChatComposer'
import { ChatThread } from '@/components/copilot/ChatThread'
import { QuickPrompts } from '@/components/copilot/QuickPrompts'
import { useCopilotChat } from '@/hooks/useCopilotChat'

export function CopilotPage() {
  const { messages, isLoading, send } = useCopilotChat()

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 p-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">Tactical Copilot</h1>
        <p className="text-sm text-slate-500">
          Lookups over live schedules and rosters. Every answer shows the SQLite tools behind it.
        </p>
      </div>

      <Card className="flex min-h-0 flex-1 flex-col overflow-hidden p-0">
        <QuickPrompts onSelect={send} disabled={isLoading} />
        <ChatThread messages={messages} isLoading={isLoading} />
        <ChatComposer onSend={send} disabled={isLoading} />
      </Card>
    </div>
  )
}
