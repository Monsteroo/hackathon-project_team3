import type { VoiceResult } from '../../lib/api/types'
import type { BasketItem } from './types'

/**
 * Розбір запиту на позиції кошика. Це робота агента (Учасник 5): `VoiceResult.text` →
 * `[{category | gtin | query, need, unit, exclude}]`. Поки агента немає, список порожній,
 * і людина додає товари вручну. Підключення агента — лише тут.
 */
export async function parseItems(voice: VoiceResult): Promise<Omit<BasketItem, 'id'>[]> {
  void voice
  return []
}
