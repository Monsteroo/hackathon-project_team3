import { useEffect, useState } from 'react'
import { api } from '../../lib/api/client'
import type { CatalogProduct } from '../../lib/api/types'
import { normalizeSearch, searchCategories, type CategoryInfo } from './categories'

export const SEARCH_MIN_CHARS = 2
export const SEARCH_DEBOUNCE_MS = 300
const PRODUCT_LIMIT = 6

export type CatalogStatus = 'idle' | 'loading' | 'ready' | 'error'

export interface ProductSearch {
  /** Локальні категорії: є завжди, навіть без бекенду. */
  categories: CategoryInfo[]
  products: CatalogProduct[]
  catalog: CatalogStatus
  /** Чи достатньо символів для пошуку. */
  active: boolean
}

/**
 * Підказки для «Додати товар»: спершу канонічні категорії (локально, миттєво), потім товари
 * з /catalog/prices із затримкою. Помилка каталогу не блокує: лишаються категорії й вільний текст.
 */
export function useProductSearch(query: string): ProductSearch {
  const q = normalizeSearch(query)
  const active = q.length >= SEARCH_MIN_CHARS
  const [result, setResult] = useState<{ q: string; products: CatalogProduct[]; catalog: CatalogStatus }>({
    q: '',
    products: [],
    catalog: 'idle',
  })

  useEffect(() => {
    if (!active) return
    const controller = new AbortController()
    const timer = setTimeout(() => {
      setResult({ q, products: [], catalog: 'loading' })
      api
        .searchProducts(q, { limit: PRODUCT_LIMIT, signal: controller.signal })
        .then((res) => {
          const products = Array.isArray(res?.products) ? res.products : []
          setResult({ q, products, catalog: 'ready' })
        })
        .catch((e: unknown) => {
          if ((e as Error)?.name === 'AbortError') return
          setResult({ q, products: [], catalog: 'error' })
        })
    }, SEARCH_DEBOUNCE_MS)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [q, active])

  const fresh = result.q === q
  return {
    categories: active ? searchCategories(q) : [],
    products: active && fresh ? result.products : [],
    // Поки чекаємо паузу в наборі, показуємо «шукаю», а не старі результати.
    catalog: !active ? 'idle' : fresh ? result.catalog : 'loading',
    active,
  }
}
