import { useEffect, useState } from 'react'
import { api } from '../../lib/api/client'

/** Скільки мереж мають ціни в місті (/catalog/stores). null — ще не відомо або каталог недоступний. */
export function useCatalogChains(city: string): number | null {
  const [state, setState] = useState<{ city: string; count: number | null }>({ city: '', count: null })

  useEffect(() => {
    const controller = new AbortController()
    api
      .catalogStores(city, controller.signal)
      .then((stores) => {
        const count = Array.isArray(stores) ? new Set(stores.map((s) => s.chain)).size : 0
        setState({ city, count: count > 0 ? count : null })
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ city, count: null })
      })
    return () => controller.abort()
  }, [city])

  return state.city === city ? state.count : null
}
