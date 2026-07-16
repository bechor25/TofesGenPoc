import { useState } from 'react'

import { useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import type { ReviewedValue } from './types'

export type JobKind = 'extract' | 'generate' | 'render'
export interface ActiveJob {
  id: string
  label: string
  kind: JobKind
}

/**
 * Drives the multi-step job lifecycle for one document: generate the data, then
 * render selected variants one at a time. `onDone` is handed to <LiveStatus> and
 * fires on each job's terminal SSE frame — it refetches the doc and, for renders,
 * advances the queue.
 */
export function useJobFlow(docId: string | null) {
  const qc = useQueryClient()
  const [job, setJob] = useState<ActiveJob | null>(null)
  const [pending, setPending] = useState<number[]>([])
  const [difficulty, setDifficulty] = useState(1)
  const [error, setError] = useState<string | null>(null)

  const refetch = () =>
    docId ? qc.invalidateQueries({ queryKey: ['doc', docId] }) : Promise.resolve()

  const onDone = async (err: string | null) => {
    if (err) {
      setError(err)
      setJob(null)
      setPending([])
      return
    }
    await refetch()
    if (job?.kind === 'render' && pending.length > 0) {
      const [next, ...rest] = pending
      setPending(rest)
      const r = await api.render(docId as string, next, difficulty)
      setJob({ id: r.job_id, label: `יוצר בדיקה (וריאציה ${next + 1}, דרגה ${difficulty})`, kind: 'render' })
    } else {
      setJob(null)
    }
  }

  const generate = async (values: ReviewedValue[], n: number) => {
    setError(null)
    const r = await api.generate(docId as string, values, n)
    setJob({ id: r.job_id, label: `מייצר דאטה (${n} וריאציות)`, kind: 'generate' })
  }

  const renderMany = async (indices: number[], level = 1) => {
    if (indices.length === 0) return
    setError(null)
    setDifficulty(level)
    const [first, ...rest] = indices
    setPending(rest)
    const r = await api.render(docId as string, first, level)
    setJob({
      id: r.job_id,
      label: `יוצר בדיקה (וריאציה ${first + 1}, דרגה ${level})`,
      kind: 'render',
    })
  }

  return { job, error, pending, onDone, generate, renderMany, setError, setJob }
}
