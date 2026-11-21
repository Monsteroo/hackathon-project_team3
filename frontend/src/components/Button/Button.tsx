import type { ButtonHTMLAttributes, ReactNode } from 'react'
import styles from './Button.module.css'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost'
  size?: 'default' | 'sm'
  icon?: ReactNode
  loading?: boolean
}

/** DESIGN.md §4.0. Primary — одна на екран. */
export function Button({
  variant = 'primary',
  size = 'default',
  icon,
  loading = false,
  className,
  children,
  type = 'button',
  ...rest
}: Props) {
  const classes = [styles.button, styles[variant], size === 'sm' && styles.sm, className]
    .filter(Boolean)
    .join(' ')
  return (
    <button type={type} className={classes} aria-busy={loading || undefined} {...rest}>
      {loading ? <span className={styles.spinner} aria-hidden="true" /> : icon && (
        <span className={styles.icon} aria-hidden="true">
          {icon}
        </span>
      )}
      {children}
    </button>
  )
}
