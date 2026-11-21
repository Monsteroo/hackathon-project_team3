import { Info, Package, Replace, ShieldCheck, TrendingDown } from 'lucide-react'
import { useState } from 'react'
import { chainName, OPTION_TITLE } from '../../features/results/options'
import {
  unitPrice,
  type CompareCell,
  type Verified,
} from '../../features/basket-details/details'
import type { AgentBasket, BasketLine, RequestedItem } from '../../lib/api/types'
import { formatPrice } from '../../lib/format'
import styles from './BasketRow.module.css'

/** Усе, що потрібно рядку кошика: і списку (мобільний), і таблиці (десктоп). */
export interface RowData {
  line: BasketLine
  item: RequestedItem | undefined
  verified: Verified[]
  /** «молоко Галичина» — що просили, якщо підставили аналог. */
  analog: string | null
  /** Різниця ціни аналога з оригіналом в іншому варіанті, ₴/од. */
  analogDiff: { value: number; unit: string } | null
  weight: string | null
  compare: CompareCell[]
}

/** Фото 56 / 40 px; не завантажилось — нейтральна заглушка `Package`. */
export function Photo({ src, small = false }: { src: string | null; small?: boolean }) {
  const [failed, setFailed] = useState(false)
  return (
    <span className={`${styles.photo} ${small ? styles.photoSm : ''}`}>
      {src && !failed ? (
        <img src={src} alt="" loading="lazy" onError={() => setFailed(true)} />
      ) : (
        <Package strokeWidth={1.75} aria-hidden="true" />
      )}
    </span>
  )
}

/** UnitPrice inline (DESIGN.md §4.4): видимий текст `aria-hidden`, для читача — словами. */
export function UnitPriceText({ line, className = '' }: { line: Pick<BasketLine, 'unit_price' | 'unit_price_label'>; className?: string }) {
  const u = unitPrice(line)
  if (!u) {
    return (
      <span className={`${styles.unit} ${className} num`}>
        <span aria-hidden="true">— ₴/кг</span>
        <span className="sr-only">ціни за кілограм немає</span>
      </span>
    )
  }
  return (
    <span className={`${styles.unit} ${className} num`}>
      <span aria-hidden="true">{u.text}</span>
      <span className="sr-only">{u.sr}</span>
    </span>
  )
}

/** Бейджі під назвою: вага, аналог, склад (не більше 2 бейджів складу). */
export function Badges({ row, onComposition }: { row: RowData; onComposition: () => void }) {
  const shown = row.verified.slice(0, 2)
  const rest = row.verified.length - shown.length
  if (!row.weight && !row.analog && shown.length === 0) return null
  return (
    <div className={styles.badges}>
      {row.weight && (
        <span className={`${styles.badge} ${styles.warn} num`}>
          <span className="sr-only">Нестандартна вага: </span>
          {row.weight}
        </span>
      )}
      {row.analog && (
        <span className={`${styles.badge} ${styles.warn}`}>
          <Replace strokeWidth={1.75} aria-hidden="true" />
          аналог
        </span>
      )}
      {shown.map((v) => (
        <button
          key={v.tag}
          type="button"
          className={`${styles.badge} ${styles.verified}`}
          aria-label={`${v.title}. Показати пояснення`}
          onClick={onComposition}
        >
          <ShieldCheck strokeWidth={1.75} aria-hidden="true" />
          {v.short}
        </button>
      ))}
      {rest > 0 && (
        <button type="button" className={`${styles.badge} ${styles.verified} num`} onClick={onComposition}>
          +{rest}
        </button>
      )}
    </div>
  )
}

function signed(value: number, unit: string): string {
  const abs = formatPrice(Math.abs(value))
  return `${value < 0 ? '−' : '+'}${abs}${unit ? `/${unit}` : ''}`
}

/** AnalogNotice inline (DESIGN.md §4.5). Плашку не можна закрити: підміна видима, поки товар у кошику. */
export function AnalogNotice({ row, storeName }: { row: RowData; storeName: string }) {
  if (!row.analog) return null
  const diff = row.analogDiff
  return (
    <div className={styles.analog}>
      <Replace strokeWidth={1.75} aria-hidden="true" />
      <div className={styles.analogBody}>
        <p className={styles.analogLine}>
          <span className={styles.analogTitle}>Аналог</span> · замість «{row.analog}»
        </p>
        <p className={styles.analogMeta}>
          Такого бренду немає в {storeName}. Підібрали найвигідніший товар тієї самої категорії.
        </p>
        {diff && Math.abs(diff.value) >= 0.01 && (
          <p className={`${styles.analogDiff} ${diff.value < 0 ? styles.analogCheaper : ''} num`}>
            {signed(diff.value, diff.unit)} до оригіналу
          </p>
        )}
      </div>
    </div>
  )
}

/** Примітка агента: менша пачка, шрінкфляція. */
export function Note({ text }: { text: string | null }) {
  if (!text) return null
  return (
    <p className={styles.note}>
      <Info strokeWidth={1.75} aria-hidden="true" />
      <span>{text}</span>
    </p>
  )
}

/** Деталі товару: склад із причиною і ціна позиції в інших варіантах. */
export function Details({ row, current }: { row: RowData; current: AgentBasket['type'] }) {
  return (
    <div className={styles.details}>
      {row.verified.length > 0 && (
        <div className={styles.detailsBlock}>
          {row.verified.map((v) => (
            <div key={v.tag}>
              <p className={styles.detailsTitle}>{v.title}</p>
              <p>{v.reason}</p>
            </div>
          ))}
          <p className={styles.detailsMeta}>Джерело: склад з каталогу мережі</p>
        </div>
      )}
      {row.compare.length > 1 && (
        <div className={styles.detailsBlock}>
          <p className={styles.detailsTitle}>Ця позиція в інших варіантах</p>
          <ul className={styles.compare}>
            {row.compare.map((c) => (
              <li key={c.basket.type} className={c.basket.type === current ? styles.compareCurrent : undefined}>
                <span className={styles.compareName}>
                  {OPTION_TITLE[c.basket.type]}
                  <span className={styles.compareChain}>
                    {' '}· {c.basket.stores.map(chainName).join(' + ')}
                  </span>
                </span>
                {c.total == null ? (
                  <span className={styles.compareMissing}>немає</span>
                ) : (
                  <span className={styles.compareNums}>
                    <span className="num">{formatPrice(c.total)}</span>
                    {c.lowest ? (
                      <span className={`${styles.lowest} num`}>
                        <TrendingDown strokeWidth={1.75} aria-hidden="true" />
                        {unitPrice(c.lines[0])?.text} · найдешевше
                      </span>
                    ) : (
                      c.lines[0] && <UnitPriceText line={c.lines[0]} />
                    )}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
