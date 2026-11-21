import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, CircleAlert, ExternalLink, Info, PackageX, RotateCcw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { BasketRow } from '../components/BasketRow/BasketRow'
import type { RowData } from '../components/BasketRow/parts'
import { BasketTable } from '../components/BasketTable/BasketTable'
import { Button } from '../components/Button/Button'
import buttonStyles from '../components/Button/Button.module.css'
import cardStyles from '../components/OptionCard/OptionCard.module.css'
import { useBasketDraft } from '../features/basket/draftStore'
import {
  analogOf,
  basketTotal,
  compareRequested,
  departmentOf,
  DEPARTMENTS,
  freshnessText,
  groupByDepartment,
  lineInStore,
  nonstandardWeight,
  requestedItem,
  trimCandidates,
  verifiedTags,
  type Group,
} from '../features/basket-details/details'
import {
  chainName,
  distanceText,
  missingReason,
  monogram,
  OPTION_TITLE,
  routeUrl,
  STORE_OPTION_PREFIX,
  storeBasket,
  tradeoff,
  type OptionType,
} from '../features/results/options'
import { loadResult } from '../features/results/resultsStore'
import { api } from '../lib/api/client'
import type { AgentBasket, BasketLine, BasketOut } from '../lib/api/types'
import { formatPrice, formatRoundPrice, pluralItems } from '../lib/format'
import { MQ_TABLE, useMediaQuery } from '../lib/useMediaQuery'
import styles from './BasketPage.module.css'

const TYPES: OptionType[] = ['nearest', 'cheapest', 'smart_split']

function isOption(v: string | undefined): v is OptionType {
  return TYPES.includes(v as OptionType)
}

