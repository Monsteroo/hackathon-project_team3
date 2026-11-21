import { useLocation } from 'react-router'
import { ScreenStub } from './ScreenStub'

export function ConfirmPage() {
  const query = (useLocation().state as { query?: string } | null)?.query
  return (
    <ScreenStub title="Я зрозумів так" note="Екран 2: чипи продуктів з кількістю, обмеження, «+ Додати товар».">
      {query && <p>Запит: {query}</p>}
    </ScreenStub>
  )
}
