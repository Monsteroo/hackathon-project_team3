import { describe, expect, it } from 'vitest'
import { addressForPosition } from './position'

const at = { lat: 50.4501, lng: 30.5234 }

describe('addressForPosition', () => {
  it('returns the reverse-geocoded label', async () => {
    expect(await addressForPosition(at, async () => ({ label: 'вулиця Хрещатик, 22, Київ' }))).toBe(
      'вулиця Хрещатик, 22, Київ',
    )
  })

  it('falls back to null on error (e.g. outside the service area)', async () => {
    expect(await addressForPosition(at, async () => Promise.reject(new Error('422')))).toBeNull()
  })

  it('does not block on a slow geocoder', async () => {
    const never = () => new Promise<{ label: string }>(() => {})
    expect(await addressForPosition(at, never, 10)).toBeNull()
  })
})
