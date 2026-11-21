import { describe, expect, it } from 'vitest'
import { filterCities, nearestCity, normalizeCityQuery, pluralChains, pluralCities } from './cities'

describe('cities', () => {
  it('normalizes case, apostrophes and «м.» prefix', () => {
    expect(normalizeCityQuery('  м. КИЇВ ')).toBe('київ')
    expect(normalizeCityQuery('Кам’янське')).toBe('камянське')
  })

  it('finds cities by Cyrillic prefix and Latin aliases', () => {
    expect(filterCities('ки').map((c) => c.id)).toEqual(['kyiv'])
    expect(filterCities('kiev').map((c) => c.id)).toEqual(['kyiv'])
    // Демо: лише Київ (бекенд geo обслуговує тільки його).
    expect(filterCities('lviv')).toEqual([])
    expect(filterCities('Ужгород')).toEqual([])
    expect(filterCities('')).toHaveLength(1)
  })

  it('picks nearest city within 60 km', () => {
    expect(nearestCity(50.43, 30.6)?.id).toBe('kyiv') // Лівий берег
    expect(nearestCity(49.84, 24.03)).toBeNull() // Львів: поза демо
    expect(nearestCity(48.62, 22.29)).toBeNull() // Ужгород
  })

  it('pluralizes in Ukrainian', () => {
    expect(pluralCities(1)).toBe('1 місто')
    expect(pluralCities(3)).toBe('3 міста')
    expect(pluralCities(5)).toBe('5 міст')
    expect(pluralCities(11)).toBe('11 міст')
    expect(pluralChains(4)).toBe('4 мережі')
    expect(pluralChains(6)).toBe('6 мереж')
  })
})
