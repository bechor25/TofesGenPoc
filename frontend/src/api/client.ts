import type {
  DocStateDTO,
  GeneratedDTO,
  JobRef,
  JobStatus,
  OpenResult,
  ReviewedValue,
  SourceDTO,
} from './types'

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(detail || `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  extract(file: File): Promise<JobRef> {
    const fd = new FormData()
    fd.append('file', file)
    return fetch('/api/extract', { method: 'POST', body: fd }).then(asJson<JobRef>)
  },

  batch(files: File[], n: number, workers: number): Promise<JobRef> {
    const fd = new FormData()
    files.forEach((f) => fd.append('files', f))
    fd.append('n', String(n))
    fd.append('workers', String(workers))
    return fetch('/api/batch', { method: 'POST', body: fd }).then(asJson<JobRef>)
  },

  jobStatus(id: string): Promise<JobStatus> {
    return fetch(`/api/jobs/${id}`).then(asJson<JobStatus>)
  },

  doc(docId: string): Promise<DocStateDTO> {
    return fetch(`/api/docs/${docId}`).then(asJson<DocStateDTO>)
  },

  generate(docId: string, values: ReviewedValue[], n: number): Promise<JobRef> {
    return fetch(`/api/docs/${docId}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ values, n }),
    }).then(asJson<JobRef>)
  },

  render(docId: string, variantIndex: number): Promise<JobRef> {
    return fetch(`/api/docs/${docId}/render`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ variant_index: variantIndex }),
    }).then(asJson<JobRef>)
  },

  uploadSources(files: File[]): Promise<{ source_ids: number[] }> {
    const fd = new FormData()
    files.forEach((f) => fd.append('files', f))
    return fetch('/api/sources/upload', { method: 'POST', body: fd }).then(
      asJson<{ source_ids: number[] }>,
    )
  },

  openSource(sourceId: number, force = false): Promise<OpenResult> {
    return fetch(`/api/sources/${sourceId}/open?force=${force}`, {
      method: 'POST',
    }).then(asJson<OpenResult>)
  },

  sources(): Promise<SourceDTO[]> {
    return fetch('/api/sources').then(asJson<SourceDTO[]>)
  },

  generated(sourceId: number): Promise<GeneratedDTO[]> {
    return fetch(`/api/sources/${sourceId}/generated`).then(asJson<GeneratedDTO[]>)
  },

  logs(n = 400): Promise<string[]> {
    return fetch(`/api/logs?n=${n}`)
      .then(asJson<{ lines: string[] }>)
      .then((r) => r.lines)
  },

  zipUrl: (docId: string) => `/api/docs/${docId}/zip`,
  generatedImageUrl: (docId: string, index: number) =>
    `/api/image/generated/${docId}/${index}`,
  archivedImageUrl: (genId: number) => `/api/image/archived/${genId}`,
  sourceImageUrl: (sourceId: number) => `/api/image/source/${sourceId}`,
  sourceZipUrl: (sourceId: number) => `/api/sources/${sourceId}/zip`,
}
