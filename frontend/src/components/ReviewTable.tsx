import { useState } from 'react'

import { FIELD_TYPES, type DetectedDTO, type ReviewedValue } from '../api/types'

interface Row {
  label: string
  value: string
  field_type: string
  is_personal: boolean
  slot: string
}

interface Props {
  initial: DetectedDTO[]
  busy?: boolean
  onSubmit: (values: ReviewedValue[], n: number) => void
}

const toRows = (d: DetectedDTO[]): Row[] =>
  d.map((x) => ({
    label: x.label,
    value: x.value,
    field_type: x.field_type,
    is_personal: x.is_personal,
    slot: x.slot ?? '',
  }))

export function ReviewTable({ initial, busy = false, onSubmit }: Props) {
  const [rows, setRows] = useState<Row[]>(() => toRows(initial))
  const [n, setN] = useState(10)

  const update = (i: number, patch: Partial<Row>) =>
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)))
  const addRow = () =>
    setRows((rs) => [
      ...rs,
      { label: '', value: '', field_type: 'free_text', is_personal: true, slot: '' },
    ])
  const removeRow = (i: number) =>
    setRows((rs) => rs.filter((_, idx) => idx !== i))

  const submit = () => {
    const values: ReviewedValue[] = rows
      .filter((r) => r.label.trim() || r.value.trim())
      .map((r) => ({
        label: r.label.trim(),
        value: r.value.trim(),
        field_type: r.field_type,
        is_personal: r.is_personal,
        slot: r.slot.trim() ? r.slot.trim() : null,
      }))
    onSubmit(values, n)
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-base font-bold">ערכים שזוהו — אשר, ערוך או הוסף</h3>
        <p className="field-label mt-1">
          סמן «אישי?» לכל ערך שיש להחליף. «קישור» = ערכים עם אותו קישור מקבלים ערך זהה
          (אותה ישות בטופס). הוסף שורות לערכים שלא זוהו.
        </p>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-right text-slate-500 dark:text-slate-400">
              <th className="p-2 font-medium">תווית</th>
              <th className="p-2 font-medium">ערך</th>
              <th className="p-2 font-medium">סוג</th>
              <th className="p-2 font-medium">אישי?</th>
              <th className="p-2 font-medium">קישור</th>
              <th className="p-2" />
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-slate-200/60 dark:border-white/10">
                <td className="p-1.5">
                  <input
                    className="input"
                    data-testid={`label-${i}`}
                    value={r.label}
                    onChange={(e) => update(i, { label: e.target.value })}
                  />
                </td>
                <td className="p-1.5">
                  <input
                    className="input"
                    data-testid={`value-${i}`}
                    value={r.value}
                    onChange={(e) => update(i, { value: e.target.value })}
                  />
                </td>
                <td className="p-1.5">
                  <select
                    className="input"
                    data-testid={`type-${i}`}
                    value={r.field_type}
                    onChange={(e) => update(i, { field_type: e.target.value })}
                  >
                    {FIELD_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="p-1.5 text-center">
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-accent"
                    data-testid={`personal-${i}`}
                    checked={r.is_personal}
                    onChange={(e) => update(i, { is_personal: e.target.checked })}
                  />
                </td>
                <td className="p-1.5">
                  <input
                    className="input"
                    data-testid={`slot-${i}`}
                    value={r.slot}
                    onChange={(e) => update(i, { slot: e.target.value })}
                  />
                </td>
                <td className="p-1.5">
                  <button
                    className="text-slate-400 hover:text-rose-500"
                    aria-label="מחק שורה"
                    onClick={() => removeRow(i)}
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button className="btn-ghost" onClick={addRow}>
          ＋ הוסף שורה
        </button>
        <label className="flex items-center gap-2">
          <span className="field-label">כמה וריאציות דאטה?</span>
          <input
            type="number"
            min={1}
            max={50}
            className="input w-20"
            value={n}
            onChange={(e) => setN(Math.max(1, Math.min(50, Number(e.target.value) || 1)))}
          />
        </label>
        <button className="btn-primary" onClick={submit} disabled={busy}>
          צור דאטה (ערכים בלבד)
        </button>
      </div>
      <p className="field-label">
        שלב זה מייצר רק את הדאטה המאומת. יצירת התמונה היקרה מתבצעת אחר כך, לפי דרישה, לכל
        וריאציה שתבחר.
      </p>
    </div>
  )
}
