import { ChevronDown } from 'lucide-react'
import { Fragment, useState } from 'react'
import { OPTION_TITLE } from '../../features/results/options'
import { brandLine, type Group } from '../../features/basket-details/details'
import type { AgentBasket } from '../../lib/api/types'
import { formatPrice } from '../../lib/format'
import { Button } from '../Button/Button'
import rowStyles from '../BasketRow/BasketRow.module.css'
import { AnalogNotice, Badges, Details, Note, Photo, UnitPriceText, type RowData } from '../BasketRow/parts'
import styles from './BasketTable.module.css'

type Props = {
  groups: Group<RowData>[]
  current: AgentBasket
  /** Усі варіанти: колонки порівняння — ті, що не вибрані. */
  baskets: AgentBasket[]
  /** Суми варіантів з урахуванням прибраних позицій. */
  totals: Map<AgentBasket['type'], number>
  storeName: string
  onRemove: (requested: string) => void
}

function signedDiff(value: number): string {
  if (Math.abs(value) < 0.01) return 'та сама сума'
  return `${value < 0 ? '−' : '+'}${formatPrice(Math.abs(value))}`
}

/** DESIGN.md §4.3, «Десктоп (≥ 1024px): таблиця». Порівняння з іншими варіантами — праворуч. */
export function BasketTable({ groups, current, baskets, totals, storeName, onRemove }: Props) {
  const others = baskets.filter((b) => b.type !== current.type)
  const [open, setOpen] = useState<string | null>(null)
  const cols = 4 + others.length
  const currentTotal = totals.get(current.type) ?? current.total

  return (
    <table className={styles.table}>
      <caption className="sr-only">Товари вибраного варіанту і їхні ціни в інших варіантах</caption>
      <thead>
        <tr>
          <th scope="col" className={styles.product}>Товар</th>
          <th scope="col" className={styles.numCol}>Пачка</th>
          <th scope="col" className={styles.numCol}>За кг/л</th>
          <th scope="col" className={styles.numCol}>Сума</th>
          {others.map((b) => (
            <th key={b.type} scope="col" className={`${styles.numCol} ${styles.compareHead}`}>
              {OPTION_TITLE[b.type]}
            </th>
          ))}
        </tr>
      </thead>
      {groups.map((g) => (
        <tbody key={g.id}>
          <tr className={styles.groupRow}>
            <th scope="colgroup" colSpan={cols}>
              {g.title}
            </th>
          </tr>
          {g.items.map((row) => {
            const { line } = row
            const key = line.requested
            const expanded = open === key
            const detailsId = `basket-details-${line.product_id}`
            const self = row.compare.find((c) => c.basket.type === current.type)
            return (
              <Fragment key={key}>
                <tr className={styles.itemRow}>
                  <td className={styles.product}>
                    <div className={styles.productCell}>
                      <Photo src={line.img_url} small />
                      <div className={styles.productText}>
                        <button
                          type="button"
                          className={rowStyles.name}
                          aria-expanded={expanded}
                          aria-controls={detailsId}
                          onClick={() => setOpen(expanded ? null : key)}
                        >
                          {line.title}
                          <ChevronDown
                            className={`${styles.chevron} ${expanded ? styles.chevronOpen : ''}`}
                            strokeWidth={1.75}
                            aria-hidden="true"
                          />
                        </button>
                        <p className={`${rowStyles.brand} num`}>{brandLine(line)}</p>
                        <Badges row={row} onComposition={() => setOpen(key)} />
                      </div>
                    </div>
                  </td>
                  <td className={`${styles.numCol} num`}>
                    {line.packs > 1 ? `${line.packs} × ${formatPrice(line.price)}` : formatPrice(line.price)}
                  </td>
                  <td className={`${styles.numCol} ${self?.lowest ? styles.lowest : ''}`}>
                    <UnitPriceText line={line} />
                    {self?.lowest && <span className="sr-only"> найдешевше</span>}
                  </td>
                  <td className={`${styles.numCol} ${styles.sum} num`}>{formatPrice(line.line_total)}</td>
                  {others.map((b) => {
                    const c = row.compare.find((x) => x.basket.type === b.type)
                    if (!c || c.total == null) {
                      return (
                        <td key={b.type} className={`${styles.numCol} ${styles.compare}`}>
                          <span aria-hidden="true">—</span>
                          <span className="sr-only">немає в цьому варіанті</span>
                        </td>
                      )
                    }
                    return (
                      <td key={b.type} className={`${styles.numCol} ${styles.compare} ${c.lowest ? styles.lowest : ''}`}>
                        <span className="num">{formatPrice(c.total)}</span>
                        {c.lines[0] && <UnitPriceText line={c.lines[0]} className={styles.block} />}
                        {c.lowest && <span className="sr-only"> найдешевше за кілограм</span>}
                      </td>
                    )
                  })}
                </tr>
                {(row.analog || line.note) && (
                  <tr className={styles.noteRow}>
                    <td colSpan={cols}>
                      <AnalogNotice row={row} storeName={storeName} />
                      <Note text={line.note} />
                    </td>
                  </tr>
                )}
                <tr className={styles.detailsRow} id={detailsId} hidden={!expanded}>
                  <td colSpan={cols}>
                    {expanded && <Details row={row} current={current.type} />}
                    <Button variant="ghost" size="sm" onClick={() => onRemove(key)}>
                      Прибрати з кошика
                    </Button>
                  </td>
                </tr>
              </Fragment>
            )
          })}
        </tbody>
      ))}
      <tfoot>
        <tr>
          <th scope="row" colSpan={3} className={styles.totalLabel}>
            Разом
          </th>
          <td className={`${styles.numCol} ${styles.total} num`}>{formatPrice(currentTotal)}</td>
          {others.map((b) => {
            const t = totals.get(b.type) ?? b.total
            return (
              <td key={b.type} className={`${styles.numCol} ${styles.compare}`}>
                <span className={`${styles.total} num`}>{formatPrice(t)}</span>
                <span className={`${styles.block} ${styles.diff} num`}>{signedDiff(t - currentTotal)}</span>
                {b.missing.length > 0 && (
                  <span className={`${styles.block} ${styles.diff} num`}>сума без {b.missing.length === 1 ? '1 товару' : `${b.missing.length} товарів`}</span>
                )}
              </td>
            )
          })}
        </tr>
      </tfoot>
    </table>
  )
}
