import { useState } from 'react'
import { Search, Send } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function ChatComposer({ onSend, disabled = false }) {
  const [value, setValue] = useState('')

  const submit = () => {
    if (!value.trim() || disabled) return
    onSend(value)
    setValue('')
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
      className="flex items-center gap-2.5 border-t border-slate-100 bg-slate-50/60 px-4 py-3"
    >
      <label className="relative flex h-10 flex-1 items-center rounded-xl bg-white ring-1 ring-slate-200 transition-shadow focus-within:ring-2 focus-within:ring-emerald-500 hover:ring-emerald-300">
        <Search className="pointer-events-none absolute left-3 h-4 w-4 text-slate-400" />
        <input
          type="text"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              submit()
            }
          }}
          placeholder="Ask an operational lookup (e.g. 'Who is on reserve at BLR on Sep 15?')…"
          disabled={disabled}
          className="h-full w-full bg-transparent pl-9 pr-3 text-sm text-slate-700 outline-none placeholder:text-slate-400 disabled:opacity-60"
        />
      </label>
      <Button type="submit" disabled={!value.trim() || disabled} className="h-10 shrink-0 rounded-xl bg-emerald-600 px-4 hover:bg-emerald-700">
        Send query
        <Send className="h-3.5 w-3.5" />
      </Button>
    </form>
  )
}
