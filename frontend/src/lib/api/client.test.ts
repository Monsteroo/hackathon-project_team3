import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, localVoiceResult, normalizeApiBase } from './client'
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

  it('sends X-API-Key and query params', async () => {
    const fetchMock = respond(200, { results: [] })
    vi.stubGlobal('fetch', fetchMock)
    await api.geocode('Хрещатик 22')
    const [path, init] = fetchMock.mock.calls[0]
    expect(path).toMatch(/^\/geo\/geocode\?q=/)
    expect(init.headers).toHaveProperty('X-API-Key')
  })

  it('builds a typed-text VoiceResult locally (no /voice/parse-text)', () => {
    expect(localVoiceResult('молоко', 'web_speech')).toMatchObject({
      text: 'молоко',
      raw_text: 'молоко',
      mode: null,
      radius_km: null,
      source: 'web_speech',
    })
  })

  it('maps module error detail to code and fallback', async () => {
    vi.stubGlobal('fetch', respond(503, { detail: { code: 'stt_not_configured', message: 'x', fallback: true } }))
    const err = await catchError(api.transcribe(new Blob(['a'], { type: 'audio/webm' })))
    expect(err).toBeInstanceOf(ApiError)
    expect(err).toMatchObject({ code: 'stt_not_configured', status: 503, fallback: true })
  })

  it('keeps fallback false for no_speech and rate_limited', async () => {
    vi.stubGlobal('fetch', respond(429, { detail: { code: 'rate_limited', message: 'x', fallback: false } }))
    const err = await catchError(api.geocode('молоко'))
    expect(err).toMatchObject({ code: 'rate_limited', fallback: false })
    expect(messageFor(err.code)).toBe('Забагато запитів. Спробуйте за хвилину')
  })

  it('maps string 401 detail and validation arrays', async () => {
    vi.stubGlobal('fetch', respond(401, { detail: 'invalid or missing API key' }))
    expect(await catchError(api.geocode('x'))).toMatchObject({ code: 'unauthorized', status: 401 })

    vi.stubGlobal('fetch', respond(422, { detail: [{ type: 'string_too_short', loc: ['body', 'text'], msg: '' }] }))
    expect(await catchError(api.geocode('x'))).toMatchObject({ code: 'validation_error', fallback: false })
  })

  it('turns fetch failure into network error with fallback', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    expect(await catchError(api.geocode('x'))).toMatchObject({ code: 'network', fallback: true })
  })

  it('names the audio file by recorder mime type', async () => {
    const fetchMock = respond(200, localVoiceResult('x'))
    vi.stubGlobal('fetch', fetchMock)
    await api.transcribe(new Blob(['a'], { type: 'audio/mp4' }))
    const form = fetchMock.mock.calls[0][1].body as FormData
    expect((form.get('audio') as File).name).toBe('voice.m4a')
  })
  it('builds /catalog/prices query with exclude list', async () => {
    const fetchMock = respond(200, { query: 'сметана', tokens: [], store_ids: [], missing_store_ids: [], products: [] })
    vi.stubGlobal('fetch', fetchMock)
    await api.searchProducts('сметана', { limit: 5, exclude: ['sugar', 'palm_oil'] })
    const [path] = fetchMock.mock.calls[0]
    const url = new URL(path, 'http://x')
    expect(url.pathname).toBe('/catalog/prices')
    expect(url.searchParams.get('q')).toBe('сметана')
    expect(url.searchParams.get('limit')).toBe('5')
    expect(url.searchParams.get('exclude')).toBe('sugar,palm_oil')
  })

  it('maps FastAPI 422 validation list (short query) to validation_error', async () => {
    // mocks/08_error_422_short_query.json
    const detail = [{ type: 'string_too_short', loc: ['query', 'q'], msg: 'String should have at least 2 characters' }]
    vi.stubGlobal('fetch', respond(422, { detail }))
    const err = await catchError(api.searchProducts('а'))
    expect(err).toMatchObject({ code: 'validation_error', status: 422, fallback: false })
  })

  it('normalizes VITE_API_BASE_URL with or without scheme', () => {
    expect(normalizeApiBase(undefined)).toBe('')
    expect(normalizeApiBase('  ')).toBe('')
    expect(normalizeApiBase('sayvy-backend.onrender.com')).toBe('https://sayvy-backend.onrender.com')
    expect(normalizeApiBase('https://sayvy-backend.onrender.com///')).toBe('https://sayvy-backend.onrender.com')
    expect(normalizeApiBase('http://localhost:8000/')).toBe('http://localhost:8000')
  })
})
