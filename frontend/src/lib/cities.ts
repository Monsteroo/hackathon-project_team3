/**
 * Міста, де Sayvy має ціни (DESIGN.md §4.7, відкрите питання 3: список для MVP ще не підтверджено).
 * Демо: лише Київ — бекенд geo обслуговує тільки його (SERVICE_CITIES), решта → 422 outside_service_area.
 */
export type City = {
  id: string
  name: string
  region: string
  chains: number
  /** Латиниця й старі транслітерації для пошуку: «kyiv», «kiev». */
  aliases: string[]
  lat: number
  lng: number
}

export const CITIES: City[] = [
  { id: 'kyiv', name: 'Київ', region: 'Київська обл.', chains: 6, aliases: ['kyiv', 'kiev', 'kyjiv'], lat: 50.4501, lng: 30.5234 },
]

export const DEFAULT_CITY = CITIES[0]

/** Без регістру, апострофів, префікса «м.» і зайвих пробілів. */
export function normalizeCityQuery(value: string): string {
  return value
    .toLowerCase()
    .replace(/['’ʼ`]/g, '')
    .replace(/^\s*м\.\s*/, '')
    .replace(/\s+/g, ' ')
    .trim()
}

export function filterCities(query: string, cities: City[] = CITIES): City[] {
  const q = normalizeCityQuery(query)
  if (!q) return cities
  return cities.filter(
    (c) => normalizeCityQuery(c.name).startsWith(q) || c.aliases.some((a) => a.startsWith(q)),
  )
}

/** «Знайдено 1 місто / 3 міста / 5 міст». */
export function pluralCities(n: number): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return `${n} місто`
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${n} міста`
  return `${n} міст`
}

/** «1 мережа / 4 мережі / 5 мереж». */
export function pluralChains(n: number): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return `${n} мережа`
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${n} мережі`
  return `${n} мереж`
}

const EARTH_RADIUS_KM = 6371
/** Далі цієї відстані від центру міста вважаємо, що людина не в місті зі списку. */
const MAX_CITY_DISTANCE_KM = 60

function distanceKm(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const rad = Math.PI / 180
  const dLat = (lat2 - lat1) * rad
  const dLng = (lng2 - lng1) * rad
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLng / 2) ** 2
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(a))
}

/** Найближче місто зі списку або null, якщо всі далі за 60 км. */
export function nearestCity(lat: number, lng: number, cities: City[] = CITIES): City | null {
  let best: City | null = null
  let bestKm = Infinity
  for (const c of cities) {
    const km = distanceKm(lat, lng, c.lat, c.lng)
    if (km < bestKm) {
      best = c
      bestKm = km
    }
  }
  return bestKm <= MAX_CITY_DISTANCE_KM ? best : null
}
