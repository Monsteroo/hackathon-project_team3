/**
 * Форматування цін і відстаней за design/design-system/sayvy/MASTER.md, розділ «Price formatting (uk-UA)».
 * Ручне форматування, бо Intl у різних браузерах дає різні пробіли.
 */
const NNBSP = ' ' // вузький нерозривний пробіл: розділювач тисяч
const NBSP = ' ' // нерозривний пробіл: перед ₴ та одиницями
const MINUS = '−' // справжній мінус

function groupThousands(int: string): string {
  return int.replace(/\B(?=(\d{3})+(?!\d))/g, NNBSP)
}

/** 1249.9 → «1 249,90 ₴» */
export function formatPrice(value: number): string {
  const [int, frac] = Math.abs(value).toFixed(2).split('.')
  const sign = value < 0 ? MINUS : ''
  return `${sign}${groupThousands(int)},${frac}${NBSP}₴`
}

/** 112.4, 'кг' → «112,40 ₴/кг» */
export function formatUnitPrice(value: number, unit: 'кг' | 'л' | 'шт'): string {
  return `${formatPrice(value)}/${unit}`
}

/** 75 → «−75 ₴»; дробові — з копійками. */
export function formatSavings(value: number): string {
  const abs = Math.abs(value)
  const body = Number.isInteger(abs)
    ? groupThousands(String(abs))
    : `${groupThousands(String(Math.trunc(abs)))},${abs.toFixed(2).split('.')[1]}`
  return `${MINUS}${body}${NBSP}₴`
}

/** 450 → «450 м»; 1200 → «1,2 км» */
export function formatDistance(meters: number): string {
  if (meters < 1000) return `${Math.round(meters)}${NBSP}м`
  const km = (meters / 1000).toFixed(1).replace('.', ',').replace(/,0$/, '')
  return `${km}${NBSP}км`
}

/** 450, 6 → «450 м · 6 хв пішки» */
export function formatWalk(meters: number, minutes: number): string {
  return `${formatDistance(meters)} · ${minutes}${NBSP}хв пішки`
}

/** 7.4 → «0:07»; 65 → «1:05». Тривалість запису голосу. */
export function formatClock(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds))
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}

/** 1500 → «1 500 ₴» (цілі гривні: бюджет, пресети). */
export function formatRoundPrice(value: number): string {
  return `${groupThousands(String(Math.round(Math.abs(value))))}${NBSP}₴`
}

/** 1500 → «1 500» (поле суми). */
export function formatInteger(value: number): string {
  return groupThousands(String(Math.round(value)))
}

/** Пачка: 1000, 'ml' → «1 л»; 350, 'g' → «350 г»; 1, 'pcs' → «поштучно»; 10, 'pcs' → «10 шт». */
export function formatPack(qty: number, unit: 'g' | 'ml' | 'pcs'): string {
  if (unit === 'pcs') return qty === 1 ? 'поштучно' : `${formatInteger(qty)}${NBSP}шт`
  const big = unit === 'g' ? 'кг' : 'л'
  const small = unit === 'g' ? 'г' : 'мл'
  if (qty < 1000) return `${formatInteger(qty)}${NBSP}${small}`
  const v = (qty / 1000).toFixed(2).replace(/\.?0+$/, '').replace('.', ',')
  return `${v}${NBSP}${big}`
}

/** «1 товар / 3 товари / 11 товарів». */
export function pluralItems(n: number): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return `${n} товар`
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${n} товари`
  return `${n} товарів`
}
