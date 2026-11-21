import { ArrowLeft, ArrowRight, LoaderCircle } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'
import { AddProductSearch } from '../components/AddProductSearch/AddProductSearch'
import { Button } from '../components/Button/Button'
import { ConstraintsPanel } from '../components/ConstraintsPanel/ConstraintsPanel'
import { ProductList } from '../components/ProductList/ProductList'
import {
  addItem,
  getBasketDraft,
  initFromVoice,
  isSameVoice,
  removeItem,
  setBudget,
  setCount,
  setMode,
  setRadius,
  toAgentItems,
  toggleExclude,
  useBasketDraft,
} from '../features/basket/draftStore'
import { parseItems } from '../features/basket/parseItems'
import type { BasketItem } from '../features/basket/types'
import { useCatalogChains } from '../features/basket/useCatalogChains'
import { api, localVoiceResult } from '../lib/api/client'
import type { VoiceResult } from '../lib/api/types'
import { pluralItems } from '../lib/format'
import { useCity } from '../lib/useCity'
import { MQ_COMPACT, useMediaQuery } from '../lib/useMediaQuery'
import styles from './ConfirmPage.module.css'

type State = { voice?: VoiceResult; query?: string } | null

/** «у 1 мережі», «у 6 мережах». */
function inChains(n: number): string {
  return n % 10 === 1 && n % 100 !== 11 ? `у ${n} мережі` : `у ${n} мережах`
}

/** Новий запит → нова чернетка; той самий (повернулися з /results) → лишаємо правки. */
async function startFrom(voice: VoiceResult) {
  if (isSameVoice(getBasketDraft()?.voice ?? null, voice)) return
  initFromVoice(voice)
  const items = await parseItems(voice)
  if (isSameVoice(getBasketDraft()?.voice ?? null, voice)) items.forEach(addItem)
}

/**
 * Екран 2 «Я зрозумів так» (design/BRIEF.md, DESIGN.md §4.9). Список ліворуч, обмеження праворуч.
 * Режим і радіус — з VoiceResult; товари поки додаються вручну, поки немає агента (parseItems).
 */
export function ConfirmPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const state = location.state as State
  const draft = useBasketDraft()
  const city = useCity()
  const compact = useMediaQuery(MQ_COMPACT)
  const chains = useCatalogChains(city.name)

  /** Прийшов лише рядок (старий формат state): спершу /voice/parse-text. */
  const [parsing, setParsing] = useState(() => !state?.voice && !!state?.query)
  const [announce, setAnnounce] = useState('')
  const searchRef = useRef<HTMLInputElement>(null)
  /** Один старт на запис історії: StrictMode викликає ефект двічі. */
  const startedRef = useRef<string | null>(null)

  useEffect(() => {
    if (startedRef.current === location.key) return
    startedRef.current = location.key
    if (state?.voice) {
      void startFrom(state.voice)
    } else if (state?.query) {
      const query = state.query
      api
        .parseText(query)
        .catch(() => localVoiceResult(query))
        .then((voice) => startFrom(voice))
        .finally(() => setParsing(false))
    } else if (!getBasketDraft()) {
      navigate('/', { replace: true })
    }
  }, [location.key, state, navigate])

  const count = draft?.items.length ?? 0
  const isEmpty = !!draft && count === 0

  // Порожній список: одразу в пошук (на десктопі, щоб не відкривати клавіатуру на телефоні).
  useEffect(() => {
    if (isEmpty && !parsing && !compact) searchRef.current?.focus()
  }, [isEmpty, parsing, compact])

  if (!draft || parsing) {
    return (
      <section className={styles.loading} aria-live="polite">
        <LoaderCircle className={styles.spin} strokeWidth={1.75} aria-hidden="true" />
        <p>Розбираю запит…</p>
      </section>
    )
  }

  function onAdd(item: Omit<BasketItem, 'id'>) {
    addItem(item)
    setAnnounce(`Додано: ${item.label}`)
  }

  function onRemove(id: string) {
    const item = draft?.items.find((i) => i.id === id)
    removeItem(id)
    if (item) setAnnounce(`Прибрано: ${item.label}`)
  }

  function submit() {
    const current = getBasketDraft()
    if (!current || current.items.length === 0) {
      searchRef.current?.focus()
      return
    }
    navigate('/results', { state: { draft: current, items: toAgentItems(current) } })
  }

  const ctaLabel = `Знайти ціни · ${pluralItems(count)}`

  return (
    <section className={styles.page} aria-labelledby="confirm-title">
      <header className={styles.head}>
        {compact && (
          <Link to="/" className={styles.back}>
            <ArrowLeft strokeWidth={1.75} aria-hidden="true" />
            До запиту
          </Link>
        )}
        <h1 id="confirm-title" className={styles.title}>
          Я зрозумів так
        </h1>
        {draft.voice && (
          <p className={styles.said}>
            <span className={styles.saidLabel}>Ви сказали:</span>
            <q>{draft.voice.raw_text}</q>
          </p>
        )}
      </header>

      <div className={styles.main}>
        <section className={styles.panel} aria-labelledby="confirm-products">
          <div className={styles.blockHead}>
            <h2 id="confirm-products" className={styles.sectionLabel}>
              Продукти
            </h2>
            <span className={`${styles.meta} num`}>{pluralItems(count)}</span>
          </div>

          {isEmpty ? (
            <p className={styles.empty}>
              <strong>Додайте товари, які треба купити</strong>
              Почніть вводити назву: підкажемо категорію або товар із каталогу
            </p>
          ) : (
            <ProductList
              items={draft.items}
              variant={compact ? 'chips' : 'list'}
              onCount={setCount}
              onRemove={onRemove}
            />
          )}
          <AddProductSearch inputRef={searchRef} onAdd={onAdd} />
          <p className="sr-only" aria-live="polite">
            {announce}
          </p>
        </section>

        <section className={styles.panel} aria-labelledby="confirm-limits">
          <div className={styles.blockHead}>
            <h2 id="confirm-limits" className={styles.sectionLabel}>
              Обмеження
            </h2>
            <span className={styles.meta}>Склад перевіримо для кожного товару</span>
          </div>
          <ConstraintsPanel
            draft={draft}
            onBudget={setBudget}
            onToggleTag={toggleExclude}
            onMode={setMode}
            onRadius={setRadius}
          />
          <div className={styles.cta}>
            <p className={`${styles.meta} num`}>
              {chains ? `Порівняємо весь кошик ${inChains(chains)}` : 'Порівняємо весь кошик, а не окремі знижки'}
            </p>
            <Button
              className={styles.ctaButton}
              disabled={count === 0}
              iconEnd={<ArrowRight strokeWidth={1.75} aria-hidden="true" />}
              onClick={submit}
            >
              {ctaLabel}
            </Button>
          </div>
        </section>
      </div>
    </section>
  )
}
