import type { AgentBasket, AgentCategory, AgentStore, BasketLine, ParsedRequest, RequestedItem } from '../../lib/api/types'
import { formatPack, formatPrice } from '../../lib/format'

/**
 * Екран 4 «Деталі кошика» (DESIGN_PROMPT §Екран 4, DESIGN.md §4.3–4.6).
 * Чисті функції без React: групування за відділами, нестандартна вага, «склад перевірено»,
 * порівняння позиції з іншими варіантами.
 */

/** Відділи в порядку обходу магазину. */
export const DEPARTMENTS = [
  { id: 'produce', title: 'Овочі й фрукти', categories: ['bananas', 'apples'] },
  { id: 'bread', title: 'Хліб', categories: ['bread'] },
  { id: 'dairy', title: 'Молочне та яйця', categories: ['milk', 'kefir', 'curd', 'sour_cream', 'butter', 'cheese', 'eggs'] },
  {
    id: 'grocery',
    title: 'Бакалія',
    categories: ['flour', 'sugar', 'vanilla_sugar', 'buckwheat', 'rice', 'pasta', 'sunflower_oil'],
  },
  { id: 'drinks', title: 'Кава й чай', categories: ['coffee_ground', 'coffee_beans', 'tea'] },
] as const satisfies readonly { id: string; title: string; categories: readonly AgentCategory[] }[]

const OTHER = { id: 'other', title: 'Інше' } as const

export interface Group<T> {
  id: string
  title: string
  items: T[]
}

export function departmentOf(category: AgentCategory | null | undefined): { id: string; title: string } {
  const dep = DEPARTMENTS.find((d) => (d.categories as readonly string[]).includes(category ?? ''))
  return dep ? { id: dep.id, title: dep.title } : OTHER
}

/** Позиції за відділами, у порядку обходу; порожніх відділів немає. */
export function groupByDepartment<T>(items: T[], categoryOf: (item: T) => AgentCategory | null | undefined): Group<T>[] {
  const order: string[] = [...DEPARTMENTS.map((d) => d.id), OTHER.id]
  const groups = new Map<string, Group<T>>()
  for (const item of items) {
    const dep = departmentOf(categoryOf(item))
    if (!groups.has(dep.id)) groups.set(dep.id, { ...dep, items: [] })
    groups.get(dep.id)!.items.push(item)
  }
  return [...groups.values()].sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id))
}

/** Позиція запиту, яку закриває рядок кошика. */
export function requestedItem(line: Pick<BasketLine, 'requested'>, parsed: ParsedRequest): RequestedItem | undefined {
  return parsed.items.find((i) => i.name === line.requested)
}

/** Рядок належить магазину (з урахуванням інших ID того ж магазину). */
export function lineInStore(line: BasketLine, store: AgentStore): boolean {
  return line.store_id === store.store_id || store.alt_store_ids.includes(line.store_id)
}

const STANDARD: Record<string, number[]> = { g: [100, 200, 250, 500, 1000], ml: [500, 1000] }

/** «870 г» для нестандартної пачки (не 100/200/250/500 г, 1 кг, 0,5/1 л), інакше null. */
export function nonstandardWeight(line: Pick<BasketLine, 'pack_qty' | 'pack_unit'>): string | null {
  const { pack_qty: qty, pack_unit: unit } = line
  if (qty == null || (unit !== 'g' && unit !== 'ml')) return null
  if (STANDARD[unit].includes(qty) || (qty > 1000 && qty % 1000 === 0)) return null
  return formatPack(qty, unit)
}

/** «950 г», «10 шт» або null, якщо ваги немає в даних. */
export function packText(line: Pick<BasketLine, 'pack_qty' | 'pack_unit'>): string | null {
  const { pack_qty: qty, pack_unit: unit } = line
  if (qty == null || (unit !== 'g' && unit !== 'ml' && unit !== 'pcs')) return null
  return formatPack(qty, unit)
}

/** «Галичина · 950 г». */
export function brandLine(line: Pick<BasketLine, 'brand' | 'pack_qty' | 'pack_unit'>): string {
  return [line.brand, packText(line)].filter(Boolean).join(' · ')
}

const UNIT_WORD: Record<string, string> = { кг: 'кілограм', л: 'літр', шт: 'штуку' }

/** «76,08 ₴/кг» + текст для читача екрана «76,08 гривні за кілограм». null — ціни за одиницю немає. */
export function unitPrice(line: Pick<BasketLine, 'unit_price' | 'unit_price_label'>): { text: string; sr: string } | null {
  if (line.unit_price == null) return null
  const unit = line.unit_price_label.split('/')[1] ?? 'кг'
  const sum = formatPrice(line.unit_price).replace(/\s₴$/, '')
  return { text: `${formatPrice(line.unit_price)}/${unit}`, sr: `${sum} гривні за ${UNIT_WORD[unit] ?? unit}` }
}

