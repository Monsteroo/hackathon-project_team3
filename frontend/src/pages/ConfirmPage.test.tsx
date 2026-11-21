import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearBasketDraft } from '../features/basket/draftStore'
import { localVoiceResult } from '../lib/api/client'
import type { VoiceResult } from '../lib/api/types'
import { ConfirmPage } from './ConfirmPage'

function renderAt(state: unknown) {
  const router = createMemoryRouter(
    [
      { path: '/', element: <p>Екран 1</p> },
      { path: '/confirm', element: <ConfirmPage /> },
      { path: '/results', element: <p>Екран 3</p> },
    ],
    { initialEntries: [{ pathname: '/confirm', state }] },
  )
  render(<RouterProvider router={router} />)
  return router
}

const voice = (over: Partial<VoiceResult> = {}): VoiceResult => ({
  ...localVoiceResult('молоко, хліб, далеко йти не хочу'),
  ...over,
})

/** Каталог недоступний (локально без DATABASE_URL так і є). */
function catalogDown() {
  return vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'db' }), { status: 500 }))
}

describe('ConfirmPage', () => {
  beforeEach(() => {
    clearBasketDraft()
    vi.stubGlobal('fetch', catalogDown())
  })
  afterEach(() => vi.unstubAllGlobals())

  it('shows what was said and pre-fills mode and radius from voice', () => {
    renderAt({ voice: voice({ mode: 'walk', radius_km: 1 }) })
    expect(screen.getByRole('heading', { name: 'Я зрозумів так' })).toBeInTheDocument()
    expect(screen.getByText('молоко, хліб, далеко йти не хочу')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Пішки' })).toBeChecked()
    expect(screen.getByRole('radio', { name: /^1\s*км/ })).toBeChecked()
  })

  it('uses the /geo default radius when voice has none', () => {
    renderAt({ voice: voice() })
    expect(screen.getByRole('radio', { name: 'Пішки' })).toBeChecked()
    expect(screen.getByRole('radio', { name: /^2\s*км/ })).toBeChecked()
    fireEvent.click(screen.getByRole('radio', { name: 'Авто' }))
    expect(screen.getByRole('radio', { name: /^10\s*км/ })).toBeChecked()
  })

  it('starts with an empty list and a disabled CTA', () => {
    renderAt({ voice: voice() })
    expect(screen.getByText('Додайте товари, які треба купити')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Знайти ціни/ })).toBeDisabled()
  })

  it('adds a category from local suggestions, edits and removes it', () => {
    renderAt({ voice: voice() })
    const input = screen.getByRole('combobox', { name: 'Додати товар' })
    fireEvent.change(input, { target: { value: 'смет' } })
    fireEvent.click(screen.getByRole('option', { name: /Сметана/ }))

    const group = screen.getByRole('group', { name: 'Кількість: Сметана' })
    fireEvent.click(within(group).getByRole('button', { name: 'Більше' }))
    expect(within(group).getByText('2')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Прибрати Сметана' }))
    expect(screen.getByText('Додайте товари, які треба купити')).toBeInTheDocument()
  })

  it('shows the catalog-down note after the search pause', async () => {
    renderAt({ voice: voice() })
    fireEvent.change(screen.getByRole('combobox', { name: 'Додати товар' }), { target: { value: 'гречка' } })
    expect(await screen.findByText(/Каталог зараз недоступний/, {}, { timeout: 1500 })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Гречка/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Додати «гречка»' })).toBeInTheDocument()
  })

  it('sends agent items and constraints to /results', async () => {
    const router = renderAt({ voice: voice({ mode: 'walk', radius_km: 1 }) })
    const input = screen.getByRole('combobox', { name: 'Додати товар' })
    fireEvent.change(input, { target: { value: 'молоко' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    fireEvent.click(screen.getByRole('checkbox', { name: 'Без цукру' }))
    fireEvent.click(screen.getByRole('radio', { name: /^500\s*₴/ }))

    fireEvent.click(screen.getByRole('button', { name: 'Знайти ціни · 1 товар' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/results'))
    expect(router.state.location.state).toMatchObject({
      items: [{ category: 'milk', need: 1000, unit: 'ml', exclude: ['sugar'] }],
      draft: { budget: 500, mode: 'walk', radiusKm: 1, exclude: ['sugar'] },
    })
  })

  it('keeps edits when coming back with the same request', () => {
    const v = voice({ mode: 'car' })
    renderAt({ voice: v })
    const input = screen.getByRole('combobox', { name: 'Додати товар' })
    fireEvent.change(input, { target: { value: 'хліб' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(screen.getByRole('group', { name: 'Кількість: Хліб' })).toBeInTheDocument()

    document.body.innerHTML = ''
    renderAt({ voice: v })
    expect(screen.getByRole('group', { name: 'Кількість: Хліб' })).toBeInTheDocument()
  })

  it('parses a plain query (old state shape) on the backend', async () => {
    const fetchMock = vi.fn((path: string) =>
      Promise.resolve(
        path.startsWith('/voice/parse-text')
          ? new Response(JSON.stringify(voice({ raw_text: 'кефір', text: 'кефір', mode: 'car', radius_km: 5 })), { status: 200 })
          : new Response('{}', { status: 500 }),
      ),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderAt({ query: 'кефір' })
    expect(screen.getByText('Розбираю запит…')).toBeInTheDocument()
    expect(await screen.findByRole('radio', { name: /^5\s*км/ })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Авто' })).toBeChecked()
  })

  it('redirects to the request screen without state or draft', async () => {
    const router = renderAt(null)
    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
  })
})
