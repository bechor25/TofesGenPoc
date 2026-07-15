import { api } from '../api/client'
import { useGenerated } from '../api/hooks'
import type { SourceDTO } from '../api/types'

/** All documents already generated from one source: view + download each or all-as-zip. */
export function SourceOutputs({ source, onBack }: { source: SourceDTO; onBack: () => void }) {
  const { data: gens = [], isLoading } = useGenerated(source.id)

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

      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">תוצרים שנוצרו ({gens.length})</h2>
        {gens.length > 0 && (
          <a className="btn-primary" href={api.sourceZipUrl(source.id)}>
            ⬇️ הורד הכל (zip)
          </a>
        )}
      </div>

      {isLoading && <div className="field-label">טוען…</div>}
      {!isLoading && gens.length === 0 && (
        <div className="card px-4 py-8 text-center">
          <p className="field-label">עדיין לא נוצרו תמונות למקור הזה.</p>
        </div>
      )}

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
    </div>
  )
}
