import { api } from '../api/client'
import type { DocStateDTO } from '../api/types'

export function Gallery({ doc }: { doc: DocStateDTO }) {
  const rendered = doc.variants.filter((v) => v.rendered)
  if (rendered.length === 0) return null
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-bold">תמונות שנוצרו ({rendered.length})</h3>
        <a className="btn-ghost" href={api.zipUrl(doc.doc_id)}>
          ⬇️ הורד הכל (zip)
        </a>
      </div>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {rendered.map((v) => {
          const src = api.generatedImageUrl(doc.doc_id, v.index)
          return (
            <figure key={v.index} className="card overflow-hidden">
              <img src={src} alt={`טופס ${v.index + 1}`} className="w-full" />
              <figcaption className="flex items-center justify-between px-3 py-2">
                <span className="text-sm">טופס {v.index + 1}</span>
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
