import { useJobEvents } from '../api/sse'

interface Props {
  jobId: string | null
  label: string
  onDone: (error: string | null) => void
}

/** Live pipeline status driven by the job's SSE stream: real stage + elapsed. */
export function LiveStatus({ jobId, label, onDone }: Props) {
  const event = useJobEvents(jobId, onDone)
  if (!jobId) return null
  const stage = event?.stage || 'עובד…'
  const elapsed = event?.elapsed ?? 0
  return (
    <div className="card flex items-center gap-3 px-4 py-3">
      <span className="h-3 w-3 animate-pulse rounded-full bg-accent" aria-hidden />
      <div className="flex-1">
        <div className="text-sm font-semibold">{label}</div>
        <div className="field-label">{stage}</div>
      </div>
      <div className="tabular-nums text-sm text-slate-500 dark:text-slate-400">
        {elapsed} שנ׳
      </div>
    </div>
  )
}
