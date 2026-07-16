import { useEffect, useState } from 'react'

import { useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import { useJobFlow } from '../api/flow'
import { useDoc, useGenerated } from '../api/hooks'
import type { SourceDTO } from '../api/types'
import { Diagnostics } from '../components/Diagnostics'
import { Gallery } from '../components/Gallery'
import { LiveStatus } from '../components/LiveStatus'
import { ReviewTable } from '../components/ReviewTable'
import { Stepper } from '../components/Stepper'
import { VariantsTable } from '../components/VariantsTable'
import { useUI } from '../store/ui'

/** Run the full flow on ONE stored source: open (reuse cached extraction or extract),
 * review, generate data, render. Everything persists under the parent source. */
export function SourceFlow({ source, onBack }: { source: SourceDTO; onBack: () => void }) {
  const qc = useQueryClient()
  const openDocs = useUI((s) => s.openDocs)
  const setOpenDoc = useUI((s) => s.setOpenDoc)
  const [docId, setDocId] = useState<string | null>(openDocs[source.id] ?? null)
  const [opening, setOpening] = useState(!openDocs[source.id])
  const flow = useJobFlow(docId)
  const { data: doc } = useDoc(docId)
  const { data: generated = [] } = useGenerated(source.id)

  useEffect(() => {
    if (openDocs[source.id]) return // already open — reuse the same run
    let cancelled = false
    void (async () => {
      try {
        const r = await api.openSource(source.id)
        if (cancelled) return
        setDocId(r.doc_id)
        setOpenDoc(source.id, r.doc_id)
        if (!r.cached && r.job_id) {
          flow.setJob({ id: r.job_id, label: 'מחלץ ערכים מהמקור', kind: 'extract' })
        }
      } finally {
        if (!cancelled) setOpening(false)
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source.id])

  const reextract = async () => {
    const r = await api.openSource(source.id, true)
    setDocId(r.doc_id)
    setOpenDoc(source.id, r.doc_id)
    if (r.job_id) flow.setJob({ id: r.job_id, label: 'מחלץ מחדש', kind: 'extract' })
  }

  // after a job finishes, also refresh the source's persisted outputs + the store list
  const onJobDone = (err: string | null) => {
    void flow.onDone(err)
    void qc.invalidateQueries({ queryKey: ['generated', source.id] })
    void qc.invalidateQueries({ queryKey: ['sources'] })
  }

  const hasDetected = !!doc && doc.detected.length > 0
  const hasVariants = !!doc && doc.variants.length > 0
  const hasRendered = !!doc && doc.variants.some((v) => v.rendered)
  const step = opening || flow.job?.kind === 'extract' ? 1 : hasVariants ? 3 : 2

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

      <Stepper active={step} />

      {flow.error && (
        <div className="card border-rose-400/40 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          שגיאה: {flow.error}
        </div>
      )}

      {opening && (
        <div className="card px-4 py-3 text-sm">פותח מסמך מהחנות…</div>
      )}
      {flow.job && (
        <LiveStatus jobId={flow.job.id} label={flow.job.label} onDone={onJobDone} />
      )}

      {doc && (
        <div className="card flex flex-col gap-3 p-4 sm:flex-row sm:items-start">
          <img
            src={api.sourceImageUrl(source.id)}
            alt="הטופס"
            className="max-h-56 w-auto rounded-lg border border-slate-200/60 dark:border-white/10"
          />
          <div className="min-w-0 flex-1">
            {doc.doc_summary && (
              <>
                <div className="field-label">📄 הבנת המסמך</div>
                <p className="mt-1 text-sm">{doc.doc_summary}</p>
              </>
            )}
            {hasDetected && (
              <button className="btn-ghost mt-3" onClick={reextract} disabled={!!flow.job}>
                ↻ חלץ מחדש
              </button>
            )}
          </div>
        </div>
      )}

      {hasDetected && !hasVariants && flow.job?.kind !== 'generate' && (
        <ReviewTable
          key={docId}
          initial={doc.detected}
          busy={!!flow.job}
          onSubmit={flow.generate}
        />
      )}

      {hasVariants && (
        <>
          <VariantsTable doc={doc} busy={!!flow.job} onRender={flow.renderMany} />
          {hasRendered ? (
            <Gallery doc={doc} />
          ) : (
            generated.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-base font-bold">תוצרים שמורים במאגר ({generated.length})</h3>
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
                  {generated.map((g) => {
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
          )}
          <Diagnostics rows={doc.diagnostics} />
        </>
      )}
    </div>
  )
}
