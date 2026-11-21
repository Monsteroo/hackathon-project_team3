import { describe, expect, it } from 'vitest'
import type { AgentBasket, BasketLine, ParsedRequest } from '../../lib/api/types'
import {
  analogOf,
  basketTotal,
  compareRequested,
  freshnessText,
  groupByDepartment,
  nonstandardWeight,
  trimCandidates,
  unitPrice,
  verifiedTags,
} from './details'

const line = (over: Partial<BasketLine>): BasketLine => ({
  requested: 'молоко',
  product_id: 1,
  title: 'Молоко Галичина 2,5% 950г',
  brand: 'Галичина',
  img_url: null,
  store_id: 's1',
  pack_qty: 950,
  pack_unit: 'g',
  packs: 1,
  price: 72.28,
  old_price: null,
  promo_percent: null,
  unit_price: 76.08,
  unit_price_label: '₴/кг',
  line_total: 72.28,
  tags: [],
  note: null,
  ...over,
})

const parsed: ParsedRequest = {
  items: [
    { name: 'молоко', search_query: 'молоко', category: 'milk', quantity: 1000, unit: 'ml', brand: 'Галичина', optional: false },
    { name: 'банани', search_query: 'банани', category: 'bananas', quantity: 1000, unit: 'g', brand: null, optional: true },
  ],
  constraints: { budget_uah: 400, exclude: ['lactose'], travel_mode: 'walk', radius_km: null, preferred_chains: [] },
  servings: null,
}

const basket = (type: AgentBasket['type'], lines: BasketLine[]): AgentBasket => ({
  type,
  stores: [],
  lines,
  total: lines.reduce((s, l) => s + l.line_total, 0),
  saving: 0,
  within_budget: true,
  missing: [],
})

describe('nonstandardWeight', () => {
  it('flags 950 г and 870 г, not 1 кг or 500 мл', () => {
    expect(nonstandardWeight({ pack_qty: 950, pack_unit: 'g' })).toBe('950\u00a0г')
    expect(nonstandardWeight({ pack_qty: 1000, pack_unit: 'g' })).toBeNull()
    expect(nonstandardWeight({ pack_qty: 500, pack_unit: 'ml' })).toBeNull()
    expect(nonstandardWeight({ pack_qty: 10, pack_unit: 'pcs' })).toBeNull()
    expect(nonstandardWeight({ pack_qty: null, pack_unit: null })).toBeNull()
  })
})

describe('unitPrice', () => {
  it('formats visible and screen-reader text', () => {
    expect(unitPrice(line({}))).toEqual({ text: '76,08\u00a0₴/кг', sr: '76,08 гривні за кілограм' })
    expect(unitPrice(line({ unit_price: 7.5, unit_price_label: '₴/шт' }))?.sr).toBe('7,50 гривні за штуку')
    expect(unitPrice(line({ unit_price: null }))).toBeNull()
  })
})

describe('groupByDepartment', () => {
  it('orders departments by store walk and skips empty ones', () => {
    const groups = groupByDepartment(['milk', 'bananas', null] as const, (c) => c)
    expect(groups.map((g) => g.title)).toEqual(['Овочі й фрукти', 'Молочне та яйця', 'Інше'])
  })
})

describe('verifiedTags', () => {
  it('shows only active filters the product passed', () => {
    expect(verifiedTags(line({}), parsed.items[0], parsed).map((v) => v.title)).toEqual([
      'Склад перевірено: без лактози',
    ])
    expect(verifiedTags(line({ tags: ['lactose'] }), parsed.items[0], parsed)).toEqual([])
    const noFilters = { ...parsed, constraints: { ...parsed.constraints, exclude: [] } }
    expect(verifiedTags(line({}), parsed.items[0], noFilters)).toEqual([])
  })
})

describe('analogOf', () => {
  it('marks a different brand than the one asked for', () => {
    expect(analogOf(line({}), parsed.items[0])).toBeNull()
    expect(analogOf(line({ brand: 'Яготинське', title: 'Молоко Яготинське' }), parsed.items[0])).toBe('молоко Галичина')
    expect(analogOf(line({}), parsed.items[1])).toBeNull()
  })
})

describe('compareRequested', () => {
  it('marks the lowest unit price only when prices differ', () => {
    const a = basket('nearest', [line({ unit_price: 80, line_total: 76 })])
    const b = basket('cheapest', [line({ unit_price: 70, line_total: 66.5 })])
    const c = basket('smart_split', [])
    const cells = compareRequested('молоко', [a, b, c])
    expect(cells.map((x) => x.lowest)).toEqual([false, true, false])
    expect(cells[2].total).toBeNull()
    expect(compareRequested('молоко', [a, a]).some((x) => x.lowest)).toBe(false)
  })
})

describe('basketTotal and trimCandidates', () => {
  it('recalculates without removed items and suggests optional first', () => {
    const milk = line({ line_total: 72.28 })
    const bananas = line({ requested: 'банани', line_total: 45.5 })
    const b = basket('cheapest', [milk, bananas])
    expect(basketTotal(b, new Set(['банани']))).toBe(72.28)
    expect(trimCandidates([milk, bananas], parsed).map((l) => l.requested)).toEqual(['банани', 'молоко'])
  })
})

describe('freshnessText', () => {
  it('says today, yesterday or a date', () => {
    const now = new Date(2026, 10, 21, 16, 0)
    expect(freshnessText(new Date(2026, 10, 21, 3, 5).toISOString(), now)).toBe('Ціни оновлено сьогодні о 03:05')
    expect(freshnessText(new Date(2026, 10, 20, 3, 5).toISOString(), now)).toBe('Ціни оновлено вчора о 03:05')
    expect(freshnessText(new Date(2026, 10, 18, 3, 5).toISOString(), now)).toBe('Ціни оновлено 18.11 о 03:05')
    expect(freshnessText(null, now)).toBeNull()
  })
})
