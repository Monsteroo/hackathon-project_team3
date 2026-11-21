import { chainName, distanceText, monogram } from '../../features/results/options'
import type { Mode, StoreOption } from '../../lib/api/types'
import { formatPrice } from '../../lib/format'
import cardStyles from '../OptionCard/OptionCard.module.css'
import styles from './StoreList.module.css'

type Props = {
  stores: StoreOption[]
  /** Скільки позицій у кошику — для «1 з 3». */
  requested: number
  mode: Mode
  selectedId: string | null
  onSelect: (storeId: string) => void
  onHover?: (storeId: string | null) => void
  rowRef?: (storeId: string, el: HTMLButtonElement | null) => void
}

/**
 * Усі магазини в радіусі з `BasketOut.stores`: сума кошика в кожному, від найдешевшого.
 * Рядок — кнопка з aria-pressed: вибір показує магазин на карті й відкриває його кошик.
 */
export function StoreList({ stores, requested, mode, selectedId, onSelect, onHover, rowRef }: Props) {
  return (
    <section className={styles.section} aria-labelledby="all-stores-title">
      <h2 id="all-stores-title" className={styles.title}>
        Усі магазини поруч <span className={`${styles.count} num`}>{stores.length}</span>
      </h2>
      <ul className={styles.list}>
        {stores.map((o) => {
          const s = o.store
          const partial = o.found < requested
          return (
            <li key={s.store_id}>
              <button
                type="button"
                ref={(el) => rowRef?.(s.store_id, el)}
                className={styles.row}
                aria-pressed={selectedId === s.store_id}
                onClick={() => onSelect(s.store_id)}
                onPointerEnter={() => onHover?.(s.store_id)}
                onPointerLeave={() => onHover?.(null)}
              >
                <span className={cardStyles.logo} aria-hidden="true">
                  {monogram(s)}
                </span>
                <span className={styles.body}>
                  <span className={styles.name}>
                    {chainName(s)}
                    {s.address && <span className={styles.address}> · {s.address}</span>}
                  </span>
                  <span className={`${styles.meta} num`}>
                    {distanceText(s, mode)}
                    {partial && ` · ${o.found} з ${requested}`}
                  </span>
                </span>
                <span className={styles.side}>
                  <span className={`${styles.price} ${o.cheapest ? styles.cheapest : ''} num`}>
                    {formatPrice(o.total)}
                  </span>
                  {(o.cheapest || o.nearest) && (
                    <span className={styles.tag}>{o.cheapest ? 'Найдешевший' : 'Найближчий'}</span>
                  )}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
