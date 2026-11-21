import { useCallback, useEffect, useRef, useState, type RefObject } from 'react'
import { attachLevelMeter } from './levelMeter'

/**
 * Запис голосу для POST /voice/transcribe. Порт tools/geo-voice-testbench/src/hooks/useVoiceRecorder.js:
 * автостоп на 60 с, webm/opus (Chrome, Firefox) або mp4/aac (Safari), 32 кбіт/с.
 * Додано: `cancel()` без відправки (Esc) і рівень гучності з того самого стріму.
 */

/** Рішення команди 21.11; бекенд приймає до 65 с і 1.5 MB. */
export const MAX_RECORDING_S = 60

const MIME_CANDIDATES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']

/** null — MediaRecorder немає; '' — є, але без відомого формату (браузер обере сам). */
function pickMime(): string | null {
  if (typeof MediaRecorder === 'undefined') return null
  return MIME_CANDIDATES.find((m) => MediaRecorder.isTypeSupported?.(m)) ?? ''
}

export const MIC_ERRORS: Record<string, string> = {
  NotAllowedError:
    'Доступ до мікрофона заборонено. Введіть список текстом або дозвольте мікрофон у налаштуваннях браузера',
  SecurityError: 'Мікрофон працює лише через HTTPS або localhost. Введіть список текстом',
  NotFoundError: 'Мікрофон не знайдено. Введіть список текстом',
  NotReadableError: 'Мікрофон зайнятий іншою програмою. Закрийте її або введіть список текстом',
}
const MIC_ERROR_DEFAULT = 'Не вдалося увімкнути мікрофон. Введіть список текстом'

export function isRecorderSupported(): boolean {
  return typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia && pickMime() !== null
}

export type RecorderStatus = 'idle' | 'starting' | 'recording' | 'error'

type Options = {
  /** Готовий запис (після stop() або автостопу). Після cancel() не викликається. */
  onStop: (blob: Blob) => void
  maxSeconds?: number
  /** Елемент для `--level`. */
  levelRef?: RefObject<HTMLElement | null>
}

export function useVoiceRecorder({ onStop, maxSeconds = MAX_RECORDING_S, levelRef }: Options) {
  const [supported] = useState(isRecorderSupported)
  const [status, setStatus] = useState<RecorderStatus>('idle')
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState<string | null>(null)
  /** DOMException.name помилки мікрофона: NotAllowedError → кнопка `blocked`. */
  const [errorName, setErrorName] = useState<string | null>(null)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const timerRef = useRef<number | undefined>(undefined)
  const stopMeterRef = useRef<(() => void) | null>(null)
  const discardRef = useRef(false)
  const onStopRef = useRef(onStop)
  useEffect(() => {
    onStopRef.current = onStop
  })

  const cleanup = useCallback(() => {
    window.clearInterval(timerRef.current)
    stopMeterRef.current?.()
    stopMeterRef.current = null
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
  }, [])

  const stop = useCallback(() => {
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
  }, [])

  const cancel = useCallback(() => {
    discardRef.current = true
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
    else {
      cleanup()
      setStatus('idle')
    }
  }, [cleanup])

  const start = useCallback(async () => {
    if (!supported) return
    setError(null)
    setErrorName(null)
    setStatus('starting')
    discardRef.current = false
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
      })
      // Скасували, поки браузер питав дозвіл.
      if (discardRef.current) {
        stream.getTracks().forEach((t) => t.stop())
        setStatus('idle')
        return
      }
      streamRef.current = stream
      const mime = pickMime() || undefined
      const recorder = new MediaRecorder(stream, mime ? { mimeType: mime, audioBitsPerSecond: 32_000 } : undefined)
      const chunks: Blob[] = []
      recorder.ondataavailable = (e) => {
        if (e.data.size) chunks.push(e.data)
      }
      recorder.onstop = () => {
        cleanup()
        recorderRef.current = null
        setStatus('idle')
        if (discardRef.current) return
        onStopRef.current(new Blob(chunks, { type: recorder.mimeType || mime || 'audio/webm' }))
      }
      recorderRef.current = recorder
      recorder.start()
      setStatus('recording')
      setElapsed(0)
      if (levelRef) stopMeterRef.current = attachLevelMeter(stream, () => levelRef.current)
      const started = Date.now()
      timerRef.current = window.setInterval(() => {
        const s = (Date.now() - started) / 1000
        setElapsed(s)
        if (s >= maxSeconds) stop()
      }, 200)
    } catch (e) {
      cleanup()
      const name = (e as DOMException)?.name ?? 'Error'
      setErrorName(name)
      setError(MIC_ERRORS[name] ?? MIC_ERROR_DEFAULT)
      setStatus('error')
    }
  }, [supported, maxSeconds, stop, cleanup, levelRef])

  useEffect(
    () => () => {
      discardRef.current = true
      if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
      cleanup()
    },
    [cleanup],
  )

  return { supported, status, elapsed, error, errorName, start, stop, cancel, maxSeconds }
}
