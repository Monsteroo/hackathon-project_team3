import { ArrowRight, Sparkles, TrendingDown } from 'lucide-react'
import { useId, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router'
import { Button } from '../components/Button/Button'
import { VoiceButton, VoiceStatus } from '../components/VoiceButton/VoiceButton'
import { useSpeechRecognition, VOICE_MESSAGES } from '../features/voice/useSpeechRecognition'
import { formatDistance, formatPrice, formatSavings } from '../lib/format'
import { useCity } from '../lib/useCity'
import { MQ_COMPACT, useMediaQuery } from '../lib/useMediaQuery'
import styles from './RequestPage.module.css'

const EXAMPLES = [
  'Борщ на 4 людини',
  'Молоко, хліб, 10 яєць, сир кисломолочний 500 г',
  'Сніданки на тиждень для двох, без лактози',
]

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
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const baseRef = useRef('')
  const id = useId()
  const errorId = `${id}-error`
  const voiceErrorId = `${id}-voice-error`
  const hintId = `${id}-hint`

  const voice = useSpeechRecognition({
    onTranscript: (text) => {
      setInvalid(false)
      setQuery(joinQuery(baseRef.current, text))
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

  function submit(e?: FormEvent) {
    e?.preventDefault()
    const text = query.trim()
    if (!text) {
      setInvalid(true)
      textareaRef.current?.focus()
      return
    }
    if (voice.state === 'listening') voice.cancel()
    navigate('/confirm', { state: { query: text, cityId: city.id } })
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Десктоп: Enter надсилає, Shift+Enter — новий рядок. Мобільний: Enter — новий рядок.
    if (e.key === 'Enter' && !e.shiftKey && !compact && !e.nativeEvent.isComposing) submit(e)
  }

  function applyExample(text: string) {
    setQuery(text)
    setInvalid(false)
    textareaRef.current?.focus()
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
              onChange={(e) => {
                setQuery(e.target.value)
                if (invalid) setInvalid(false)
              }}
              onKeyDown={onKeyDown}
            />
            {!compact && voiceButton}
            <div className={styles.submit}>
              <Button type="submit" className={styles.submitButton} iconEnd={<ArrowRight />}>
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

          <ul className={styles.examples} aria-label="Приклади запитів">
            {EXAMPLES.map((text) => (
              <li key={text}>
                <button type="button" className={`${styles.example} num`} onClick={() => applyExample(text)}>
                  <Sparkles strokeWidth={1.75} aria-hidden="true" />
                  {text}
                </button>
              </li>
            ))}
          </ul>

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
