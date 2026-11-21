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

  it('submits typed text to /confirm without a backend call', async () => {
    const router = renderPage()
    expect(screen.queryByRole('list', { name: 'Приклади запитів' })).toBeNull()
    fireEvent.change(screen.getByLabelText('Введіть або вставте список'), { target: { value: 'Борщ на 4 людини' } })
    fireEvent.click(screen.getByRole('button', { name: 'Знайти кошик' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/confirm'))

    expect(fetchMock.mock.calls.some(([path]) => String(path).startsWith('/voice/'))).toBe(false)
    expect(router.state.location.state).toMatchObject({
      query: 'Борщ на 4 людини',
      cityId: 'kyiv',
      voice: { text: 'Борщ на 4 людини', mode: null, radius_km: null, source: 'manual' },
    })
  })

  it('submits on Enter in the desktop composer', async () => {
    const router = renderPage()
    const field = screen.getByLabelText('Введіть або вставте список')
    fireEvent.change(field, { target: { value: 'молоко, хліб' } })
    fireEvent.keyDown(field, { key: 'Enter' })
    await waitFor(() => expect(router.state.location.pathname).toBe('/confirm'))
  })

  it('trims typed text into a local VoiceResult', async () => {
    const router = renderPage()
    fireEvent.change(screen.getByLabelText('Введіть або вставте список'), { target: { value: '  молоко  ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Знайти кошик' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/confirm'))
    expect(router.state.location.state).toMatchObject({
      voice: { text: 'молоко', raw_text: 'молоко', mode: null, radius_km: null, source: 'manual' },
    })
  })
})
