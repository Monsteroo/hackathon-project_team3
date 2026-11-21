import { useLocation } from 'react-router'
import type { VoiceResult } from '../lib/api/types'
import { ScreenStub } from './ScreenStub'

type State = { voice?: VoiceResult; query?: string } | null

const MODE_LABEL = { walk: 'пішки', car: 'авто' } as const

export function ConfirmPage() {
  const state = useLocation().state as State
  const voice = state?.voice
  return (
    <ScreenStub title="Я зрозумів так" note="Екран 2: чипи продуктів з кількістю, обмеження, «+ Додати товар».">
      {voice ? (
        <dl>
          <dt>Ви сказали</dt>
          <dd>{voice.raw_text}</dd>
          <dt>Запит для пошуку</dt>
          <dd>{voice.text}</dd>
          <dt>Як добиратися</dt>
          <dd>{voice.mode ? MODE_LABEL[voice.mode] : 'не вказано'}</dd>
          <dt>Відстань</dt>
          <dd className="num">{voice.radius_km != null ? `до ${String(voice.radius_km).replace('.', ',')} км` : 'не вказано'}</dd>
        </dl>
      ) : (
        state?.query && <p>Запит: {state.query}</p>
      )}
    </ScreenStub>
  )
}
