import type { AgentBasket, AgentStore, Mode, StoreOption } from '../../lib/api/types'
import { formatDistance, formatPrice, formatRoundPrice, formatSavings, pluralItems } from '../../lib/format'
import type { Origin } from '../location/position'

/**
 * Картки варіантів екрана 3 (DESIGN.md §4.2 StoreCard): назви, рядок компромісу, мета.
 * Чисті функції без React: усі тексти тестуються окремо.
 */
export type OptionType = AgentBasket['type']

export const OPTION_TITLE: Record<OptionType, string> = {
  nearest: 'Найближчий',
  cheapest: 'Найвигідніший',
  smart_split: 'Smart Split',
  store: 'Магазин поруч',
}

/** Префікс `optionId` екрана 4 для кошика одного магазину: `/basket/store-<store_id>`. */
export const STORE_OPTION_PREFIX = 'store-'

/** Кошик одного магазину зі списку «усі магазини» у формі варіанту: ті самі картка, маршрут і деталі. */
export function storeBasket(o: StoreOption): AgentBasket {
  return {
    type: 'store',
    stores: [o.store],
    lines: o.lines,
    total: o.total,
    saving: 0,
    within_budget: o.within_budget,
    missing: o.missing,
  }
}

const NBSP = ' '

export function chainName(store: AgentStore): string {
  return store.chain_name || store.chain
}

/** Монограма, поки немає логотипів мереж у даних. */
export function monogram(store: AgentStore): string {
  return chainName(store).trim().charAt(0).toLocaleUpperCase('uk') || '?'
}

/** Варіант за замовчуванням: «Найвигідніший» (DESIGN.md §4.2, sheet peek). */
export function defaultOption(baskets: AgentBasket[]): OptionType | null {
  return baskets.find((b) => b.type === 'cheapest')?.type ?? baskets[0]?.type ?? null
}

/**
 * Найдешевший кошик серед тих, де бракує найменше товарів: Savings-бейдж лише на ньому.
 * Кошик без двох товарів дешевший «нечесно», тому спершу повнота; якщо неповний ще дешевший — бейджа немає.
 */
export function bestOption(baskets: AgentBasket[]): OptionType | null {
  // Один кошик: бекенд злив «Найближчий» і «Найвигідніший» (той самий магазин), saving — до інших магазинів.
  if (baskets.length === 1) return baskets[0].saving > 0 ? baskets[0].type : null
  if (baskets.length < 2) return null
  const fewestMissing = Math.min(...baskets.map((b) => b.missing.length))
  const complete = baskets.filter((b) => b.missing.length === fewestMissing)
  const best = complete.reduce((x, b) => (b.total < x.total ? b : x))
  // Неповний кошик ще дешевший — «найдешевший» на повному збив би з пантелику.
  return baskets.some((b) => b.total < best.total) ? null : best.type
}

/** Найдальший магазин варіанту, км: для одного магазину — його відстань. */
export function farthestKm(b: AgentBasket): number {
  return Math.max(0, ...b.stores.map((s) => s.distance_km))
}

export interface Tradeoff {
  /** Економія відносно «Найближчого», оливковим. */
  save?: string
  rest: string
}

/** Рядок компромісу: різниця завжди від варіанту «Найближчий» (DESIGN.md §4.2). */
export function tradeoff(b: AgentBasket, baskets: AgentBasket[]): Tradeoff | null {
  const nearest = baskets.find((x) => x.type === 'nearest')
  if (b.type === 'nearest' || !nearest) {
    if (b.type !== 'nearest') return null
    const cheapestToo =
      baskets.length > 1 ? baskets.every((x) => x === b || x.total >= b.total) : b.saving > 0
    return { rest: cheapestToo ? 'Найдешевший і найближчий' : 'Найближчий до вас' }
  }

  const dTotal = Math.round(b.total - nearest.total)

  if (b.type === 'smart_split') {
    if (dTotal < 0) return { save: formatSavings(-dTotal), rest: `${NBSP}за +1 магазин` }
    return { rest: '2 магазини одним маршрутом' }
  }

  const sameStore = b.stores[0]?.store_id === nearest.stores[0]?.store_id
  if (sameStore) return { rest: 'Той самий магазин, що й найближчий' }

  const dMeters = (farthestKm(b) - farthestKm(nearest)) * 1000
  if (dTotal < 0 && dMeters > 0) return { save: formatSavings(-dTotal), rest: `${NBSP}за +${formatDistance(dMeters)}` }
  if (dTotal < 0) return { save: formatSavings(-dTotal), rest: `${NBSP}і не далі` }
  if (dTotal === 0) return { rest: 'Та сама сума, що й у найближчому' }
  if (dMeters < 0) return { rest: `+${formatRoundPrice(dTotal)}, але на ${formatDistance(-dMeters)} ближче` }
  return { rest: `+${formatRoundPrice(dTotal)} до найближчого` }
}

