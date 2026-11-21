import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { localVoiceResult } from '../lib/api/client'
import { ConfirmPage } from './ConfirmPage'
import { RequestPage } from './RequestPage'

function renderPage() {
  const router = createMemoryRouter(
    [
      { path: '/', element: <RequestPage /> },
      { path: '/confirm', element: <ConfirmPage /> },
    ],
    { initialEntries: ['/'] },
  )
  render(<RouterProvider router={router} />)
  return router
}

function respond(status: number, body: unknown) {
  return vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status }))
}

describe('RequestPage', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = respond(200, {
      ...localVoiceResult('Борщ на 4 людини'),
      mode: 'walk',
      radius_km: 1,
      cleanup: { model: 'qwen', guard: 'ok', new_words: [], issues: {}, tokens: 10 },
    })
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => vi.unstubAllGlobals())

  it('shows text fallback hint when Web Speech API is unavailable', () => {
    renderPage()
    expect(screen.queryByRole('button', { name: 'Почати голосове введення' })).not.toBeInTheDocument()
    expect(screen.getByText('Браузер не підтримує голос. Введіть список текстом')).toBeInTheDocument()
  })

  it('blocks empty submit with an error and focuses the field', () => {
    const router = renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Знайти кошик' }))
    const field = screen.getByLabelText('Введіть або вставте список')
    expect(screen.getByRole('alert')).toHaveTextContent('Введіть або скажіть, що купити')
    expect(field).toHaveAttribute('aria-invalid', 'true')
    expect(field).toHaveFocus()
    expect(router.state.location.pathname).toBe('/')
  })

  it('fills the field from an example, parses it on the backend and submits to /confirm', async () => {
    const router = renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Борщ на 4 людини' }))
    expect(screen.getByLabelText('Введіть або вставте список')).toHaveValue('Борщ на 4 людини')
    fireEvent.click(screen.getByRole('button', { name: 'Знайти кошик' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/confirm'))

    const [path, init] = fetchMock.mock.calls[0]
    expect(path).toBe('/voice/parse-text')
    expect(JSON.parse(init.body)).toEqual({ text: 'Борщ на 4 людини', source: 'manual' })
    expect(router.state.location.state).toMatchObject({
      query: 'Борщ на 4 людини',
      cityId: 'kyiv',
      voice: { mode: 'walk', radius_km: 1 },
    })
  })

  it('submits on Enter in the desktop composer', async () => {
    const router = renderPage()
    const field = screen.getByLabelText('Введіть або вставте список')
    fireEvent.change(field, { target: { value: 'молоко, хліб' } })
    fireEvent.keyDown(field, { key: 'Enter' })
    await waitFor(() => expect(router.state.location.pathname).toBe('/confirm'))
  })

  it('still submits when /voice/parse-text is rate limited', async () => {
    vi.stubGlobal('fetch', respond(429, { detail: { code: 'rate_limited', message: 'x', fallback: false } }))
    const router = renderPage()
    fireEvent.change(screen.getByLabelText('Введіть або вставте список'), { target: { value: '  молоко  ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Знайти кошик' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/confirm'))
    expect(router.state.location.state).toMatchObject({
      voice: { text: 'молоко', raw_text: 'молоко', mode: null, radius_km: null, source: 'manual' },
    })
  })
})
