import { useCallback, useSyncExternalStore } from 'react'

/** Брейкпоінти з MASTER.md (desktop-first). У CSS media queries змінні недоступні, тому значення тут. */
export const MQ_COMPACT = '(max-width: 1023px)'
/** Екран 4: таблиці порівняння потрібно ~780px поруч із підсумком, тому вона лише від 1280px; вужче — список. */
export const MQ_TABLE = '(min-width: 1280px)'
export const MQ_MOBILE = '(max-width: 767px)'

export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      if (typeof window === 'undefined' || !window.matchMedia) return () => {}
      const mql = window.matchMedia(query)
      mql.addEventListener('change', onChange)
      return () => mql.removeEventListener('change', onChange)
    },
    [query],
  )
  return useSyncExternalStore(
    subscribe,
    () => (typeof window !== 'undefined' && window.matchMedia ? window.matchMedia(query).matches : false),
    () => false,
  )
}
