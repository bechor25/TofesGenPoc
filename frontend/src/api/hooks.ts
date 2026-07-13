import { useQuery } from '@tanstack/react-query'

import { api } from './client'

export const useDoc = (docId: string | null) =>
  useQuery({
    queryKey: ['doc', docId],
    queryFn: () => api.doc(docId as string),
    enabled: !!docId,
  })

export const useSources = () =>
  useQuery({ queryKey: ['sources'], queryFn: () => api.sources() })

export const useGenerated = (sourceId: number | null) =>
  useQuery({
    queryKey: ['generated', sourceId],
    queryFn: () => api.generated(sourceId as number),
    enabled: sourceId != null,
  })

export const useLogs = (open: boolean) =>
  useQuery({
    queryKey: ['logs'],
    queryFn: () => api.logs(400),
    enabled: open,
    refetchInterval: open ? 2000 : false,
  })
