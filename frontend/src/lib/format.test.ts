import { describe, expect, it } from 'vitest'
import {
  formatClock,
  formatDistance,
  formatInteger,
  formatPack,
  formatPrice,
  formatRoundPrice,
  formatSavings,
  formatUnitPrice,
  formatWalk,
  pluralItems,
} from './format'

describe('format (uk-UA)', () => {
  it('formats pack price with narrow nbsp thousands and comma', () => {
    expect(formatPrice(1249.9)).toBe('1 249,90 ₴')
    expect(formatPrice(72.2)).toBe('72,20 ₴')
  })

  it('formats unit price', () => {
    expect(formatUnitPrice(112.4, 'кг')).toBe('112,40 ₴/кг')
  })

  it('formats savings with real minus', () => {
    expect(formatSavings(75)).toBe('−75 ₴')
    expect(formatSavings(97.5)).toBe('−97,50 ₴')
  })

  it('formats distance', () => {
    expect(formatDistance(450)).toBe('450 м')
    expect(formatDistance(1200)).toBe('1,2 км')
    expect(formatDistance(2000)).toBe('2 км')
    expect(formatWalk(450, 6)).toBe('450 м · 6 хв пішки')
  })

  it('formats recording time as m:ss', () => {
    expect(formatClock(0)).toBe('0:00')
    expect(formatClock(7.9)).toBe('0:07')
    expect(formatClock(65)).toBe('1:05')
  })
  it('formats whole-hryvnia budget and integers', () => {
    expect(formatRoundPrice(1500)).toBe('1\u202f500\u00a0₴')
    expect(formatRoundPrice(500)).toBe('500\u00a0₴')
    expect(formatInteger(12000)).toBe('12\u202f000')
  })

  it('formats pack size', () => {
    expect(formatPack(1000, 'ml')).toBe('1\u00a0л')
    expect(formatPack(1500, 'g')).toBe('1,5\u00a0кг')
    expect(formatPack(350, 'g')).toBe('350\u00a0г')
    expect(formatPack(1, 'pcs')).toBe('поштучно')
    expect(formatPack(10, 'pcs')).toBe('10\u00a0шт')
  })

  it('pluralizes items', () => {
    expect(pluralItems(1)).toBe('1 товар')
    expect(pluralItems(3)).toBe('3 товари')
    expect(pluralItems(11)).toBe('11 товарів')
    expect(pluralItems(21)).toBe('21 товар')
  })
})
