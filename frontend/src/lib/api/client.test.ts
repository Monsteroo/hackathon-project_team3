import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, localVoiceResult } from './client'
import { messageFor } from './errors'

function respond(status: number, body: unknown) {
  return vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status }))
}

async function catchError(p: Promise<unknown>): Promise<ApiError> {
  try {
    await p
  } catch (e) {
    return e as ApiError
  }
  throw new Error('expected rejection')
}

describe('api client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('sends X-API-Key and JSON body to /voice/parse-text', async () => {
    const fetchMock = respond(200, localVoiceResult('молоко'))
    vi.stubGlobal('fetch', fetchMock)
    await api.parseText('молоко', 'web_speech')
    const [path, init] = fetchMock.mock.calls[0]
    expect(path).toBe('/voice/parse-text')
    expect(init.headers).toHaveProperty('X-API-Key')
    expect(JSON.parse(init.body)).toEqual({ text: 'молоко', source: 'web_speech' })
  })

  it('maps module error detail to code and fallback', async () => {
    vi.stubGlobal('fetch', respond(503, { detail: { code: 'stt_not_configured', message: 'x', fallback: true } }))
    const err = await catchError(api.transcribe(new Blob(['a'], { type: 'audio/webm' })))
    expect(err).toBeInstanceOf(ApiError)
    expect(err).toMatchObject({ code: 'stt_not_configured', status: 503, fallback: true })
  })

  it('keeps fallback false for no_speech and rate_limited', async () => {
    vi.stubGlobal('fetch', respond(429, { detail: { code: 'rate_limited', message: 'x', fallback: false } }))
    const err = await catchError(api.parseText('молоко'))
    expect(err).toMatchObject({ code: 'rate_limited', fallback: false })
    expect(messageFor(err.code)).toBe('Забагато запитів. Спробуйте за хвилину')
  })

  it('maps string 401 detail and validation arrays', async () => {
    vi.stubGlobal('fetch', respond(401, { detail: 'invalid or missing API key' }))
    expect(await catchError(api.parseText('x'))).toMatchObject({ code: 'unauthorized', status: 401 })

    vi.stubGlobal('fetch', respond(422, { detail: [{ type: 'string_too_short', loc: ['body', 'text'], msg: '' }] }))
    expect(await catchError(api.parseText('x'))).toMatchObject({ code: 'validation_error', fallback: false })
  })

  it('turns fetch failure into network error with fallback', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    expect(await catchError(api.parseText('x'))).toMatchObject({ code: 'network', fallback: true })
  })

  it('names the audio file by recorder mime type', async () => {
    const fetchMock = respond(200, localVoiceResult('x'))
    vi.stubGlobal('fetch', fetchMock)
    await api.transcribe(new Blob(['a'], { type: 'audio/mp4' }))
    const form = fetchMock.mock.calls[0][1].body as FormData
    expect((form.get('audio') as File).name).toBe('voice.m4a')
  })
})
