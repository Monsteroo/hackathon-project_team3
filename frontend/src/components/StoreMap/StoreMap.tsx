import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useRef } from 'react'
import styles from './StoreMap.module.css'

/** Безкоштовні векторні тайли OSM, без API-ключа. */
const STYLE_URL = 'https://tiles.openfreemap.org/styles/positron'
const KYIV_CENTER: [number, number] = [30.5234, 50.4501]

type Props = {
  center?: [number, number]
  zoom?: number
  /** Доступна назва карти для скрінрідерів. */
  label?: string
}

export function StoreMap({ center = KYIV_CENTER, zoom = 13, label = 'Карта магазинів поруч' }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)

  const [lng, lat] = center

  useEffect(() => {
    if (!containerRef.current) return
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE_URL,
      center: [lng, lat],
      zoom,
      attributionControl: { compact: true },
    })
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')

    // Підписи українською, якщо є name:uk; інакше — локальна назва.
    map.on('style.load', () => {
      for (const layer of map.getStyle().layers ?? []) {
        if (layer.type === 'symbol' && map.getLayoutProperty(layer.id, 'text-field')) {
          map.setLayoutProperty(layer.id, 'text-field', [
            'coalesce',
            ['get', 'name:uk'],
            ['get', 'name'],
          ])
        }
      }
    })

    return () => map.remove()
  }, [lng, lat, zoom])

  return <div ref={containerRef} className={styles.map} role="region" aria-label={label} />
}
