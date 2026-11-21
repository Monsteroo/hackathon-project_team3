import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { localVoiceResult } from '../../lib/api/client'
import type { CatalogProduct } from '../../lib/api/types'
import { categoryInfo, searchCategories } from './categories'
import {
  addItem,
  clearBasketDraft,
  getBasketDraft,
  initFromVoice,
  isSameVoice,
  itemFromCategory,
  itemFromProduct,
  itemFromQuery,
  MAX_COUNT,
  radiusOptions,
  setCount,
  setMode,
  setRadius,
  toAgentItems,
  toggleExclude,
} from './draftStore'

const voice = (over: Partial<ReturnType<typeof localVoiceResult>> = {}) => ({ ...localVoiceResult('молоко'), ...over })

describe('basket draft', () => {
  beforeEach(() => clearBasketDraft())
  afterEach(() => vi.restoreAllMocks())

  it('takes mode and radius from voice', () => {
    initFromVoice(voice({ mode: 'walk', radius_km: 1 }))
    expect(getBasketDraft()).toMatchObject({ mode: 'walk', radiusKm: 1, items: [], budget: null })
  })

  it('falls back to /geo defaults when voice says nothing', () => {
    initFromVoice(voice())
    expect(getBasketDraft()).toMatchObject({ mode: 'walk', radiusKm: 2 })
    initFromVoice(voice({ mode: 'car' }))
    expect(getBasketDraft()).toMatchObject({ mode: 'car', radiusKm: 10 })
  })

  it('resets radius to the mode default when mode changes', () => {
    initFromVoice(voice({ mode: 'walk', radius_km: 1 }))
    setMode('car')
    expect(getBasketDraft()).toMatchObject({ mode: 'car', radiusKm: 10 })
    setRadius(500)
    expect(getBasketDraft()?.radiusKm).toBe(50)
  })

  it('merges the same category instead of duplicating and clamps count', () => {
    initFromVoice(voice())
    const milk = itemFromCategory(categoryInfo('milk')!)
    const id = addItem(milk)
    expect(addItem(milk)).toBe(id)
    expect(getBasketDraft()?.items).toHaveLength(1)
    expect(getBasketDraft()?.items[0].count).toBe(2)
    setCount(id, 0)
    expect(getBasketDraft()?.items[0].count).toBe(1)
    setCount(id, 1000)
    expect(getBasketDraft()?.items[0].count).toBe(MAX_COUNT)
  })

  it('builds agent items by contract: need = count × pack, basket exclude merged', () => {
    initFromVoice(voice())
    const id = addItem(itemFromCategory(categoryInfo('milk')!))
    setCount(id, 2)
    addItem(itemFromQuery('  буряк   червоний '))
    addItem(
      itemFromProduct({ gtin: '4823005209157', title: 'Сир Яготинський 180г', category: 'curd', pack_qty: 180, pack_unit: 'g' } as CatalogProduct),
    )
    toggleExclude('sugar')
    expect(toAgentItems(getBasketDraft()!)).toEqual([
      { category: 'milk', need: 2000, unit: 'ml', exclude: ['sugar'] },
      { query: 'буряк червоний', need: 1, unit: 'pcs', exclude: ['sugar'] },
      { gtin: '4823005209157', need: 180, unit: 'g', exclude: ['sugar'] },
    ])
  })

  it('keeps working when sessionStorage throws', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    initFromVoice(voice())
    addItem(itemFromCategory(categoryInfo('eggs')!))
    expect(getBasketDraft()?.items[0]).toMatchObject({ label: 'Яйця', count: 10, unit: 'pcs' })
  })

  it('compares voice results by text and source', () => {
    expect(isSameVoice(voice(), voice())).toBe(true)
    expect(isSameVoice(voice(), voice({ raw_text: 'кефір', text: 'кефір' }))).toBe(false)
    expect(isSameVoice(null, voice())).toBe(false)
  })

  it('adds an off-preset voice radius to the options', () => {
    expect(radiusOptions('walk', 1)).toEqual([0.5, 1, 2, 3])
    expect(radiusOptions('walk', 1.5)).toEqual([0.5, 1, 1.5, 2, 3])
  })

  it('finds categories by word prefixes and aliases', () => {
    expect(searchCategories('смет').map((c) => c.id)).toEqual(['sour_cream'])
    expect(searchCategories('сирники').map((c) => c.id)).toEqual(['curd'])
    expect(searchCategories('кава зер').map((c) => c.id)).toEqual(['coffee_beans'])
    expect(searchCategories('x')).toEqual([])
  })
})
