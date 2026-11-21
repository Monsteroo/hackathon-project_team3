import { TrendingDown } from 'lucide-react'
import { useId, type KeyboardEvent, type Ref } from 'react'
import {
  budgetText,
  chainName,
  coverageText,
  distanceText,
  missingBadge,
  monogram,
  OPTION_TITLE,
  optionLabel,
  splitRows,
  tradeoff,
} from '../../features/results/options'
import type { AgentBasket, Mode } from '../../lib/api/types'
import { formatPrice, formatSavings } from '../../lib/format'
import styles from './OptionCard.module.css'

type Props = {
  basket: AgentBasket
  baskets: AgentBasket[]
  selected: boolean
  /** Найдешевший повний кошик: Savings-бейдж. */
  best: boolean
  requested: number
  budget: number | null
  mode: Mode
  tabIndex: number
  onSelect: () => void
  onKeyDown: (e: KeyboardEvent<HTMLDivElement>) => void
  onHover?: (hover: boolean) => void
  cardRef?: Ref<HTMLDivElement>
}

/** DESIGN.md §4.2 StoreCard, варіанти `option` і `split`. Елемент radiogroup, без вкладених кнопок. */
export function OptionCard({
  basket,
  baskets,
  selected,
  best,
  requested,
  budget,
  mode,
  tabIndex,
  onSelect,
  onKeyDown,
  onHover,
  cardRef,
}: Props) {
  const split = basket.type === 'smart_split' && basket.stores.length > 1
  const store = basket.stores[0]
  const trade = tradeoff(basket, baskets)
  const missing = basket.missing.length
  const budgetLine = budgetText(basket, budget)
  const detailsId = useId()

  const meta: string[] = []
  if (split) {
    meta.push(`${basket.stores.map((s) => distanceText(s, mode).split(' · ')[0]).join(' і ')} від вас`)
  } else if (store) {
    meta.push(distanceText(store, mode))
  }
  meta.push(coverageText(basket, requested))
  if (budgetLine) meta.push(budgetLine)

  return (
    <div
      ref={cardRef}
      className={styles.card}
      role="radio"
      aria-checked={selected}
      aria-label={optionLabel(basket)}
      aria-describedby={detailsId}
      tabIndex={tabIndex}
      onClick={onSelect}
      onKeyDown={onKeyDown}
      onPointerEnter={() => onHover?.(true)}
      onPointerLeave={() => onHover?.(false)}
    >
      <div className={styles.head}>
        <p className={styles.title}>{OPTION_TITLE[basket.type]}</p>
        <div className={styles.badges}>
          {best && (
            <span className={`${styles.badge} ${styles.savings} num`}>
              <TrendingDown strokeWidth={1.75} aria-hidden="true" />
              {basket.saving > 0 ? `${formatSavings(Math.round(basket.saving))} до інших` : 'Найдешевший кошик'}
            </span>
          )}
          {split && <span className={`${styles.badge} ${styles.neutral} num`}>2 магазини</span>}
          {missing > 0 && <span className={`${styles.badge} ${styles.warning} num`}>{missingBadge(missing)}</span>}
        </div>
      </div>

      {split ? (
        splitRows(basket).map((row) => (
          <p key={row.store.store_id} className={styles.splitRow}>
            <span className={styles.logo} aria-hidden="true">
              {monogram(row.store)}
            </span>
            <span className={styles.chain}>{chainName(row.store)}</span>
            <span className={`${styles.splitMeta} num`}>{row.items}</span>
            <span className={`${styles.splitSum} num`}>{row.subtotal}</span>
          </p>
        ))
      ) : store ? (
        <p className={styles.chainRow}>
          <span className={styles.logo} aria-hidden="true">
            {monogram(store)}
          </span>
          <span className={styles.chain}>{chainName(store)}</span>
          {store.address && <span className={styles.address}>· {store.address}</span>}
        </p>
      ) : null}

      <p className={`${styles.total} num`}>{formatPrice(basket.total)}</p>
      {missing > 0 && <p className={`${styles.meta} num`}>Сума без {missing === 1 ? '1 товару' : `${missing} товарів`}</p>}
      <div id={detailsId}>
        {trade && (
          <p className={`${styles.trade} num`}>
            {trade.save && <span className={styles.save}>{trade.save}</span>}
            {trade.rest}
          </p>
        )}
        <p className={`${styles.meta} num`}>{meta.join(' · ')}</p>
      </div>
    </div>
  )
}
