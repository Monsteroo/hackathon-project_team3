import type { ReactNode } from 'react'
import styles from './ScreenStub.module.css'

type Props = { title: string; note: string; children?: ReactNode }

/** Тимчасова заглушка екрана. Видаліть, коли екран буде зверстано. */
export function ScreenStub({ title, note, children }: Props) {
  return (
    <section className={styles.stub}>
      <h1>{title}</h1>
      <p className={styles.note}>{note}</p>
      {children}
    </section>
  )
}
