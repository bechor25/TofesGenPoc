import { useState } from 'react'

import type { DocStateDTO } from '../api/types'

interface Props {
  doc: DocStateDTO
  busy?: boolean
  onRender: (indices: number[], difficulty: number) => void
}

export function VariantsTable({ doc, busy = false, onRender }: Props) {
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [difficulty, setDifficulty] = useState(1)

  const toggle = (i: number) =>
    setSelected((s) => {
      const next = new Set(s)
      if (next.has(i)) next.delete(i)
      else next.add(i)
      return next
    })

  const selectedList = [...selected].sort((a, b) => a - b)

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-base font-bold">יצירת בדיקות — בחר דרגת קושי והפק תמונות</h3>
        <p className="field-label mt-1">
          כל תמונה = קריאה יקרה ל-gpt-image-2. «דרגת קושי» 1-10 קובעת עד כמה התמונה תיראה
          מצולמת בשטח (זווית/תאורה/רקע) — 1 = העתק נקי, 10 = קשה מאוד לזיהוי. הדרגה נשמרת
          כציון על כל בדיקה.
        </p>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-right text-slate-500 dark:text-slate-400">
              <th className="p-2 font-medium">יצירת טופס</th>
              <th className="p-2 font-medium">#</th>
              <th className="p-2 font-medium">סטטוס</th>
              {doc.columns.map((c) => (
                <th key={c.id} className="whitespace-nowrap p-2 font-medium">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {doc.variants.map((v) => (
              <tr key={v.index} className="border-t border-slate-200/60 dark:border-white/10">
                <td className="p-2 text-center">
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-accent"
                    data-testid={`render-${v.index}`}
                    checked={selected.has(v.index)}
                    onChange={() => toggle(v.index)}
                  />
                </td>
                <td className="p-2 tabular-nums">{v.index + 1}</td>
                <td className="whitespace-nowrap p-2">
                  {v.rendered ? (
                    <span className="text-emerald-600 dark:text-emerald-300">✓ נוצר</span>
                  ) : (
                    <span className="text-slate-400">ממתין</span>
                  )}
                </td>
                {doc.columns.map((c) => (
                  <td key={c.id} className="whitespace-nowrap p-2">
                    {v.values[c.id] ?? '—'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2">
          <span className="field-label">דרגת קושי</span>
          <input
            type="range"
            min={1}
            max={10}
            value={difficulty}
            data-testid="difficulty"
            onChange={(e) => setDifficulty(Number(e.target.value))}
            className="accent-accent"
          />
          <span className="w-6 text-center font-bold text-accent">{difficulty}</span>
        </label>
        <button
          className="btn-primary"
          disabled={busy || selectedList.length === 0}
          onClick={() => onRender(selectedList, difficulty)}
        >
          🖼️ רנדר נבחרים ({selectedList.length}) · דרגה {difficulty}
        </button>
        <button
          className="btn-ghost"
          disabled={busy || doc.variants.length === 0}
          onClick={() => onRender(doc.variants.map((v) => v.index), difficulty)}
        >
          🖼️ רנדר הכל ({doc.variants.length}) · דרגה {difficulty}
        </button>
      </div>
    </div>
  )
}
