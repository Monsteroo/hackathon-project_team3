import { Link, Outlet, useLocation } from 'react-router'
import { CitySelect } from '../components/CitySelect/CitySelect'
import styles from './AppLayout.module.css'

/** Кроки потоку з MASTER.md, «Pattern: Voice in → Numbers out». */
const STEPS = [
  { label: 'Запит', match: (p: string) => p === '/' },
  { label: 'Список', match: (p: string) => p.startsWith('/confirm') },
  { label: 'Варіанти', match: (p: string) => p.startsWith('/results') },
  { label: 'Кошик', match: (p: string) => p.startsWith('/basket') },
  { label: 'У магазині', match: (p: string) => p.startsWith('/store') },
]

/** Поки немає акаунта й бекенду — усі 3 безкоштовні кошики доступні. */
const FREE_LEFT = 3
const FREE_TOTAL = 3

export function AppLayout() {
  const { pathname } = useLocation()
  const inFlow = STEPS.some((s) => s.match(pathname))

  return (
    <>
      <a className="skip-link" href="#main">
        Перейти до вмісту
      </a>
      <header className={styles.header}>
        <Link to="/" className={styles.logo} aria-label="Sayvy, на головну">
          Sayvy
          <span className={styles.dot} aria-hidden="true" />
        </Link>
        {inFlow && (
          <nav className={styles.stepsNav} aria-label="Кроки">
            <ol className={styles.steps}>
              {STEPS.map((s) => {
                const current = s.match(pathname)
                return (
                  <li key={s.label} aria-current={current ? 'step' : undefined}>
                    <span>{s.label}</span>
                  </li>
                )
              })}
            </ol>
          </nav>
        )}
        <div className={styles.actions}>
          <CitySelect />
          <span className={`${styles.freePill} num`}>
            {FREE_LEFT} з {FREE_TOTAL} безкоштовних
          </span>
        </div>
      </header>
      <main id="main" className={styles.main}>
        <Outlet />
      </main>
    </>
  )
}
