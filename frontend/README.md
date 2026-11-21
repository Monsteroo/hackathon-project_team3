# Sayvy — фронтенд

Голосовий веб-помічник для покупок продуктів. Desktop-first, мобільна адаптація.

## Стек

| Що | Чим | Чому |
|---|---|---|
| Збірка | Vite 8 + React 19 + TypeScript | Швидкий старт і dev-сервер, SPA для живого демо |
| Стилі | CSS Modules + CSS custom properties | Токени з `design/DESIGN.md` читаються напряму, без дублювання |
| Роутинг | React Router 7 (data router) | Екрани 0–5 з брифу, lazy-маршрут для карти |
| Дані | TanStack Query | Кеш і стани завантаження/помилки для запитів до API |
| Карта | MapLibre GL + OpenFreeMap (OSM) | Векторні тайли без API-ключа, Київ покритий повністю, підписи `name:uk` |
| Іконки | lucide-react, stroke 1.75 | Вимога дизайн-системи, без емодзі |
| Шрифти | Onest (заголовки) + Inter (UI, цифри з `tabular-nums`) | Кирилиця, ціни вирівнюються в колонках |
| Голос | Web Speech API у браузері | Текстове введення рівноправне: Firefox голос не підтримує |
| Тести | Vitest + Testing Library | |
| Лінт | oxlint | |

## Запуск

```bash
npm install
npm run dev        # http://localhost:5173
npm test           # Vitest
npm run typecheck
npm run lint
npm run build
```

Запити на `/api/*` проксюються на `http://localhost:8000` (див. `vite.config.ts`). Змініть ціль, коли буде відомий порт бекенду.

## Структура

```
design/                    джерело правди дизайну (перенесено з репо sayvy)
├── BRIEF.md               підтверджений бриф: екрани, стани, правила
├── design-system/sayvy/MASTER.md   токени, кольорові правила, формат цін, чек-лист
├── DESIGN.md              архітектура токенів і специфікації компонентів
├── DESIGN_PROMPT.md       завдання для дизайну функціоналу
└── mocks/sayvy-prototype.html      клікабельний HTML-прототип
src/
├── app/                   App, router, layout
├── pages/                 екрани (зараз заглушки ScreenStub)
├── components/            Button, StoreMap; далі VoiceButton, StoreCard, BasketRow…
├── lib/format.ts          формат цін і відстаней uk-UA
└── styles/
    ├── tokens/            primitives → semantic → components (з DESIGN.md §2–4)
    └── base.css           reset, .num, .sr-only, фокус
```

## Правила дизайн-системи (коротко)

- Компоненти читають лише component- або semantic-токени. Сирий hex і primitive-токени (`--lime-400`) у компонентах заборонено.
- Лайм `--color-accent` — лише заливка дії. Текст, іконки й межі з акцентом — `--color-accent-fg`.
- Оливковий `--color-savings*` — лише економія, завжди зі знаком «−».
- Кольорів торговельних мереж немає в палітрі.
- Будь-яке число — клас `.num` (Inter + `tabular-nums`). Ціни форматуються через `src/lib/format.ts`.
- Breakpoints desktop-first: `max-width: 1439px` / `1023px` / `767px`.
- Змінюєте токен — спершу в `design/DESIGN.md`, потім у `src/styles/tokens/`.
