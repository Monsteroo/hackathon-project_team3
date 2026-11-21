import { describe, expect, it } from 'vitest'
import type { AgentBasket, AgentStore } from '../../lib/api/types'
import { routeLegs, straightLine } from './useRoutes'

const store = (id: string, lat: number, lng: number, distance_km: number) =>
  ({ store_id: id, lat, lng, distance_km }) as AgentStore
const basket = (stores: AgentStore[]) => ({ stores }) as AgentBasket
const origin = { lat: 50.45, lng: 30.52 }

describe('routeLegs', () => {
  it('one store: origin → store', () => {
    expect(routeLegs(basket([store('a', 50.46, 30.53, 1.2)]), origin)).toEqual([
      { from: origin, storeId: 'a', to: { lat: 50.46, lng: 30.53 } },
    ])
  })

  it('smart split: origin → nearer → farther, like the Google Maps link', () => {
    const legs = routeLegs(basket([store('far', 50.5, 30.6, 5), store('near', 50.46, 30.53, 1)]), origin)
    expect(legs.map((l) => l.storeId)).toEqual(['near', 'far'])
    expect(legs[1].from).toEqual({ lat: 50.46, lng: 30.53 })
  })

  it('no basket or origin: no legs', () => {
    expect(routeLegs(null, origin)).toEqual([])
    expect(routeLegs(basket([store('a', 50.46, 30.53, 1)]), null)).toEqual([])
  })

  it('fallback line is [lng, lat] and marked estimated', () => {
    const [leg] = routeLegs(basket([store('a', 50.46, 30.53, 1)]), origin)
    expect(straightLine(leg)).toEqual({ coordinates: [[30.52, 50.45], [30.53, 50.46]], estimated: true })
  })
})
