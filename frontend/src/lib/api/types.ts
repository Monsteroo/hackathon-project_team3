/**
 * Контракт модулів geo і voice бекенду (tools/geo-voice-testbench/HANDOFF.md, розділ «TypeScript-типи»).
 * Реальні відповіді: mocks/09_* … mocks/15_*.
 */

export type Mode = 'walk' | 'car'
export type StoreSource = 'zakaz' | 'silpo' | 'osm'

export interface MapsUrls {
  walking: string
  driving: string
  transit: string
}

export interface Store {
  /** Zakaz: "482010105", Сільпо: uuid — як у /catalog; OSM без цін: "osm:n123". */
  store_id: string
  source: StoreSource
  chain: string
  /** «Сільпо», «NOVUS» — для показу. */
  chain_name: string
  name: string
  city: string
  address: string
  lat: number
  lng: number
  /** Однаковий для магазинів в одній будівлі: групуйте маркери. */
  place_id: string
  alt_store_ids: string[]
  has_online_prices: boolean
  offers_count: number | null
  online_catalog: boolean
  has_pickup: boolean
}

export interface NearbyStore extends Store {
  confirmed: boolean
  /** false — магазин з цінами поза радіусом, доданий, щоб було куди вести. */
  in_radius: boolean
  straight_km: number
  distance_km: number
  duration_min: number
  /** Valhalla недоступний — оцінка за прямою, показуйте «≈». */
  estimated: boolean
  maps_urls: MapsUrls
}

export interface NearbyResponse {
  origin: { lat: number; lng: number }
  mode: Mode
  radius_km: number
  /** У радіусі було порожньо — радіус подвоєно. */
  radius_expanded: boolean
  routing: 'valhalla' | 'mixed' | 'estimated'
  recommended_store_id: string | null
  recommended_reason: 'confirmed_offer' | 'nearest_with_online_prices' | null
  unknown_store_ids: string[]
  count: number
  /** Уже відсортовані за duration_min. */
  stores: NearbyStore[]
}

export interface RouteResponse {
  store_id: string
  source: StoreSource
  chain: string
  mode: Mode
  distance_km: number
  duration_min: number
  /** true → geometry — пряма з двох точок. */
  estimated: boolean
  /** [lng, lat] — готово для MapLibre. */
  geometry: { type: 'LineString'; coordinates: [number, number][] }
  maps_urls: MapsUrls
}

export interface Place {
  /** «вулиця Хрещатик, 22, Київ». */
  label: string
  full: string
  lat: number
  lng: number
  /** coords — адресу не знайдено, label = "50.44980, 30.52310". */
  source: 'nominatim' | 'photon' | 'coords'
}

export interface GeocodeResponse {
  results: Place[]
}

export type VoiceSource = 'groq_whisper' | 'manual' | 'web_speech'

export interface VoiceResult {
  /** Очищений запит → агенту. */
  text: string
  /** Що почули — показати користувачу. */
  raw_text: string
  /** null — не згадано, лишити перемикач як є. */
  mode: Mode | null
  /** null — дефолт /geo (пішки 2 км, авто 10 км). */
  radius_km: number | null
  duration_s: number | null
  source: VoiceSource
  cleanup: {
    model: string | null
    /** rejected → text = raw_text. */
    guard: 'ok' | 'rejected' | 'skipped' | 'llm_unavailable'
    new_words: string[]
    issues: Record<string, unknown[]>
    tokens: number
  }
}

// --- catalog (backend/app/catalog/schemas.py, mocks/01_* … 08_*) ---

export interface CatalogStore {
  store_id: string
  source: 'zakaz' | 'silpo'
  chain: string
  name: string
  city: string | null
  address: string | null
  lat: number | null
  lng: number | null
  has_pickup: boolean
  offers_count: number
}

export interface CatalogPrice {
  store_id: string
  chain: string
  store_name: string
  city: string | null
  address: string | null
  /** Грн за пачку; для вагових товарів — за кг. */
  price: number
  old_price: number | null
  promo_percent: number | null
  promo_until: string | null
  unit_price: number | null
  unit_price_label: string
  in_stock: boolean
  stock: number | null
  url: string | null
  fetched_at: string
}

export interface CatalogProduct {
  product_id: number
  gtin: string | null
  title: string
  brand: string | null
  /** Канонічна категорія: milk, curd, eggs, … */
  category: string | null
  pack_qty: number | null
  pack_unit: 'g' | 'ml' | 'pcs' | null
  fat_pct: number | null
  tags: string[]
  /** false — склад невідомий, це не те саме, що «чистий». */
  composition_known: boolean
  img_url: string | null
  stores_count: number
  min_price: number
  max_price: number
  min_unit_price: number | null
  prices: CatalogPrice[]
}

export interface PriceSearchResponse {
  query: string
  tokens: string[]
  store_ids: string[]
  missing_store_ids: string[]
  products: CatalogProduct[]
}
