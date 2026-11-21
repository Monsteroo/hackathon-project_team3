import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useRef, useState } from 'react'
import styles from './StoreMap.module.css'

/** Безкоштовні векторні тайли OSM, без API-ключа. */
const STYLE_URL = 'https://tiles.openfreemap.org/styles/positron'
const KYIV_CENTER: [number, number] = [30.5234, 50.4501]

export interface MapPin {
  id: string
  lat: number
  lng: number
  /** Монограма мережі всередині піна. */
  text: string
  /** Підказка при наведенні: мережа й адреса. */
  title: string
}

/** Відрізок маршруту з /geo/route: [lng, lat]. estimated → пряма-оцінка, малюємо пунктиром. */
export interface MapRoute {
  coordinates: [number, number][]
  estimated: boolean
}

const ROUTE_SOURCE = 'route'
const ROUTE_LAYERS = ['route-casing', 'route-line', 'route-line-estimated'] as const

/** Колір із дизайн-токена (сирі hex у коді заборонено; MapLibre не розуміє CSS-змінні). */
function tokenColor(el: Element, name: string, fallback: string): string {
  return getComputedStyle(el).getPropertyValue(name).trim() || fallback
}

function routeData(routes: MapRoute[]) {
  return {
    type: 'FeatureCollection' as const,
    features: routes
      .filter((r) => r.coordinates.length >= 2)
      .map((r) => ({
        type: 'Feature' as const,
        properties: { estimated: r.estimated },
        geometry: { type: 'LineString' as const, coordinates: r.coordinates },
      })),
  }
}

type Props = {
  center?: [number, number]
  zoom?: number
  /** Доступна назва карти для скрінрідерів. */
  label?: string
  className?: string
  /** Позиція людини: лаймове коло з чорною обводкою (MASTER, Map). */
  origin?: { lat: number; lng: number } | null
  pins?: MapPin[]
  /** Піни вибраного варіанту: лаймові, карта підлаштовується під них і origin. */
  selectedIds?: string[]
  /** Наведення на картку підсвічує пін. */
  hoverIds?: string[]
  onPinClick?: (id: string) => void
  /** Маршрут від людини до магазину(-ів) вибраного варіанту. */
  routes?: MapRoute[]
}

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
}

/**
 * Карта MapLibre. Піни — HTML-маркери з aria-hidden: вибір доступний через картки (radiogroup),
 * клік на пін — лише дубль для миші.
 */
