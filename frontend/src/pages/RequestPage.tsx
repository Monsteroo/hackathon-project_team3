import { ArrowRight, TrendingDown } from 'lucide-react'
import { useId, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router'
import { Button } from '../components/Button/Button'
import { VoiceButton, VoiceStatus } from '../components/VoiceButton/VoiceButton'
import { VOICE_MESSAGES } from '../features/voice/useSpeechRecognition'
import { useVoiceInput } from '../features/voice/useVoiceInput'
import { localVoiceResult, MAX_TEXT_LENGTH } from '../lib/api/client'
import type { VoiceResult } from '../lib/api/types'
import { formatDistance, formatPrice, formatSavings } from '../lib/format'
import { useCity } from '../lib/useCity'
import { MQ_COMPACT, useMediaQuery } from '../lib/useMediaQuery'
import styles from './RequestPage.module.css'

/** Статичний приклад результату для «Борщ на 4 людини» (прототип, екран 01). */
const PREVIEW = [
  { name: 'Найближчий', sum: 1012.3, store: 'Novus', meters: 180 },
  { name: 'Найвигідніший', sum: 937.4, store: 'Сільпо', meters: 630, best: true },
  { name: 'Smart Split', sum: 897.1, store: 'АТБ + Сільпо', meters: 1100 },
]
const PREVIEW_TRADEOFF = `${formatSavings(75)} за +${formatDistance(450)}`

const EMPTY_ERROR = 'Введіть або скажіть, що купити'

/** Додає розпізнаний текст до того, що людина вже ввела. */
function joinQuery(base: string, spoken: string): string {
  const head = base.trimEnd()
  if (!head) return spoken
  return /[,;:]$/.test(head) ? `${head} ${spoken}` : `${head}, ${spoken}`
}

/** Екран 1 (design/BRIEF.md): «Голос на вході». */
export function RequestPage() {
  const navigate = useNavigate()
  const city = useCity()
  const compact = useMediaQuery(MQ_COMPACT)

  const [query, setQuery] = useState('')
  const [invalid, setInvalid] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const baseRef = useRef('')
  /** Останній результат Whisper і текст поля з ним: якщо поле не правили, сабміт не робить ще один запит. */
  const lastVoiceRef = useRef<{ result: VoiceResult; field: string } | null>(null)
  /** Текст поля, яке заповнив Web Speech: тоді VoiceResult має source=web_speech. */
  const webSpeechFieldRef = useRef<string | null>(null)
  const id = useId()
  const errorId = `${id}-error`
  const voiceErrorId = `${id}-voice-error`
  const hintId = `${id}-hint`

  const voice = useVoiceInput({
    onTranscript: (text) => {
      const next = joinQuery(baseRef.current, text)
      setInvalid(false)
      setQuery(next)
      webSpeechFieldRef.current = next
    },
    onResult: (result) => {
      // У поле — те, що почули (прототип, екран 05b); агенту далі піде очищений `text`.
      const next = joinQuery(baseRef.current, result.raw_text)
      setInvalid(false)
      setQuery(next)
      lastVoiceRef.current = { result, field: next }
    },
  })

  // Автовисота поля до 6 рядків (max-height у CSS).
  useLayoutEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }, [query, compact])

  function toggleVoice() {
    if (voice.state !== 'listening') baseRef.current = query
    voice.toggle()
  }

  /** VoiceResult для /confirm. Набраний текст не йде на бекенд тут: його розбирає агент на екрані 2. */
  async function resolveVoice(text: string): Promise<VoiceResult> {
    const last = lastVoiceRef.current
    // Поле = лише результат Whisper без правок → готовий VoiceResult без нового запиту.
    if (last && last.field.trim() === text && last.result.raw_text.trim() === text) return last.result
    const source = webSpeechFieldRef.current?.trim() === text ? 'web_speech' : 'manual'
    return localVoiceResult(text, source)
  }

  async function submit(e?: FormEvent) {
    e?.preventDefault()
    if (submitting) return
    const text = query.trim().slice(0, MAX_TEXT_LENGTH)
    if (!text) {
      setInvalid(true)
      textareaRef.current?.focus()
      return
    }
    if (voice.state === 'listening') voice.cancel()
    setSubmitting(true)
    const result = await resolveVoice(text)
    navigate('/confirm', { state: { voice: result, query: result.text, cityId: city.id } })
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Десктоп: Enter надсилає, Shift+Enter — новий рядок. Мобільний: Enter — новий рядок.
    if (e.key === 'Enter' && !e.shiftKey && !compact && !e.nativeEvent.isComposing) void submit(e)
  }

  const supported = voice.state !== 'unsupported'
  const voiceButton = supported && (
    <VoiceButton
      state={voice.state as Exclude<typeof voice.state, 'unsupported'>}
      variant={compact ? 'default' : 'inline'}
      onToggle={toggleVoice}
      onCancel={voice.cancel}
      levelRef={voice.levelRef}
      errorId={voiceErrorId}
    />
  )
  const voiceStatus = supported && (
    <VoiceStatus
      state={voice.state}
      error={voice.error}
      errorId={voiceErrorId}
      elapsed={voice.elapsed}
      align={compact ? 'center' : 'start'}
      hint={compact ? 'Говоріть ближче до телефона, наприклад: «молоко, хліб і десяток яєць»' : undefined}
    />
  )
  const describedBy = [invalid && errorId, !supported && hintId].filter(Boolean).join(' ') || undefined

  return (
    <div className={styles.page}>
      <section className={styles.hero} aria-labelledby={`${id}-title`}>
        <form className={styles.intro} onSubmit={submit} noValidate>
          <div className={styles.heading}>
            <h1 className={styles.title} id={`${id}-title`}>
              Той самий кошик — <mark className={styles.highlight}>до 30% дешевше</mark>
            </h1>
            <p className={styles.sub}>
              Скажіть або вставте список. Порівняємо весь кошик у <span className="num">{city.chains}</span> мережах
              поруч.
            </p>
          </div>

          {compact && supported && (
            <div className={styles.voiceZone} aria-label="Голосове введення" role="group">
              {voiceButton}
              {voiceStatus}
            </div>
          )}

          <label className={styles.label} htmlFor={`${id}-query`}>
            {compact && supported ? 'Або введіть чи вставте список' : 'Введіть або вставте список'}
          </label>
          <div className={styles.composer} data-invalid={invalid || undefined}>
            <textarea
              ref={textareaRef}
              id={`${id}-query`}
              className={styles.textarea}
              rows={compact ? 3 : 1}
              placeholder="Молоко, хліб, десяток яєць…"
              value={query}
              aria-invalid={invalid || undefined}
              aria-describedby={describedBy}
              maxLength={MAX_TEXT_LENGTH}
              onChange={(e) => {
                setQuery(e.target.value)
                if (invalid) setInvalid(false)
              }}
              onKeyDown={onKeyDown}
            />
            {!compact && voiceButton}
            <div className={styles.submit}>
              <Button type="submit" className={styles.submitButton} iconEnd={<ArrowRight />} loading={submitting}>
                Знайти кошик
              </Button>
            </div>
          </div>

          {invalid && (
            <p className={styles.fieldError} id={errorId} role="alert">
              {EMPTY_ERROR}
            </p>
          )}
          {!supported && (
            <p className={styles.fieldHint} id={hintId}>
              {VOICE_MESSAGES.unsupported}
            </p>
          )}
          {!compact && supported && <div className={styles.voiceMessages}>{voiceStatus}</div>}

          {compact && (
            <p className={styles.previewLine}>
              <span className={styles.meta}>Приклад:</span>
              <span className={`${styles.savings} num`}>
                <TrendingDown strokeWidth={1.75} aria-hidden="true" />
                {PREVIEW_TRADEOFF}
              </span>
            </p>
          )}
          <p className={`${styles.trust} num`}>
            3 кошики безкоштовно · без реєстрації · ціни {city.chains} мереж
          </p>
        </form>

        {!compact && (
          <aside className={styles.preview} aria-label="Приклад результату">
            <p className="sr-only">
              Приклад результату: найвигідніший кошик у Сільпо, на 75 гривень дешевше за найближчий.
            </p>
            <div aria-hidden="true">
              <p className={styles.previewCaption}>Приклад для «Борщ на 4 людини»</p>
              <ul className={styles.previewList}>
                {PREVIEW.map((p) => (
                  <li key={p.name} className={p.best ? styles.best : undefined}>
                    <span className={styles.previewName}>{p.name}</span>
                    <span className={`${styles.previewSum} num`}>{formatPrice(p.sum)}</span>
                    <span className={`${styles.previewStore} num`}>
                      {p.store} · {formatDistance(p.meters)}
                    </span>
                  </li>
                ))}
              </ul>
              <span className={`${styles.savings} num`}>
                <TrendingDown strokeWidth={1.75} aria-hidden="true" />
                {PREVIEW_TRADEOFF}
              </span>
            </div>
          </aside>
        )}
      </section>
    </div>
  )
}
