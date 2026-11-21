import { useId, useState } from 'react'
import type { AgentBasket } from '../../lib/api/types'
import { formatPrice } from '../../lib/format'
import { Button } from '../Button/Button'
import styles from './BasketRow.module.css'
import { AnalogNotice, Badges, Details, Note, Photo, UnitPriceText, type RowData } from './parts'
import { brandLine } from '../../features/basket-details/details'

type Props = {
  row: RowData
  current: AgentBasket['type']
  storeName: string
  onRemove: () => void
}

/**
 * DESIGN.md §4.3 BasketRow (мобільний). Рядок цілком не клікабельний: назва — кнопка, що розкриває
 * деталі (склад, ціни в інших варіантах); бейджі складу — окремі кнопки.
 */
export function BasketRow({ row, current, storeName, onRemove }: Props) {
  const [open, setOpen] = useState(false)
  const detailsId = useId()
  const { line } = row

  return (
    <li className={styles.row}>
      <Photo src={line.img_url} />
      <div className={styles.main}>
        <button
          type="button"
          className={styles.name}
          aria-expanded={open}
          aria-controls={detailsId}
          onClick={() => setOpen((v) => !v)}
        >
          {line.title}
        </button>
        <p className={`${styles.brand} num`}>{brandLine(line)}</p>
        <Badges row={row} onComposition={() => setOpen(true)} />
      </div>
      <div className={styles.price}>
        {line.packs > 1 && (
          <span className={`${styles.qty} num`}>
            {line.packs} × {formatPrice(line.price)}
          </span>
        )}
        <span className={`${styles.sum} num`}>{formatPrice(line.line_total)}</span>
        {line.old_price != null && line.old_price > line.price && (
          <span className={`${styles.old} num`}>
            <span className="sr-only">Без акції: </span>
            {formatPrice(line.old_price * line.packs)}
          </span>
        )}
        <UnitPriceText line={line} />
      </div>
      <div className={styles.full}>
        <AnalogNotice row={row} storeName={storeName} />
        <Note text={line.note} />
        <div id={detailsId} hidden={!open}>
          {open && <Details row={row} current={current} />}
          <Button variant="ghost" size="sm" className={styles.remove} onClick={onRemove}>
            Прибрати з кошика
          </Button>
        </div>
      </div>
    </li>
  )
}
