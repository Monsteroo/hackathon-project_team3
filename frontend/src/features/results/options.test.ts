import { describe, expect, it } from 'vitest'
import type { AgentBasket, AgentStore } from '../../lib/api/types'
import { bestOption, coverageText, defaultOption, budgetText, distanceText, routeUrl, splitRows, tradeoff } from './options'

function store(over: Partial<AgentStore> = {}): AgentStore {
  return {
    store_id: 's1',
    alt_store_ids: [],
    chain: 'silpo',
    chain_name: 'Сільпо',
    name: 'Сільпо',
    address: 'Хрещатик, 34',
    lat: 50.45,
    lng: 30.52,
    distance_km: 0.4,
    duration_min: 5.2,
    estimated: false,
    maps_url: 'https://maps.example/s1',
    ...over,
  }
}

function basket(type: AgentBasket['type'], total: number, stores: AgentStore[], over: Partial<AgentBasket> = {}): AgentBasket {
  return { type, stores, lines: [], total, saving: 0, within_budget: true, missing: [], ...over }
}

/** Нерозривні пробіли з format.ts → звичайні, щоб очікування читалися. */
function plain<T>(value: T): T {
  return JSON.parse(JSON.stringify(value).replace(/[\u00a0\u202f]/g, ' ')) as T
}

const nearest = basket('nearest', 1413.8, [store()])
const cheapest = basket('cheapest', 1173.8, [store({ store_id: 's2', chain_name: 'АТБ', distance_km: 0.85 })])
const split = basket('smart_split', 1228.6, [
  store({ store_id: 's2', chain_name: 'АТБ', distance_km: 0.85, lat: 50.46 }),
  store({ store_id: 's3', chain_name: 'NOVUS', distance_km: 1.1, lat: 50.47 }),
])
const all = [nearest, cheapest, split]

describe('tradeoff', () => {
  it('is measured from the nearest option', () => {
    expect(plain(tradeoff(cheapest, all))).toEqual({ save: '−240 ₴', rest: ' за +450 м' })
    expect(plain(tradeoff(split, all))).toEqual({ save: '−185 ₴', rest: ' за +1 магазин' })
    expect(tradeoff(nearest, all)).toEqual({ rest: 'Найближчий до вас' })
  })

  it('says when the nearest is also the cheapest', () => {
    const pricier = basket('cheapest', 1500, [store({ store_id: 's2', distance_km: 0.2 })])
    expect(tradeoff(nearest, [nearest, pricier])).toEqual({ rest: 'Найдешевший і найближчий' })
    expect(plain(tradeoff(pricier, [nearest, pricier]))).toEqual({ rest: '+86 ₴, але на 200 м ближче' })
  })
})

describe('bestOption', () => {
  it('marks the cheapest complete basket, and none when a partial one is cheaper', () => {
    const missing = [{ name: 'кава', reason: 'not_found' }]
    expect(bestOption(all)).toBe('cheapest')
    expect(bestOption([nearest, cheapest, basket('smart_split', 1300, split.stores, { missing })])).toBe('cheapest')
    expect(bestOption([nearest, cheapest, basket('smart_split', 900, split.stores, { missing })])).toBeNull()
    expect(bestOption([nearest])).toBeNull()
    expect(bestOption([{ ...nearest, saving: 142.5 }])).toBe('nearest')
    expect(bestOption([nearest, { ...cheapest, missing: [{ name: 'кава', reason: 'not_found' }] }])).toBeNull()
  })

  it('defaults to cheapest', () => {
    expect(defaultOption(all)).toBe('cheapest')
    expect(defaultOption([nearest])).toBe('nearest')
    expect(defaultOption([])).toBeNull()
  })
})

describe('meta texts', () => {
  it('formats distance, coverage and budget', () => {
    expect(plain(distanceText(store({ distance_km: 1.68, duration_min: 5.3 }), 'car'))).toBe('1,7 км · 5 хв на авто')
    expect(plain(distanceText(store({ estimated: true }), 'walk'))).toBe('≈400 м · 5 хв пішки')
    expect(plain(coverageText(basket('nearest', 1, [], { missing: [{ name: 'x', reason: 'not_found' }] }), 11))).toBe(
      '10 з 11 товарів',
    )
    expect(coverageText(basket('nearest', 1, []), 4)).toBe('4 з 4 товарів')
    expect(budgetText(nearest, null)).toBeNull()
    expect(plain(budgetText(basket('nearest', 415.86, [], { within_budget: false }), 400))).toBe('+16 ₴ понад бюджет')
  })

  it('sums each store of a split basket', () => {
    const line = (store_id: string, line_total: number) =>
      ({ store_id, line_total }) as AgentBasket['lines'][number]
    const b = { ...split, lines: [line('s2', 100), line('s2', 50.5), line('s3', 20)] }
    expect(plain(splitRows(b).map((r) => [r.items, r.subtotal]))).toEqual([
      ['2 товари', '150,50 ₴'],
      ['1 товар', '20,00 ₴'],
    ])
  })
})

describe('routeUrl', () => {
  it('uses the geo link for one store and a waypoint for smart split', () => {
    const origin = { lat: 50.4, lng: 30.6, label: null, source: 'gps' as const }
    expect(routeUrl(nearest, origin, 'walk')).toBe('https://maps.example/s1')
    const url = new URL(routeUrl(split, origin, 'car')!)
    expect(url.searchParams.get('origin')).toBe('50.400000,30.600000')
    expect(url.searchParams.get('waypoints')).toBe('50.460000,30.520000')
    expect(url.searchParams.get('destination')).toBe('50.470000,30.520000')
    expect(url.searchParams.get('travelmode')).toBe('driving')
  })
})
