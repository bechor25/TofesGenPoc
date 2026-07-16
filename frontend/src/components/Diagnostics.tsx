import { useState } from 'react'

import type { DiagnosticsRowDTO } from '../api/types'

export function Diagnostics({ rows }: { rows: DiagnosticsRowDTO[] }) {
  const [open, setOpen] = useState(false)
  if (rows.length === 0) return null
  return (
    <div className="card">
      <button
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-semibold"
        onClick={() => setOpen((o) => !o)}
      >
        <span>🔍 אבחון — מה קרה לכל שדה (מקצה לקצה)</span>
        <span>{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="overflow-x-auto border-t border-slate-200/60 dark:border-white/10">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-right text-slate-500 dark:text-slate-400">
                <th className="p-2 font-medium">תווית</th>
                <th className="p-2 font-medium">סוג</th>
                <th className="p-2 font-medium">להחלפה?</th>
                <th className="p-2 font-medium">קישור</th>
                <th className="p-2 font-medium">ערך מקורי</th>
                <th className="p-2 font-medium">ערך שנוצר</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-t border-slate-200/60 dark:border-white/10">
                  <td className="p-2">{r.label}</td>
                  <td className="whitespace-nowrap p-2">{r.field_type}</td>
                  <td className="p-2">{r.is_personal ? 'כן' : 'לא'}</td>
                  <td className="p-2">{r.slot ?? '—'}</td>
                  <td className="whitespace-nowrap p-2">{r.original}</td>
                  <td className="whitespace-nowrap p-2">{r.generated}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
