/** Звідки шукати магазини: GPS браузера або адреса з /geo/geocode. */
export interface Origin {
  lat: number
  lng: number
  /** Адреса для показу. null — координати з GPS, адресу ще не знаємо. */
  label: string | null
  source: 'gps' | 'address'
}

/** denied — людина заборонила; unavailable — не вдалося або таймаут; unsupported — браузер не вміє. */
export type PositionFailure = 'denied' | 'unavailable' | 'unsupported'

export class PositionError extends Error {
  readonly reason: PositionFailure

  constructor(reason: PositionFailure) {
    super(reason)
    this.name = 'PositionError'
    this.reason = reason
  }
}

/**
 * Тимчасовий мок для демо й розробки поза Києвом: `VITE_MOCK_LOCATION=kyiv-center` у `.env.local`
 * → центр Києва (Майдан Незалежності) замість GPS. Без змінної — справжня геолокація.
 */
const MOCK_POSITION = import.meta.env.VITE_MOCK_LOCATION === 'kyiv-center' ? { lat: 50.4501, lng: 30.5234 } : null

/** Promise-обгортка над navigator.geolocation. Помилка — завжди PositionError. */
export function getCurrentPosition(timeoutMs = 10_000): Promise<{ lat: number; lng: number }> {
  if (MOCK_POSITION) return Promise.resolve(MOCK_POSITION)
  return new Promise((resolve, reject) => {
    if (typeof navigator === 'undefined' || !('geolocation' in navigator)) {
      reject(new PositionError('unsupported'))
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      (err) => reject(new PositionError(err.code === err.PERMISSION_DENIED ? 'denied' : 'unavailable')),
      { timeout: timeoutMs, maximumAge: 300_000 },
    )
  })
}

/** Чому просимо адресу: текст над полем. */
export const POSITION_MESSAGES: Record<PositionFailure, string> = {
  denied: 'Доступ до геолокації заборонено. Вкажіть адресу, від якої шукати магазини',
  unavailable: 'Не вдалося визначити, де ви. Вкажіть адресу, від якої шукати магазини',
  unsupported: 'Браузер не визначає місце. Вкажіть адресу, від якої шукати магазини',
}

/**
 * Адреса для координат GPS («вулиця Хрещатик, 22, Київ»), щоб людина бачила, що ми визначили її місце правильно.
 * Не блокує сценарій: таймаут, помилка чи точка поза зоною обслуговування → null («Ваше місце»).
 */
export async function addressForPosition(
  { lat, lng }: { lat: number; lng: number },
  reverse: (p: { lat: number; lng: number }) => Promise<{ label: string }>,
  timeoutMs = 2_500,
): Promise<string | null> {
  const timeout = new Promise<null>((resolve) => setTimeout(() => resolve(null), timeoutMs))
  try {
    const place = await Promise.race([reverse({ lat, lng }), timeout])
    return place?.label?.trim() || null
  } catch {
    return null
  }
}
