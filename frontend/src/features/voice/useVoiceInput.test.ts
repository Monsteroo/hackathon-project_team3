import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { localVoiceResult } from '../../lib/api/client'
import { FALLBACK_MESSAGES, useVoiceInput } from './useVoiceInput'

// Ключ API задається у .env.local; у тестах — увімкнений, щоб працював серверний рушій.
vi.mock('../../lib/api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../lib/api/client')>()),
  hasApiKey: true,
}))

class FakeRecorder {
  static isTypeSupported = () => true
  state: 'inactive' | 'recording' = 'inactive'
  mimeType = 'audio/webm;codecs=opus'
  ondataavailable: ((e: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null
  start() {
    this.state = 'recording'
  }
  stop() {
    this.state = 'inactive'
    this.ondataavailable?.({ data: new Blob(['voice'], { type: this.mimeType }) })
    this.onstop?.()
  }
}

class FakeSpeech {
  lang = ''
  continuous = false
  interimResults = false
  onresult = null
  onerror = null
  onend: (() => void) | null = null
  start = vi.fn()
  stop = vi.fn()
  abort = vi.fn()
}

function respond(status: number, body: unknown) {
  return vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status }))
}

const stream = { getTracks: () => [{ stop: vi.fn() }] }

describe('useVoiceInput', () => {
  beforeEach(() => {
    vi.stubGlobal('MediaRecorder', FakeRecorder)
    vi.stubGlobal('webkitSpeechRecognition', FakeSpeech)
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: vi.fn().mockResolvedValue(stream) },
    })
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    Reflect.deleteProperty(navigator, 'mediaDevices')
  })

  async function record(result: ReturnType<typeof renderHook<ReturnType<typeof useVoiceInput>, unknown>>['result']) {
    await act(async () => result.current.toggle())
    expect(result.current.state).toBe('listening')
    await act(async () => result.current.toggle())
  }

  it('sends the recording to /voice/transcribe and returns the result', async () => {
    const voice = { ...localVoiceResult('молоко'), source: 'groq_whisper' as const, mode: 'walk' as const }
    vi.stubGlobal('fetch', respond(200, voice))
    const onResult = vi.fn()
    const { result } = renderHook(() => useVoiceInput({ onTranscript: vi.fn(), onResult }))
    expect(result.current.engine).toBe('server')

    await record(result)
    await waitFor(() => expect(onResult).toHaveBeenCalledWith(voice))
    expect(result.current.state).toBe('idle')
    expect(vi.mocked(fetch).mock.calls[0][0]).toBe('/voice/transcribe')
  })

  it('switches to Web Speech when the backend answers with fallback: true', async () => {
    vi.stubGlobal('fetch', respond(503, { detail: { code: 'stt_not_configured', message: 'x', fallback: true } }))
    const { result } = renderHook(() => useVoiceInput({ onTranscript: vi.fn(), onResult: vi.fn() }))

    await record(result)
    await waitFor(() => expect(result.current.engine).toBe('browser'))
    expect(result.current.state).toBe('error')
    expect(result.current.error).toBe(FALLBACK_MESSAGES.toBrowser)

    // Наступне натискання — вже Web Speech, без нового запиту до бекенду.
    act(() => result.current.toggle())
    expect(result.current.state).toBe('listening')
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('stays on the server and shows the message when fallback is false', async () => {
    vi.stubGlobal('fetch', respond(422, { detail: { code: 'no_speech', message: 'x', fallback: false } }))
    const { result } = renderHook(() => useVoiceInput({ onTranscript: vi.fn(), onResult: vi.fn() }))

    await record(result)
    await waitFor(() => expect(result.current.state).toBe('error'))
    expect(result.current.engine).toBe('server')
    expect(result.current.error).toBe('Не почув. Спробуйте ще раз або введіть текстом')
  })

  it('marks the button blocked when microphone access is denied', async () => {
    vi.mocked(navigator.mediaDevices.getUserMedia).mockRejectedValue(new DOMException('denied', 'NotAllowedError'))
    const { result } = renderHook(() => useVoiceInput({ onTranscript: vi.fn(), onResult: vi.fn() }))
    await act(async () => result.current.toggle())
    expect(result.current.state).toBe('blocked')
  })

  it('cancel discards the recording without a request', async () => {
    vi.stubGlobal('fetch', vi.fn())
    const { result } = renderHook(() => useVoiceInput({ onTranscript: vi.fn(), onResult: vi.fn() }))
    await act(async () => result.current.toggle())
    act(() => result.current.cancel())
    expect(result.current.state).toBe('idle')
    expect(fetch).not.toHaveBeenCalled()
  })
})
