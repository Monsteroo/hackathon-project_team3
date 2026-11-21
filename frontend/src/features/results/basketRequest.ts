import type { BasketRequest } from '../../lib/api/types'
import type { Origin } from '../location/position'
import type { BasketDraft, Tag, Unit } from '../basket/types'

/** Теги складу, які розуміє агент (backend/app/agent/schemas.py, ExcludeTag). */
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

/**
 * Чернетка екрана 2 → текст для /agent/basket. Агент приймає лише текст і розбирає його заново,
 * тому збираємо його з того, що людина бачила й правила: позиції з кількістю, склад, бюджет.
 * Режим і радіус ідуть окремими полями (головніші за текст).
 */
export function draftToText(draft: BasketDraft): string {
  // Лише перша літера мала: бренди («Галичина») лишаються як є.
  const items = draft.items.map((i) => `${lowerFirst(i.label)} ${quantityText(i.count * i.packQty, i.unit)}`)
  const limits = [...new Set(draft.exclude)].flatMap((t) => EXCLUDE_TEXT[t] ?? [])
  if (draft.budget != null) limits.push(`до ${draft.budget} грн`)
  return [items.join(', '), ...limits].filter(Boolean).join(', ')
}

/** Фільтри, які агент поки не вміє (напр. «без власних марок»): показати попередження. */
export function unsupportedExcludes(draft: BasketDraft): Tag[] {
  return draft.exclude.filter((t) => !EXCLUDE_TEXT[t])
}

export function toBasketRequest(draft: BasketDraft, origin: Origin, city?: string): BasketRequest {
  return {
    text: draftToText(draft),
    raw_text: draft.voice?.raw_text ?? null,
    lat: origin.lat,
    lng: origin.lng,
    mode: draft.mode,
    radius_km: draft.radiusKm,
    ...(city ? { city } : {}),
  }
}
