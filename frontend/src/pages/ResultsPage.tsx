import { ArrowLeft, ArrowRight, CircleAlert, ExternalLink, Info, MapPin, RotateCcw } from 'lucide-react'
import { useEffect, useRef, useState, type KeyboardEvent, type MouseEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'
import buttonStyles from '../components/Button/Button.module.css'
import { Button } from '../components/Button/Button'
import { OptionCard } from '../components/OptionCard/OptionCard'
import cardStyles from '../components/OptionCard/OptionCard.module.css'
import { StoreList } from '../components/StoreList/StoreList'
import { StoreMap, type MapPin as Pin } from '../components/StoreMap/StoreMap'
import { useBasketDraft } from '../features/basket/draftStore'
import type { Origin } from '../features/location/position'
import { toBasketRequest, unsupportedExcludes } from '../features/results/basketRequest'
import {
  bestOption,
  chainName,
  defaultOption,
  missingReason,
  monogram,
  routeUrl,
  STORE_OPTION_PREFIX,
  storeBasket,
  type OptionType,
} from '../features/results/options'
import { loadResult, requestKey, saveResult } from '../features/results/resultsStore'
import { useRoutes } from '../features/results/useRoutes'
import { api, ApiError } from '../lib/api/client'
import type { AgentBasket, AgentStore, BasketOut, StoreOption } from '../lib/api/types'
import { formatPrice, pluralItems } from '../lib/format'
import { useCity } from '../lib/useCity'
import styles from './ResultsPage.module.css'

type State = { origin?: Origin; from?: 'confirm' } | null

const NO_BASKETS: AgentBasket[] = []
const NO_STORES: StoreOption[] = []

type Load =
  | { status: 'loading' }
  | { status: 'ready'; result: BasketOut }
  | { status: 'error'; code: string; status_code: number }

/** Відповідь агента на конкретний запит і спробу. */
type Fetched = { key: string; attempt: number } & (
  | { result: BasketOut; code?: undefined; statusCode?: undefined }
  | { result?: undefined; code: string; statusCode: number }
)

/** «1 варіант / 3 варіанти / 5 варіантів». */
function pluralOptions(n: number): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return `${n} варіант кошика`
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${n} варіанти кошика`
  return `${n} варіантів кошика`
}

function errorText(code: string, statusCode: number): string {
  if (statusCode === 422) return 'Не вдалося розпізнати продукти в списку. Поверніться й уточніть назви'
  if (code === 'network') return 'Немає зʼєднання з сервером. Перевірте інтернет і спробуйте ще раз'
  if (code === 'unauthorized') return 'Помилка доступу до сервера'
  return 'Не вдалося отримати ціни. Спробуйте ще раз'
}

/**
 * Екран 3 «Карта + 3 варіанти» (BRIEF, DESIGN.md §4.2, MASTER OptionCard / Map).
 * Чернетка екрана 2 + місце → POST /agent/basket (5–9 с) → до 3 карток і піни на карті.
 */
export function ResultsPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const draft = useBasketDraft()
  const city = useCity()

  const saved = loadResult()
  const cameFromList = (location.state as State)?.from === 'confirm'

  /** «До списку»: якщо прийшли з /confirm — крок назад в історії (браузерні «Назад/Вперед» працюють як очікується). */
  function backToList(e: MouseEvent<HTMLAnchorElement>) {
    if (!cameFromList) return
    e.preventDefault()
    navigate(-1)
  }
  const origin = (location.state as State)?.origin ?? saved?.origin ?? null
  const request = draft && origin ? toBasketRequest(draft, origin, city.name) : null
  const key = request ? requestKey(request) : null
  /** Свіжі request і origin для ефекту запиту: сам ефект залежить лише від key. */
  const latest = useRef({ request, origin })
  useEffect(() => {
    latest.current = { request, origin }
  })

  const [fetched, setFetched] = useState<Fetched | null>(null)
  const [attempt, setAttempt] = useState(0)
  const [selected, setSelected] = useState<OptionType | null>(null)
  /** Магазин зі списку «усі магазини» (або клік на його пін): замінює вибраний варіант. */
  const [selectedStore, setSelectedStore] = useState<string | null>(null)
  const [hoveredStore, setHoveredStore] = useState<string | null>(null)
  const storeRowRefs = useRef(new Map<string, HTMLButtonElement>())

  // Той самий запит уже рахували (повернулися з екрана 4) — без нового виклику агента.
  const cached = key && saved?.key === key ? saved.result : null
  let load: Load = { status: 'loading' }
  if (cached) load = { status: 'ready', result: cached }
  else if (fetched && fetched.key === key && fetched.attempt === attempt) {
    load = fetched.result
      ? { status: 'ready', result: fetched.result }
      : { status: 'error', code: fetched.code ?? 'unknown', status_code: fetched.statusCode ?? 0 }
  }
  const [hovered, setHovered] = useState<OptionType | null>(null)
  const cardRefs = useRef(new Map<OptionType, HTMLDivElement>())

  // Без списку чи місця тут нічого показати: назад на потрібний крок.
  useEffect(() => {
    if (!draft) navigate('/', { replace: true })
    else if (!origin || draft.items.length === 0) navigate('/confirm', { replace: true })
  }, [draft, origin, navigate])

  const hasCache = !!cached
  useEffect(() => {
    const { request, origin } = latest.current
    if (!request || !key || !origin || hasCache) return
    const controller = new AbortController()
    // StrictMode прибирає і повторно запускає ефект. Даємо першій спробі скасуватися до POST.
    queueMicrotask(() => {
      if (controller.signal.aborted) return
      api
        .buildBasket(request, controller.signal)
        .then((result) => {
          if (controller.signal.aborted) return
          saveResult({ key, origin, request, result, savedAt: new Date().toISOString() })
          setFetched({ key, attempt, result })
        })
        .catch((e: unknown) => {
          if (controller.signal.aborted || (e as Error)?.name === 'AbortError') return
          const err = e instanceof ApiError ? e : new ApiError('unknown', 'unknown')
          setFetched({ key, attempt, code: err.code, statusCode: err.status })
        })
    })
    return () => controller.abort()
  }, [key, hasCache, attempt])

  const result = load.status === 'ready' ? load.result : null
  const baskets = result?.baskets ?? NO_BASKETS
  const fallback = defaultOption(baskets)
  const allStores = result?.stores ?? NO_STORES
  const activeOption =
    baskets.find((b) => b.type === selected) ?? baskets.find((b) => b.type === fallback) ?? baskets[0] ?? null
  const storeOption = selectedStore ? allStores.find((o) => o.store.store_id === selectedStore) : undefined
  const current = storeOption ? storeBasket(storeOption) : activeOption
  const best = bestOption(baskets)
  const requested = result?.parsed.items.length ?? draft?.items.length ?? 0
  const mode = request?.mode ?? draft?.mode ?? 'walk'

  /** Піни: магазини варіантів + усі інші магазини в радіусі з `stores` (сума кошика під піном). */
  const pins: Pin[] = (() => {
    const totals = new Map((result?.stores ?? []).map((o) => [o.store.store_id, o]))
    const seen = new Map<string, Pin>()
    const add = (s: AgentStore, muted: boolean) => {
      if (seen.has(s.store_id)) return
      const option = totals.get(s.store_id)
      const price = option ? formatPrice(option.total) : undefined
      const found = option && option.found < requested ? `знайдено ${option.found} з ${requested}` : null
      seen.set(s.store_id, {
        id: s.store_id,
        lat: s.lat,
        lng: s.lng,
        text: monogram(s),
        title: [chainName(s), s.address, price, found].filter(Boolean).join(' · '),
        price,
        muted,
        cheapest: option?.cheapest,
      })
    }
    for (const b of baskets) for (const s of b.stores) add(s, false)
    for (const o of result?.stores ?? []) add(o.store, true)
    return [...seen.values()]
  })()

  const storeIds = (b: AgentBasket | null | undefined) => b?.stores.map((s) => s.store_id) ?? []
  const hoveredBasket = baskets.find((b) => b.type === hovered)
  const hoverIds = hoveredStore ? [hoveredStore] : storeIds(hoveredBasket)

  function select(type: OptionType, focus = false) {
    setSelected(type)
    setSelectedStore(null)
    if (focus) cardRefs.current.get(type)?.focus()
  }

  function selectStore(id: string, scroll = false) {
    setSelectedStore(id)
    if (scroll) storeRowRefs.current.get(id)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }

  /** Клік на пін: варіант з одним цим магазином, інакше магазин зі списку «усі магазини», інакше Smart Split. */
  function onPinClick(id: string) {
    const single = baskets.find((b) => b.stores.length === 1 && b.stores[0].store_id === id && b.type === selected)
    const match = single ?? baskets.find((b) => b.stores.length === 1 && b.stores[0].store_id === id)
    if (match) return select(match.type)
    if (allStores.some((o) => o.store.store_id === id)) return selectStore(id, true)
    const split = baskets.find((b) => b.stores.some((s) => s.store_id === id))
    if (split) select(split.type)
  }

  function onCardKeyDown(e: KeyboardEvent<HTMLDivElement>, index: number) {
    const last = baskets.length - 1
    let next = index
    switch (e.key) {
      case 'ArrowDown':
      case 'ArrowRight':
        next = index === last ? 0 : index + 1
        break
      case 'ArrowUp':
      case 'ArrowLeft':
        next = index === 0 ? last : index - 1
        break
      case 'Home':
        next = 0
        break
      case 'End':
        next = last
        break
      case ' ':
      case 'Enter':
        e.preventDefault()
        select(baskets[index].type)
        return
      default:
        return
    }
    e.preventDefault()
    select(baskets[next].type, true)
  }

  const warnings = [
    ...(result?.warnings ?? []),
    ...(draft && result?.parser !== 'items' && unsupportedExcludes(draft).includes('private_label')
      ? ['Фільтр «без власних марок» поки не враховується під час підбору']
      : []),
  ]
  const route = current && origin ? routeUrl(current, origin, mode) : null
  const routes = useRoutes(current, origin, mode)
  const itemsCount = draft?.items.length ?? 0

  return (
    <section className={styles.page} aria-labelledby="results-title">
      <div className={styles.left}>
        <header className={styles.head}>
          <Link to="/confirm" className={styles.back} onClick={backToList}>
            <ArrowLeft strokeWidth={1.75} aria-hidden="true" />
            До списку
          </Link>
          <h1 id="results-title" className={styles.title}>
            {result && baskets.length > 0 ? pluralOptions(baskets.length) : 'Варіанти кошика'}
          </h1>
          <p className={`${styles.whole} num`}>
            <Info strokeWidth={1.75} aria-hidden="true" />
            Порівнюємо весь кошик, а не окремі знижки · {pluralItems(itemsCount)}
          </p>
        </header>

        {load.status === 'loading' && (
          <div className={styles.cards} aria-busy="true">
            <p className={styles.status} role="status">
              Шукаю ціни в магазинах поруч… Зазвичай це 5–10 секунд
            </p>
            {[0, 1, 2].map((i) => (
              <div key={i} className={cardStyles.skeleton} aria-hidden="true" />
            ))}
          </div>
        )}

        {load.status === 'error' && (
          <div className={styles.problem} role="alert">
            <CircleAlert strokeWidth={1.75} aria-hidden="true" />
            <p>{errorText(load.code, load.status_code)}</p>
            <div className={styles.problemActions}>
              {load.status_code !== 422 && (
                <Button
                  variant="secondary"
                  icon={<RotateCcw strokeWidth={1.75} />}
                  onClick={() => setAttempt((n) => n + 1)}
                >
                  Спробувати ще
                </Button>
              )}
              <Link to="/confirm" className={`${buttonStyles.button} ${buttonStyles.ghost}`} onClick={backToList}>
                Змінити список
              </Link>
            </div>
          </div>
        )}

        {result && baskets.length === 0 && (
          <div className={styles.problem} role="status">
            <CircleAlert strokeWidth={1.75} aria-hidden="true" />
            <p>Поруч не знайшли магазинів з цими товарами. Спробуйте більший радіус або інший список</p>
            <div className={styles.problemActions}>
              <Link to="/confirm" className={`${buttonStyles.button} ${buttonStyles.secondary}`} onClick={backToList}>
                Змінити список і радіус
              </Link>
            </div>
          </div>
        )}

        {result && baskets.length > 0 && (
          <div className={styles.cards} role="radiogroup" aria-label="Варіанти кошика">
            {baskets.map((b, i) => (
              <OptionCard
                key={b.type}
                basket={b}
                baskets={baskets}
                selected={!storeOption && b.type === activeOption?.type}
                best={b.type === best}
                requested={requested}
                budget={draft?.budget ?? result.parsed.constraints.budget_uah}
                mode={mode}
                tabIndex={b.type === activeOption?.type ? 0 : -1}
                onSelect={() => select(b.type)}
                onKeyDown={(e) => onCardKeyDown(e, i)}
                onHover={(on) => setHovered(on ? b.type : null)}
                cardRef={(el) => {
                  if (el) cardRefs.current.set(b.type, el)
                  else cardRefs.current.delete(b.type)
                }}
              />
            ))}
          </div>
        )}

        {result && (
          <div className={styles.notes}>
            {current && current.missing.length > 0 && (
              <div className={styles.missing}>
                <p className={styles.notesTitle}>{storeOption ? 'Не знайшли в цьому магазині' : 'Не знайшли в цьому варіанті'}</p>
                <ul>
                  {current.missing.map((m) => (
                    <li key={m.name}>
                      <span className={styles.missingName}>{m.name}</span> — {missingReason(m.reason)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {result.explanation && (
              <div className={styles.why}>
                <p className={styles.notesTitle}>Чому такі варіанти</p>
                <p>{result.explanation}</p>
              </div>
            )}
            {warnings.map((w) => (
              <p key={w} className={styles.warning}>
                <CircleAlert strokeWidth={1.75} aria-hidden="true" />
                <span>{w}</span>
              </p>
            ))}
          </div>
        )}

        {current && (
          <div className={styles.actions}>
            {route && (
              <a
                className={`${buttonStyles.button} ${buttonStyles.secondary}`}
                href={route}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Маршрут у Google Maps (відкриється зовнішня карта)"
              >
                <span className={buttonStyles.icon} aria-hidden="true">
                  <ExternalLink strokeWidth={1.75} />
                </span>
                Маршрут
              </a>
            )}
            <Link
              to={`/basket/${storeOption ? STORE_OPTION_PREFIX + storeOption.store.store_id : current.type}`}
              className={`${buttonStyles.button} ${buttonStyles.primary} ${styles.grow}`}
            >
              Деталі кошика
              <span className={buttonStyles.icon} aria-hidden="true">
                <ArrowRight strokeWidth={1.75} />
              </span>
            </Link>
          </div>
        )}

        {allStores.length > 0 && (
          <StoreList
            stores={allStores}
            requested={requested}
            mode={mode}
            selectedId={storeOption ? storeOption.store.store_id : null}
            onSelect={(id) => selectStore(id)}
            onHover={setHoveredStore}
            rowRef={(id, el) => {
              if (el) storeRowRefs.current.set(id, el)
              else storeRowRefs.current.delete(id)
            }}
          />
        )}
      </div>

      <div className={styles.mapCol}>
        {origin && (
          <p className={styles.originChip}>
            <MapPin strokeWidth={1.75} aria-hidden="true" />
            <span>{origin.label ?? 'Ваше місце'}</span>
          </p>
        )}
        <StoreMap
          className={styles.map}
          center={origin ? [origin.lng, origin.lat] : [city.lng, city.lat]}
          origin={origin}
          pins={pins}
          selectedIds={storeIds(current)}
          hoverIds={hoverIds}
          onPinClick={onPinClick}
          routes={routes}
          label="Карта: ви, усі магазини поруч із сумою кошика і маршрут до вибраного"
        />
      </div>
    </section>
  )
}
