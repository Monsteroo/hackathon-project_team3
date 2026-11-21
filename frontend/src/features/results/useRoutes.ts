import { useEffect, useState } from 'react'
import type { MapRoute } from '../../components/StoreMap/StoreMap'
import { api } from '../../lib/api/client'
import type { AgentBasket, Mode } from '../../lib/api/types'
import type { Origin } from '../location/position'

type Point = { lat: number; lng: number }
export type RouteLeg = { from: Point; storeId: string; to: Point }

/**
 * Відрізки маршруту варіанту: людина → магазин; для Smart Split — людина → ближчий → дальший
 * (той самий порядок, що й у посиланні Google Maps, `routeUrl`).
 */
export function routeLegs(basket: AgentBasket | null, origin: Point | null): RouteLeg[] {
  if (!basket || !origin || basket.stores.length === 0) return []
  const ordered = [...basket.stores].sort((a, b) => a.distance_km - b.distance_km)
  const legs: RouteLeg[] = []
  let from: Point = origin
  for (const s of ordered) {
    const to = { lat: s.lat, lng: s.lng }
    legs.push({ from, storeId: s.store_id, to })
    from = to
  }
  return legs
}

/** Пряма — якщо /geo/route недоступний: лінія все одно видна, пунктиром. */
export function straightLine(leg: RouteLeg): MapRoute {
  return {
    coordinates: [
      [leg.from.lng, leg.from.lat],
      [leg.to.lng, leg.to.lat],
    ],
    estimated: true,
  }
}

const cache = new Map<string, MapRoute>()
const legKey = (leg: RouteLeg, mode: Mode) =>
  `${leg.from.lat.toFixed(5)},${leg.from.lng.toFixed(5)}|${leg.storeId}|${mode}`

/** Лінія маршруту для карти: /geo/route на кожен відрізок, кеш у пам'яті між перемиканнями варіантів. */
export function useRoutes(basket: AgentBasket | null, origin: Origin | null, mode: Mode): MapRoute[] {
  const legs = routeLegs(basket, origin)
  const key = legs.map((l) => legKey(l, mode)).join(';')
  const [state, setState] = useState<{ key: string; routes: MapRoute[] }>({ key: '', routes: [] })

  useEffect(() => {
    if (!key) return
    let cancelled = false
    const current = routeLegs(basket, origin)
    Promise.all(
      current.map(async (leg) => {
        const k = legKey(leg, mode)
        const hit = cache.get(k)
        if (hit) return hit
        try {
          const r = await api.route({ lat: leg.from.lat, lng: leg.from.lng, storeId: leg.storeId, mode })
          const route = { coordinates: r.geometry.coordinates, estimated: r.estimated }
          cache.set(k, route)
          return route
        } catch {
          return straightLine(leg)
        }
      }),
    ).then((routes) => {
      if (!cancelled) setState({ key, routes })
    })
    return () => {
      cancelled = true
    }
    // basket/origin читаємо лише через key: масиви з батька нові на кожному рендері.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  // Поки нова лінія вантажиться — пряма, щоб не показувати маршрут попереднього варіанту.
  if (!key) return []
  return state.key === key ? state.routes : legs.map(straightLine)
}
