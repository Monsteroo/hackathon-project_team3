import { api } from '../../lib/api/client'
import type { Mode, ParsedRequest, RequestedItem, VoiceResult } from '../../lib/api/types'
import { categoryInfo } from './categories'
import { MAX_COUNT, MIN_COUNT } from './draftStore'
import type { BasketItem, Tag } from './types'

/** ok — є позиції; empty — агент відповів, але продуктів не знайшов; unavailable — агент недоступний. */
export type ParseStatus = 'ok' | 'empty' | 'unavailable'

/** Що агент зрозумів із запиту: позиції для списку й обмеження для чернетки. */
export interface ParsedDraft {
  status: ParseStatus
  items: Omit<BasketItem, 'id'>[]
  budget: number | null
  exclude: Tag[]
  /** null — у тексті не сказано (агент за замовчуванням ставить walk, тому беремо лише car). */
  mode: Mode | null
  radiusKm: number | null
}

const NOTHING = { items: [], budget: null, exclude: [], mode: null, radiusKm: null }

function clampCount(n: number): number {
  return Math.min(Math.max(Math.round(n), MIN_COUNT), MAX_COUNT)
}

function capitalize(text: string): string {
  return text.charAt(0).toLocaleUpperCase('uk') + text.slice(1)
}

/**
 * Позиція агента → рядок екрана 2. Кількість переводимо в пачки типової для категорії фасовки.
 * Агент іноді дає штуки для пачкових категорій («кава: 1 pcs») — тоді це кількість пачок.
 */
export function itemFromRequested(r: RequestedItem): Omit<BasketItem, 'id'> {
  const cat = categoryInfo(r.category ?? undefined)
  const brand = r.brand?.trim() || null
  const label = capitalize(brand ? `${r.name} ${brand}` : r.name)
  const quantity = r.quantity > 0 ? r.quantity : 1
  // Бренд звужує пошук: категорія сама по собі його загубить.
  const query = brand ? `${r.search_query} ${brand}` : cat ? undefined : r.search_query

  if (cat && cat.unit === r.unit) {
    return {
      label,
      category: cat.id,
      query,
      count: clampCount(Math.ceil(quantity / cat.packQty)),
      packQty: cat.packQty,
      unit: cat.unit,
      exclude: [],
    }
  }
  if (cat && r.unit === 'pcs') {
    return { label, category: cat.id, query, count: clampCount(quantity), packQty: cat.packQty, unit: cat.unit, exclude: [] }
  }
  if (r.unit === 'pcs') {
    return { label, category: cat?.id, query: query ?? r.search_query, count: clampCount(quantity), packQty: 1, unit: 'pcs', exclude: [] }
  }
  // Вага чи об'єм без відомої фасовки: одна «пачка» потрібного розміру.
  return { label, category: cat?.id, query: query ?? r.search_query, count: 1, packQty: quantity, unit: r.unit, exclude: [] }
}

export function draftFromParsed(parsed: ParsedRequest): ParsedDraft {
  const c = parsed.constraints
  return {
    status: parsed.items.length > 0 ? 'ok' : 'empty',
    items: parsed.items.map(itemFromRequested),
    budget: c.budget_uah != null && c.budget_uah > 0 ? c.budget_uah : null,
    exclude: [...new Set(c.exclude)],
    mode: c.travel_mode === 'car' ? 'car' : null,
    radiusKm: c.radius_km != null && c.radius_km > 0 ? c.radius_km : null,
  }
}

/**
 * Розбір запиту агентом (`POST /agent/parse`). Агент недоступний чи нічого не знайшов — порожній
 * список зі статусом, і людина додає товари вручну.
 */
export async function parseItems(voice: VoiceResult, signal?: AbortSignal): Promise<ParsedDraft> {
  const text = voice.text.trim() || voice.raw_text.trim()
  if (!text) return { status: 'empty', ...NOTHING }
  try {
    return draftFromParsed(await api.parseRequest(text, signal))
  } catch (e) {
    if ((e as Error)?.name === 'AbortError') throw e
    return { status: 'unavailable', ...NOTHING }
  }
}
