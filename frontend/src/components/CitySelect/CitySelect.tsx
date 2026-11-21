import { Check, ChevronDown, LoaderCircle, LocateFixed, MapPin, Search, X } from 'lucide-react'
import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import { CITIES, filterCities, nearestCity, pluralChains, pluralCities, type City } from '../../lib/cities'
import { setCity, useCity } from '../../lib/useCity'
import styles from './CitySelect.module.css'

type Option = { kind: 'locate' } | { kind: 'city'; city: City }

const AVAILABLE = CITIES.map((c) => c.name).join(', ')

/**
 * DESIGN.md §4.7, варіант `compact`: тригер у шапці + панель із пошуком (ARIA combobox 1.2).
 * < 768px панель на весь екран, ≥ 768px — випадна під тригером.
 */
export function CitySelect() {
  const city = useCity()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const [detecting, setDetecting] = useState(false)
  const [detectFailed, setDetectFailed] = useState(false)
  const [geoDenied, setGeoDenied] = useState(false)

  const rootRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const id = useId()
  const listId = `${id}-list`
  const panelId = `${id}-panel`

  const canLocate = typeof navigator !== 'undefined' && 'geolocation' in navigator && !geoDenied
  const cities = filterCities(query)
  const options: Option[] = [
    ...(canLocate && !query ? [{ kind: 'locate' } as const] : []),
    ...cities.map((c) => ({ kind: 'city', city: c }) as const),
  ]
  const activeIndex = Math.min(active, options.length - 1)
  const optionId = (i: number) => `${id}-opt-${i}`

  useEffect(() => {
    if (!navigator.permissions?.query) return
    let cancelled = false
    navigator.permissions
      .query({ name: 'geolocation' })
      .then((status) => {
        if (!cancelled) setGeoDenied(status.state === 'denied')
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!open) return
    inputRef.current?.focus()
    function onPointerDown(e: PointerEvent) {
      if (!rootRef.current?.contains(e.target as Node)) close(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [open])

  function openPanel() {
    setQuery('')
    setActive(0)
    setDetectFailed(false)
    setOpen(true)
  }

  function close(returnFocus = true) {
    setOpen(false)
    if (returnFocus) triggerRef.current?.focus()
  }

  function choose(c: City) {
    setCity(c)
    close()
  }

  function locate() {
    setDetecting(true)
    setDetectFailed(false)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setDetecting(false)
        const found = nearestCity(pos.coords.latitude, pos.coords.longitude)
        if (found) choose(found)
        else setDetectFailed(true)
      },
      (err) => {
        setDetecting(false)
        setDetectFailed(true)
        if (err.code === err.PERMISSION_DENIED) setGeoDenied(true)
      },
      { timeout: 10_000, maximumAge: 600_000 },
    )
  }

  function select(option: Option | undefined) {
    if (!option) return
    if (option.kind === 'locate') locate()
    else choose(option.city)
  }

  function onInputKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setActive((i) => Math.min(Math.min(i, options.length - 1) + 1, options.length - 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setActive((i) => Math.max(Math.min(i, options.length - 1) - 1, 0))
        break
      case 'Enter':
        e.preventDefault()
        select(options[activeIndex])
        break
      case 'Escape':
        e.preventDefault()
        close()
        break
      case 'Tab':
        close(false)
        break
    }
  }

  return (
    <div className={styles.root} ref={rootRef}>
      <button
        ref={triggerRef}
        type="button"
        className={styles.trigger}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-label={`Місто: ${city.name}. Змінити`}
        aria-busy={detecting || undefined}
        onClick={() => (open ? close() : openPanel())}
      >
        {detecting ? (
          <LoaderCircle className={`${styles.pin} ${styles.spin}`} strokeWidth={1.75} aria-hidden="true" />
        ) : (
          <MapPin className={styles.pin} strokeWidth={1.75} aria-hidden="true" />
        )}
        <span>{detecting ? 'Визначаю місто…' : city.name}</span>
        <ChevronDown className={styles.chevron} strokeWidth={1.75} aria-hidden="true" />
      </button>

      {open && (
        <div className={styles.panel} id={panelId} role="dialog" aria-modal="false" aria-labelledby={`${id}-label`}>
          <div className={styles.head}>
            <div className={styles.headRow}>
              <label className={styles.label} id={`${id}-label`} htmlFor={`${id}-input`}>
                Місто
              </label>
              <button type="button" className={styles.close} aria-label="Закрити" onClick={() => close()}>
                <X strokeWidth={1.75} aria-hidden="true" />
              </button>
            </div>
            <div className={styles.field}>
              <Search strokeWidth={1.75} aria-hidden="true" />
              <input
                ref={inputRef}
                id={`${id}-input`}
                type="text"
                role="combobox"
                aria-expanded="true"
                aria-controls={listId}
                aria-autocomplete="list"
                aria-activedescendant={options.length ? optionId(activeIndex) : undefined}
                autoComplete="off"
                spellCheck={false}
                placeholder="Почніть вводити назву"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value)
                  setActive(0)
                }}
                onKeyDown={onInputKeyDown}
              />
            </div>
          </div>

          <ul className={styles.list} id={listId} role="listbox" aria-label="Міста">
            {options.map((opt, i) => {
              const isActive = i === activeIndex
              if (opt.kind === 'locate') {
                return (
                  <li
                    key="locate"
                    id={optionId(i)}
                    role="option"
                    aria-selected={false}
                    className={[styles.option, styles.locate, isActive && styles.active].filter(Boolean).join(' ')}
                    onPointerEnter={() => setActive(i)}
                    onClick={() => select(opt)}
                  >
                    {detecting ? (
                      <LoaderCircle className={styles.spin} strokeWidth={1.75} aria-hidden="true" />
                    ) : (
                      <LocateFixed strokeWidth={1.75} aria-hidden="true" />
                    )}
                    <span className={styles.name}>{detecting ? 'Визначаю місто…' : 'Визначити автоматично'}</span>
                  </li>
                )
              }
              const selected = opt.city.id === city.id
              return (
                <li
                  key={opt.city.id}
                  id={optionId(i)}
                  role="option"
                  aria-selected={selected}
                  className={[styles.option, isActive && styles.active].filter(Boolean).join(' ')}
                  onPointerEnter={() => setActive(i)}
                  onClick={() => select(opt)}
                >
                  <Check className={styles.check} strokeWidth={1.75} aria-hidden="true" />
                  <span className={styles.name}>{opt.city.name}</span>
                  <span className={`${styles.meta} num`}>
                    {opt.city.region} · {pluralChains(opt.city.chains)}
                  </span>
                </li>
              )
            })}
          </ul>

          {cities.length === 0 && (
            <div className={styles.empty}>
              <strong>Поки не працюємо в місті «{query.trim()}»</strong>
              Доступні: {AVAILABLE}
            </div>
          )}
          {detectFailed && <p className={styles.hint}>Не вдалося визначити місто. Оберіть зі списку</p>}
          <p className={styles.note}>Показуємо лише міста, де маємо ціни. Місто зберігається на цьому пристрої.</p>
          <p className="sr-only" aria-live="polite">
            Знайдено {pluralCities(cities.length)}
          </p>
        </div>
      )}
    </div>
  )
}
