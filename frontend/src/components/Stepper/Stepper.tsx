import { Minus, Plus } from 'lucide-react'
import styles from './Stepper.module.css'

type Props = {
  value: number
  min: number
  max: number
  /** Що рахуємо, для екранного читача: «Кількість: Молоко». */
  label: string
  onChange: (value: number) => void
  size?: 'default' | 'sm'
}

/** DESIGN.md §4.9 BasketEditor: степпер кількості. */
export function Stepper({ value, min, max, label, onChange, size = 'default' }: Props) {
  return (
    <div className={[styles.stepper, size === 'sm' && styles.sm].filter(Boolean).join(' ')} role="group" aria-label={label}>
      <button type="button" aria-label="Менше" disabled={value <= min} onClick={() => onChange(value - 1)}>
        <Minus strokeWidth={1.75} aria-hidden="true" />
      </button>
      <output className="num" aria-live="polite">
        {value}
      </output>
      <button type="button" aria-label="Більше" disabled={value >= max} onClick={() => onChange(value + 1)}>
        <Plus strokeWidth={1.75} aria-hidden="true" />
      </button>
    </div>
  )
}
