# Design System Master File — Sayvy

> **LOGIC:** When building a specific page, first check `design-system/sayvy/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** Sayvy — голосовий веб-помічник для покупок продуктів
**Generated:** 2026-11-21 (ui-ux-pro-max `--design-system`, вручну узгоджено з `BRIEF.md`)
**Stack:** React (стилізація — будь-яка; токени подано як CSS custom properties)
**Design Dials:** Variance 4/10 (Balanced / Modern) | Motion 3/10 (Subtle) | Density 5/10 (Standard)
**Характер:** «Голос на вході, цифри на виході». Вхід — асистент, вихід — розумний економіст.

### Що змінено відносно згенерованого результату

Генератор віддав категорію «Insurance Platform» з синьо-зеленою палітрою, зеленою CTA-кнопкою та IBM Plex Sans.
Це суперечить підтвердженому брифу, тому перевизначено:

| Згенеровано | Стало | Причина (бриф) |
|---|---|---|
| Blue base `#0369A1` + sky `#0EA5E9` | Графітова нейтральна база | «Нейтральна графітова база» |
| CTA зелений `#16A34A` | CTA — лаймова заливка `#C6F432` з чорним текстом (ред. 2026-11-21, раніше індиго `#3B4BD8`) | Фідбек «занадто сіро й серйозно». Економія відрізняється формою, а не відтінком |
| IBM Plex Sans | Onest (заголовки) + Inter (UI, ціни, `tnum`) | Кирилиця + табличні цифри |
| Landing pattern «Trust & Authority» | Патерн застосунку «Voice in → Numbers out» | Це веб-застосунок, не лендинг |
| GSAP scroll reveal | CSS-переходи, без scroll-анімацій | Motion 3, утилітарний застосунок |

Залишено з генерації: стиль **Accessible & Ethical** (WCAG 2.1 AA), dials, шкала відступів, чек-лист, анти-патерни.

---

## Global Rules

### Кольорові правила (жорсткі)

1. **Лайм — колір Sayvy, і дія, і економія належать до нього, але мають різну форму.**
   - **Дія:** лаймова заливка + чорний текст (`--color-accent` + `--color-on-accent`). Головна кнопка, мікрофон, вибраний стан, активний пін, виділення в заголовку.
   - **Економія:** оливковий текст `--color-savings` зі знаком «−» («−75 ₴») або чорна пігулка з лаймовою сумою (`--color-savings-solid` + `--color-on-savings-solid`). Оливковий — лише економія: не для посилань, успіху, «склад перевірено», чекбоксів.
2. **Лайм ніколи не текст і не межа на світлих поверхнях** (1.28:1 на білому). Текст, іконки й межі з акцентним значенням — `--color-accent-fg` (чорнило). Фокус — `--color-ring` (чорнило).
3. **Кольори мереж (АТБ, Сільпо, Novus тощо) у палітру не входять.** Мережа впізнається лише за логотипом із даних. Sayvy — нейтральний арбітр.
4. Значення ніколи не передається лише кольором: економія має знак «−» і суму, аналог має текст «аналог», помилка має іконку й текст.
5. Компоненти використовують лише семантичні токени, без сирих hex.

### Color Tokens — Light (MVP)

