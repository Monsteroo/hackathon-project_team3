import type { Mode, VoiceResult } from '../../lib/api/types'

/** Одиниця потреби з контракту «Позиція кошика» (CLAUDE.md). */
export type Unit = 'g' | 'ml' | 'pcs'

/** Теги складу, які вміє відсіяти каталог (`exclude` у /catalog/prices). */
export type Tag = 'sugar' | 'lactose' | 'palm_oil' | 'private_label'

/** Канонічні категорії демо (CLAUDE.md, «Канонічні категорії»). */
export type Category =
  | 'milk'
  | 'kefir'
  | 'curd'
  | 'sour_cream'
  | 'butter'
  | 'cheese'
  | 'eggs'
  | 'flour'
  | 'sugar'
  | 'vanilla_sugar'
  | 'buckwheat'
  | 'rice'
  | 'pasta'
  | 'sunflower_oil'
  | 'bread'
  | 'coffee_ground'
  | 'coffee_beans'
  | 'tea'
  | 'bananas'
  | 'apples'

/**
 * Позиція на екрані 2. Поле `count` — скільки пачок (або штук). Потреба для агента дорівнює
 * `count * packQty` в одиницях `unit`.
 */
export interface BasketItem {
  id: string
  /** Назва для людини: «Молоко» або назва товару з каталогу. */
  label: string
  category?: Category
  gtin?: string
  /** Вільний текст, якщо товар не зведено до категорії чи GTIN. */
  query?: string
  count: number
  packQty: number
  unit: Unit
  exclude: Tag[]
}

/** Позиція кошика для агента й каталогу (контракт із CLAUDE.md). */
export interface AgentItem {
  category?: Category
  gtin?: string
  query?: string
  need: number
  unit: Unit
  exclude: Tag[]
}

export interface BasketDraft {
  /** Запит, з якого почали. null — список зібрано вручну. */
  voice: VoiceResult | null
  items: BasketItem[]
  /** Бюджет у гривнях. null — без бюджету. */
  budget: number | null
  /** Фільтри складу для всього кошика. */
  exclude: Tag[]
  mode: Mode
  radiusKm: number
}
