import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router'
import buttonStyles from '../components/Button/Button.module.css'
import { ScreenStub } from './ScreenStub'

export function InStorePage() {
  return (
    <ScreenStub title="У магазині" note="Екран 5: список за відділами, чекбокси, кнопка «Маршрут».">
      <Link to="/results" className={`${buttonStyles.button} ${buttonStyles.secondary}`}>
        <span className={buttonStyles.icon} aria-hidden="true">
          <ArrowLeft strokeWidth={1.75} />
        </span>
        До варіантів
      </Link>
    </ScreenStub>
  )
}