| Role | Hex | CSS Variable | Контраст |
|---|---|---|---|
| Background (app) | `#F8F8F4` | `--color-bg` | теплий off-white |
| Surface (cards, sheet) | `#FFFFFF` | `--color-surface` | — |
| Surface subtle (chips, rows) | `#F1F1EB` | `--color-surface-2` | — |
| Text primary | `#18181B` | `--color-text` | 16.5:1 на bg |
| Text secondary | `#52525B` | `--color-text-2` | 7.2:1 на bg |
| Text tertiary (meta, ціна/кг) | `#63636B` | `--color-text-3` | ≥4.5:1 на всіх поверхнях |
| Border | `#E2E2E6` | `--color-border` | декоративна |
| Border strong (inputs, controls) | `#8E8E98` | `--color-border-strong` | 3.2:1 (UI ≥3:1) |
| Accent (лише заливка) | `#C6F432` | `--color-accent` | 1.28:1 на surface — не для тексту |
| Accent hover / pressed | `#B5E61D` | `--color-accent-hover` | — |
| Accent subtle (selected bg) | `#F7FDE6` | `--color-accent-subtle` | — |
| Accent tint (hero bg) | `#ECFCCB` | `--color-accent-tint` | декоративний; text-2 на ньому 7:1+ |
| On accent | `#18181B` | `--color-on-accent` | 13.8:1 на accent |
| Accent fg (текст/іконка/межа) | `#18181B` | `--color-accent-fg` | 16.5:1 на bg |
| Savings (текст, сума) | `#4D7C0F` | `--color-savings` | 5.0:1 на surface, 4.7:1 на bg |
| Savings strong | `#3F6212` | `--color-savings-strong` | 6.5:1 на savings-subtle |
| Savings subtle (бейдж bg) | `#ECFCCB` | `--color-savings-subtle` | — |
| Savings solid (пігулка bg) | `#18181B` | `--color-savings-solid` | — |
| On savings solid | `#C6F432` | `--color-on-savings-solid` | 13.8:1 |
| Warning (аналог, нестанд. вага) | `#9A4A06` | `--color-warning` | 5.7:1 на warning-subtle |
| Warning subtle | `#FEF3E2` | `--color-warning-subtle` | — |
| Danger (бюджет, помилка) | `#C2261F` | `--color-danger` | 5.9:1 на surface |
| Danger strong | `#A61F19` | `--color-danger-strong` | 6.5:1 на danger-subtle |
| Danger subtle | `#FDECEC` | `--color-danger-subtle` | — |
| Focus ring | `#18181B` | `--color-ring` | 2px + 2px offset, 16.6:1 на bg |
| Scrim (modal, sheet) | `rgba(24,24,27,0.48)` | `--color-scrim` | — |

### Color Tokens — Dark (готові, не в MVP)

| Variable | Hex | Контраст |
|---|---|---|
| `--color-bg` | `#111114` | — |
| `--color-surface` | `#1B1B20` | — |
| `--color-surface-2` | `#24242A` | — |
| `--color-text` | `#F4F4F5` | 17.2:1 |
| `--color-text-2` | `#A1A1AA` | 6.7:1 |
| `--color-text-3` | `#8B8B94` | 5.1:1 |
| `--color-border` | `#2E2E36` | — |
| `--color-border-strong` | `#6B6B75` | 3.3:1 |
| `--color-accent` | `#C6F432` | 13.4:1 |
| `--color-accent-hover` | `#D4F75E` | — |
| `--color-accent-subtle` | `#262F12` | — |
| `--color-accent-tint` | `#262F12` | — |
| `--color-on-accent` | `#18181B` | 13.8:1 |
| `--color-accent-fg` | `#F4F4F5` | 15.6:1 |
| `--color-ring` | `#C6F432` | 14.7:1 |
| `--color-savings` | `#C6F432` | 13.4:1 |
| `--color-savings-strong` | `#D4F75E` | 12.4:1 на savings-subtle |
| `--color-savings-subtle` | `#1F2A0A` | — |
| `--color-savings-solid` | `#1F2A0A` | — |
| `--color-on-savings-solid` | `#C6F432` | 11.8:1 |
| `--color-warning` | `#F5B454` | 9.4:1 |
| `--color-warning-subtle` | `#3A2A12` | — |
| `--color-danger` | `#F87171` | 6.2:1 |
| `--color-danger-subtle` | `#3B1616` | — |

Перемикання: `[data-theme="dark"]` на `<html>`. Тіні в темній темі замінюються на `--color-border`.

### Typography

- **Display / заголовки:** Onest 600–700 (кирилиця, cyrillic-ext).
- **UI, текст, усі цифри й ціни:** Inter 400/500/600 з `font-variant-numeric: tabular-nums` — ціни вирівнюються в колонках.
- **Правило:** будь-яке число, ціна, вага, відстань, час — Inter + `tabular-nums`, навіть усередині заголовка.

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Onest:wght@600;700&subset=cyrillic,cyrillic-ext&display=swap');

