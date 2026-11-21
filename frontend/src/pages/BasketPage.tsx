import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router'
import buttonStyles from '../components/Button/Button.module.css'
import { ScreenStub } from './ScreenStub'

export function BasketPage() {
  return (
    <ScreenStub title="Деталі кошика" note="Екран 4: позиції, ціна за пачку і за кг, бейдж складу, «аналог».">
      <Link to="/results" className={`${buttonStyles.button} ${buttonStyles.secondary}`}>
        <span className={buttonStyles.icon} aria-hidden="true">
          <ArrowLeft strokeWidth={1.75} />
        </span>
        До варіантів
      </Link>
    </ScreenStub>
  )
}
