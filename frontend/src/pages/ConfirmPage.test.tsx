import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearBasketDraft, getBasketDraft } from '../features/basket/draftStore'
import { draftToText } from '../features/results/basketRequest'
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

/** Дочекатися кінця розбору агентом (у тестах він падає разом з усім бекендом). */
async function ready() {
  await waitFor(() => expect(screen.queryByText('Розбираю запит…')).not.toBeInTheDocument())
}

const voice = (over: Partial<VoiceResult> = {}): VoiceResult => ({
  ...localVoiceResult('молоко, хліб, далеко йти не хочу'),
  ...over,
})

/** GPS: ok — координати Хрещатика; denied — людина заборонила. */
function stubGeolocation(result: 'ok' | 'denied') {
  const getCurrentPosition = vi.fn((ok: PositionCallback, fail: PositionErrorCallback) => {
    if (result === 'ok') ok({ coords: { latitude: 50.45, longitude: 30.52 } } as GeolocationPosition)
    else fail({ code: 1, PERMISSION_DENIED: 1 } as GeolocationPositionError)
  })
  Object.defineProperty(navigator, 'geolocation', { value: { getCurrentPosition }, configurable: true })
  return getCurrentPosition
}

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

  it('shows what was said and pre-fills mode and radius from voice', async () => {
    renderAt({ voice: voice({ mode: 'walk', radius_km: 1 }) })
    await ready()
    expect(screen.getByRole('heading', { name: 'Я зрозумів так' })).toBeInTheDocument()
    expect(screen.getByText('молоко, хліб, далеко йти не хочу')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Пішки' })).toBeChecked()
    expect(screen.getByRole('radio', { name: /^1\s*км/ })).toBeChecked()
  })

  it('uses the /geo default radius when voice has none', async () => {
    renderAt({ voice: voice() })
    await ready()
    expect(screen.getByRole('radio', { name: 'Пішки' })).toBeChecked()
    expect(screen.getByRole('radio', { name: /^2\s*км/ })).toBeChecked()
    fireEvent.click(screen.getByRole('radio', { name: 'Авто' }))
    expect(screen.getByRole('radio', { name: /^10\s*км/ })).toBeChecked()
  })

  it('starts with an empty list and a disabled CTA when the agent is down', async () => {
    renderAt({ voice: voice() })
    expect(screen.getByText('Розбираю запит…')).toBeInTheDocument()
    await ready()
    expect(screen.getByText('Не вдалося розібрати запит автоматично')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Знайти ціни/ })).toBeDisabled()
  })

  it('adds a category from local suggestions, edits and removes it', async () => {
    renderAt({ voice: voice() })
    await ready()
    const input = screen.getByRole('combobox', { name: 'Додати товар' })
    fireEvent.change(input, { target: { value: 'смет' } })
    fireEvent.click(screen.getByRole('option', { name: /Сметана/ }))

    const group = screen.getByRole('group', { name: 'Кількість: Сметана' })
    fireEvent.click(within(group).getByRole('button', { name: 'Більше' }))
    expect(within(group).getByText('2')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Прибрати Сметана' }))
    expect(screen.getByText('Не вдалося розібрати запит автоматично')).toBeInTheDocument()
  })

  it('shows the catalog-down note after the search pause', async () => {
    renderAt({ voice: voice() })
    await ready()
    fireEvent.change(screen.getByRole('combobox', { name: 'Додати товар' }), { target: { value: 'гречка' } })
    expect(await screen.findByText(/Каталог зараз недоступний/, {}, { timeout: 1500 })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Гречка/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Додати «гречка»' })).toBeInTheDocument()
  })

  it('sends agent items and constraints to /results', async () => {
    const router = renderAt({ voice: voice({ mode: 'walk', radius_km: 1 }) })
    await ready()
    const input = screen.getByRole('combobox', { name: 'Додати товар' })
    fireEvent.change(input, { target: { value: 'молоко' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    fireEvent.click(screen.getByRole('checkbox', { name: 'Без цукру' }))
    fireEvent.click(screen.getByRole('radio', { name: /^500\s*₴/ }))

    stubGeolocation('ok')
    fireEvent.click(screen.getByRole('button', { name: 'Знайти ціни · 1 товар' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/results'))
    expect(router.state.location.state).toEqual({
      origin: { lat: 50.45, lng: 30.52, label: null, source: 'gps' },
      from: 'confirm',
    })
    expect(getBasketDraft()).toMatchObject({ budget: 500, mode: 'walk', radiusKm: 1, exclude: ['sugar'] })
    expect(draftToText(getBasketDraft()!)).toBe('молоко 1 л, без цукру, до 500 грн')
  })

  it('asks for an address when geolocation is denied', async () => {
    const geocode = {
      results: [{ label: 'вулиця Хрещатик, 22, Київ', full: '', lat: 50.4498, lng: 30.5231, source: 'nominatim' }],
    }
    vi.stubGlobal(
      'fetch',
      vi.fn((path: string) =>
        Promise.resolve(
          path.startsWith('/geo/geocode')
            ? new Response(JSON.stringify(geocode), { status: 200 })
            : new Response('{}', { status: 500 }),
        ),
      ),
    )
    const router = renderAt({ voice: voice() })
    await ready()
    const input = screen.getByRole('combobox', { name: 'Додати товар' })
    fireEvent.change(input, { target: { value: 'молоко' } })
    fireEvent.keyDown(input, { key: 'Enter' })

    stubGeolocation('denied')
    fireEvent.click(screen.getByRole('button', { name: 'Знайти ціни · 1 товар' }))
    expect(await screen.findByText(/Доступ до геолокації заборонено/)).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/confirm')

    fireEvent.change(screen.getByRole('combobox', { name: 'Ваша адреса' }), { target: { value: 'Хрещатик 22' } })
    fireEvent.click(await screen.findByRole('option', { name: 'вулиця Хрещатик, 22, Київ' }, { timeout: 1500 }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/results'))
    expect(router.state.location.state).toEqual({
      origin: { lat: 50.4498, lng: 30.5231, label: 'вулиця Хрещатик, 22, Київ', source: 'address' },
      from: 'confirm',
    })
  })

  it('keeps edits when coming back with the same request', async () => {
    const v = voice({ mode: 'car' })
    renderAt({ voice: v })
    await ready()
    const input = screen.getByRole('combobox', { name: 'Додати товар' })
    fireEvent.change(input, { target: { value: 'хліб' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(screen.getByRole('group', { name: 'Кількість: Хліб' })).toBeInTheDocument()

    document.body.innerHTML = ''
    renderAt({ voice: v })
    expect(screen.getByRole('group', { name: 'Кількість: Хліб' })).toBeInTheDocument()
  })

  it('fills products and constraints from /agent/parse', async () => {
    const parsed = {
      items: [
        { name: 'молоко', search_query: 'молоко', category: 'milk', quantity: 2000, unit: 'ml', brand: 'Галичина', optional: false },
        { name: 'яйця', search_query: 'яйця курячі', category: 'eggs', quantity: 10, unit: 'pcs', brand: null, optional: false },
        { name: 'кава', search_query: 'кава мелена', category: 'coffee_ground', quantity: 1, unit: 'pcs', brand: null, optional: false },
      ],
      constraints: { budget_uah: 400, exclude: ['sugar'], travel_mode: 'car', radius_km: null, preferred_chains: [] },
      servings: null,
    }
    const fetchMock = vi.fn((path: string, _init?: RequestInit) =>
      Promise.resolve(
        path === '/agent/parse'
          ? new Response(JSON.stringify(parsed), { status: 200 })
          : new Response('{}', { status: 500 }),
      ),
    )
    vi.stubGlobal('fetch', fetchMock)
    const router = renderAt({ voice: voice({ mode: 'walk', radius_km: 1 }) })
    expect(screen.getByText('Розбираю запит…')).toBeInTheDocument()
    await ready()

    expect(screen.getByRole('group', { name: 'Кількість: Молоко Галичина' })).toBeInTheDocument()
    expect(within(screen.getByRole('group', { name: 'Кількість: Яйця' })).getByText('10')).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Кількість: Кава' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Без цукру' })).toBeChecked()
    expect(screen.getByRole('textbox', { name: 'Сума бюджету, гривень' })).toHaveValue('400')
    // Режим і радіус з голосу головніші за розбір тексту.
    expect(screen.getByRole('radio', { name: 'Пішки' })).toBeChecked()
    expect(screen.getByRole('radio', { name: /^1\s*км/ })).toBeChecked()

    stubGeolocation('ok')
    fireEvent.click(screen.getByRole('button', { name: /Знайти ціни · 3 товари/ }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/results'))
    expect(draftToText(getBasketDraft()!)).toBe('молоко Галичина 2 л, яйця 10 шт, кава 250 г, без цукру, до 400 грн')
    const [, init] = fetchMock.mock.calls.find(([p]) => p === '/agent/parse')!
    expect(JSON.parse(init?.body as string)).toEqual({ text: 'молоко, хліб, далеко йти не хочу' })
  })

  it('explains when the agent found no products in the request', async () => {
    const empty = {
      items: [],
      constraints: { budget_uah: null, exclude: [], travel_mode: 'walk', radius_km: null, preferred_chains: [] },
      servings: null,
    }
    vi.stubGlobal(
      'fetch',
      vi.fn((path: string) =>
        Promise.resolve(
          path === '/agent/parse'
            ? new Response(JSON.stringify(empty), { status: 200 })
            : new Response('{}', { status: 500 }),
        ),
      ),
    )
    renderAt({ voice: voice({ raw_text: 'Борщ на 4 людини', text: 'Борщ на 4 людини' }) })
    await ready()
    expect(screen.getByText('Не вдалося розпізнати продукти в запиті')).toBeInTheDocument()
  })

  it('says the agent is unavailable when /agent/parse fails', async () => {
    renderAt({ voice: voice() })
    await ready()
    expect(screen.getByText('Не вдалося розібрати запит автоматично')).toBeInTheDocument()
  })

  it('parses a plain query (old state shape) with the agent, without /voice/parse-text', async () => {
    const parsed = {
      items: [{ name: 'кефір', search_query: 'кефір', category: 'kefir', quantity: 1000, unit: 'ml', brand: null, optional: false }],
      constraints: { budget_uah: null, exclude: [], travel_mode: 'car', radius_km: 5, preferred_chains: [] },
      servings: null,
    }
    const fetchMock = vi.fn((path: string) =>
      Promise.resolve(
        path === '/agent/parse'
          ? new Response(JSON.stringify(parsed), { status: 200 })
          : new Response('{}', { status: 500 }),
      ),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderAt({ query: 'кефір, на авто в радіусі 5 км' })
    expect(screen.getByText('Розбираю запит…')).toBeInTheDocument()
    expect(await screen.findByRole('radio', { name: /^5\s*км/ })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Авто' })).toBeChecked()
    expect(fetchMock.mock.calls.some(([path]) => String(path).startsWith('/voice/'))).toBe(false)
  })

  it('redirects to the request screen without state or draft', async () => {
    const router = renderAt(null)
    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
  })
})
