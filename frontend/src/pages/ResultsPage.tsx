import { StoreMap } from '../components/StoreMap/StoreMap'
import { ScreenStub } from './ScreenStub'

export function ResultsPage() {
  return (
    <ScreenStub
      title="3 варіанти кошика"
      note="Екран 3: картки ліворуч (Найближчий / Найвигідніший / Smart Split), карта праворуч."
    >
      <StoreMap />
    </ScreenStub>
  )
}
