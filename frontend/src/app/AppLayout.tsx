import { Link, Outlet } from 'react-router'
import styles from './AppLayout.module.css'

export function AppLayout() {
  return (
    <>
      <a className="skip-link" href="#main">
        Перейти до вмісту
      </a>
      <header className={styles.header}>
        <Link to="/" className={styles.logo}>
          Sayvy
        </Link>
      </header>
      <main id="main" className={styles.main}>
        <Outlet />
      </main>
    </>
  )
}
