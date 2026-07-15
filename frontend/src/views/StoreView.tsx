import { useState } from 'react'

import { useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import { useSources } from '../api/hooks'
import type { SourceDTO } from '../api/types'
import { UploadZone } from '../components/UploadZone'
import { SourceFlow } from './SourceFlow'
import { SourceOutputs } from './SourceOutputs'

function SourceCard({
  s, onOpen, onViewOutputs,
}: {
  s: SourceDTO
  onOpen: () => void
  onViewOutputs: () => void
}) {
  return (
    <div className="card group flex flex-col overflow-hidden transition hover:border-accent hover:shadow-lg">
      <button onClick={onOpen} className="flex flex-1 flex-col text-right">
        <div className="aspect-[4/3] w-full overflow-hidden bg-slate-100 dark:bg-white/5">
          {s.has_page_image ? (
            <img
              src={api.sourceImageUrl(s.id)}
              alt={s.filename}
              className="h-full w-full object-cover transition group-hover:scale-[1.02]"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-3xl">📄</div>
          )}
        </div>
        <div className="flex flex-1 flex-col gap-2 p-3">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate font-semibold">{s.filename}</span>
            <span className="shrink-0 rounded-full bg-accent/15 px-2 py-0.5 text-xs font-bold text-accent-700 dark:text-accent">
              #{s.id}
            </span>
          </div>
          {s.doc_summary && <p className="field-label line-clamp-2">{s.doc_summary}</p>}
        </div>
      </button>

      <div className="flex flex-wrap items-center gap-1.5 border-t border-slate-200/60 px-3 py-2 dark:border-white/10">
        {s.has_detected && (
          <span className="rounded-md bg-emerald-500/15 px-2 py-0.5 text-xs text-emerald-600 dark:text-emerald-300">
            ✓ מחולץ
          </span>
        )}
        {s.n_generated > 0 ? (
          <button
            onClick={onViewOutputs}
            className="rounded-md bg-accent/15 px-2 py-0.5 text-xs font-semibold text-accent-700 hover:bg-accent/25 dark:text-accent"
          >
            {s.n_generated} נוצרו ←
          </button>
        ) : (
          <span className="rounded-md bg-slate-500/10 px-2 py-0.5 text-xs text-slate-500 dark:text-slate-400">
            0 נוצרו
          </span>
        )}
        <button
          onClick={onOpen}
          className="ms-auto text-xs font-semibold text-accent hover:underline"
        >
          בצע תהליך ←
        </button>
      </div>
    </div>
  )
}

export function StoreView() {
  const qc = useQueryClient()
  const { data: sources = [], isLoading } = useSources()
  const [selected, setSelected] = useState<SourceDTO | null>(null)
  const [outputs, setOutputs] = useState<SourceDTO | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onUpload = async (files: File[]) => {
    setUploading(true)
    setError(null)
    try {
      await api.uploadSources(files)
      await qc.invalidateQueries({ queryKey: ['sources'] })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setUploading(false)
    }
  }

  if (selected) {
    return (
      <SourceFlow
        source={selected}
        onBack={() => {
          setSelected(null)
          void qc.invalidateQueries({ queryKey: ['sources'] })
        }}
      />
    )
  }

  if (outputs) {
    return <SourceOutputs source={outputs} onBack={() => setOutputs(null)} />
  }

  return (
    <div className="space-y-8">
      <section className="space-y-2">
        <div className="flex items-baseline justify-between">
          <h2 className="text-lg font-bold">הוסף מסמך למאגר</h2>
          <span className="field-label">אפשר כמה קבצים בבת אחת</span>
        </div>
        <UploadZone multiple disabled={uploading} onFiles={onUpload} />
        {uploading && <div className="field-label">מעלה למאגר…</div>}
        {error && (
          <div className="card border-rose-400/40 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
            {error}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 className="text-lg font-bold">חנות המסמכים</h2>
          <span className="field-label">{sources.length} מקורות</span>
        </div>

        {isLoading && <div className="field-label">טוען…</div>}
        {!isLoading && sources.length === 0 && (
          <div className="card px-4 py-8 text-center">
            <p className="field-label">
              המאגר ריק. הוסף מסמך למעלה — הוא יישמר כאן עם מספר יוניק, ותוכל להריץ עליו את
              התהליך בכל עת. (דורש DATABASE_URL / הרצה ב-docker-compose.)
            </p>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sources.map((s) => (
            <SourceCard
              key={s.id}
              s={s}
              onOpen={() => setSelected(s)}
              onViewOutputs={() => setOutputs(s)}
            />
          ))}
        </div>
      </section>
    </div>
  )
}
