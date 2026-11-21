import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearResult, saveResult } from '../features/results/resultsStore'
import type { AgentBasket, BasketLine, BasketOut } from '../lib/api/types'
import { BasketPage } from './BasketPage'

const line = (over: Partial<BasketLine>): BasketLine => ({
  requested: 'молоко',
  product_id: 1,
  title: 'Молоко Галичина 2,5% 900г',
  brand: 'Галичина',
  img_url: null,
  store_id: 'auchan',
  pack_qty: 900,
  pack_unit: 'g',
  packs: 1,
  price: 44.9,
  old_price: 60.9,
  promo_percent: 26,
  unit_price: 49.89,
  unit_price_label: '₴/кг',
  line_total: 44.9,
  tags: [],
  note: 'Менша пачка: 900 г замість 1000 мл',
  ...over,
})

const store = (id: string, chain_name: string, distance_km: number) => ({
  store_id: id,
  alt_store_ids: [],
  chain: id,
  chain_name,
  name: chain_name,
  address: 'Хоткевича, 1Б',
  lat: 50.45,
  lng: 30.63,
  distance_km,
  duration_min: 10,
  estimated: false,
  maps_url: `https://maps.example/${id}`,
})

const basket = (type: AgentBasket['type'], lines: BasketLine[], extra: Partial<AgentBasket> = {}): AgentBasket => ({
  type,
  stores: [store(type === 'nearest' ? 'metro' : 'auchan', type === 'nearest' ? 'METRO' : 'Auchan', type === 'nearest' ? 1.7 : 9.5)],
  lines,
  total: Math.round(lines.reduce((s, l) => s + l.line_total, 0) * 100) / 100,
  saving: 0,
  within_budget: true,
  missing: [],
  ...extra,
})

const RESULT: BasketOut = {
  parsed: {
    items: [
      { name: 'молоко', search_query: 'молоко', category: 'milk', quantity: 1000, unit: 'ml', brand: null, optional: false },
      { name: 'гречка', search_query: 'гречка', category: 'buckwheat', quantity: 1000, unit: 'g', brand: null, optional: false },
    ],
    constraints: { budget_uah: 150, exclude: ['sugar'], travel_mode: 'walk', radius_km: null, preferred_chains: [] },
    servings: null,
  },
  parser: 'items',
  stores_considered: 2,
  baskets: [
    basket('nearest', [
      line({ store_id: 'metro', price: 72.28, old_price: null, unit_price: 76.08, line_total: 72.28 }),
      line({ requested: 'гречка', title: 'Гречка Хуторок 800г', brand: 'Хуторок', store_id: 'metro', pack_qty: 800, packs: 2, price: 94.34, unit_price: 117.93, line_total: 188.68, note: null, old_price: null }),
    ]),
    basket(
      'cheapest',
      [
        line({}),
        line({ requested: 'гречка', title: 'Гречка Auchan 1кг', brand: 'Auchan', pack_qty: 1000, price: 120, unit_price: 120, line_total: 120, note: null, old_price: null }),
      ],
      { missing: [{ name: 'пастернак', reason: 'not_found' }] },
    ),
  ],
  explanation: '',
  warnings: [],
}

function renderPage(path = '/basket/cheapest') {
  const router = createMemoryRouter(
    [
      { path: '/basket/:optionId', element: <BasketPage /> },
      { path: '/results', element: <p>results</p> },
      { path: '/store/:optionId', element: <p>store</p> },
    ],
    { initialEntries: [path] },
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('offline'))))
  saveResult({
    key: 'k',
    origin: { lat: 50.4, lng: 30.6, label: 'Позняки', source: 'address' },
    request: { text: '', lat: 50.4, lng: 30.6, mode: 'walk' },
    result: RESULT,
    savedAt: '2026-11-21T15:00:00Z',
  })
})

afterEach(() => {
  clearResult()
  vi.unstubAllGlobals()
})

describe('BasketPage', () => {
  it('shows the selected basket: total, departments, weight, composition and missing item', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: 'Деталі кошика' })).toBeInTheDocument()
    expect(screen.getByText('Найвигідніший')).toBeInTheDocument()
    expect(screen.getAllByText('164,90 ₴').length).toBeGreaterThan(0)
    expect(screen.getByText('Сума без 1 товару')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Молочне та яйця' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Бакалія' })).toBeInTheDocument()
    expect(screen.getByText('900 г')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /Склад перевірено: без цукру/ }).length).toBe(2)
    expect(screen.getByText('пастернак')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Почати покупки/ })).toHaveAttribute('href', '/store/cheapest')
    expect(screen.getByRole('link', { name: /Маршрут/ })).toHaveAttribute('href', 'https://maps.example/auchan')
  })

  it('expands a row with prices in other options and the lowest unit price', () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Молоко Галичина 2,5% 900г' }))
    const details = screen.getByText('Ця позиція в інших варіантах').parentElement!
    expect(within(details).getByText(/найдешевше/)).toBeInTheDocument()
    expect(within(details).getByText('72,28 ₴')).toBeInTheDocument()
  })

  it('warns about the budget and recalculates after removing an item', () => {
    renderPage()
    expect(screen.getByText(/Понад бюджет на/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Прибрати Гречка Auchan 1кг/ }))
    expect(screen.queryByText(/Понад бюджет на/)).not.toBeInTheDocument()
    expect(screen.getAllByText('44,90 ₴').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: 'Повернути Гречка Auchan 1кг' }))
    expect(screen.getByText(/Понад бюджет на/)).toBeInTheDocument()
  })

  it('offers to go back when the option is unknown', () => {
    renderPage('/basket/smart_split')
    expect(screen.getByRole('heading', { name: 'Такого варіанту немає' })).toBeInTheDocument()
  })
})
