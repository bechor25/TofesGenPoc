import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { DetectedDTO, ReviewedValue } from '../api/types'
import { ReviewTable } from './ReviewTable'

const initial: DetectedDTO[] = [
  {
    id: 'a', label: 'שם', value: 'דנה',
    field_type: 'hebrew_name', is_personal: false, slot: null,
  },
]

describe('ReviewTable', () => {
  it('edits a value, toggles personal, adds a row, and submits', async () => {
    const onSubmit = vi.fn()
    render(<ReviewTable initial={initial} onSubmit={onSubmit} />)
    const user = userEvent.setup()

    await user.clear(screen.getByTestId('value-0'))
    await user.type(screen.getByTestId('value-0'), 'רון')
    await user.click(screen.getByTestId('personal-0'))
    await user.click(screen.getByText(/הוסף שורה/))
    await user.type(screen.getByTestId('label-1'), 'עיר')
    await user.click(screen.getByRole('button', { name: /צור דאטה/ }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    const [values, n] = onSubmit.mock.calls[0] as [ReviewedValue[], number]
    expect(values).toHaveLength(2)
    expect(values[0]).toMatchObject({
      value: 'רון', is_personal: true, field_type: 'hebrew_name',
    })
    expect(values[1].label).toBe('עיר')
    expect(n).toBe(10)
  })

  it('constrains the type select to FieldType options', () => {
    render(<ReviewTable initial={initial} onSubmit={vi.fn()} />)
    const select = screen.getByTestId('type-0')
    const options = Array.from(select.querySelectorAll('option')).map((o) => o.value)
    expect(options).toContain('address')
    expect(options).toContain('free_text')
  })
})
