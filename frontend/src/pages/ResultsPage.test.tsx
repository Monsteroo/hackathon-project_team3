import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { StrictMode } from 'react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { addItem, clearBasketDraft, initFromVoice, setBudget, toggleExclude } from '../features/basket/draftStore'
import type { Origin } from '../features/location/position'
import { clearResult } from '../features/results/resultsStore'
import { localVoiceResult } from '../lib/api/client'
import type { BasketOut } from '../lib/api/types'
import { ResultsPage } from './ResultsPage'

// MapLibre потребує WebGL, якого немає в jsdom.
vi.mock('../components/StoreMap/StoreMap', () => ({ StoreMap: () => <div data-testid="map" /> }))

const ORIGIN: Origin = { lat: 50.398, lng: 30.634, label: 'вулиця Григоренка, 1, Київ', source: 'address' }

/** Скорочена реальна відповідь з mocks/17_agent_basket.json. */
const RESULT: BasketOut = {
  parsed: {
    items: [
      { name: 'молоко', search_query: 'молоко', category: 'milk', quantity: 1000, unit: 'ml', brand: null, optional: false },
      { name: 'гречка', search_query: 'гречка', category: 'buckwheat', quantity: 1000, unit: 'g', brand: null, optional: false },
    ],
    constraints: { budget_uah: 400, exclude: [], travel_mode: 'car', radius_km: null, preferred_chains: [] },
    servings: null,
  },
  parser: 'items',
  stores_considered: 6,
  baskets: [
    {
      type: 'nearest',
      stores: [
        {
          store_id: '48215610',
          alt_store_ids: [],
          chain: 'metro',
          chain_name: 'METRO',
          name: 'METRO Позняки',
          address: 'Григоренка, 43',
          lat: 50.39,
          lng: 30.64,
          distance_km: 1.68,
          duration_min: 5.3,
          estimated: false,
          maps_url: 'https://maps.example/metro',
        },
      ],
      lines: [],
      total: 415.86,
      saving: 0,
      within_budget: false,
      missing: [{ name: 'кава', reason: 'filtered_by_composition' }],
    },
    {
      type: 'cheapest',
      stores: [
        {
          store_id: '48246401',
          alt_store_ids: [],
          chain: 'auchan',
          chain_name: 'Auchan',
          name: 'Auchan Петрівка',
          address: 'Степана Бандери, 15А',
          lat: 50.48,
          lng: 30.49,
          distance_km: 9.47,
          duration_min: 14.1,
          estimated: false,
          maps_url: 'https://maps.example/auchan',
        },
      ],
      lines: [],
      total: 288.3,
      saving: 127.56,
      within_budget: true,
      missing: [],
    },
  ],
  explanation: 'Найвигідніше: Auchan — 288.30 грн, економія 127.56 грн.',
  warnings: ['Ціни оновлено вночі'],
}