:root {
  --font-display: 'Onest', system-ui, sans-serif;
  --font-ui: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
}
.num { font-family: var(--font-ui); font-variant-numeric: tabular-nums; }
```

| Token | Size / Line-height | Font / Weight | Використання |
|---|---|---|---|
| `--text-display` | 40 / 48 (мобільний 32 / 40) | Onest 700 | Онбординг, paywall |
| `--text-h1` | 24 / 32 | Onest 700 | Заголовок екрана |
| `--text-h2` | 20 / 28 | Onest 600 | Секція, назва варіанту |
| `--text-price-lg` | 28 / 32 | Inter 600 tnum | Сума кошика |
| `--text-body-lg` | 18 / 28 | Inter 400 | Живе розпізнавання голосу |
| `--text-body` | 16 / 24 | Inter 400 | Базовий текст, поля (не менше 16px — без зуму в iOS) |
| `--text-label` | 14 / 20 | Inter 500 | Кнопки, чипи, ціна за пачку |
| `--text-meta` | 13 / 18 | Inter 400 tnum | Ціна за кг, відстань, «870 г» |
| `--text-caption` | 12 / 16 | Inter 500 | Бейджі (мінімум; основний текст не менше 14px) |

### Price formatting (uk-UA)

- Пачка: `1 249,90 ₴` — розділювач тисяч U+202F (вузький нерозривний пробіл), десяткова кома, нерозривний пробіл перед `₴`.
- Одиниця: `112,40 ₴/кг`, `48,90 ₴/л`, `6,20 ₴/шт`.
- Ціна за кг/л завжди поруч із ціною за пачку, `--text-meta`, `--color-text-3`.
- Нестандартна вага (не 100/200/250/500 г, 1 кг, 0,5/1 л): бейдж Warning «870 г».
- Економія: `−75 ₴` зі справжнім мінусом U+2212, `--color-savings`.
- Відстань: `450 м · 6 хв пішки`; від 1 000 м — `1,2 км`.

### Spacing Variables

*Density: 5/10 — Standard*

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` / `0.25rem` | Іконка ↔ текст у бейджі |
| `--space-sm` | `8px` / `0.5rem` | Між чипами, inline |
| `--space-md` | `16px` / `1rem` | Внутрішній відступ карток, бокове поле на мобільному |
| `--space-lg` | `24px` / `1.5rem` | Між секціями всередині екрана |
| `--space-xl` | `32px` / `2rem` | Великі розриви, бокове поле на десктопі |
| `--space-2xl` | `48px` / `3rem` | Відступи між секціями |
| `--space-3xl` | `64px` / `4rem` | Онбординг, paywall |

### Radius

| Token | Value | Usage |
|---|---|---|
| `--radius-sm` | `6px` | Бейджі |
| `--radius-md` | `10px` | Кнопки, поля, чипи |
| `--radius-lg` | `14px` | Картки варіантів, позиції |
| `--radius-xl` | `20px` | Верх bottom sheet, модальні вікна |
| `--radius-full` | `9999px` | Мікрофон, аватар, пігулки |

### Elevation

