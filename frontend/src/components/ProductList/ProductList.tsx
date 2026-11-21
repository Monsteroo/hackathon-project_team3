import { Check, X } from 'lucide-react'
import { useState } from 'react'
import { MAX_COUNT, MIN_COUNT } from '../../features/basket/draftStore'
import type { BasketItem } from '../../features/basket/types'
import { formatPack } from '../../lib/format'
import { Stepper } from '../Stepper/Stepper'
import styles from './ProductList.module.css'

type Props = {
  items: BasketItem[]
  /** `list` — десктоп (рядки зі степпером), `chips` — мобільний (чип + редактор). */
  variant: 'list' | 'chips'
  onCount: (id: string, count: number) => void
  onRemove: (id: string) => void
}

/** «пачка 1 л», «поштучно», «пачка 350 г». */
function packMeta(item: BasketItem): string {
  const pack = formatPack(item.packQty, item.unit)
  return item.unit === 'pcs' && item.packQty === 1 ? pack : `пачка ${pack}`
}

/** Кількість на чипі: «2 × 1 л», «10 шт», «200 г». */
function chipQty(item: BasketItem): string {
  if (item.unit === 'pcs' && item.packQty === 1) return `${item.count} шт`
  const pack = formatPack(item.packQty, item.unit)
  return item.count === 1 ? pack : `${item.count} × ${pack}`
}

/** DESIGN.md §4.9 BasketEditor: список товарів екрана 2. */
export function ProductList({ items, variant, onCount, onRemove }: Props) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const editing = items.find((i) => i.id === editingId) ?? null

  if (variant === 'list') {
    return (
      <ul className={styles.list}>
        {items.map((item) => (
          <li key={item.id} className={styles.row}>
            <span className={styles.name}>
              {item.label}
              <span className={`${styles.meta} num`}>{packMeta(item)}</span>
            </span>
            <Stepper
              size="sm"
              value={item.count}
              min={MIN_COUNT}
              max={MAX_COUNT}
              label={`Кількість: ${item.label}`}
              onChange={(n) => onCount(item.id, n)}
            />
            <button
              type="button"
              className={styles.remove}
              aria-label={`Прибрати ${item.label}`}
              onClick={() => onRemove(item.id)}
            >
              <X strokeWidth={1.75} aria-hidden="true" />
            </button>
          </li>
        ))}
      </ul>
    )
  }

  return (
    <>
      <ul className={styles.chips}>
        {items.map((item) => (
          <li key={item.id} className={[styles.chip, item.id === editingId && styles.editing].filter(Boolean).join(' ')}>
            <button
              type="button"
              className={styles.chipMain}
              aria-expanded={item.id === editingId}
              aria-label={`${item.label}, ${chipQty(item)}. Змінити кількість`}
              onClick={() => setEditingId(item.id === editingId ? null : item.id)}
            >
              {item.label} <span className={`${styles.qty} num`}>{chipQty(item)}</span>
            </button>
            <button
              type="button"
              className={styles.chipRemove}
              aria-label={`Прибрати ${item.label}`}
              onClick={() => {
                if (item.id === editingId) setEditingId(null)
                onRemove(item.id)
              }}
            >
              <X strokeWidth={1.75} aria-hidden="true" />
            </button>
          </li>
        ))}
      </ul>
      {editing && (
        <div className={styles.editor}>
          <p className={styles.editorName}>
            {editing.label}
            <span className={`${styles.meta} num`}>{packMeta(editing)}</span>
          </p>
          <Stepper
            value={editing.count}
            min={MIN_COUNT}
            max={MAX_COUNT}
            label={`Кількість: ${editing.label}`}
            onChange={(n) => onCount(editing.id, n)}
          />
          <button type="button" className={styles.remove} aria-label="Готово" onClick={() => setEditingId(null)}>
            <Check strokeWidth={1.75} aria-hidden="true" />
          </button>
        </div>
      )}
    </>
  )
}
