import type { BasketRequest } from '../../lib/api/types'
import type { Origin } from '../location/position'
import type { BasketDraft, Tag, Unit } from '../basket/types'
import { toAgentItems } from '../basket/draftStore'

/** Теги складу, які агент розпізнає під час повторного розбору тексту. */
const EXCLUDE_TEXT: Partial<Record<Tag, string>> = {
  sugar: 'без цукру',
  lactose: 'без лактози',
  palm_oil: 'без пальмової олії',
}

function lowerFirst(text: string): string {
  return text.charAt(0).toLocaleLowerCase('uk') + text.slice(1)
}

/** 800, 'g' → «800 г»; 1500, 'g' → «1,5 кг»; 10, 'pcs' → «10 шт». Звичайні пробіли: текст іде в LLM. */
export function quantityText(qty: number, unit: Unit): string {
  if (unit === 'pcs') return `${Math.round(qty)} шт`
  const [small, big] = unit === 'g' ? ['г', 'кг'] : ['мл', 'л']
  if (qty < 1000) return `${Math.round(qty)} ${small}`
  const v = (qty / 1000).toFixed(2).replace(/\.?0+$/, '').replace('.', ',')
  return `${v} ${big}`
}

/** Текстовий варіант підтвердженої чернетки для старішої версії /agent/basket. */
export function draftToText(draft: BasketDraft): string {
  // Лише перша літера мала: бренди («Галичина») лишаються як є.
  const items = draft.items.map((i) => `${lowerFirst(i.label)} ${quantityText(i.count * i.packQty, i.unit)}`)
  const limits = [...new Set(draft.exclude)].flatMap((t) => EXCLUDE_TEXT[t] ?? [])
  if (draft.budget != null) limits.push(`до ${draft.budget} грн`)
  return [items.join(', '), ...limits].filter(Boolean).join(', ')
}

/** Фільтри, які потребують структурованих позицій. */
export function unsupportedExcludes(draft: BasketDraft): Tag[] {
  return draft.exclude.filter((t) => !EXCLUDE_TEXT[t])
}

export function toBasketRequest(draft: BasketDraft, origin: Origin, city?: string): BasketRequest {
  return {
    text: draftToText(draft).slice(0, 1000),
    items: toAgentItems(draft),
    budget_uah: draft.budget,
    raw_text: draft.voice?.raw_text ?? null,
    lat: origin.lat,
    lng: origin.lng,
    mode: draft.mode,
    radius_km: draft.radiusKm,
    ...(city ? { city } : {}),
  }
}