function minutes(m: number): string {
  return `${Math.max(1, Math.round(m))}${NBSP}хв`
}

const MODE_WORD: Record<Mode, string> = { walk: 'пішки', car: 'на авто' }

/** «≈650 м · 8 хв пішки». ≈ — маршрут оцінено за прямою. */
export function distanceText(store: AgentStore, mode: Mode): string {
  const approx = store.estimated ? '≈' : ''
  return `${approx}${formatDistance(store.distance_km * 1000)} · ${minutes(store.duration_min)} ${MODE_WORD[mode]}`
}

/** «11 з 11 товарів», «4 з 4 товарів». */
export function coverageText(b: AgentBasket, requested: number): string {
  const found = Math.max(0, requested - b.missing.length)
  // Після «з» — родовий: «з 1 товару», «з 4 товарів».
  const noun = requested % 10 === 1 && requested % 100 !== 11 ? 'товару' : 'товарів'
  return `${found} з ${requested} ${noun}`
}

/** null — бюджету немає. */
export function budgetText(b: AgentBasket, budget: number | null): string | null {
  if (budget == null) return null
  if (b.within_budget || b.total <= budget) return 'у бюджеті'
  return `+${formatRoundPrice(b.total - budget)} понад бюджет`
}

/** «Немає 1 товару / 2 товарів». */
export function missingBadge(n: number): string {
  return n % 10 === 1 && n % 100 !== 11 ? `Немає ${n} товару` : `Немає ${n} товарів`
}

export interface SplitRow {
  store: AgentStore
  items: string
  subtotal: string
}

/** Smart Split: підсумок кожного магазину. */
export function splitRows(b: AgentBasket): SplitRow[] {
  return b.stores.map((store) => {
    const lines = b.lines.filter((l) => l.store_id === store.store_id || store.alt_store_ids.includes(l.store_id))
    const sum = lines.reduce((acc, l) => acc + l.line_total, 0)
    return { store, items: pluralItems(lines.length), subtotal: formatPrice(sum) }
  })
}

/** Причина з `missing` → текст для людини (CLAUDE.md: невідомий склад не дорівнює чистому). */
export function missingReason(reason: string): string {
  if (reason === 'not_found') return 'немає в магазинах поруч'
  if (reason === 'filtered_by_composition') return 'склад не пройшов фільтр або невідомий'
  return 'не знайшли'
}

const TRAVEL: Record<Mode, string> = { walk: 'walking', car: 'driving' }

/**
 * Посилання «Маршрут» (Google Maps). Один магазин — `maps_url` з geo. Smart Split — один маршрут
 * через обидва магазини: ближчий — проміжна точка.
 */
export function routeUrl(b: AgentBasket, origin: Origin, mode: Mode): string | null {
  if (b.stores.length === 0) return null
  if (b.stores.length === 1) return b.stores[0].maps_url
  const ordered = [...b.stores].sort((x, y) => x.distance_km - y.distance_km)
  const point = (s: { lat: number; lng: number }) => `${s.lat.toFixed(6)},${s.lng.toFixed(6)}`
  const params = new URLSearchParams({
    api: '1',
    origin: point(origin),
    destination: point(ordered[ordered.length - 1]),
    waypoints: ordered.slice(0, -1).map(point).join('|'),
    travelmode: TRAVEL[mode],
  })
  return `https://www.google.com/maps/dir/?${params.toString()}`
}

/** Підпис для скрінрідера на картці. */
export function optionLabel(b: AgentBasket): string {
  const where = b.stores.map(chainName).join(' і ')
  return `${OPTION_TITLE[b.type]}: ${where}, ${formatPrice(b.total)}`
}
