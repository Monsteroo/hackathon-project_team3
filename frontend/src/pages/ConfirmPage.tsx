import { ArrowLeft, ArrowRight, LoaderCircle, LocateFixed } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'
import { AddProductSearch } from '../components/AddProductSearch/AddProductSearch'
import { AddressSearch } from '../components/AddressSearch/AddressSearch'
import { Button } from '../components/Button/Button'
import { ConstraintsPanel } from '../components/ConstraintsPanel/ConstraintsPanel'
import { ProductList } from '../components/ProductList/ProductList'
import {
  addItem,
  applyConstraints,
  getBasketDraft,
  initFromVoice,
  isSameVoice,
  removeItem,
  setBudget,
  setCount,
  setMode,
  setRadius,
  toggleExclude,
  useBasketDraft,
} from '../features/basket/draftStore'
import { parseItems, type ParseStatus } from '../features/basket/parseItems'
import type { BasketItem } from '../features/basket/types'
import { useCatalogChains } from '../features/basket/useCatalogChains'
import {
  getCurrentPosition,
  POSITION_MESSAGES,
  PositionError,
  type Origin,
  type PositionFailure,
} from '../features/location/position'
import { localVoiceResult } from '../lib/api/client'
import type { Place, VoiceResult } from '../lib/api/types'
import { pluralItems } from '../lib/format'
import { useCity } from '../lib/useCity'
import { MQ_COMPACT, useMediaQuery } from '../lib/useMediaQuery'
import styles from './ConfirmPage.module.css'

type State = { voice?: VoiceResult; query?: string } | null

/** «у 1 мережі», «у 6 мережах». */
function inChains(n: number): string {
  return n % 10 === 1 && n % 100 !== 11 ? `у ${n} мережі` : `у ${n} мережах`
}

/** Той самий запит (повернулися з /results) → лишаємо правки, агента не кличемо. */
function needsParse(voice: VoiceResult): boolean {
  return !isSameVoice(getBasketDraft()?.voice ?? null, voice)
}

/** Нова чернетка з запиту + позиції й обмеження від агента (/agent/parse). null — розбору не було. */
async function startFrom(voice: VoiceResult): Promise<ParseStatus | null> {
  if (!needsParse(voice)) return null
  initFromVoice(voice)
  const parsed = await parseItems(voice)
  if (!isSameVoice(getBasketDraft()?.voice ?? null, voice)) return null
  parsed.items.forEach(addItem)
  applyConstraints(parsed)
  return parsed.status
}

/** Порожній список: чому він порожній. */
const EMPTY_TITLE: Record<ParseStatus | 'none', string> = {
  ok: 'Додайте товари, які треба купити',
  none: 'Додайте товари, які треба купити',
  empty: 'Не вдалося розпізнати продукти в запиті',
  unavailable: 'Не вдалося розібрати запит автоматично',
}

/**
 * Екран 2 «Я зрозумів так» (design/BRIEF.md, DESIGN.md §4.9). Список ліворуч, обмеження праворуч.
 * Режим і радіус — з VoiceResult; товари, бюджет і склад — з розбору агента (parseItems), далі правки вручну.
 */
export function ConfirmPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const state = location.state as State
  const draft = useBasketDraft()
  const city = useCity()
  const compact = useMediaQuery(MQ_COMPACT)
  const chains = useCatalogChains(city.name)

  /** Агент розбирає запит (LLM — 2–4 с). Рядок без VoiceResult (старий формат state) — VoiceResult збираємо локально. */
  const [parsing, setParsing] = useState(() => (state?.voice ? needsParse(state.voice) : !!state?.query))
  const [announce, setAnnounce] = useState('')
  const [parseStatus, setParseStatus] = useState<ParseStatus | null>(null)
  /** Крок 3: визначаємо місце після CTA. */
  const [locating, setLocating] = useState(false)
  /** GPS не вийшов → поле адреси. */
  const [positionFailure, setPositionFailure] = useState<PositionFailure | null>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const addressRef = useRef<HTMLInputElement>(null)
  /** Один старт на запис історії: StrictMode викликає ефект двічі. */
  const startedRef = useRef<string | null>(null)

  useEffect(() => {
    if (startedRef.current === location.key) return
    startedRef.current = location.key
    if (state?.voice) {
      void startFrom(state.voice)
        .then(setParseStatus)
        .finally(() => setParsing(false))
    } else if (state?.query) {
      const query = state.query
      void startFrom(localVoiceResult(query))
        .then(setParseStatus)
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

  function goToResults(origin: Origin) {
    // from: 'confirm' → «До списку» на /results повертає по історії, а не додає новий запис.
    navigate('/results', { state: { origin, from: 'confirm' } })
  }

  /** «Знайти ціни»: спершу GPS; заборонено чи не вийшло — поле адреси. */
  async function submit() {
    const current = getBasketDraft()
    if (!current || current.items.length === 0) {
      searchRef.current?.focus()
      return
    }
    if (locating) return
    setLocating(true)
    try {
      const { lat, lng } = await getCurrentPosition()
      goToResults({ lat, lng, label: null, source: 'gps' })
    } catch (e) {
      setLocating(false)
      setPositionFailure(e instanceof PositionError ? e.reason : 'unavailable')
      // Поле з'являється після рендера.
      requestAnimationFrame(() => {
        addressRef.current?.focus()
        addressRef.current?.scrollIntoView?.({ block: 'center' })
      })
    }
  }

  function onAddress(place: Place) {
    goToResults({ lat: place.lat, lng: place.lng, label: place.label, source: 'address' })
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
              <strong>{EMPTY_TITLE[parseStatus ?? 'none']}</strong>
              {parseStatus === 'empty' || parseStatus === 'unavailable'
                ? 'Додайте товари вручну: почніть вводити назву, і ми підкажемо категорію або товар із каталогу'
                : 'Почніть вводити назву: підкажемо категорію або товар із каталогу'}
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
          {positionFailure && (
            <div className={styles.location}>
              <p className={styles.locationNote}>
                <LocateFixed strokeWidth={1.75} aria-hidden="true" />
                <span role="status">{POSITION_MESSAGES[positionFailure]}</span>
              </p>
              <AddressSearch inputRef={addressRef} near={{ lat: city.lat, lng: city.lng }} onPick={onAddress} />
            </div>
          )}
          <div className={styles.cta}>
            <p className={`${styles.meta} num`}>
              {chains ? `Порівняємо весь кошик ${inChains(chains)}` : 'Порівняємо весь кошик, а не окремі знижки'}
            </p>
            <Button
              className={styles.ctaButton}
              disabled={count === 0}
              loading={locating}
              iconEnd={<ArrowRight strokeWidth={1.75} aria-hidden="true" />}
              onClick={() => void submit()}
            >
              {locating ? 'Визначаю, де ви…' : ctaLabel}
            </Button>
          </div>
        </section>
      </div>
    </section>
  )
}
