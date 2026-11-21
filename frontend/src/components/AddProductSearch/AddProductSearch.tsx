import { LoaderCircle, Package, Plus, Search, Tag } from 'lucide-react'
import { useEffect, useId, useRef, useState, type KeyboardEvent, type MouseEvent, type Ref } from 'react'
import type { CategoryInfo } from '../../features/basket/categories'
import { itemFromCategory, itemFromProduct, itemFromQuery } from '../../features/basket/draftStore'
import type { BasketItem } from '../../features/basket/types'
import { useProductSearch } from '../../features/basket/useProductSearch'
import type { CatalogProduct } from '../../lib/api/types'
import { formatPack, formatPrice } from '../../lib/format'
import styles from './AddProductSearch.module.css'

type Option =
  | { kind: 'category'; category: CategoryInfo }
  | { kind: 'product'; product: CatalogProduct }
  | { kind: 'text'; text: string }

type Props = {
  onAdd: (item: Omit<BasketItem, 'id'>) => void
  inputRef?: Ref<HTMLInputElement>
}

function productMeta(p: CatalogProduct): string {
  const parts: string[] = []
  if (p.pack_qty && p.pack_unit) parts.push(formatPack(p.pack_qty, p.pack_unit))
  if (p.stores_count > 0) parts.push(`від ${formatPrice(p.min_price)}`)
  return parts.join(' · ')
}

/**
 * DESIGN.md §4.9 BasketEditor: поле «Додати товар» (ARIA combobox 1.2, як CitySelect).
 * Категорії — локально, товари — з /catalog/prices, останнім — вільний текст.
 */
export function AddProductSearch({ onAdd, inputRef }: Props) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const rootRef = useRef<HTMLDivElement>(null)
  const id = useId()
  const listId = `${id}-list`
  const optionId = (i: number) => `${id}-opt-${i}`

  const search = useProductSearch(query)
  const text = query.trim().replace(/\s+/g, ' ')
  const options: Option[] = search.active
    ? [
        ...search.categories.map((c) => ({ kind: 'category', category: c }) as const),
        ...search.products.map((p) => ({ kind: 'product', product: p }) as const),
        { kind: 'text', text },
      ]
    : []
  const expanded = open && options.length > 0
  const activeIndex = Math.min(active, Math.max(options.length - 1, 0))

  useEffect(() => {
    if (!open) return
    function onPointerDown(e: PointerEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [open])

  function select(option: Option | undefined) {
    if (!option) return
    if (option.kind === 'category') onAdd(itemFromCategory(option.category))
    else if (option.kind === 'product') onAdd(itemFromProduct(option.product))
    else if (option.text) onAdd(itemFromQuery(option.text))
    setQuery('')
    setActive(0)
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setOpen(true)
        setActive((i) => Math.min(Math.min(i, options.length - 1) + 1, options.length - 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setActive((i) => Math.max(Math.min(i, options.length - 1) - 1, 0))
        break
      case 'Enter':
        if (!expanded) return
        e.preventDefault()
        select(options[activeIndex])
        break
      case 'Escape':
        if (query) setQuery('')
        setOpen(false)
        break
      case 'Tab':
        setOpen(false)
        break
    }
  }

  return (
    <div className={styles.root} ref={rootRef}>
      <div className={styles.field}>
        <Search strokeWidth={1.75} aria-hidden="true" />
        <label className="sr-only" htmlFor={`${id}-input`}>
          Додати товар
        </label>
        <input
          ref={inputRef}
          id={`${id}-input`}
          type="text"
          role="combobox"
          aria-expanded={expanded}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={expanded ? optionId(activeIndex) : undefined}
          autoComplete="off"
          spellCheck={false}
          placeholder="Додати товар: сметана, гречка…"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setActive(0)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
        />
        {search.catalog === 'loading' && (
          <LoaderCircle className={styles.spin} strokeWidth={1.75} aria-hidden="true" />
        )}
      </div>

      <div className={styles.popover} hidden={!expanded}>
        <ul className={styles.list} id={listId} role="listbox" aria-label="Підказки товарів">
          {options.map((opt, i) => {
            const cls = [styles.option, i === activeIndex && styles.active].filter(Boolean).join(' ')
            const common = {
              id: optionId(i),
              role: 'option' as const,
              'aria-selected': i === activeIndex,
              className: cls,
              onPointerEnter: () => setActive(i),
              // mousedown, щоб поле не втрачало фокус до вибору
              onMouseDown: (e: MouseEvent) => e.preventDefault(),
              onClick: () => select(opt),
            }
            if (opt.kind === 'category') {
              return (
                <li key={`c-${opt.category.id}`} {...common}>
                  <Tag strokeWidth={1.75} aria-hidden="true" />
                  <span className={styles.name}>{opt.category.label}</span>
                  <span className={`${styles.meta} num`}>
                    будь-який · {formatPack(opt.category.packQty, opt.category.unit)}
                  </span>
                </li>
              )
            }
            if (opt.kind === 'product') {
              return (
                <li key={`p-${opt.product.product_id}`} {...common}>
                  <Package strokeWidth={1.75} aria-hidden="true" />
                  <span className={styles.name}>{opt.product.title}</span>
                  <span className={`${styles.meta} num`}>{productMeta(opt.product)}</span>
                </li>
              )
            }
            return (
              <li key="text" {...common}>
                <Plus strokeWidth={1.75} aria-hidden="true" />
                <span className={styles.name}>Додати «{opt.text}»</span>
              </li>
            )
          })}
        </ul>
        {search.catalog === 'loading' && <p className={styles.note}>Шукаю в каталозі…</p>}
        {search.catalog === 'error' && (
          <p className={styles.note}>Каталог зараз недоступний. Можна додати категорію або свій текст</p>
        )}
        {search.catalog === 'ready' && search.products.length === 0 && (
          <p className={styles.note}>У каталозі такого товару не знайшли</p>
        )}
      </div>
    </div>
  )
}