function respond(basket: () => Response) {
  const fetchMock = vi.fn((path: string, _init?: RequestInit) =>
    Promise.resolve(path === '/agent/basket' ? basket() : new Response('{}', { status: 500 })),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderAt(state: unknown) {
  const router = createMemoryRouter(
    [
      { path: '/', element: <p>Екран 1</p> },
      { path: '/confirm', element: <p>Екран 2</p> },
      { path: '/results', element: <ResultsPage /> },
      { path: '/basket/:optionId', element: <p>Екран 4</p> },
    ],
    { initialEntries: [{ pathname: '/results', state }] },
  )
  render(
    <StrictMode>
      <RouterProvider router={router} />
    </StrictMode>,
  )
  return router
}

function basketCalls(fetchMock: ReturnType<typeof respond>) {
  return fetchMock.mock.calls.filter(([p]) => p === '/agent/basket')
}

describe('ResultsPage', () => {
  beforeEach(() => {
    clearBasketDraft()
    clearResult()
    initFromVoice({ ...localVoiceResult('молоко і гречка'), mode: 'car' })
    addItem({ label: 'Молоко', category: 'milk', count: 1, packQty: 1000, unit: 'ml', exclude: [] })
    addItem({ label: 'Гречка', category: 'buckwheat', count: 1, packQty: 1000, unit: 'g', exclude: [] })
    setBudget(400)
  })
  afterEach(() => vi.unstubAllGlobals())

  it('sends the edited list with the location and shows the options', async () => {
    toggleExclude('private_label')
    const fetchMock = respond(() => new Response(JSON.stringify(RESULT), { status: 200 }))
    renderAt({ origin: ORIGIN })
    expect(screen.getByRole('status')).toHaveTextContent('Шукаю ціни в магазинах поруч')

    const cheapest = await screen.findByRole('radio', { name: /^Найвигідніший: Auchan, 288,30\s₴$/ })
    expect(cheapest).toBeChecked()
    expect(screen.getByRole('heading', { name: '2 варіанти кошика' })).toBeInTheDocument()
    expect(screen.getByText('−128 ₴ до інших')).toBeInTheDocument()
    expect(screen.getByText('Немає 1 товару')).toBeInTheDocument()
    expect(screen.getByText(RESULT.explanation)).toBeInTheDocument()
    expect(screen.getByText('Ціни оновлено вночі')).toBeInTheDocument()
    expect(screen.queryByText(/фільтр .*поки не враховується/i)).not.toBeInTheDocument()
    expect(screen.getByText('вулиця Григоренка, 1, Київ')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Маршрут/ })).toHaveAttribute('href', 'https://maps.example/auchan')

    const [, init] = basketCalls(fetchMock)[0]
    expect(JSON.parse(init?.body as string)).toEqual({
      text: 'молоко 1 л, гречка 1 кг, до 400 грн',
      items: [
        { label: 'Молоко', category: 'milk', need: 1000, unit: 'ml', exclude: ['private_label'] },
        { label: 'Гречка', category: 'buckwheat', need: 1000, unit: 'g', exclude: ['private_label'] },
      ],
      budget_uah: 400,
      raw_text: 'молоко і гречка',
      lat: 50.398,
      lng: 30.634,
      mode: 'car',
      radius_km: 10,
      city: 'Київ',
    })
  })

  it('requests baskets once for GPS and uses a local label', async () => {
    const fetchMock = respond(() => new Response(JSON.stringify(RESULT), { status: 200 }))
    renderAt({ origin: { lat: 50.45, lng: 30.52, label: null, source: 'gps' } })

    await screen.findByRole('radio', { name: /Найвигідніший/ })
    expect(screen.getByText('Ваше місце')).toBeInTheDocument()
    const paths = fetchMock.mock.calls.map(([path]) => String(path))
    // Агент — рівно один раз; після нього — лінія маршруту до вибраного магазину (/geo/route).
    expect(paths.filter((p) => p.startsWith('/agent/'))).toEqual(['/agent/basket'])
    expect(paths.filter((p) => p.startsWith('/geo/route')).length).toBeGreaterThanOrEqual(1)
    const [, init] = fetchMock.mock.calls[0]
    expect(init?.method).toBe('POST')
    expect(JSON.parse(init?.body as string)).toMatchObject({ lat: 50.45, lng: 30.52, mode: 'car' })
  })

  it('moves the selection with arrow keys', async () => {
    respond(() => new Response(JSON.stringify(RESULT), { status: 200 }))
    renderAt({ origin: ORIGIN })
    const cheapest = await screen.findByRole('radio', { name: /Найвигідніший/ })
    fireEvent.keyDown(cheapest, { key: 'ArrowDown' })
    const nearest = screen.getByRole('radio', { name: /Найближчий/ })
    expect(nearest).toBeChecked()
    expect(nearest).toHaveFocus()
    expect(screen.getByText(/склад не пройшов фільтр/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Маршрут/ })).toHaveAttribute('href', 'https://maps.example/metro')
    expect(screen.getByRole('link', { name: /Деталі кошика/ })).toHaveAttribute('href', '/basket/nearest')
  })

  it('offers a retry when the agent fails', async () => {
    let fail = true
    const fetchMock = respond(() =>
      fail
        ? new Response(JSON.stringify({ detail: 'database unavailable' }), { status: 503 })
        : new Response(JSON.stringify(RESULT), { status: 200 }),
    )
    renderAt({ origin: ORIGIN })
    expect(await screen.findByRole('alert')).toHaveTextContent('Не вдалося отримати ціни')
    fail = false
    fireEvent.click(screen.getByRole('button', { name: 'Спробувати ще' }))
    expect(await screen.findByRole('radio', { name: /Найвигідніший/ })).toBeInTheDocument()
    expect(basketCalls(fetchMock)).toHaveLength(2)
  })

  it('reuses the saved result for the same request', async () => {
    const fetchMock = respond(() => new Response(JSON.stringify(RESULT), { status: 200 }))
    renderAt({ origin: ORIGIN })
    await screen.findByRole('radio', { name: /Найвигідніший/ })

    document.body.innerHTML = ''
    renderAt(null)
    expect(screen.getByRole('radio', { name: /Найвигідніший/ })).toBeInTheDocument()
    expect(basketCalls(fetchMock)).toHaveLength(1)
  })

  it('goes back to the list when there is no location', async () => {
    respond(() => new Response('{}', { status: 500 }))
    const router = renderAt(null)
    await waitFor(() => expect(router.state.location.pathname).toBe('/confirm'))
  })
})
