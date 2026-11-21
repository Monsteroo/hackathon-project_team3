import type { BasketOut, BasketRequest } from '../../lib/api/types'
import type { Origin } from '../location/position'

/**
 * Останній результат /agent/basket у sessionStorage: «Назад» з екрана 4 і перезавантаження
 * не запускають агента вдруге (5–9 с). Новий запит — новий ключ.
 */
const STORAGE_KEY = 'sayvy.basketResult'

export interface SavedResult {
  key: string
  origin: Origin
  request: BasketRequest
  result: BasketOut
  /** ISO-час, коли отримали. */
  savedAt: string
}

let memory: SavedResult | null = null

export function requestKey(request: BasketRequest): string {
  return JSON.stringify([
    request.items, request.budget_uah, request.text, request.lat, request.lng, request.mode, request.radius_km, request.city,
  ])
}

export function loadResult(): SavedResult | null {
  if (memory) return memory
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    memory = raw ? (JSON.parse(raw) as SavedResult) : null
  } catch {
    memory = null
  }
  return memory
}

export function saveResult(saved: SavedResult) {
  memory = saved
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(saved))
  } catch {
    // приватний режим: результат живе до перезавантаження
  }
}

export function clearResult() {
  memory = null
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // нічого
  }
}
