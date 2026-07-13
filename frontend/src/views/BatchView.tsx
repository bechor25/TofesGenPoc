import { useState } from 'react'

import { api } from '../api/client'
import { useJobFlow } from '../api/flow'
import { useDoc } from '../api/hooks'
import type { BatchItem } from '../api/types'
import { Gallery } from '../components/Gallery'
import { LiveStatus } from '../components/LiveStatus'
import { UploadZone } from '../components/UploadZone'
import { VariantsTable } from '../components/VariantsTable'

function BatchFileCard({ item }: { item: BatchItem }) {
  const flow = useJobFlow(item.doc_id)
  const { data: doc } = useDoc(item.doc_id)
  return (
    <div className="card space-y-3 p-4">
      <div className="flex items-center justify-between">
        <h4 className="font-bold">📄 {item.filename}</h4>
        <span className="field-label">{item.n_variants} וריאציות</span>
      </div>
      {item.error && <div className="text-sm text-rose-500">{item.error}</div>}
      {flow.error && <div className="text-sm text-rose-500">שגיאה: {flow.error}</div>}
      {doc?.doc_summary && <p className="field-label text-sm">📄 {doc.doc_summary}</p>}
      {flow.job && (
        <LiveStatus jobId={flow.job.id} label={flow.job.label} onDone={flow.onDone} />
      )}
      {doc && doc.variants.length > 0 && (
        <>
          <VariantsTable doc={doc} busy={!!flow.job} onRender={flow.renderMany} />
          <Gallery doc={doc} />
        </>
      )}
    </div>
  )
}

export function BatchView() {
  const [files, setFiles] = useState<File[]>([])
  const [n, setN] = useState(10)
  const [workers, setWorkers] = useState(4)
  const [jobId, setJobId] = useState<string | null>(null)
  const [items, setItems] = useState<BatchItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const run = async () => {
    if (files.length === 0) return
    setError(null)
    setItems(null)
    const r = await api.batch(files, n, workers)
    setJobId(r.job_id)
  }

  const onDone = async (err: string | null) => {
    if (err) {
      setError(err)
      setJobId(null)
      return
    }
    const st = await api.jobStatus(jobId as string)
    setItems((st.result as BatchItem[]) ?? [])
    setJobId(null)
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-bold">אצווה — עיבוד הרבה קבצים בסקייל</h2>
        <p className="field-label mt-1">
          שלב הדאטה (חילוץ + יצירת ערכים מאומתים) זול ורץ על כל הקבצים. רינדור התמונה יקר —
          נעשה לפי דרישה, לכל וריאציה בנפרד.
        </p>
      </div>

      <UploadZone multiple disabled={!!jobId} onFiles={setFiles} />
      {files.length > 0 && (
        <div className="field-label">נבחרו {files.length} קבצים.</div>
      )}

      <div className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-1">
          <span className="field-label">וריאציות לכל קובץ</span>
          <input
            type="number" min={1} max={50} className="input w-24" value={n}
            onChange={(e) => setN(Math.max(1, Math.min(50, Number(e.target.value) || 1)))}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="field-label">מקביליות (קבצים במקביל)</span>
          <input
            type="number" min={1} max={16} className="input w-24" value={workers}
            onChange={(e) =>
              setWorkers(Math.max(1, Math.min(16, Number(e.target.value) || 1)))
            }
          />
        </label>
        <button
          className="btn-primary"
          disabled={files.length === 0 || !!jobId}
          onClick={run}
        >
          עבד אצווה (חילוץ + יצירת ערכים)
        </button>
      </div>

      {error && (
        <div className="card border-rose-400/40 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          שגיאה: {error}
        </div>
      )}
      {jobId && (
        <LiveStatus jobId={jobId} label={`מעבד ${files.length} קבצים`} onDone={onDone} />
      )}

      {items && (
        <div className="space-y-4">
          <div className="field-label">עובדו {items.length} קבצים. ערכים מאומתים מוכנים.</div>
          {items.map((it) => (
            <BatchFileCard key={it.doc_id} item={it} />
          ))}
        </div>
      )}
    </div>
  )
}
