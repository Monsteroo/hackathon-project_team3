import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError, hasApiKey } from '../../lib/api/client'
import { messageFor } from '../../lib/api/errors'
import type { VoiceResult } from '../../lib/api/types'
import { useSpeechRecognition, type VoiceState } from './useSpeechRecognition'
import { useVoiceRecorder } from './useVoiceRecorder'

/**
 * Голосове введення екрана 1 (frontend/docs/GEO_VOICE_SCREENS.md, «Ланцюжок голосу»):
 * 1. `server` — MediaRecorder → POST /voice/transcribe (Whisper) → `onResult(VoiceResult)`.
 * 2. Помилка з `fallback: true` → до перезавантаження сторінки `browser` (Web Speech, `onTranscript`).
 * 3. Поле ручного вводу доступне завжди.
 * Повертає ту саму форму, що й useSpeechRecognition, тож VoiceButton і VoiceStatus не змінюються.
 */

export type VoiceEngine = 'server' | 'browser' | 'none'

/** Бекенд обрізає Groq на 20 с; ще 10 с на завантаження й чистку тексту. */
const TRANSCRIBE_TIMEOUT_MS = 30_000

export const FALLBACK_MESSAGES = {
  toBrowser: 'Розпізнавання на сервері недоступне. Натисніть мікрофон ще раз або введіть текстом',
  none: 'Розпізнавання голосу зараз недоступне. Введіть список текстом',
} as const

type Options = {
  /** Текст від Web Speech (проміжний і фінальний), як у useSpeechRecognition. */
  onTranscript: (text: string) => void
  /** Готовий результат /voice/transcribe. */
  onResult: (result: VoiceResult) => void
}

type ServerPhase = { phase: 'idle' | 'processing' } | { phase: 'error'; message: string }

export function useVoiceInput({ onTranscript, onResult }: Options) {
  const {
    state: speechState,
    error: speechError,
    toggle: speechToggle,
    cancel: speechCancel,
    levelRef: speechLevelRef,
  } = useSpeechRecognition({ onTranscript })
  const speechSupported = speechState !== 'unsupported'

  /** Один елемент для `--level` обох рушіїв. */
  const levelRef = useRef<HTMLDivElement | null>(null)
  const setLevelEl = useCallback(
    (el: HTMLDivElement | null) => {
      levelRef.current = el
      speechLevelRef.current = el
    },
    [speechLevelRef],
  )

  const [server, setServer] = useState<ServerPhase>({ phase: 'idle' })
  /** Повідомлення після перемикання рушія; зникає з наступним натисканням. */
  const [notice, setNotice] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const onResultRef = useRef(onResult)
  useEffect(() => {
    onResultRef.current = onResult
  })

  const recorder = useVoiceRecorder({
    levelRef,
    onStop: (blob) => void transcribe(blob),
  })

  const [engine, setEngine] = useState<VoiceEngine>(() => {
    if (recorder.supported && hasApiKey) return 'server'
    return speechSupported ? 'browser' : 'none'
  })

  const switchAfterFailure = useCallback(() => {
    const next: VoiceEngine = speechSupported ? 'browser' : 'none'
    setEngine(next)
    setServer({ phase: 'idle' })
    setNotice(next === 'browser' ? FALLBACK_MESSAGES.toBrowser : FALLBACK_MESSAGES.none)
  }, [speechSupported])

  async function transcribe(blob: Blob) {
    const controller = new AbortController()
    abortRef.current = controller
    let timedOut = false
    const timer = window.setTimeout(() => {
      timedOut = true
      controller.abort()
    }, TRANSCRIBE_TIMEOUT_MS)
    setServer({ phase: 'processing' })
    try {
      const result = await api.transcribe(blob, controller.signal)
      setServer({ phase: 'idle' })
      onResultRef.current(result)
    } catch (e) {
      if (controller.signal.aborted && !timedOut) return // unmount або скасування
      const err = timedOut
        ? new ApiError('stt_timeout', 'transcribe timed out', { fallback: true })
        : e instanceof ApiError
          ? e
          : new ApiError('unknown', String(e))
      if (err.fallback) switchAfterFailure()
      else setServer({ phase: 'error', message: messageFor(err.code) })
    } finally {
      window.clearTimeout(timer)
      if (abortRef.current === controller) abortRef.current = null
    }
  }

  useEffect(() => () => abortRef.current?.abort(), [])

  let state: VoiceState
  let error: string | null = null
  if (engine === 'none') {
    // Від початку голосу немає — `unsupported` (підказка біля поля); після збою сервера — пояснення.
    state = notice ? 'blocked' : 'unsupported'
    error = notice
  } else if (notice) {
    state = 'error'
    error = notice
  } else if (engine === 'browser') {
    state = speechState
    error = speechError
  } else if (recorder.status === 'recording' || recorder.status === 'starting') {
    state = 'listening'
  } else if (server.phase === 'processing') {
    state = 'processing'
  } else if (recorder.status === 'error') {
    const denied = recorder.errorName === 'NotAllowedError' || recorder.errorName === 'SecurityError'
    state = denied ? 'blocked' : 'error'
    error = recorder.error
  } else if (server.phase === 'error') {
    state = 'error'
    error = server.message
  } else {
    state = 'idle'
  }

  const toggle = () => {
    if (engine === 'none' || state === 'processing' || state === 'blocked') return
    setNotice(null)
    if (engine === 'browser') {
      // Після перемикання стан Web Speech `idle`: одразу починаємо слухати.
      speechToggle()
      return
    }
    if (state === 'listening') recorder.stop()
    else {
      setServer({ phase: 'idle' })
      void recorder.start()
    }
  }

  const cancel = () => {
    if (engine === 'browser') speechCancel()
    else recorder.cancel()
  }

  return {
    state,
    error,
    engine,
    /** Секунди запису (лише `server`). */
    elapsed: engine === 'server' && state === 'listening' ? recorder.elapsed : null,
    maxSeconds: recorder.maxSeconds,
    toggle,
    cancel,
    levelRef: setLevelEl,
  }
}
