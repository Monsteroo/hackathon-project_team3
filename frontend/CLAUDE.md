# Sayvy frontend: правила для агентів

- Перед версткою екрана або компонента прочитай `design/BRIEF.md`, `design/design-system/sayvy/MASTER.md` і відповідний розділ `design/DESIGN.md`. Пріоритет при конфлікті: MASTER → DESIGN → BRIEF.
- Стилі: CSS Modules (`Component.module.css`) поруч із компонентом. Лише semantic- і component-токени з `src/styles/tokens/`; сирі hex, px-значення кольорів і primitive-токени заборонено.
- Немає потрібного токена — не вигадуй значення: додай токен у `design/DESIGN.md` і `src/styles/tokens/`, познач це в PR.
- Числа — клас `.num`; ціни, відстані — функції з `src/lib/format.ts`.
- Іконки — `lucide-react`, `strokeWidth={1.75}`, декоративні з `aria-hidden`. Без емодзі.
- Доступність WCAG 2.1 AA: `:focus-visible`, цілі ≥44px (56px у режимі «У магазині»), `aria-live` для статусів голосу й пошуку, `prefers-reduced-motion`.
- Мова інтерфейсу — лише українська.
- Перевірка перед комітом: `npm run typecheck && npm run lint && npm test && npm run build`.