/** Фільтри складу → коротка назва (бейдж) і пояснення (деталі). */
const TAG_TEXT: Record<string, { short: string; reason: string }> = {
  lactose: { short: 'Без лактози', reason: 'лактози' },
  sugar: { short: 'Без цукру', reason: 'доданого цукру' },
  palm_oil: { short: 'Без пальмової олії', reason: 'пальмової олії' },
}

export interface Verified {
  tag: string
  short: string
  /** «Склад перевірено: без лактози». */
  title: string
  /** Чому товар пройшов фільтр. */
  reason: string
}

/**
 * «Склад перевірено» — лише для активних фільтрів, які товар пройшов.
 * Каталог не пропускає товари з невідомим складом (CLAUDE.md), тож рядок у кошику = склад відомий і тегу немає.
 */
export function verifiedTags(line: Pick<BasketLine, 'tags'>, item: RequestedItem | undefined, parsed: ParsedRequest): Verified[] {
  const active = new Set([...(parsed.constraints.exclude ?? []), ...(item?.exclude ?? [])])
  return [...active].flatMap((tag) => {
    const text = TAG_TEXT[tag]
    if (!text || line.tags.includes(tag)) return []
    return [
      {
        tag,
        short: text.short,
        title: `Склад перевірено: ${text.short.toLocaleLowerCase('uk')}`,
        reason: `Пройшов фільтр «${text.short}»: у складі за даними мережі немає ${text.reason}.`,
      },
    ]
  })
}

/** Бренд, який людина назвала сама, але в магазині його немає — підставили аналог. */
export function analogOf(line: Pick<BasketLine, 'brand' | 'title'>, item: RequestedItem | undefined): string | null {
  const wanted = item?.brand?.trim()
  if (!wanted) return null
  const norm = (s: string | null | undefined) => (s ?? '').toLocaleLowerCase('uk')
  if (norm(line.brand).includes(norm(wanted)) || norm(line.title).includes(norm(wanted))) return null
  return `${item!.name} ${wanted}`
}

export interface CompareCell {
  basket: AgentBasket
  /** Рядки цієї позиції у варіанті (зазвичай один). */
  lines: BasketLine[]
  total: number | null
  unitPrice: number | null
  /** Найнижча ціна за одиницю серед варіантів (лише якщо варіантів із ціною ≥ 2). */
  lowest: boolean
}

/** Ціна тієї самої позиції запиту в кожному варіанті. */
export function compareRequested(requested: string, baskets: AgentBasket[]): CompareCell[] {
  const cells = baskets.map((basket) => {
    const lines = basket.lines.filter((l) => l.requested === requested)
    const total = lines.length ? lines.reduce((s, l) => s + l.line_total, 0) : null
    const unit = lines.find((l) => l.unit_price != null)?.unit_price ?? null
    return { basket, lines, total, unitPrice: unit, lowest: false }
  })
  const priced = cells.filter((c) => c.unitPrice != null)
  if (priced.length >= 2) {
    const min = Math.min(...priced.map((c) => c.unitPrice!))
    const max = Math.max(...priced.map((c) => c.unitPrice!))
    if (min < max) for (const c of priced) c.lowest = c.unitPrice === min
  }
  return cells
}

/** Сума кошика без прибраних позицій. */
export function basketTotal(basket: AgentBasket, removed: ReadonlySet<string>): number {
  return Math.round(basket.lines.filter((l) => !removed.has(l.requested)).reduce((s, l) => s + l.line_total, 0) * 100) / 100
}

/** Що прибрати, щоб влізти в бюджет: спершу необовʼязкові, потім найдорожчі. */
export function trimCandidates(lines: BasketLine[], parsed: ParsedRequest, limit = 3): BasketLine[] {
  const optional = (l: BasketLine) => (requestedItem(l, parsed)?.optional ? 1 : 0)
  return [...lines].sort((a, b) => optional(b) - optional(a) || b.line_total - a.line_total).slice(0, limit)
}

const pad = (n: number) => String(n).padStart(2, '0')

/** «Ціни оновлено сьогодні о 03:40» / «… 20.11 о 03:40». null — часу немає. */
export function freshnessText(iso: string | null | undefined, now = new Date()): string | null {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  const time = `${pad(d.getHours())}:${pad(d.getMinutes())}`
  const sameDay = (a: Date, b: Date) => a.toDateString() === b.toDateString()
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  const day = sameDay(d, now) ? 'сьогодні' : sameDay(d, yesterday) ? 'вчора' : `${pad(d.getDate())}.${pad(d.getMonth() + 1)}`
  return `Ціни оновлено ${day} о ${time}`
}
