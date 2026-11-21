import { LoaderCircle, MapPin } from 'lucide-react'
import { useEffect, useId, useRef, useState, type KeyboardEvent, type MouseEvent, type Ref } from 'react'
import { api, ApiError } from '../../lib/api/client'
import { messageFor } from '../../lib/api/errors'
import type { Place } from '../../lib/api/types'
import styles from './AddressSearch.module.css'

type Props = {
  onPick: (place: Place) => void
  /** Центр міста: підказки ближче до нього вище. */
  near?: { lat: number; lng: number }
  inputRef?: Ref<HTMLInputElement>
  disabled?: boolean
}

type Status = 'idle' | 'loading' | 'ready' | 'error'

const MIN_CHARS = 3
const DEBOUNCE_MS = 300

/**
 * Ручна адреса, коли геолокацію заборонено (BRIEF: «Мікрофон або геолокацію заборонено»).
 * ARIA combobox 1.2, як AddProductSearch. Підказки — /geo/geocode?suggest=true.
 */
export function AddressSearch({ onPick, near, inputRef, disabled }: Props) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  /** Остання відповідь геокодера і запит, на який вона прийшла. */
  const [resp, setResp] = useState<{ q: string; results: Place[]; error: string | null }>({
    q: '',
    results: [],
    error: null,
  })
  const rootRef = useRef<HTMLDivElement>(null)
  const id = useId()
  const listId = `${id}-list`
  const hintId = `${id}-hint`
  const optionId = (i: number) => `${id}-opt-${i}`

  const text = query.trim()
  const nearLat = near?.lat
  const nearLng = near?.lng

  const searching = text.length >= MIN_CHARS
  let status: Status = 'idle'
  if (searching) status = resp.q !== text ? 'loading' : resp.error ? 'error' : 'ready'
  // Поки шукаємо нове, лишаємо попередні підказки: список не блимає під час набору.
  const results = searching ? resp.results : []

  useEffect(() => {
    if (!searching) return
    let cancelled = false
    const timer = setTimeout(() => {
      const nearPoint = nearLat != null && nearLng != null ? { lat: nearLat, lng: nearLng } : undefined
      api
        .geocode(text, { suggest: true, near: nearPoint })
        .then((r) => {
          if (!cancelled) setResp({ q: text, results: r.results, error: null })
        })
        .catch((e: unknown) => {
          if (!cancelled) {
            setResp({ q: text, results: [], error: messageFor(e instanceof ApiError ? e.code : undefined) })
          }
        })
    }, DEBOUNCE_MS)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [text, searching, nearLat, nearLng])

  useEffect(() => {
    if (!open) return
    function onPointerDown(e: PointerEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [open])

  const expanded = open && results.length > 0
  const activeIndex = Math.min(active, Math.max(results.length - 1, 0))

  function select(place: Place | undefined) {
    if (!place) return
    setQuery(place.label)
    setOpen(false)
    onPick(place)
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setOpen(true)
        setActive((i) => Math.min(Math.min(i, results.length - 1) + 1, results.length - 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setActive((i) => Math.max(Math.min(i, results.length - 1) - 1, 0))
        break
      case 'Enter':
        e.preventDefault()
        if (results.length > 0) select(results[expanded ? activeIndex : 0])
        break
      case 'Escape':
        setOpen(false)
        break
      case 'Tab':
        setOpen(false)
        break
    }
  }

  let hint = 'Вулиця й номер будинку, напр. Хрещатик, 22'
  if (status === 'loading') hint = 'Шукаю адресу…'
  else if (status === 'error') hint = resp.error ?? ''
  else if (status === 'ready' && results.length === 0) hint = 'Адресу не знайдено. Уточніть вулицю й номер будинку'

  return (
    <div className={styles.root} ref={rootRef}>
      <label className={styles.label} htmlFor={`${id}-input`}>
        Ваша адреса
      </label>
      <div className={styles.combo}>
        <div className={styles.field}>
          <MapPin strokeWidth={1.75} aria-hidden="true" />
          <input
            ref={inputRef}
            id={`${id}-input`}
            type="text"
            role="combobox"
            aria-expanded={expanded}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-describedby={hintId}
            aria-activedescendant={expanded ? optionId(activeIndex) : undefined}
            autoComplete="street-address"
            spellCheck={false}
            placeholder="Хрещатик, 22"
            disabled={disabled}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setActive(0)
              setOpen(true)
            }}
            onFocus={() => setOpen(true)}
            onKeyDown={onKeyDown}
          />
          {status === 'loading' && <LoaderCircle className={styles.spin} strokeWidth={1.75} aria-hidden="true" />}
        </div>
        <div className={styles.popover} hidden={!expanded}>
          <ul className={styles.list} id={listId} role="listbox" aria-label="Знайдені адреси">
            {results.map((place, i) => (
              <li
                key={`${place.lat},${place.lng},${i}`}
                id={optionId(i)}
                role="option"
                aria-selected={i === activeIndex}
                className={[styles.option, i === activeIndex && styles.active].filter(Boolean).join(' ')}
                onPointerEnter={() => setActive(i)}
                onMouseDown={(e: MouseEvent) => e.preventDefault()}
                onClick={() => select(place)}
              >
                <MapPin strokeWidth={1.75} aria-hidden="true" />
                <span className={styles.name}>{place.label}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <p
        id={hintId}
        className={status === 'error' ? `${styles.hint} ${styles.error}` : styles.hint}
        aria-live="polite"
      >
        {hint}
      </p>

    </div>
  )
}
