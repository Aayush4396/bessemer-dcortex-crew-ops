import { useState } from 'react'
import { CheckCircle2, ChevronDown, Database, ListTree } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

function resultSummary(result) {
  if (Array.isArray(result)) {
    return `${result.length} record${result.length === 1 ? '' : 's'}`
  }
  if (result && typeof result === 'object') {
    return `${Object.keys(result).length} fields`
  }
  if (result == null) return 'empty'
  return '1 value'
}

function formatArgs(args) {
  if (!args || Object.keys(args).length === 0) return 'no parameters'
  return Object.entries(args)
    .filter(([, value]) => value != null && value !== '')
    .map(([key, value]) => `${key}=${typeof value === 'object' ? JSON.stringify(value) : value}`)
    .join(' · ')
}

function ToolBlock({ call, result }) {
  const [showRows, setShowRows] = useState(false)
  const payload = result?.result
  const hasPayload = payload != null

  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="font-mono text-[11px] font-semibold text-slate-800">{call.name}</p>
          <p className="mt-0.5 font-mono text-[11px] text-slate-500">{formatArgs(call.args)}</p>
        </div>
        <Badge variant="low">{resultSummary(payload)}</Badge>
      </div>
      {hasPayload && (
        <div className="mt-2">
          <button
            type="button"
            onClick={() => setShowRows((open) => !open)}
            className="text-[11px] font-medium text-emerald-700 hover:text-emerald-800"
          >
            {showRows ? 'Hide SQLite rows' : 'Show SQLite rows'}
          </button>
          {showRows && (
            <pre className="mt-2 max-h-56 overflow-auto rounded-md bg-slate-50 px-2.5 py-2 font-mono text-[10px] leading-relaxed text-slate-600">
              {JSON.stringify(payload, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}

export function ReasoningTrail({
  reasoningTrace = [],
  toolCalls = [],
  toolResults = [],
  defaultOpen = true,
}) {
  const [open, setOpen] = useState(defaultOpen)
  const hasTrail = reasoningTrace.length > 0 || toolCalls.length > 0 || toolResults.length > 0
  if (!hasTrail) return null

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-slate-50 text-left">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left hover:bg-slate-100/80"
        aria-expanded={open}
      >
        <span className="flex min-w-0 items-center gap-2">
          <ListTree className="h-3.5 w-3.5 shrink-0 text-emerald-600" />
          <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">
            Reasoning
          </span>
          <Badge variant="low" className="normal-case tracking-normal">
            <CheckCircle2 className="mr-1 h-3 w-3" />
            SQLite · no LLM math
          </Badge>
          {toolCalls.length > 0 && (
            <span className="text-[11px] text-slate-400">
              {toolCalls.length} tool call{toolCalls.length === 1 ? '' : 's'}
            </span>
          )}
        </span>
        <ChevronDown className={cn('h-4 w-4 text-slate-400 transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="space-y-3 border-t border-slate-200 px-3 py-3">
          {reasoningTrace.length > 0 && (
            <ol className="space-y-1.5">
              {reasoningTrace.map((step, index) => (
                <li key={`${index}-${step}`} className="flex gap-2 text-[12px] leading-relaxed text-slate-600">
                  <span className="mt-px w-4 shrink-0 text-right font-mono text-[10px] text-slate-400">
                    {index + 1}
                  </span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          )}

          {toolCalls.length > 0 && (
            <div className="space-y-2">
              <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                <Database className="h-3 w-3" />
                Deterministic tools
              </p>
              {toolCalls.map((call, index) => (
                <ToolBlock
                  key={call.id || `${call.name}-${index}`}
                  call={call}
                  result={toolResults[index] || toolResults.find((item) => item.tool_name === call.name)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
