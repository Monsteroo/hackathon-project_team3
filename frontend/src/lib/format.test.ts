import { describe, expect, it } from 'vitest'
import { formatDistance, formatPrice, formatSavings, formatUnitPrice, formatWalk } from './format'

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
})
