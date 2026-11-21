import { fireEvent, render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'
import { ConfirmPage } from './ConfirmPage'
import { RequestPage } from './RequestPage'

function renderPage() {
  const router = createMemoryRouter(
    [
      { path: '/', element: <RequestPage /> },
      { path: '/confirm', element: <ConfirmPage /> },
    ],
    { initialEntries: ['/'] },
  )
  render(<RouterProvider router={router} />)
  return router
}

describe('RequestPage', () => {
  it('shows text fallback hint when Web Speech API is unavailable', () => {
    renderPage()
    expect(screen.queryByRole('button', { name: 'Почати голосове введення' })).not.toBeInTheDocument()
    expect(screen.getByText('Браузер не підтримує голос. Введіть список текстом')).toBeInTheDocument()
  })

  it('blocks empty submit with an error and focuses the field', () => {
    const router = renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Знайти кошик' }))
    const field = screen.getByLabelText('Введіть або вставте список')
    expect(screen.getByRole('alert')).toHaveTextContent('Введіть або скажіть, що купити')
    expect(field).toHaveAttribute('aria-invalid', 'true')
    expect(field).toHaveFocus()
    expect(router.state.location.pathname).toBe('/')
  })

  it('fills the field from an example and submits to /confirm', () => {
    const router = renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Борщ на 4 людини' }))
    expect(screen.getByLabelText('Введіть або вставте список')).toHaveValue('Борщ на 4 людини')
    fireEvent.click(screen.getByRole('button', { name: 'Знайти кошик' }))
    expect(router.state.location.pathname).toBe('/confirm')
    expect(router.state.location.state).toMatchObject({ query: 'Борщ на 4 людини', cityId: 'kyiv' })
  })

  it('submits on Enter in the desktop composer', () => {
    const router = renderPage()
    const field = screen.getByLabelText('Введіть або вставте список')
    fireEvent.change(field, { target: { value: 'молоко, хліб' } })
    fireEvent.keyDown(field, { key: 'Enter' })
    expect(router.state.location.pathname).toBe('/confirm')
  })
})
