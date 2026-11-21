import { useCallback, useEffect, useRef, useState } from 'react'
import { attachLevelMeter } from './levelMeter'

/**
 * Web Speech API + рівень гучності для VoiceButton (DESIGN.md §4.1).
 * Firefox та частина браузерів API не мають — тоді `unsupported`, а поле вводу стає головним.
 */

export type VoiceState = 'idle' | 'listening' | 'processing' | 'error' | 'blocked' | 'unsupported'

type RecognitionResult = { isFinal: boolean; 0: { transcript: string } }
type RecognitionEvent = { results: ArrayLike<RecognitionResult> }
type RecognitionErrorEvent = { error: string }
type Recognition = {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((e: RecognitionEvent) => void) | null
  onerror: ((e: RecognitionErrorEvent) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
  abort: () => void
}
type RecognitionCtor = new () => Recognition

function getRecognitionCtor(): RecognitionCtor | null {
  if (typeof window === 'undefined') return null
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

export const VOICE_MESSAGES = {
  noSpeech: 'Не почув. Спробуйте ще раз або введіть текстом',
  network: "Немає з'єднання. Голос тимчасово недоступний — введіть текстом",
  notAllowed:
    'Доступ до мікрофона заборонено. Введіть список текстом або дозвольте мікрофон у налаштуваннях браузера',
  audioCapture: 'Мікрофон не знайдено. Введіть список текстом',
  timeout: 'Не вдалося розібрати запит. Спробуйте ще раз або введіть текстом',
  unsupported: 'Браузер не підтримує голос. Введіть список текстом',
} as const

const PROCESSING_TIMEOUT_MS = 10_000

type Options = {
  lang?: string
  /** Увесь розпізнаний текст цієї сесії, проміжний і фінальний. */
  onTranscript: (text: string) => void
}

export function useSpeechRecognition({ lang = 'uk-UA', onTranscript }: Options) {
  const [Ctor] = useState(getRecognitionCtor)
  const [state, setState] = useState<VoiceState>(Ctor ? 'idle' : 'unsupported')
  const [error, setError] = useState<string | null>(null)

  /** Елемент, на який пишемо `--level` (0…1) без ре-рендерів. */
  const levelRef = useRef<HTMLDivElement | null>(null)
  const recRef = useRef<Recognition | null>(null)
  const session = useRef({ heard: false, aborted: false, failed: false })
  const timer = useRef<number | undefined>(undefined)
  const meter = useRef<{ stream: MediaStream; stop: () => void } | null>(null)
  const onTranscriptRef = useRef(onTranscript)
  useEffect(() => {
    onTranscriptRef.current = onTranscript
  })

  const stopMeter = useCallback(() => {
    const m = meter.current
    meter.current = null
    if (m) {
      m.stop()
      m.stream.getTracks().forEach((t) => t.stop())
    }
    levelRef.current?.style.setProperty('--level', '0')
  }, [])

  const startMeter = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (!recRef.current) {
        stream.getTracks().forEach((t) => t.stop())
        return
      }
      meter.current = { stream, stop: attachLevelMeter(stream, () => levelRef.current) }
    } catch {
      // Рівень гучності — прикраса; помилки доступу обробляє саме розпізнавання.
    }
  }, [])

  const fail = useCallback((next: 'error' | 'blocked', message: string) => {
    session.current.failed = true
    setError(message)
    setState(next)
  }, [])

  const start = useCallback(() => {
    if (!Ctor) return
    const rec = new Ctor()
    rec.lang = lang
    rec.continuous = true
    rec.interimResults = true
    session.current = { heard: false, aborted: false, failed: false }

    rec.onresult = (e) => {
      let text = ''
      for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript
      text = text.trim()
      if (text) {
        session.current.heard = true
        onTranscriptRef.current(text)
      }
    }
    rec.onerror = (e) => {
      switch (e.error) {
        case 'aborted':
          break
        case 'no-speech':
          fail('error', VOICE_MESSAGES.noSpeech)
          break
        case 'network':
          fail('error', VOICE_MESSAGES.network)
          break
        case 'not-allowed':
        case 'service-not-allowed':
          fail('blocked', VOICE_MESSAGES.notAllowed)
          break
        case 'audio-capture':
          fail('blocked', VOICE_MESSAGES.audioCapture)
          break
        default:
          fail('error', VOICE_MESSAGES.noSpeech)
      }
    }
    rec.onend = () => {
      window.clearTimeout(timer.current)
      recRef.current = null
      stopMeter()
      const s = session.current
      if (s.failed) return
      if (s.aborted || s.heard) {
        setState('idle')
        return
      }
      fail('error', VOICE_MESSAGES.noSpeech)
    }

    recRef.current = rec
    setError(null)
    setState('listening')
    try {
      rec.start()
    } catch {
      recRef.current = null
      fail('error', VOICE_MESSAGES.noSpeech)
      return
    }
    void startMeter()
  }, [Ctor, lang, fail, startMeter, stopMeter])

  /** Стоп запису → обробка останнього фрагмента. */
  const stop = useCallback(() => {
    const rec = recRef.current
    if (!rec) return
    setState('processing')
    stopMeter()
    rec.stop()
    timer.current = window.setTimeout(() => {
      session.current.failed = true
      rec.abort()
      setError(VOICE_MESSAGES.timeout)
      setState('error')
    }, PROCESSING_TIMEOUT_MS)
  }, [stopMeter])

  /** Esc: скасувати без помилки. */
  const cancel = useCallback(() => {
    const rec = recRef.current
    if (!rec) return
    session.current.aborted = true
    rec.abort()
  }, [])

  const toggle = useCallback(() => {
    if (state === 'listening') stop()
    else if (state === 'idle' || state === 'error') start()
  }, [state, start, stop])

  useEffect(
    () => () => {
      window.clearTimeout(timer.current)
      session.current.aborted = true
      recRef.current?.abort()
      stopMeter()
    },
    [stopMeter],
  )

  return { state, error, toggle, stop, cancel, levelRef }
}
