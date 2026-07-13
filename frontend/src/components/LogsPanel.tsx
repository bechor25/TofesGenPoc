import { useState } from 'react'

import { useLogs } from '../api/hooks'

export function LogsPanel() {
  const [open, setOpen] = useState(false)
  const { data: lines = [] } = useLogs(open)
  return (
    <div className="card mt-8">
      <button
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-semibold"
        onClick={() => setOpen((o) => !o)}
      >
        <span>🧾 לוגים (מקצה לקצה)</span>
        <span>{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <pre
          dir="ltr"
          className="max-h-72 overflow-auto border-t border-slate-200/60 bg-slate-950/90 px-4 py-3 text-left text-xs leading-relaxed text-slate-200 dark:border-white/10"
        >
          {lines.length ? lines.join('\n') : '—'}
        </pre>
      )}
    </div>
  )
}
