import { useState } from 'react'

import { api } from '../api/client'
import { useJobFlow } from '../api/flow'
import { useDoc } from '../api/hooks'
import { Diagnostics } from '../components/Diagnostics'
import { Gallery } from '../components/Gallery'
import { LiveStatus } from '../components/LiveStatus'
import { ReviewTable } from '../components/ReviewTable'
import { Stepper } from '../components/Stepper'
import { UploadZone } from '../components/UploadZone'
import { VariantsTable } from '../components/VariantsTable'

export function SingleView() {
  const [docId, setDocId] = useState<string | null>(null)
  const flow = useJobFlow(docId)
  const { data: doc } = useDoc(docId)

  const onUpload = async (files: File[]) => {
    flow.setError(null)
    const r = await api.extract(files[0])
    setDocId(r.doc_id ?? null)
    flow.setJob({ id: r.job_id, label: 'מזהה ערכים', kind: 'extract' })
  }

  const reset = () => {
    setDocId(null)
    flow.setJob(null)
    flow.setError(null)
  }

  const hasDetected = !!doc && doc.detected.length > 0
  const hasVariants = !!doc && doc.variants.length > 0
  const step = !docId ? 0 : flow.job?.kind === 'extract' ? 1 : hasVariants ? 3 : 2

  return (
    <div className="space-y-5">
      <Stepper active={step} />

      {flow.error && (
        <div className="card border-rose-400/40 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          שגיאה: {flow.error}
        </div>
      )}

      {!docId && <UploadZone onFiles={onUpload} />}

      {flow.job && (
        <LiveStatus jobId={flow.job.id} label={flow.job.label} onDone={flow.onDone} />
      )}

      {doc && (doc.page_image_url || doc.doc_summary) && (
        <div className="card flex flex-col gap-3 p-4 sm:flex-row">
          {doc.page_image_url && (
            <img
              src={doc.page_image_url}
              alt="הטופס שנקלט"
              className="max-h-64 w-auto rounded-lg border border-slate-200/60 dark:border-white/10"
            />
          )}
          {doc.doc_summary && (
            <div>
              <div className="field-label">📄 הבנת המסמך</div>
              <p className="mt-1 text-sm">{doc.doc_summary}</p>
            </div>
          )}
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
          <Gallery doc={doc} />
          <Diagnostics rows={doc.diagnostics} />
        </>
      )}

      {docId && (
        <button className="btn-ghost" onClick={reset}>
          ↺ התחל מחדש
        </button>
      )}
    </div>
  )
}