/** «1 аналог / 2 аналоги / 5 аналогів». */
function pluralAnalogs(n: number): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return `${n} аналог`
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${n} аналоги`
  return `${n} аналогів`
}

function capitalize(text: string): string {
  return text.charAt(0).toLocaleUpperCase('uk') + text.slice(1)
}

/** «без 1 товару / без 3 товарів». */
function withoutItems(n: number): string {
  return n % 10 === 1 && n % 100 !== 11 ? `${n} товару` : `${n} товарів`
}

/** Різниця ціни аналога з оригіналом (той самий бренд в іншому варіанті), за одиницю. */
function analogDiff(line: BasketLine, result: BasketOut): RowData['analogDiff'] {
  const item = requestedItem(line, result.parsed)
  const original = result.baskets
    .flatMap((b) => b.lines)
    .find((l) => l.requested === line.requested && analogOf(l, item) == null && l.unit_price != null)
  if (!original || line.unit_price == null || original.unit_price == null) return null
  return { value: line.unit_price - original.unit_price, unit: line.unit_price_label.split('/')[1] ?? '' }
}

function rowData(line: BasketLine, result: BasketOut): RowData {
  const item = requestedItem(line, result.parsed)
  const analog = analogOf(line, item)
  return {
    line,
    item,
    verified: verifiedTags(line, item, result.parsed),
    analog,
    analogDiff: analog ? analogDiff(line, result) : null,
    weight: nonstandardWeight(line),
    compare: compareRequested(line.requested, result.baskets),
  }
}

/** Smart Split — спершу за магазином, всередині за відділами; один магазин — за відділами. */
function buildGroups(basket: AgentBasket, rows: RowData[]): Group<RowData>[] {
  const category = (r: RowData) => r.item?.category
  if (basket.stores.length < 2) return groupByDepartment(rows, category)
  const order = DEPARTMENTS.map((d) => d.id as string)
  const rank = (r: RowData) => {
    const i = order.indexOf(departmentOf(category(r)).id)
    return i === -1 ? order.length : i
  }
  return basket.stores.map((store, i) => {
    const items = rows.filter((r) => lineInStore(r.line, store)).sort((a, b) => rank(a) - rank(b))
    const sum = items.reduce((s, r) => s + r.line.line_total, 0)
    return {
      id: store.store_id,
      title: `Магазин ${i + 1} · ${chainName(store)} · ${pluralItems(items.length)} · ${formatPrice(sum)}`,
      items,
    }
  })
}

/**
 * Екран 4 «Деталі кошика» (BRIEF, DESIGN_PROMPT §Екран 4, DESIGN.md §4.3–4.6).
 * Дані — збережена відповідь /agent/basket з екрана 3 (sessionStorage), без нового виклику агента.
 * Мобільний: підсумок, список BasketRow за відділами, нижня панель дій.
 * Десктоп: ліворуч підсумок і дії, праворуч таблиця з порівнянням з іншими варіантами.
 */
export function BasketPage() {
  const { optionId } = useParams()
  const navigate = useNavigate()
  const draft = useBasketDraft()
  const wide = useMediaQuery(MQ_TABLE)
  const saved = loadResult()
  const result = saved?.result ?? null
  const storeId = optionId?.startsWith(STORE_OPTION_PREFIX) ? optionId.slice(STORE_OPTION_PREFIX.length) : null
  const storeOption = storeId ? result?.stores?.find((o) => o.store.store_id === storeId) : undefined
  const basket = isOption(optionId)
    ? (result?.baskets.find((b) => b.type === optionId) ?? null)
    : storeOption
      ? storeBasket(storeOption)
      : null
  const [removed, setRemoved] = useState<Set<string>>(() => new Set())

  const etl = useQuery({
    queryKey: ['etl-status'],
    queryFn: ({ signal }) => api.etlStatus(signal),
    staleTime: 5 * 60_000,
    retry: false,
  })

  // Перезавантаження в новій вкладці або старе посилання: рахуємо варіанти на екрані 3.
  useEffect(() => {
    if (!result) navigate('/results', { replace: true })
  }, [result, navigate])

  if (!result || !saved) return null

  if (!basket) {
    return (
      <section className={styles.empty} aria-labelledby="basket-title">
        <h1 id="basket-title" className={styles.title}>
          Такого варіанту немає
        </h1>
        <p className={styles.meta}>Можливо, список змінився. Поверніться до варіантів і виберіть інший.</p>
        <Link to="/results" className={`${buttonStyles.button} ${buttonStyles.secondary}`}>
          <span className={buttonStyles.icon} aria-hidden="true">
            <ArrowLeft strokeWidth={1.75} />
          </span>
          До варіантів
        </Link>
      </section>
    )
  }

  const totals = new Map(result.baskets.map((b) => [b.type, basketTotal(b, removed)]))
  // Кошик магазину зі списку «усі магазини» не входить у baskets: його суму рахуємо окремо.
  totals.set(basket.type, basketTotal(basket, removed))
  const total = totals.get(basket.type) ?? basket.total
  const view = result.baskets.map((b) => ({ ...b, total: totals.get(b.type) ?? b.total }))
  const trade = tradeoff({ ...basket, total }, view)

  const allRows = basket.lines.map((l) => rowData(l, result))
  const rows = allRows.filter((r) => !removed.has(r.line.requested))
  const removedRows = allRows.filter((r) => removed.has(r.line.requested))
  const groups = buildGroups(basket, rows)

  const mode = saved.request.mode ?? result.parsed.constraints.travel_mode
  const store = basket.stores[0]
  const storeName = basket.stores.map(chainName).join(' і ')
  const analogs = rows.filter((r) => r.analog).length
  const missing = basket.missing
  const budget = draft?.budget ?? result.parsed.constraints.budget_uah
  const over = budget != null && total > budget ? total - budget : 0
  const route = routeUrl(basket, saved.origin, mode)
  const fresh = freshnessText(etl.data?.prices_updated_at)

  const remove = (requested: string) => setRemoved((s) => new Set(s).add(requested))
  const restore = (requested: string) =>
    setRemoved((s) => {
      const next = new Set(s)
      next.delete(requested)
      return next
    })

  const summaryMeta = [pluralItems(rows.length)]
  if (analogs > 0) summaryMeta.push(pluralAnalogs(analogs))

  return (
    <section className={styles.page} aria-labelledby="basket-title">
      <aside className={styles.summaryCol}>
        <Link to="/results" className={styles.back}>
          <ArrowLeft strokeWidth={1.75} aria-hidden="true" />
          До варіантів
        </Link>

        <div className={styles.summary} aria-label="Підсумок кошика" role="group">
          <p className={styles.overline}>{OPTION_TITLE[basket.type]}</p>
          <h1 id="basket-title" className={styles.title}>
            Деталі кошика
          </h1>
          {basket.stores.map((s) => (
            <div key={s.store_id} className={styles.store}>
              <p className={styles.chainRow}>
                <span className={cardStyles.logo} aria-hidden="true">
                  {monogram(s)}
                </span>
                <span className={styles.chain}>{chainName(s)}</span>
                {s.address && <span className={styles.address}>· {s.address}</span>}
              </p>
              <p className={`${styles.meta} num`}>{distanceText(s, mode)}</p>
            </div>
          ))}

          <p className={`${styles.total} num`} aria-live="polite">
            {formatPrice(total)}
          </p>
          {missing.length > 0 && <p className={`${styles.meta} num`}>Сума без {withoutItems(missing.length)}</p>}
          {trade && (
            <p className={`${styles.trade} num`}>
              {trade.save && <span className={styles.save}>{trade.save}</span>}
              {trade.rest}
            </p>
          )}
          <p className={`${styles.meta} num`}>{summaryMeta.join(' · ')}</p>
        </div>

        {over > 0 && (
          <div className={styles.danger} role="status">
            <CircleAlert strokeWidth={1.75} aria-hidden="true" />
            <div>
              <p className={styles.dangerTitle}>
                Понад бюджет на <span className="num">{formatRoundPrice(Math.ceil(over))}</span>
              </p>
              <p className={styles.dangerText}>Бюджет {formatRoundPrice(budget!)}. Що можна прибрати:</p>
              <ul className={styles.trim}>
                {trimCandidates(
                  rows.map((r) => r.line),
                  result.parsed,
                ).map((l) => (
                  <li key={l.requested}>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => remove(l.requested)}
                      aria-label={`Прибрати ${l.title}, мінус ${formatPrice(l.line_total)}`}
                    >
                      <span className={styles.trimName}>{l.requested}</span>
                      <span className={`${styles.trimSum} num`}>−{formatPrice(l.line_total)}</span>
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        <p className={`${styles.fresh} num`}>
          <Info strokeWidth={1.75} aria-hidden="true" />
          <span>
            {fresh ?? 'Ціни з нічного оновлення каталогу мереж'}. На полиці можуть відрізнятися
          </span>
        </p>

        <div className={styles.actions}>
          {route && (
            <a
              className={`${buttonStyles.button} ${buttonStyles.primary} ${styles.grow}`}
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
        </div>
      </aside>

      <div className={styles.content}>
        <p className={styles.whole}>
          <Info strokeWidth={1.75} aria-hidden="true" />
          {result.baskets.length > 1
            ? 'Порівнюємо весь кошик, а не окремі знижки. Один товар може бути дешевшим деінде, але разом цей варіант вигідніший'
            : 'Порівнюємо весь кошик, а не окремі знижки'}
        </p>

        {rows.length === 0 ? (
          <p className={styles.meta}>У кошику не залишилось товарів.</p>
        ) : !wide ? (
          groups.map((g) => (
            <section key={g.id} className={styles.group} aria-labelledby={`dep-${g.id}`}>
              <h2 id={`dep-${g.id}`} className={styles.groupTitle}>
                {g.title}
              </h2>
              <ul className={styles.list}>
                {g.items.map((r) => (
                  <BasketRow
                    key={r.line.requested}
                    row={r}
                    current={basket.type}
                    storeName={storeName}
                    onRemove={() => remove(r.line.requested)}
                  />
                ))}
              </ul>
            </section>
          ))
        ) : (
          <BasketTable
            groups={groups}
            current={basket}
            baskets={result.baskets}
            totals={totals}
            storeName={store ? chainName(store) : storeName}
            onRemove={remove}
          />
        )}

        {missing.length > 0 && (
          <section className={styles.group} aria-labelledby="missing-title">
            <h2 id="missing-title" className={styles.groupTitle}>
              Не знайшли ({missing.length})
            </h2>
            <ul className={styles.list}>
              {missing.map((m) => (
                <li key={m.name} className={styles.missingRow}>
                  <span className={styles.missingIcon}>
                    <PackageX strokeWidth={1.75} aria-hidden="true" />
                  </span>
                  <div>
                    <p className={styles.missingName}>{m.name}</p>
                    <span className={styles.badgeDanger}>
                      <CircleAlert strokeWidth={1.75} aria-hidden="true" />
                      {capitalize(missingReason(m.reason))}
                    </span>
                    <p className={styles.meta}>Суму порахували без цієї позиції</p>
                  </div>
                  <span className={styles.missingPrice} aria-label="Ціни немає">
                    —
                  </span>
                </li>
              ))}
            </ul>
            <Link to="/confirm" className={`${buttonStyles.button} ${buttonStyles.ghost} ${styles.changeList}`}>
              Змінити список
            </Link>
          </section>
        )}

        {removedRows.length > 0 && (
          <section className={styles.group} aria-labelledby="removed-title">
            <h2 id="removed-title" className={styles.groupTitle}>
              Прибрані ({removedRows.length})
            </h2>
            <ul className={styles.list}>
              {removedRows.map((r) => (
                <li key={r.line.requested} className={styles.removedRow}>
                  <span className={styles.removedName}>{r.line.title}</span>
                  <span className={`${styles.meta} num`}>{formatPrice(r.line.line_total)}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={<RotateCcw strokeWidth={1.75} />}
                    onClick={() => restore(r.line.requested)}
                    aria-label={`Повернути ${r.line.title}`}
                  >
                    Повернути
                  </Button>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </section>
  )
}
