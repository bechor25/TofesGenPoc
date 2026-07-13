import { useState } from 'react'

import { api } from '../api/client'
import { useGenerated, useSources } from '../api/hooks'

export function ArchiveView() {
  const { data: sources = [], isLoading } = useSources()
  const [sel, setSel] = useState<number | null>(null)
  const { data: gens = [] } = useGenerated(sel)

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-bold">מאגר — קבצי מקור וכל מה שנוצר מהם</h2>
        <p className="field-label mt-1">
          כל קובץ מקור מקבל מספר יוניקי; תחתיו כל התמונות שנוצרו ממנו. לחץ על מקור כדי לראות
          ולהוריד את התוצרים.
        </p>
      </div>

      {isLoading && <div className="field-label">טוען…</div>}
      {!isLoading && sources.length === 0 && (
        <div className="card px-4 py-6 text-center">
          <p className="field-label">
            עדיין לא נשמרו קבצים. עבד מסמך והפק תמונה — הוא ייכנס למאגר עם מספר יוניקי.
            (דורש DATABASE_URL / הרצה ב-docker-compose.)
          </p>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {sources.map((s) => (
          <button
            key={s.id}
            onClick={() => setSel(s.id)}
            className={
              'card p-4 text-right transition hover:border-accent ' +
              (sel === s.id ? 'border-accent ring-2 ring-accent/30' : '')
            }
          >
            <div className="flex items-center justify-between">
              <span className="font-semibold">#{s.id} · {s.filename}</span>
              <span className="field-label">{s.n_generated} תוצרים</span>
            </div>
            {s.doc_summary && (
              <p className="field-label mt-1 line-clamp-2">{s.doc_summary}</p>
            )}
          </button>
        ))}
      </div>

      {sel != null && (
        <div className="space-y-3">
          <h3 className="text-base font-bold">תוצרים של מקור #{sel}</h3>
          {gens.length === 0 ? (
            <p className="field-label">אין עדיין תמונות שנוצרו (דאטה בלבד).</p>
          ) : (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
              {gens.map((g) => {
                const src = api.archivedImageUrl(g.id)
                return (
                  <figure key={g.id} className="card overflow-hidden">
                    <img src={src} alt={`וריאציה ${g.variant_index + 1}`} className="w-full" />
                    <figcaption className="flex items-center justify-between px-3 py-2">
                      <span className="text-sm">וריאציה {g.variant_index + 1}</span>
                      <a className="text-sm text-accent hover:underline" href={src} download>
                        הורד
                      </a>
                    </figcaption>
                  </figure>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
