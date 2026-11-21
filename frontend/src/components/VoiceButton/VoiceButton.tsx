import { CircleAlert, LoaderCircle, Mic, MicOff, Square } from 'lucide-react'
import type { KeyboardEvent, Ref } from 'react'
import type { VoiceState } from '../../features/voice/useSpeechRecognition'
import { formatClock } from '../../lib/format'
import styles from './VoiceButton.module.css'

type ButtonProps = {
  state: Exclude<VoiceState, 'unsupported'>
  variant?: 'default' | 'inline'
  onToggle: () => void
  onCancel: () => void
  /** Обгортка отримує `--level` від лічильника гучності. */
  levelRef?: Ref<HTMLDivElement>
  /** id повідомлення про помилку для `aria-describedby`. */
  errorId?: string
}

const LABEL: Record<ButtonProps['state'], string> = {
  idle: 'Почати голосове введення',
  listening: 'Зупинити запис',
  processing: 'Розбираю запит',
  error: 'Спробувати голосове введення ще раз',
  blocked: 'Голосове введення недоступне',
}

/** DESIGN.md §4.1. Unsupported не рендериться — замість кнопки підказка біля поля. */
export function VoiceButton({ state, variant = 'default', onToggle, onCancel, levelRef, errorId }: ButtonProps) {
  const disabled = state === 'processing' || state === 'blocked'

  function handleKeyDown(e: KeyboardEvent<HTMLButtonElement>) {
    if (e.key === 'Escape' && state === 'listening') {
      e.preventDefault()
      onCancel()
    }
  }

  const Icon = state === 'listening' ? Square : state === 'processing' ? LoaderCircle : state === 'blocked' ? MicOff : Mic

  return (
    <div
      ref={levelRef}
      className={[styles.wrap, variant === 'inline' && styles.inline].filter(Boolean).join(' ')}
      data-state={state}
    >
      <button
        type="button"
        className={styles.voice}
        aria-label={LABEL[state]}
        aria-pressed={state === 'listening'}
        aria-busy={state === 'processing' || undefined}
        aria-disabled={disabled || undefined}
        aria-describedby={state === 'error' || state === 'blocked' ? errorId : undefined}
        onClick={disabled ? undefined : onToggle}
        onKeyDown={handleKeyDown}
      >
        <span className={styles.ring} aria-hidden="true" />
        <Icon
          className={[styles.icon, state === 'processing' && styles.spin].filter(Boolean).join(' ')}
          strokeWidth={1.75}
          aria-hidden="true"
        />
      </button>
      {variant === 'default' && (
        <span className={styles.level} aria-hidden="true">
          <span />
        </span>
      )}
    </div>
  )
}

type StatusProps = {
  state: VoiceState
  error: string | null
  errorId: string
  /** Підказка до помилки «не почув» (лише мобільний, де кнопка велика). */
  hint?: string
  align?: 'center' | 'start'
  /** Секунди запису: «Слухаю… · 0:12». Лічильник прихований від скрінрідера, щоб не зачитувався щосекунди. */
  elapsed?: number | null
}

const STATUS: Partial<Record<VoiceState, string>> = {
  listening: 'Слухаю…',
  processing: 'Розбираю запит…',
}

/** Статус (aria-live) і помилки голосу. Окремо від кнопки, бо на десктопі кнопка всередині поля. */
export function VoiceStatus({ state, error, errorId, hint, align = 'center', elapsed }: StatusProps) {
  const showError = (state === 'error' || state === 'blocked') && error
  return (
    <div className={[styles.messages, align === 'start' && styles.start].filter(Boolean).join(' ')}>
      <p className={styles.status} aria-live="polite">
        {STATUS[state] ?? ''}
        {state === 'listening' && elapsed != null && (
          <span className="num" aria-hidden="true">
            {' · '}
            {formatClock(elapsed)}
          </span>
        )}
      </p>
      {showError && (
        <p className={styles.error} id={errorId} role="alert">
          <CircleAlert strokeWidth={1.75} aria-hidden="true" />
          <span>{error}</span>
        </p>
      )}
      {showError && state === 'error' && hint && <p className={styles.hint}>{hint}</p>}
    </div>
  )
}
