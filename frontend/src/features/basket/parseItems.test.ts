import { afterEach, describe, expect, it, vi } from 'vitest'
import { localVoiceResult } from '../../lib/api/client'
import type { ParsedRequest, RequestedItem } from '../../lib/api/types'
import { draftFromParsed, itemFromRequested, parseItems } from './parseItems'

const req = (over: Partial<RequestedItem>): RequestedItem => ({
  name: 'молоко',
  search_query: 'молоко',
  category: 'milk',
  quantity: 1000,
  unit: 'ml',
  brand: null,
  optional: false,
  ...over,
})

describe('itemFromRequested', () => {
  it('converts quantity to packs of the category', () => {
    expect(itemFromRequested(req({ quantity: 1500 }))).toMatchObject({
      label: 'Молоко',
      category: 'milk',
      query: undefined,
      count: 2,
      packQty: 1000,
      unit: 'ml',
    })
  })

  it('treats pcs for a packed category as a number of packs', () => {
    const item = itemFromRequested(req({ name: 'кава', category: 'coffee_ground', quantity: 2, unit: 'pcs' }))
    expect(item).toMatchObject({ count: 2, packQty: 250, unit: 'g' })
  })

  it('keeps the brand in the label and the search query', () => {
    expect(itemFromRequested(req({ brand: 'Галичина' }))).toMatchObject({
      label: 'Молоко Галичина',
      category: 'milk',
      query: 'молоко Галичина',
    })
  })

  it('uses search_query for items outside the demo categories', () => {
    expect(
      itemFromRequested(req({ name: 'шоколад', search_query: 'шоколад чорний', category: null, quantity: 100, unit: 'g' })),
    ).toMatchObject({ label: 'Шоколад', query: 'шоколад чорний', count: 1, packQty: 100, unit: 'g' })
    expect(
      itemFromRequested(req({ name: 'лимони', search_query: 'лимон', category: null, quantity: 3, unit: 'pcs' })),
    ).toMatchObject({ query: 'лимон', count: 3, packQty: 1, unit: 'pcs' })
  })

  it('clamps the count to the stepper range', () => {
    expect(itemFromRequested(req({ name: 'яйця', category: 'eggs', quantity: 500, unit: 'pcs' })).count).toBe(99)
    expect(itemFromRequested(req({ quantity: 0 })).count).toBe(1)
  })
})

describe('draftFromParsed', () => {
  const parsed = (constraints: Partial<ParsedRequest['constraints']>): ParsedRequest => ({
    items: [],
    constraints: { budget_uah: null, exclude: [], travel_mode: 'walk', radius_km: null, preferred_chains: [], ...constraints },
    servings: null,
  })

  it('maps constraints; default walk means "not said"', () => {
    expect(draftFromParsed(parsed({}))).toMatchObject({
      status: 'empty',
      budget: null,
      exclude: [],
      mode: null,
      radiusKm: null,
    })
    expect(draftFromParsed(parsed({ budget_uah: 400, exclude: ['sugar'], travel_mode: 'car', radius_km: 5 }))).toMatchObject(
      { budget: 400, exclude: ['sugar'], mode: 'car', radiusKm: 5 },
    )
  })
})

describe('parseItems', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('returns an empty draft when the agent is down', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 503 })))
    expect(await parseItems(localVoiceResult('молоко'))).toEqual({
      status: 'unavailable',
      items: [],
      budget: null,
      exclude: [],
      mode: null,
      radiusKm: null,
    })
  })
})
