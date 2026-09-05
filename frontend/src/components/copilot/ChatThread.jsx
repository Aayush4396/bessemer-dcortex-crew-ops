import { useEffect, useRef } from 'react'
import { Loader2 } from 'lucide-react'
import { Avatar } from '@/components/ui/avatar'
import { ReasoningTrail } from '@/components/copilot/ReasoningTrail'
import { cn } from '@/lib/utils'

function renderInline(text) {
  const parts = text.split(/(\*\*.*?\*\*)/g)
  return parts.map((part, idx) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={idx} className="font-semibold text-slate-900">
          {part.slice(2, -2)}
        </strong>
      )
    }
    return part
  })
}

function MarkdownTable({ rows, tableKey }) {
  if (rows.length < 2) return null
  const splitRow = (row) => row.split('|').filter((cell) => cell.trim() !== '').map((cell) => cell.trim())
  const header = splitRow(rows[0])
  const body = rows.slice(2).map(splitRow)

  return (
    <div key={tableKey} className="my-2 overflow-x-auto rounded-lg border border-slate-200">
      <table className="w-full border-collapse text-left text-xs">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50 text-slate-500">
            {header.map((cell, idx) => (
              <th key={idx} className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide">
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 text-slate-700">
          {body.map((row, rowIdx) => (
            <tr key={rowIdx} className="transition-colors hover:bg-slate-50">
              {row.map((cell, cellIdx) => (
                <td key={cellIdx} className="px-3 py-2 font-mono text-[11px]">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function formatText(text) {
  const lines = text.split('\n')
  const elements = []
  let tableRows = []

  const flushTable = (key) => {
    if (tableRows.length > 0) {
      elements.push(<MarkdownTable key={key} rows={tableRows} tableKey={key} />)
      tableRows = []
    }
  }

  lines.forEach((line, index) => {
    const trimmed = line.trim()
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      tableRows.push(trimmed)
      return
    }
    flushTable(`table-${index}`)

    if (trimmed.startsWith('###')) {
      elements.push(
        <h3 key={index} className="mt-3 mb-1 text-sm font-semibold text-slate-900">
          {trimmed.replace(/^###/, '').trim()}
        </h3>,
      )
    } else if (trimmed.startsWith('##')) {
      elements.push(
        <h2 key={index} className="mt-3 mb-1 text-sm font-semibold text-slate-900">
          {trimmed.replace(/^##/, '').trim()}
        </h2>,
      )
    } else if (/^[-*]\s/.test(trimmed)) {
      elements.push(
        <li key={index} className="ml-4 list-disc text-sm leading-relaxed">
          {renderInline(trimmed.substring(1).trim())}
        </li>,
      )
    } else if (trimmed === '') {
      elements.push(<div key={index} className="h-1.5" />)
    } else {
      elements.push(
        <p key={index} className="text-sm leading-relaxed">
          {renderInline(line)}
        </p>,
      )
    }
  })

  flushTable('table-end')
  return elements
}

export function ChatThread({ messages, isLoading }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  return (
    <div className="flex-1 space-y-5 overflow-y-auto px-4 py-5">
      {messages.map((message) => {
        const isUser = message.sender === 'user'
        return (
          <div key={message.id} className={cn('flex items-start gap-3', isUser && 'flex-row-reverse')}>
            <Avatar initials={isUser ? 'CC' : 'dC'} tone={isUser ? 'muted' : 'low'} />

            <div className={cn('max-w-3xl space-y-2', isUser && 'text-right')}>
              <div className={cn('flex items-center gap-2 text-[11px] text-slate-400', isUser && 'justify-end')}>
                <span className="font-semibold text-slate-500">
                  {isUser ? 'Crew Controller' : 'dCortex AI Advisor'}
                </span>
                <span>•</span>
                <span>{message.timestamp}</span>
              </div>

              <div
                className={cn(
                  'rounded-2xl border px-4 py-3 text-left shadow-sm',
                  isUser
                    ? 'rounded-tr-sm border-emerald-600 bg-emerald-600 text-white'
                    : message.isError
                      ? 'rounded-tl-sm border-rose-200 bg-rose-50 text-rose-700'
                      : 'rounded-tl-sm border-slate-200 bg-white text-slate-700',
                )}
              >
                {isUser ? (
                  <p className="text-sm font-medium">{message.text}</p>
                ) : (
                  <div className={cn(message.isError && '[&_strong]:text-rose-800')}>
                    {formatText(message.text)}
                  </div>
                )}
              </div>
              {!isUser && !message.isError && (
                <ReasoningTrail
                  reasoningTrace={message.reasoningTrace}
                  toolCalls={message.toolCalls}
                  toolResults={message.toolResults}
                />
              )}
            </div>
          </div>
        )
      })}

      {isLoading && (
        <div className="flex items-start gap-3">
          <Avatar initials="dC" tone="low" />
          <div className="flex items-center gap-2.5 rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 shadow-sm">
            <Loader2 className="h-4 w-4 animate-spin text-emerald-600" />
            Analyzing controller query &amp; evaluating CAR regulations via LangGraph…
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
