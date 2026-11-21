import { VOICE_MESSAGES } from '../../features/voice/useSpeechRecognition'

/**
 * Код помилки бекенду → текст для UI (tools/geo-voice-testbench/HANDOFF.md, «Коди помилок → текст для UI»).
 * `detail.message` від бекенду англійською, його не показуємо.
 */
const MESSAGES: Record<string, string> = {
  // geo
  outside_service_area: 'Поки працюємо лише по Києву',
  not_found_in_service_area: 'Адресу не знайдено в Києві. Уточніть вулицю й номер будинку',
  geocoder_unavailable: 'Пошук адреси тимчасово недоступний. Спробуйте кнопку геолокації',
  store_not_found: 'Магазин не знайдено',
  // voice, fallback: true
  stt_rate_limited: 'Розпізнавання перевантажене — спробуйте в браузері або введіть текстом',
  stt_unavailable: 'Розпізнавання голосу недоступне — спробуйте в браузері або введіть текстом',
  stt_timeout: 'Розпізнавання не відповіло вчасно',
  stt_not_configured: 'Розпізнавання голосу не налаштоване',
  audio_unsupported: 'Не вдалося прочитати запис',
  // voice, fallback: false
  no_speech: VOICE_MESSAGES.noSpeech,
  audio_empty: 'Порожній запис',
  audio_too_large: 'Запис задовгий (максимум 60 с)',
  audio_too_long: 'Запис задовгий (максимум 60 с)',
  rate_limited: 'Забагато запитів. Спробуйте за хвилину',
  // транспорт
  network: VOICE_MESSAGES.network,
  unauthorized: 'Помилка доступу до сервера',
  validation_error: 'Перевірте введені дані',
}

const FALLBACK_MESSAGE = 'Щось пішло не так. Спробуйте ще раз'

export function messageFor(code: string | undefined): string {
  return (code && MESSAGES[code]) || FALLBACK_MESSAGE
}
