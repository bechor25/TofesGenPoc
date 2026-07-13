import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useJobEvents } from './sse'

class MockEventSource {
  static last: MockEventSource | null = null
  onmessage: ((e: MessageEvent<string>) => void) | null = null
  onerror: (() => void) | null = null
  url: string
  closed = false

  constructor(url: string) {
    this.url = url
    MockEventSource.last = this
  }

  close() {
    this.closed = true
  }

  emit(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent<string>)
  }
}

describe('useJobEvents', () => {
  beforeEach(() => {
    vi.stubGlobal('EventSource', MockEventSource)
  })

  it('parses stage frames and fires onDone + closes on the done frame', async () => {
    const onDone = vi.fn()
    const { result } = renderHook(() => useJobEvents('job-1', onDone))

    act(() =>
      MockEventSource.last?.emit({ stage: 'מתעתק', elapsed: 3, done: false, error: null }),
    )
    await waitFor(() => expect(result.current?.stage).toBe('מתעתק'))

    act(() =>
      MockEventSource.last?.emit({ stage: 'סיום', elapsed: 9, done: true, error: null }),
    )
    expect(onDone).toHaveBeenCalledWith(null)
    expect(MockEventSource.last?.closed).toBe(true)
  })
})
