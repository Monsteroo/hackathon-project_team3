import type { Category, Unit } from './types'

export interface CategoryInfo {
  id: Category
  label: string
  /** Інші назви й форми слова для пошуку: «сирники» → curd. */
  aliases: string[]
  /** Типова пачка. Для штучних товарів 1. */
  packQty: number
  unit: Unit
  /** Скільки пачок пропонувати одразу: яйця — десяток. */
  defaultCount: number
}

/**
 * 20 канонічних категорій демо (CLAUDE.md). Це локальні підказки для «Додати товар», коли
 * каталог недоступний, і назви категорій у списку.
 */
export const CATEGORIES: CategoryInfo[] = [
  { id: 'milk', label: 'Молоко', aliases: ['молоко', 'молока'], packQty: 1000, unit: 'ml', defaultCount: 1 },
  { id: 'kefir', label: 'Кефір', aliases: ['кефір', 'кефіру'], packQty: 1000, unit: 'ml', defaultCount: 1 },
  {
    id: 'curd',
    label: 'Сир кисломолочний',
    aliases: ['кисломолочний', 'творог', 'сирники', 'сир'],
    packQty: 500,
    unit: 'g',
    defaultCount: 1,
  },
  { id: 'sour_cream', label: 'Сметана', aliases: ['сметана', 'сметани'], packQty: 350, unit: 'g', defaultCount: 1 },
  { id: 'butter', label: 'Масло вершкове', aliases: ['масло', 'вершкове'], packQty: 200, unit: 'g', defaultCount: 1 },
  { id: 'cheese', label: 'Сир твердий', aliases: ['твердий', 'сир'], packQty: 200, unit: 'g', defaultCount: 1 },
  { id: 'eggs', label: 'Яйця', aliases: ['яйця', 'яєць', 'яйце'], packQty: 1, unit: 'pcs', defaultCount: 10 },
  { id: 'flour', label: 'Борошно', aliases: ['борошно', 'мука'], packQty: 1000, unit: 'g', defaultCount: 1 },
  { id: 'sugar', label: 'Цукор', aliases: ['цукор', 'цукру'], packQty: 1000, unit: 'g', defaultCount: 1 },
  {
    id: 'vanilla_sugar',
    label: 'Ванільний цукор',
    aliases: ['ванільний', 'ванілін', 'ваніль'],
    packQty: 10,
    unit: 'g',
    defaultCount: 1,
  },
  { id: 'buckwheat', label: 'Гречка', aliases: ['гречка', 'гречки', 'гречану'], packQty: 1000, unit: 'g', defaultCount: 1 },
  { id: 'rice', label: 'Рис', aliases: ['рис', 'рису'], packQty: 1000, unit: 'g', defaultCount: 1 },
  { id: 'pasta', label: 'Макарони', aliases: ['макарони', 'паста', 'спагеті'], packQty: 500, unit: 'g', defaultCount: 1 },
  {
    id: 'sunflower_oil',
    label: 'Олія соняшникова',
    aliases: ['олія', 'олії', 'соняшникова'],
    packQty: 1000,
    unit: 'ml',
    defaultCount: 1,
  },
  { id: 'bread', label: 'Хліб', aliases: ['хліб', 'батон', 'хлібина'], packQty: 1, unit: 'pcs', defaultCount: 1 },
  { id: 'coffee_ground', label: 'Кава мелена', aliases: ['кава', 'мелена'], packQty: 250, unit: 'g', defaultCount: 1 },
  { id: 'coffee_beans', label: 'Кава в зернах', aliases: ['кава', 'зерна', 'зернах'], packQty: 1000, unit: 'g', defaultCount: 1 },
  { id: 'tea', label: 'Чай', aliases: ['чай', 'чаю'], packQty: 1, unit: 'pcs', defaultCount: 1 },
  { id: 'bananas', label: 'Банани', aliases: ['банани', 'банан', 'бананів'], packQty: 1000, unit: 'g', defaultCount: 1 },
  { id: 'apples', label: 'Яблука', aliases: ['яблука', 'яблуко', 'яблук'], packQty: 1000, unit: 'g', defaultCount: 1 },
]

const BY_ID = new Map(CATEGORIES.map((c) => [c.id, c]))

export function categoryInfo(id: Category | undefined): CategoryInfo | undefined {
  return id ? BY_ID.get(id) : undefined
}

/** Без регістру, апострофів і зайвих пробілів. */
export function normalizeSearch(value: string): string {
  return value
    .toLowerCase()
    .replace(/['’ʼ`]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

/** Кожне слово запиту — початок якогось слова з назви або синонімів. */
export function searchCategories(query: string): CategoryInfo[] {
  const tokens = normalizeSearch(query).split(' ').filter(Boolean)
  if (!tokens.length) return []
  return CATEGORIES.filter((c) => {
    const words = normalizeSearch([c.label, ...c.aliases].join(' ')).split(' ')
    return tokens.every((t) => words.some((w) => w.startsWith(t)))
  })
}