Плоско за замовчуванням: картки відділяються `1px solid var(--color-border)`, не тінню.

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(24,24,27,0.06)` | Вибрана картка варіанту |
| `--shadow-md` | `0 4px 12px rgba(24,24,27,0.08)` | Плаваюча кнопка, пін на карті |
| `--shadow-lg` | `0 -4px 24px rgba(24,24,27,0.12)` | Bottom sheet над картою |
| `--shadow-xl` | `0 16px 40px rgba(24,24,27,0.16)` | Модальне вікно (paywall на десктопі) |

### Layout & Breakpoints (desktop-first)

Основна платформа — десктоп. Базові стилі пишуться для десктопа, менші ширини — через `max-width`.

| Token | Media query | Layout |
|---|---|---|
| base | дизайн на 1440px | Два стовпці: список/картки ліворуч (min 400, max 480px), карта/обмеження праворуч. Контент max 1280px по центру, поле 32px |
| `--bp-xl` | `max-width: 1439px` | Контент на всю ширину, поле 32px |
| `--bp-lg` | `max-width: 1023px` | Один стовпець, ширші картки. Бічна панель → нижній sheet |
| `--bp-md` | `max-width: 767px` | Мобільна адаптація (перевірка на 375px): поле 16px, нижній sheet |

- Висота: `100dvh`, безпечні зони `env(safe-area-inset-*)` для нижніх панелей і sheet.
- Без горизонтального скролу; масштабування не блокувати.

### Touch targets

- Мінімум **44×44px**, між цілями не менше 8px.
- **Режим «У магазині» (екран 5): рядки та чекбокси не менше 56px заввишки, весь рядок клікабельний.**
- Мікрофон: 96px на мобільному (екран 1), 72px у компактному стані.

### Motion (dial 3 — Subtle)

Без scroll-анімацій і хореографії. Рух лише пояснює зміну стану. GSAP не потрібен — CSS-переходів достатньо.

| Token | Value | Usage |
|---|---|---|
| `--dur-fast` | `120ms` | Hover, натискання, чекбокс |
| `--dur-base` | `200ms` | Чипи, бейджі, розкриття |
| `--dur-slow` | `280ms` | Bottom sheet, модальне вікно |
| `--ease-out` | `cubic-bezier(0.2, 0, 0, 1)` | Вхід |
| `--ease-in` | `cubic-bezier(0.4, 0, 1, 1)` | Вихід (на 30% коротший за вхід) |

- Анімувати лише `transform` і `opacity`.
- Мікрофон під час запису: кільце масштабується від рівня гучності (`scale 1→1.15`), без нескінченного декоративного пульсу.
- Перерахунок суми: цифри змінюються без анімації підрахунку — точність важливіша за ефект.
- `prefers-reduced-motion: reduce` — переходи 0–1ms, кільце мікрофона статичне, рівень показується смужкою.

### Icons

Lucide (`lucide-react`), stroke 1.75, розміри 16 / 20 / 24. Іконки-кнопки мають `aria-label`, декоративні — `aria-hidden="true"`. Без емодзі.

---

## Pattern: «Voice in → Numbers out»

Застосунок, не лендинг. Потік екранів: 0 Онбординг → 1 Запит → 2 «Я зрозумів так» → 3 Карта + 3 варіанти → 4 Деталі кошика → 5 У магазині; 6 Paywall після 3-го кошика.

- **Вхід (екрани 0–2):** мінімум хрому, великий мікрофон і текстове поле як рівноправні способи. Текст розпізнавання — `--text-body-lg`.
- **Вихід (екрани 3–5):** щільність середня, цифри вирівняні, кожна рекомендація пояснена одним рядком.
- **Порівнюється весь кошик:** над варіантами завжди рядок «Порівнюємо весь кошик, а не окремі знижки».
- **Деградація:** без мікрофона — лише поле вводу (не помилка); без геолокації — поле адреси.

---

## Component Specs

### Buttons

```css
.btn {
  min-height: 48px; padding: 0 var(--space-lg);
  border-radius: var(--radius-md);
  font: 500 var(--text-label) var(--font-ui);
  transition: background-color var(--dur-fast) var(--ease-out);
  cursor: pointer;
}
.btn:focus-visible { outline: 2px solid var(--color-ring); outline-offset: 2px; }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* Primary — одна на екран */
.btn-primary { background: var(--color-accent); color: var(--color-on-accent); }
.btn-primary:hover, .btn-primary:active { background: var(--color-accent-hover); }

/* Secondary */
.btn-secondary { background: var(--color-surface); color: var(--color-text); border: 1px solid var(--color-border-strong); }
.btn-secondary:hover { background: var(--color-surface-2); }

