import { Mic } from 'lucide-react'
import { useNavigate } from 'react-router'
import { Button } from '../components/Button/Button'
import { formatSavings } from '../lib/format'
import { ScreenStub } from './ScreenStub'

export function RequestPage() {
  const navigate = useNavigate()
  return (
    <ScreenStub
      title="Той самий кошик — до 30% дешевше"
      note="Екран 1: поле з мікрофоном усередині і кнопкою «Знайти кошик»."
    >
      <div style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
        <Button onClick={() => navigate('/results')}>Знайти кошик</Button>
        <Button variant="secondary" icon={<Mic />}>
          Сказати голосом
        </Button>
        <Button variant="ghost">+ Додати товар</Button>
      </div>
      <p className="num" style={{ color: 'var(--color-savings)' }}>
        Економія {formatSavings(97.5)}
      </p>
    </ScreenStub>
  )
}
