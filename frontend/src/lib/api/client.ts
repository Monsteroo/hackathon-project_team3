import type {
  BasketOut,
  BasketRequest,
  CatalogStore,
  GeocodeResponse,
  Mode,
  NearbyResponse,
  Place,
  ParsedRequest,
  PriceSearchResponse,
  RouteResponse,
  VoiceResult,
} from './types'

/**
 * Клієнт спільного бекенду (backend/, через проксі Vite). Порт tools/geo-voice-testbench/src/api.js.
 * Усі помилки → ApiError з `code` від бекенду; український текст для UI — `messageFor` з ./errors.
 */

/** Нормалізує базовий URL бекенду: порожній рядок локально (Vite proxy), `https://...` у продакшені. */
export function normalizeApiBase(raw: string | undefined): string {
  const trimmed = (raw ?? '').trim().replace(/\/+$/, '')
  if (!trimmed) return ''
  return /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`
}

const API_BASE = normalizeApiBase(import.meta.env.VITE_API_BASE_URL)
const API_KEY = import.meta.env.VITE_API_KEY ?? ''

/** Без ключа бекенд відповідає 401 на все: голос тоді одразу йде через Web Speech. */
export const hasApiKey = API_KEY.length > 0

/** Максимум тексту в полі запиту (екран 1). Агенту йде не більше MAX_AGENT_TEXT_LENGTH. */
export const MAX_TEXT_LENGTH = 2000

/** Максимум тексту для /agent/* (backend/app/agent/schemas.py, ParseIn). */
export const MAX_AGENT_TEXT_LENGTH = 1000

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  /** true → бекенд не впорався: перейти на Web Speech або ручний ввід. */
  readonly fallback: boolean

  constructor(code: string, message: string, { status = 0, fallback = false } = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.fallback = fallback
  }
}

type Detail = { code?: string; message?: string; fallback?: boolean }

/** detail: {code, message[, fallback]} від модулів; масив — валідація FastAPI; рядок — auth/інше. */
function toApiError(status: number, body: unknown): ApiError {
  const d = (body as { detail?: unknown } | null)?.detail
  let detail: Detail
  if (Array.isArray(d)) detail = { code: 'validation_error' }
  else if (d && typeof d === 'object') detail = d as Detail
  else detail = { code: status === 401 ? 'unauthorized' : undefined, message: typeof d === 'string' ? d : undefined }
  return new ApiError(detail.code || `http_${status}`, detail.message || 'server error', {
    status,
    fallback: detail.fallback ?? status >= 500,
  })
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, headers: { 'X-API-Key': API_KEY, ...init.headers } })
  } catch (e) {
    if ((e as Error)?.name === 'AbortError') throw e
    throw new ApiError('network', 'network error', { fallback: true })
  }
  const body: unknown = await res.json().catch(() => null)
  if (!res.ok) throw toApiError(res.status, body)
  return body as T
}

function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const entries = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => [k, String(v)])
  return new URLSearchParams(entries).toString()
}

function audioExtension(type: string): string {
  if (type.includes('mp4')) return 'm4a'
  if (type.includes('ogg')) return 'ogg'
  return 'webm'
}

type LatLng = { lat: number; lng: number }

export const api = {
  transcribe(blob: Blob, signal?: AbortSignal): Promise<VoiceResult> {
    const form = new FormData()
    form.append('audio', blob, `voice.${audioExtension(blob.type)}`)
    return request('/voice/transcribe', { method: 'POST', body: form, signal })
  },

  geocode(q: string, { suggest = false, near }: { suggest?: boolean; near?: LatLng } = {}): Promise<GeocodeResponse> {
    return request(`/geo/geocode?${qs({ q, suggest, lat: near?.lat, lng: near?.lng, limit: 5 })}`)
  },

  reverse({ lat, lng }: LatLng): Promise<Place> {
    return request(`/geo/reverse?${qs({ lat, lng })}`)
  },

  nearby({
    lat,
    lng,
    mode = 'walk',
    radiusKm,
    storeIds,
  }: LatLng & { mode?: Mode; radiusKm?: number | null; storeIds?: string[] }): Promise<NearbyResponse> {
    return request(
      `/geo/stores/nearby?${qs({ lat, lng, mode, radius_km: radiusKm, store_ids: storeIds?.join(',') })}`,
    )
  },

  route({ lat, lng, storeId, mode = 'walk' }: LatLng & { storeId: string; mode?: Mode }): Promise<RouteResponse> {
    return request(`/geo/route?${qs({ lat, lng, store_id: storeId, mode })}`)
  },

  /** Пошук товарів у каталозі: назва має містити всі слова запиту (мінімум 2 символи). */
  searchProducts(
    q: string,
    { limit = 8, exclude, signal }: { limit?: number; exclude?: string[]; signal?: AbortSignal } = {},
  ): Promise<PriceSearchResponse> {
    return request(`/catalog/prices?${qs({ q, limit, exclude: exclude?.join(',') })}`, { signal })
  },

  /** Розбір запиту агентом: позиції з категоріями й обмеження. Для екрана «Я зрозумів так». */
  parseRequest(text: string, signal?: AbortSignal): Promise<ParsedRequest> {
    return request('/agent/parse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text.slice(0, MAX_AGENT_TEXT_LENGTH) }),
      signal,
    })
  },

  /** До 3 кошиків (nearest, cheapest, smart_split). Поля VoiceResult передавайте як є. */
  buildBasket(body: BasketRequest, signal?: AbortSignal): Promise<BasketOut> {
    return request('/agent/basket', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...body, text: body.text.slice(0, MAX_AGENT_TEXT_LENGTH) }),
      signal,
    })
  },

  /** Магазини з цінами в місті. */
  catalogStores(city: string, signal?: AbortSignal): Promise<CatalogStore[]> {
    return request(`/catalog/stores?${qs({ city, with_prices: true })}`, { signal })
  },
}

/** VoiceResult для набраного тексту: текст як є. Продукти, режим, радіус і бюджет розбирає агент (/agent/parse). */
export function localVoiceResult(text: string, source: 'manual' | 'web_speech' = 'manual'): VoiceResult {
  return {
    text,
    raw_text: text,
    mode: null,
    radius_km: null,
    duration_s: null,
    source,
    cleanup: { model: null, guard: 'skipped', new_words: [], issues: {}, tokens: 0 },
  }
}
