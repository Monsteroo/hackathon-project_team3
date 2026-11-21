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
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<maplibregl.Map | null>(null)
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
    setMap(m)

    const markers = markersRef.current
    return () => {
      markers.clear()
      m.remove()
      setMap(null)
    }
  }, [])

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
    if (points.length === 0) return
    const bounds = points.reduce(
      (b, p) => b.extend(p),
      new maplibregl.LngLatBounds(points[0], points[0]),
    )
    // Зверху — місце під чип адреси.
    map.fitBounds(bounds, { padding: { top: 96, right: 64, bottom: 80, left: 48 }, maxZoom: 15, duration: prefersReducedMotion() ? 0 : 600 })
  }, [map, pinsKey, selectedKey, originLat, originLng])

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
