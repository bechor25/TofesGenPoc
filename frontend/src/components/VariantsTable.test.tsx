import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { DocStateDTO } from '../api/types'
import { VariantsTable } from './VariantsTable'

const doc: DocStateDTO = {
  doc_id: 'doc-1', filename: 'f.png', doc_summary: '', page_image_url: null,
  detected: [], diagnostics: [],
  columns: [{ id: 'name', label: 'שם' }],
  variants: [
    { index: 0, values: { name: 'דנה' }, rendered: false },
    { index: 1, values: { name: 'רון' }, rendered: false },
    { index: 2, values: { name: 'לי' }, rendered: true },
  ],
}

describe('VariantsTable', () => {
  it('sends the selected indices + difficulty to onRender', async () => {
    const onRender = vi.fn()
    render(<VariantsTable doc={doc} onRender={onRender} />)
    const user = userEvent.setup()
    await user.click(screen.getByTestId('render-0'))
    await user.click(screen.getByTestId('render-2'))
    await user.click(screen.getByRole('button', { name: /רנדר נבחרים/ }))
    expect(onRender).toHaveBeenCalledWith([0, 2], 1)
  })

  it('render-all passes the chosen difficulty', async () => {
    const onRender = vi.fn()
    render(<VariantsTable doc={doc} onRender={onRender} />)
    fireEvent.change(screen.getByTestId('difficulty'), { target: { value: '7' } })
    await userEvent.setup().click(screen.getByRole('button', { name: /רנדר הכל/ }))
    expect(onRender).toHaveBeenCalledWith([0, 1, 2], 7)
  })
})
