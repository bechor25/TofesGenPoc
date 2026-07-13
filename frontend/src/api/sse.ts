import { useEffect, useRef, useState } from 'react'

export interface JobEvent {
  stage: string
  elapsed: number
  done: boolean
  error: string | null
}

/**
 * Subscribe to a job's SSE progress stream. Emits the latest {stage, elapsed}
 * while running; on the terminal `done` frame it closes the stream and invokes
 * `onDone(error)`. Passing `null` clears the subscription.
 */
export function useJobEvents(
  jobId: string | null,
  onDone?: (error: string | null) => void,
): JobEvent | null {
  const [event, setEvent] = useState<JobEvent | null>(null)
  const onDoneRef = useRef(onDone)
  onDoneRef.current = onDone

  useEffect(() => {
    if (!jobId) {
      setEvent(null)
      return
    }
    const es = new EventSource(`/api/jobs/${jobId}/events`)
    es.onmessage = (e: MessageEvent<string>) => {
      const data = JSON.parse(e.data) as JobEvent
      setEvent(data)
      if (data.done) {
        es.close()
        onDoneRef.current?.(data.error)
      }
    }
    es.onerror = () => es.close()
    return () => es.close()
  }, [jobId])

  return event
}
