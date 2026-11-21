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

/** Promise-обгортка над navigator.geolocation. Помилка — завжди PositionError. */
export function getCurrentPosition(timeoutMs = 10_000): Promise<{ lat: number; lng: number }> {
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
