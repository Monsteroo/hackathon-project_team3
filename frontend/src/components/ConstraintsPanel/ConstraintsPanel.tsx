import { Car, Check, Footprints } from 'lucide-react'
import { useId } from 'react'
import { estimateMinutes, radiusOptions } from '../../features/basket/draftStore'
import type { BasketDraft, Tag } from '../../features/basket/types'
import type { Mode } from '../../lib/api/types'
import { formatDistance, formatInteger, formatRoundPrice } from '../../lib/format'
import styles from './ConstraintsPanel.module.css'

const BUDGET_PRESETS = [500, 1000, 1500]
const MAX_BUDGET = 100_000

/** Лише фільтри, які перевіряє каталог (теги складу з CLAUDE.md). */
const TAG_LABELS: Record<Tag, string> = {
  sugar: 'Без цукру',
  lactose: 'Без лактози',
  palm_oil: 'Без пальмової олії',
  private_label: 'Без власних марок мереж',
}
const TAGS = Object.keys(TAG_LABELS) as Tag[]

const MODES: { id: Mode; label: string; Icon: typeof Footprints }[] = [
  { id: 'walk', label: 'Пішки', Icon: Footprints },
  { id: 'car', label: 'Авто', Icon: Car },
]

type Props = {
  draft: BasketDraft
  onBudget: (budget: number | null) => void
  onToggleTag: (tag: Tag) => void
  onMode: (mode: Mode) => void
  onRadius: (km: number) => void
}

/** DESIGN.md §4.9 BasketEditor: бюджет, склад, відстань. */
export function ConstraintsPanel({ draft, onBudget, onToggleTag, onMode, onRadius }: Props) {
  const id = useId()
  const radii = radiusOptions(draft.mode, draft.radiusKm)

  return (
    <div className={styles.panel}>
      <fieldset className={styles.fset}>
        <legend>Бюджет</legend>
        <div className={styles.budgetRow}>
          <label className={styles.money}>
            <span className="sr-only">Сума бюджету, гривень</span>
            <input
              className="num"
              inputMode="numeric"
              placeholder="Без обмежень"
              value={draft.budget != null ? formatInteger(draft.budget) : ''}
              onChange={(e) => {
                const n = Number(e.target.value.replace(/\D/g, ''))
                onBudget(n > 0 ? Math.min(n, MAX_BUDGET) : null)
              }}
            />
            <span aria-hidden="true">₴</span>
          </label>
          <div className={styles.choices} role="radiogroup" aria-label="Швидкий вибір бюджету">
            {BUDGET_PRESETS.map((v) => (
              <label key={v} className={styles.choice}>
                <input
                  type="radio"
                  name={`${id}-budget`}
                  checked={draft.budget === v}
                  onChange={() => onBudget(v)}
                />
                <span className="num">{formatRoundPrice(v)}</span>
              </label>
            ))}
            <label className={styles.choice}>
              <input type="radio" name={`${id}-budget`} checked={draft.budget == null} onChange={() => onBudget(null)} />
              <span>Без бюджету</span>
            </label>
          </div>
        </div>
        <p className={styles.hint}>Покажемо, якщо варіант не вкладається, і що можна прибрати</p>
      </fieldset>

      <fieldset className={styles.fset}>
        <legend>Склад</legend>
        <div className={styles.checks}>
          {TAGS.map((tag) => (
            <label key={tag} className={styles.check}>
              <span className={styles.box}>
                <input type="checkbox" checked={draft.exclude.includes(tag)} onChange={() => onToggleTag(tag)} />
                <Check strokeWidth={2.5} aria-hidden="true" />
              </span>
              <span>{TAG_LABELS[tag]}</span>
            </label>
          ))}
        </div>
        <p className={styles.hint}>Товар із невідомим складом фільтр не пройде: краще перевірити, ніж вгадати</p>
      </fieldset>

      <fieldset className={styles.fset}>
        <legend>Відстань</legend>
        <div className={styles.choices} role="radiogroup" aria-label="Як добиратися">
          {MODES.map(({ id: m, label, Icon }) => (
            <label key={m} className={styles.choice}>
              <input type="radio" name={`${id}-mode`} checked={draft.mode === m} onChange={() => onMode(m)} />
              <span>
                <Icon strokeWidth={1.75} aria-hidden="true" />
                {label}
              </span>
            </label>
          ))}
        </div>
        <div
          className={styles.seg}
          role="radiogroup"
          aria-label={draft.mode === 'walk' ? 'Радіус пішки' : 'Радіус на авто'}
        >
          {radii.map((km) => (
            <label key={km} className={styles.segItem}>
              <input type="radio" name={`${id}-radius`} checked={draft.radiusKm === km} onChange={() => onRadius(km)} />
              <span>
                <span className="num">{formatDistance(km * 1000)}</span>
                <small className="num">≈ {estimateMinutes(km, draft.mode)} хв</small>
              </span>
            </label>
          ))}
        </div>
        <p className={styles.hint}>Шукаємо магазини в цьому радіусі від вашої адреси</p>
      </fieldset>
    </div>
  )
}
