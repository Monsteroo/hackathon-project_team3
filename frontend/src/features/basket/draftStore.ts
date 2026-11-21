import { useSyncExternalStore } from 'react'
import type { AgentItem, CatalogProduct, Mode, VoiceResult } from '../../lib/api/types'
import { categoryInfo, type CategoryInfo } from './categories'
import type { BasketDraft, BasketItem, Tag, Unit } from './types'

/**
 * Чернетка кошика екрана 2. Зберігається в sessionStorage, щоб пережити «Назад» з /results
 * і перезавантаження сторінки. Сховище може бути недоступне — тоді лише в пам'яті.
 */
const STORAGE_KEY = 'sayvy.basketDraft'

/** Дефолтний радіус /geo (backend/app/geo/routing.py, DEFAULT_RADIUS_KM). */
export const DEFAULT_RADIUS_KM: Record<Mode, number> = { walk: 2, car: 10 }
/** Межа радіуса /geo (MAX_RADIUS_KM). */
export const MAX_RADIUS_KM = 50
export const RADIUS_PRESETS_KM: Record<Mode, number[]> = { walk: [0.5, 1, 2, 3], car: [3, 5, 10, 20] }

export const MIN_COUNT = 1
export const MAX_COUNT = 99

const listeners = new Set<() => void>()
let current: BasketDraft | null | undefined

function read(): BasketDraft | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as BasketDraft) : null
  } catch {
    return null
  }
}

