import { useState } from 'react'

import { api } from '../api/client'
import { useDifficulties, useGenerated } from '../api/hooks'
import type { SourceDTO } from '../api/types'

type Sort = 'difficulty' | 'newest'

/** The test bank of one source: all generated images, filterable + sortable by
 * recognition-difficulty, with per-image download and download-all (respecting the filter). */
export function SourceOutputs({ source, onBack }: { source: SourceDTO; onBack: () => void }) {
  const [filter, setFilter] = useState<number | null>(null)
  const [sort, setSort] = useState<Sort>('difficulty')
  const { data: levels = [] } = useDifficulties(source.id)
  const { data: gens = [], isLoading } = useGenerated(source.id, filter ?? undefined)

  const sorted = [...gens].sort((a, b) =>
    sort === 'difficulty' ? a.difficulty - b.difficulty || a.id - b.id : b.id - a.id,
  )

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <button className="btn-ghost" onClick={onBack}>
          → חזרה לחנות
        </button>
        <div className="truncate text-sm">
          <span className="font-bold">#{source.id}</span> · {source.filename}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-bold">מאגר בדיקות ({sorted.length})</h2>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1.5">
            <span className="field-label">דרגה</span>
            <select
              className="input w-32"
              value={filter ?? ''}
              onChange={(e) => setFilter(e.target.value === '' ? null : Number(e.target.value))}
            >
              <option value="">כל הדרגות</option>
              {levels.map((d) => (
                <option key={d} value={d}>
                  דרגה {d}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-1.5">
            <span className="field-label">מיון</span>
            <select
              className="input w-32"
              value={sort}
              onChange={(e) => setSort(e.target.value as Sort)}
            >
              <option value="difficulty">לפי דרגה</option>
              <option value="newest">החדשים תחילה</option>
            </select>
          </label>
          {sorted.length > 0 && (
            <a className="btn-primary" href={api.sourceZipUrl(source.id, filter ?? undefined)}>
              ⬇️ הורד {filter != null ? `דרגה ${filter}` : 'הכל'} (zip)
            </a>
          )}
        </div>
      </div>

      {isLoading && <div className="field-label">טוען…</div>}
      {!isLoading && sorted.length === 0 && (
        <div className="card px-4 py-8 text-center">
          <p className="field-label">אין בדיקות שמורות{filter != null ? ` בדרגה ${filter}` : ''}.</p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {sorted.map((g) => {
          const src = api.archivedImageUrl(g.id)
          return (
            <figure key={g.id} className="card relative overflow-hidden">
              <span className="absolute end-2 top-2 rounded-md bg-black/60 px-2 py-0.5 text-xs font-bold text-white">
                דרגה {g.difficulty}
              </span>
              <img src={src} alt={`בדיקה ${g.variant_index + 1}`} className="w-full" />
              <figcaption className="flex items-center justify-between px-3 py-2">
                <span className="text-sm">בדיקה #{g.variant_index + 1}</span>
                <a className="text-sm text-accent hover:underline" href={src} download>
                  הורד
                </a>
              </figcaption>
            </figure>
          )
        })}
      </div>
    </div>
  )
}
