import { createBrowserRouter } from 'react-router'
import { AppLayout } from './AppLayout'
import { OnboardingPage } from '../pages/OnboardingPage'
import { RequestPage } from '../pages/RequestPage'
import { ConfirmPage } from '../pages/ConfirmPage'
import { BasketPage } from '../pages/BasketPage'
import { InStorePage } from '../pages/InStorePage'
import { NotFoundPage } from '../pages/NotFoundPage'

/** Екрани 0–5 з design/BRIEF.md. Paywall (екран 6) — модальне вікно, не маршрут. */
export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: '/', element: <RequestPage /> },
      { path: '/welcome', element: <OnboardingPage /> },
      { path: '/confirm', element: <ConfirmPage /> },
      {
        path: '/results',
        // MapLibre важкий (~1 MB): вантажимо лише на екрані карти.
        lazy: () => import('../pages/ResultsPage').then((m) => ({ Component: m.ResultsPage })),
      },
      { path: '/basket/:optionId', element: <BasketPage /> },
      { path: '/store/:optionId', element: <InStorePage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