function getSnapshot(): BasketDraft | null {
  if (current === undefined) current = read()
  return current
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function commit(next: BasketDraft | null) {
  current = next
  try {
    if (next) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    else sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // приватний режим або заблоковане сховище: чернетка живе до перезавантаження
  }
  listeners.forEach((l) => l())
}

function update(fn: (d: BasketDraft) => BasketDraft) {
  const d = getSnapshot()
  if (d) commit(fn(d))
}

export function useBasketDraft(): BasketDraft | null {
  return useSyncExternalStore(subscribe, getSnapshot, () => null)
}

export function getBasketDraft(): BasketDraft | null {
  return getSnapshot()
}

/** Той самий запит: повернулися з /results, правки не скидаємо. */
export function isSameVoice(a: VoiceResult | null, b: VoiceResult | null): boolean {
  return !!a && !!b && a.raw_text === b.raw_text && a.text === b.text && a.source === b.source
}

function clampRadius(km: number): number {
  return Math.min(Math.max(km, 0.1), MAX_RADIUS_KM)
}

/** Новий запит з екрана 1: режим і радіус з голосу, null → дефолти /geo. */
export function initFromVoice(voice: VoiceResult) {
  const mode = voice.mode ?? 'walk'
  commit({
    voice,
    items: [],
    budget: null,
    exclude: [],
    mode,
    radiusKm: voice.radius_km != null ? clampRadius(voice.radius_km) : DEFAULT_RADIUS_KM[mode],
  })
}

/** Порожня чернетка без запиту, напр. перший вхід на /confirm напряму. */
export function initEmpty() {
  commit({ voice: null, items: [], budget: null, exclude: [], mode: 'walk', radiusKm: DEFAULT_RADIUS_KM.walk })
}

export function clearBasketDraft() {
  commit(null)
}

let seq = 0
function newId(): string {
  seq += 1
  return `${Date.now().toString(36)}-${seq}`
}

function clampCount(n: number): number {
  return Math.min(Math.max(Math.round(n), MIN_COUNT), MAX_COUNT)
}

/** Ключ однакової позиції: той самий GTIN, категорія або текст. */
function sameKey(a: BasketItem, b: BasketItem): boolean {
  if (a.gtin || b.gtin) return a.gtin === b.gtin
  if (a.category || b.category) return a.category === b.category && !a.query && !b.query
  return (a.query ?? '').toLowerCase() === (b.query ?? '').toLowerCase()
}

/** Додає позицію. Якщо така вже є — збільшує кількість, а не дублює рядок. Повертає id рядка. */
export function addItem(item: Omit<BasketItem, 'id'>): string {
  const d = getSnapshot()
  if (!d) return ''
  const candidate = { ...item, id: newId() }
  const existing = d.items.find((i) => sameKey(i, candidate))
  if (existing) {
    commit({
      ...d,
      items: d.items.map((i) => (i.id === existing.id ? { ...i, count: clampCount(i.count + item.count) } : i)),
    })
    return existing.id
  }
  commit({ ...d, items: [...d.items, candidate] })
  return candidate.id
}

export function setCount(id: string, count: number) {
  update((d) => ({ ...d, items: d.items.map((i) => (i.id === id ? { ...i, count: clampCount(count) } : i)) }))
}

export function removeItem(id: string) {
  update((d) => ({ ...d, items: d.items.filter((i) => i.id !== id) }))
}

export function setBudget(budget: number | null) {
  update((d) => ({ ...d, budget: budget != null && budget > 0 ? Math.round(budget) : null }))
}

export function toggleExclude(tag: Tag) {
  update((d) => ({
    ...d,
    exclude: d.exclude.includes(tag) ? d.exclude.filter((t) => t !== tag) : [...d.exclude, tag],
  }))
}

/** Інший режим — інший масштаб відстаней, тому радіус повертається до дефолту режиму. */
export function setMode(mode: Mode) {
  update((d) => (d.mode === mode ? d : { ...d, mode, radiusKm: DEFAULT_RADIUS_KM[mode] }))
}

export function setRadius(km: number) {
  update((d) => ({ ...d, radiusKm: clampRadius(km) }))
}

/**
 * Обмеження з розбору агента. Не перетирає те, що вже задано: бюджет і склад лише доповнюються,
 * режим і радіус з голосу (VoiceResult) головніші за розбір тексту.
 */
export function applyConstraints(c: {
  budget: number | null
  exclude: Tag[]
  mode: Mode | null
  radiusKm: number | null
}) {
  update((d) => {
    const voiceMode = d.voice?.mode ?? null
    const voiceRadius = d.voice?.radius_km ?? null
    const mode = voiceMode ?? c.mode ?? d.mode
    let radiusKm = d.radiusKm
    if (voiceRadius == null && c.radiusKm != null) radiusKm = clampRadius(c.radiusKm)
    else if (mode !== d.mode) radiusKm = DEFAULT_RADIUS_KM[mode]
    return {
      ...d,
      budget: d.budget ?? (c.budget != null && c.budget > 0 ? Math.round(c.budget) : null),
      exclude: [...new Set([...d.exclude, ...c.exclude])],
      mode,
      radiusKm,
    }
  })
}

// --- Фабрики позицій ---

export function itemFromCategory(c: CategoryInfo): Omit<BasketItem, 'id'> {
  return { label: c.label, category: c.id, count: c.defaultCount, packQty: c.packQty, unit: c.unit, exclude: [] }
}

function isUnit(u: string | null | undefined): u is Unit {
  return u === 'g' || u === 'ml' || u === 'pcs'
}

export function itemFromProduct(p: CatalogProduct): Omit<BasketItem, 'id'> {
  const cat = categoryInfo(p.category as BasketItem['category'])
  const unit = isUnit(p.pack_unit) ? p.pack_unit : (cat?.unit ?? 'pcs')
  const packQty = p.pack_qty && p.pack_qty > 0 && isUnit(p.pack_unit) ? p.pack_qty : (cat?.packQty ?? 1)
  return {
    label: p.title,
    category: cat?.id,
    gtin: p.gtin ?? undefined,
    query: p.gtin ? undefined : p.title,
    count: 1,
    packQty,
    unit,
    exclude: [],
  }
}

export function itemFromQuery(text: string): Omit<BasketItem, 'id'> {
  const query = text.trim().replace(/\s+/g, ' ')
  const label = query.charAt(0).toLocaleUpperCase('uk') + query.slice(1)
  return { label, query, count: 1, packQty: 1, unit: 'pcs', exclude: [] }
}

/** Позиції для агента: потреба в одиницях, фільтри складу кошика + позиції. */
export function toAgentItems(draft: BasketDraft): AgentItem[] {
  return draft.items.map((i) => {
    const exclude = [...new Set([...draft.exclude, ...i.exclude])]
    const base = { label: i.label, need: i.count * i.packQty, unit: i.unit, exclude }
    if (i.gtin) return { ...base, gtin: i.gtin }
    if (i.category && !i.query) return { ...base, category: i.category }
    return { ...base, query: i.query ?? i.label }
  })
}

/** Пресети радіуса + значення з голосу, якщо його немає серед пресетів (напр. 1,5 км). */
export function radiusOptions(mode: Mode, currentKm: number): number[] {
  const presets = RADIUS_PRESETS_KM[mode]
  return presets.includes(currentKm) ? presets : [...presets, currentKm].sort((a, b) => a - b)
}

/** Орієнтовний час: пішки ~4,8 км/год (як у прототипі: 1 км ≈ 12 хв), авто ~30 км/год у місті. */
export function estimateMinutes(km: number, mode: Mode): number {
  return Math.max(1, Math.floor(km * (mode === 'walk' ? 12.5 : 2)))
}