export function StoreMap({
  center = KYIV_CENTER,
  zoom = 13,
  label = 'Карта магазинів поруч',
  className,
  origin,
  pins,
  selectedIds,
  hoverIds,
  onPinClick,
  routes,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<maplibregl.Map | null>(null)
  /** Джерела й шари можна додавати лише після завантаження стилю. */
  const [styleReady, setStyleReady] = useState(false)
  const markersRef = useRef(new Map<string, { marker: maplibregl.Marker; el: HTMLElement }>())
  const onPinClickRef = useRef(onPinClick)
  useEffect(() => {
    onPinClickRef.current = onPinClick
  }, [onPinClick])
  const initial = useRef({ center, zoom })

  const [lng, lat] = center
  const originLat = origin?.lat
  /** Піни порівнюються за вмістом: масив з батька може бути новим на кожному рендері. */
  const pinsKey = (pins ?? []).map((p) => `${p.id}:${p.lat}:${p.lng}:${p.text}`).join('|')
  const pinsRef = useRef(pins)
  useEffect(() => {
    pinsRef.current = pins
  })
  const originLng = origin?.lng

  // Карта створюється один раз; центр і піни оновлюються окремими ефектами.
  useEffect(() => {
    if (!containerRef.current) return
    const m = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE_URL,
      center: initial.current.center,
      zoom: initial.current.zoom,
      attributionControl: { compact: true },
    })
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')

    // Підписи українською, якщо є name:uk; інакше — локальна назва.
    m.on('style.load', () => {
      for (const layer of m.getStyle().layers ?? []) {
        if (layer.type === 'symbol' && m.getLayoutProperty(layer.id, 'text-field')) {
          m.setLayoutProperty(layer.id, 'text-field', ['coalesce', ['get', 'name:uk'], ['get', 'name']])
        }
      }
    })
    m.on('load', () => setStyleReady(true))
    setMap(m)

    const markers = markersRef.current
    return () => {
      markers.clear()
      m.remove()
      setMap(null)
      setStyleReady(false)
    }
  }, [])

  // Лінія маршруту: обводка графітом + лайм (як вибраний пін), оцінка за прямою — пунктиром.
  const routesKey = (routes ?? [])
    .map((r) => `${r.estimated ? 'e' : 'r'}:${r.coordinates.length}:${r.coordinates[0]?.join(',')}:${r.coordinates.at(-1)?.join(',')}`)
    .join('|')
  const routesRef = useRef(routes)
  useEffect(() => {
    routesRef.current = routes
  })
  useEffect(() => {
    const el = containerRef.current
    if (!map || !styleReady || !el) return
    const data = routeData(routesRef.current ?? [])
    const source = map.getSource(ROUTE_SOURCE) as maplibregl.GeoJSONSource | undefined
    if (source) {
      source.setData(data)
      return
    }
    const ink = tokenColor(el, '--color-accent-fg', 'black')
    const accent = tokenColor(el, '--color-accent', 'yellowgreen')
    map.addSource(ROUTE_SOURCE, { type: 'geojson', data })
    // Під пінами HTML-маркерів шари лежать і так; додаємо поверх базової карти.
    map.addLayer({
      id: ROUTE_LAYERS[0],
      type: 'line',
      source: ROUTE_SOURCE,
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': ink, 'line-width': 8, 'line-opacity': 0.85 },
    })
    map.addLayer({
      id: ROUTE_LAYERS[1],
      type: 'line',
      source: ROUTE_SOURCE,
      filter: ['!=', ['get', 'estimated'], true],
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': accent, 'line-width': 5 },
    })
    map.addLayer({
      id: ROUTE_LAYERS[2],
      type: 'line',
      source: ROUTE_SOURCE,
      filter: ['==', ['get', 'estimated'], true],
      layout: { 'line-join': 'round', 'line-cap': 'butt' },
      paint: { 'line-color': accent, 'line-width': 5, 'line-dasharray': [1.5, 1.5] },
    })
  }, [map, styleReady, routesKey])

  // Без пінів — просто центр (напр. місто).
  useEffect(() => {
    if (!map || pinsKey) return
    map.jumpTo({ center: [lng, lat] })
  }, [map, lng, lat, pinsKey])

  // Позиція людини.
  useEffect(() => {
    if (!map || originLat == null || originLng == null) return
    const el = document.createElement('div')
    el.className = styles.me
    el.setAttribute('aria-hidden', 'true')
    const marker = new maplibregl.Marker({ element: el }).setLngLat([originLng, originLat]).addTo(map)
    return () => {
      marker.remove()
    }
  }, [map, originLat, originLng])

  // Піни магазинів.
  useEffect(() => {
    const pins = pinsRef.current
    if (!map || !pins) return
    const markers = markersRef.current
    for (const pin of pins) {
      const el = document.createElement('div')
      el.className = styles.pin
      el.setAttribute('aria-hidden', 'true')
      el.title = pin.title
      const body = document.createElement('span')
      body.className = styles.pinBody
      const logo = document.createElement('span')
      logo.className = styles.logo
      logo.textContent = pin.text
      body.append(logo)
      el.append(body)
      el.addEventListener('click', (e) => {
        e.stopPropagation()
        onPinClickRef.current?.(pin.id)
      })
      const marker = new maplibregl.Marker({ element: el }).setLngLat([pin.lng, pin.lat]).addTo(map)
      markers.set(pin.id, { marker, el })
    }
    return () => {
      for (const { marker } of markers.values()) marker.remove()
      markers.clear()
    }
  }, [map, pinsKey])

  // Вибраний варіант: підсвітка й рамка карти.
  const selectedKey = (selectedIds ?? []).join('|')
  useEffect(() => {
    const pins = pinsRef.current
    if (!map || !pins) return
    const selected = new Set(selectedKey ? selectedKey.split('|') : [])
    for (const [id, { el }] of markersRef.current) {
      el.classList.toggle(styles.selected, selected.has(id))
    }
    const points = pins.filter((p) => selected.has(p.id)).map((p) => [p.lng, p.lat] as [number, number])
    if (originLat != null && originLng != null) points.push([originLng, originLat])
    // Маршрут може вигинатися за межі прямокутника «людина — магазин»: він теж має влізти в кадр.
    for (const r of routesRef.current ?? []) points.push(...r.coordinates)
    if (points.length === 0) return
    const bounds = points.reduce(
      (b, p) => b.extend(p),
      new maplibregl.LngLatBounds(points[0], points[0]),
    )
    // Зверху — місце під чип адреси.
    map.fitBounds(bounds, { padding: { top: 96, right: 64, bottom: 80, left: 48 }, maxZoom: 15, duration: prefersReducedMotion() ? 0 : 600 })
  }, [map, pinsKey, selectedKey, originLat, originLng, routesKey])

  const hoverKey = (hoverIds ?? []).join('|')
  useEffect(() => {
    const hover = new Set(hoverKey ? hoverKey.split('|') : [])
    for (const [id, { el }] of markersRef.current) el.classList.toggle(styles.hover, hover.has(id))
  }, [hoverKey, pinsKey, map])

  return (
    <div
      ref={containerRef}
      className={[styles.map, className].filter(Boolean).join(' ')}
      role="region"
      aria-label={label}
    />
  )
}