/* Ghost — «Замінити», «+ Додати товар» */
.btn-ghost { background: transparent; color: var(--color-accent-fg); }
.btn-ghost:hover { background: var(--color-accent-subtle); }
```

Без `translateY` на hover — макет не зсувається. Стан завантаження: спінер замість іконки, текст залишається, кнопка `aria-busy="true"`.

### MicButton

- 96px коло, `--color-accent` (лайм) з чорною іконкою `Mic` 32px, `aria-label="Почати голосове введення"`, `aria-pressed` під час запису.
- Стани: idle → listening (кільце від гучності, підпис «Слухаю…») → processing (спінер, «Розбираю запит…») → error.
- Помилки під кнопкою, текстом із іконкою: «Не почув. Спробуйте ще раз або введіть текстом» / «Браузер не підтримує голос. Введіть список текстом».
- Якщо Web Speech API недоступний, кнопка не рендериться, поле вводу стає головним.

### Request input

Багаторядкове поле, label «Введіть або вставте список» (видимий, не лише placeholder), `font-size: 16px`, автозбільшення висоти до 6 рядків, кнопка надсилання 44px.

### ProductChip (екран 2)

`--color-surface-2`, `--radius-md`, висота 40px (зона натискання 44px). Назва + кількість (`2 × 1 л`, tnum) + кнопка видалення `aria-label="Прибрати {назва}"`. Натискання відкриває редагування кількості.

### ConstraintChip

Бюджет, алергени, дієта, відстань. Неактивний: border strong. Активний: лаймова заливка `--color-accent` + межа й текст `--color-accent-fg` + іконка `Check`. Не оливковий.

### PriceBlock

```
48,90 ₴            ← --text-label, Inter 600 tnum, --color-text
112,40 ₴/кг · 870 г  ← --text-meta tnum, --color-text-3; «870 г» — Warning-бейдж, якщо вага нестандартна
```

Вирівнювання праворуч у таблицях і списках.

### Badges

| Variant | Колір | Іконка | Приклад |
|---|---|---|---|
| Savings | on-savings-solid на savings-solid (лайм на чорному, 13.8:1) | `TrendingDown` | «−240 ₴ до інших» |
| Analog | warning on warning-subtle | `Replace` | «аналог» + кнопка «Замінити» |
| Nonstandard weight | warning on warning-subtle | — | «870 г» |
| Composition verified | text-2 on surface-2 | `ShieldCheck` | «Склад перевірено: без лактози» |
| Not found | danger on danger-subtle | `CircleAlert` | «Немає в жодній мережі» |

«Склад перевірено» завжди містить причину, чому товар пройшов фільтр (tooltip/розкриття на мобільному — натисканням, не hover).

### OptionCard (екран 3)

- Три варіанти: **Найближчий / Найвигідніший / Smart Split** (2 магазини одним маршрутом).
- Вміст: назва варіанту (`--text-h2`), логотип(и) мережі 24px з даних, сума `--text-price-lg`, рядок компромісу, відстань і час.
- **Рядок компромісу:** «−75 ₴ за +450 м» — сума `--color-savings` (оливковий), відстань `--color-text-2`. Якщо варіант дорожчий: «+40 ₴, але на 600 м ближче» — без оливкового.
- Вибраний: `border: 2px solid var(--color-accent-fg)` + фон `--color-accent-subtle` + `--shadow-sm`, `aria-pressed`/radio-група.
- Мобільний: горизонтальний snap-скрол у sheet, або вертикальний стек у розгорнутому sheet. Десктоп: стек ліворуч.

### BottomSheet (екран 3, мобільний)

Три положення: peek (тільки найкращий варіант, ~180px), half (50%), full. Ручка 32×4px, ціль перетягування 44px. Клавіатура: ручка — кнопка «Розгорнути список варіантів». `--radius-xl` зверху, `--shadow-lg`.

### Map

Нейтральний графітовий стиль тайлів (без яскравих кольорів). Піни: неактивні `--color-text-2`, вибраний — лаймова заливка `--color-accent` з чорною обводкою `--color-accent-fg` і логотипом мережі. Позиція користувача — лаймове коло з чорною обводкою. Кнопка «Маршрут» відкриває Google Maps / Apple Maps (зовнішнє посилання, іконка `ExternalLink`).

### Basket item row (екран 4)

Фото 56px (`aspect-ratio: 1`, `object-fit: contain`, фон surface-2, lazy), назва + бренд, бейджі, PriceBlock праворуч. Десктоп: таблиця з колонками «Товар / Пачка / За кг / Варіант Б / Варіант В», числа праворуч, tnum.

### In-store row (екран 5)

Висота не менше 56px, чекбокс 24px у зоні 56×56, фото 48px, назва `--text-body`. Відмічений: назва `--color-text-3` + закреслення, рядок переходить униз відділу (200ms). Заголовки відділів липкі. Кнопка «Маршрут» закріплена знизу з safe-area.

### Paywall (екран 6)

Мобільний — повноекранний; десктоп — модальне вікно max 480px, `--shadow-xl`, scrim. Акцент на економії: «Ви вже заощадили 312 ₴ на 3 кошиках» — сума в чорній пігулці з лаймовим текстом (`--color-savings-solid`). Ціна «165 ₴/міс» — Inter 600. Primary CTA accent. Вхід Google / email. Фокус затиснений у модальному вікні, Esc закриває.

### Banners & empty states

Іконка + заголовок + одне речення + дія. Помилка мережі: «Немає з'єднання» + «Спробувати знову». Бюджет перевищено: «Бракує 86 ₴» (danger) + список того, що можна прибрати, з сумою кожної позиції. Немає магазинів поруч: збільшити радіус / ввести адресу.

### Loading

Скелетони з фіксованою висотою (CLS < 0.1) + текст етапу з `aria-live="polite"`: «Розбираю запит…» → «Шукаю ціни в 6 мережах…». Без нескінченних спінерів понад 10 с — показати стан помилки.

---

## Style Guidelines

**Style:** Accessible & Ethical, плоский, стриманий.

**Keywords:** high contrast, 16px+ body, keyboard navigation, screen reader friendly, visible focus, semantic HTML, tabular numerals, neutral arbiter

**Key Effects:** focus ring 2px + offset 2px, ARIA labels, skip link, `aria-live` для статусів голосу й пошуку, `prefers-reduced-motion`, цілі 44px (56px у магазині)

**Accessibility target:** WCAG 2.1 AA (припущення 4 брифу).

---

## Anti-Patterns (Do NOT Use)

- ❌ Оливковий `--color-savings` для чогось, крім економії (посилання, успіх, перевірений склад, чекбокси)
- ❌ Лайм як колір тексту, іконки чи межі на світлому фоні
- ❌ Кольори торговельних мереж у UI-палітрі
- ❌ Приховування ціни за кг або нестандартної ваги
- ❌ Підсвічування окремих знижок замість суми всього кошика
- ❌ Голос як єдиний спосіб вводу; помилка замість деградації при відмові в дозволах
- ❌ Анімований підрахунок цифр, декоративні нескінченні анімації
- ❌ Нетабличні цифри в цінах
- ❌ AI purple/pink gradients, glassmorphism

### Additional Forbidden Patterns

- ❌ **Emojis as icons** — Lucide SVG
- ❌ **Missing cursor:pointer** — All clickable elements must have cursor:pointer
- ❌ **Layout-shifting hovers** — без scale/translate на hover
- ❌ **Low contrast text** — Maintain 4.5:1 minimum contrast ratio
- ❌ **Instant state changes** — переходи 120–280ms (крім reduced motion)
- ❌ **Invisible focus states** — Focus states must be visible for a11y
- ❌ **Hover-only info** — пояснення «склад перевірено» має працювати натисканням

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] Оливковий і чорна пігулка — лише економія; лайм — лише заливка
- [ ] Жодних кольорів мереж поза логотипами
- [ ] Ціна за кг/л поруч із кожною ціною за пачку; нестандартна вага позначена
- [ ] Усі числа — Inter + `tabular-nums`
- [ ] Застосунок працює без мікрофона та без геолокації
- [ ] No emojis used as icons (Lucide only)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Light mode: text contrast 4.5:1 minimum, UI-межі 3:1
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Touch targets ≥44px, у режимі магазину ≥56px
- [ ] Responsive: 1440px (база), 1024px, 768px, 375px
- [ ] Safe areas для sheet і нижніх кнопок
- [ ] No horizontal scroll на жодній ширині
