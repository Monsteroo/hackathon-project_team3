# Sayvy — Design System

> Токени (primitive → semantic → component) і специфікації компонентів для передачі в розробку.
> Джерело: [`design-system/sayvy/MASTER.md`](design-system/sayvy/MASTER.md) + [`BRIEF.md`](BRIEF.md).
> Якщо цей файл і MASTER розходяться в значеннях, правильний MASTER. Відхилення від MASTER зібрано в розділі 6.

**Статус:** чернетка для розробки, 2026-11-21
**Тема MVP:** світла. Темна тема описана, але не входить у MVP (`[data-theme="dark"]` на `<html>`).
**Доступність:** WCAG 2.1 AA. Усі кольорові пари перевірено розрахунком (розділ 5).

---

## Зміст

1. [Архітектура токенів](#1-архітектура-токенів)
2. [Primitive tokens](#2-primitive-tokens)
3. [Semantic tokens](#3-semantic-tokens)
4. [Component tokens і специфікації](#4-component-tokens-і-специфікації)
   - 4.0 [Button (базова, для дій у компонентах)](#40-button-базова)
   - 4.1 [VoiceButton — кнопка голосу](#41-voicebutton--кнопка-голосу)
   - 4.2 [StoreCard — картка магазину](#42-storecard--картка-магазину)
   - 4.3 [BasketRow — рядок кошика](#43-basketrow--рядок-кошика)
   - 4.4 [UnitPrice — бейдж «ціна за 1 кг»](#44-unitprice--бейдж-ціна-за-1-кг)
   - 4.5 [AnalogNotice — плашка аналога](#45-analognotice--плашка-аналога)
   - 4.6 [AllergenBadge — бейдж алергену](#46-allergenbadge--бейдж-алергену)
   - 4.7 [CitySelect — вибір міста](#47-cityselect--вибір-міста)
   - 4.8 [AppHeader і RequestHero — шапка й екран 1](#48-appheader-і-requesthero--шапка-й-екран-1)
   - 4.9 [BasketEditor — екран 2 «Я зрозумів так»](#49-basketeditor--екран-2-я-зрозумів-так)
5. [Перевірка контрастів](#5-перевірка-контрастів)
6. [Відхилення від MASTER і відкриті питання](#6-відхилення-від-master-і-відкриті-питання)

---

## 1. Архітектура токенів

```
Primitive   --graphite-600, --lime-400, --dim-4          сирі значення, без змісту
    ↓
Semantic    --color-text-2, --color-accent, --space-md   зміст; перемикається темою
    ↓
Component   --voice-bg, --store-card-border              один компонент; посилається лише на semantic
```

### Правила

1. **Компоненти читають лише component- або semantic-токени.** Primitive у компонентах заборонено. Сирий hex у компонентах заборонено.
2. **Component-токени посилаються лише на semantic.** Виняток: розміри, яких немає в semantic-шарі (наприклад, іконка мікрофона 32px), посилаються на `--dim-*`.
3. **Тема перемикає лише semantic-шар.** Component- і primitive-шари однакові для світлої й темної теми.
4. Оливковий і інверсна пігулка (`--color-savings*`) — лише економія. У component-шарі такі токени мають у назві `savings` або `lowest`. Лайм (`--color-accent`) — лише заливка дії або вибору; текст, іконки й межі з акцентним значенням читають `--color-accent-fg`.
5. Кольорів торговельних мереж немає в жодному шарі. Мережа впізнається лише за логотипом із даних.

### Іменування

```
primitive   --{палітра}-{крок}          --graphite-600, --amber-50
            --{категорія}-{значення}    --dim-4, --round-14, --duration-200
semantic    --{категорія}-{роль}[-{варіант}]       --color-text-2, --color-savings-strong
component   --{компонент}-{властивість}[-{стан}]   --voice-bg-listening, --store-card-border-selected
```

### Файли в коді

```
src/styles/tokens/
├── primitives.css   розділ 2
├── semantic.css     розділ 3 (light + dark + reduced motion)
├── components.css   розділ 4, усі блоки «Component tokens»
└── index.css        @import трьох файлів у цьому порядку
```

---

## 2. Primitive tokens

Значення взято з MASTER без змін. Кроки палітри не рівномірні: у палітрі є лише ті значення, які використовує semantic-шар.

```css
/* === PRIMITIVES === */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Onest:wght@600;700&subset=cyrillic,cyrillic-ext&display=swap');

:root {
  /* --- Graphite: нейтральна база (світла й темна тема) --- */
  --graphite-0:   #FFFFFF;
  --graphite-25:  #F8F8F4;   /* теплий off-white замість холодного сірого */
  --graphite-50:  #F4F4F5;
  --graphite-75:  #F1F1EB;
  --graphite-100: #E2E2E6;
  --graphite-300: #A1A1AA;
  --graphite-400: #8E8E98;
  --graphite-450: #8B8B94;
  --graphite-500: #6B6B75;
  --graphite-550: #63636B;
  --graphite-600: #52525B;
  --graphite-800: #2E2E36;
  --graphite-850: #24242A;
  --graphite-900: #1B1B20;
  --graphite-925: #18181B;
  --graphite-950: #111114;
  --graphite-925-a48: rgba(24, 24, 27, 0.48);

  /* --- Lime: акцент Sayvy (заливки) і економія (оливкові кроки 700–800) --- */
  --lime-50:  #F7FDE6;
  --lime-100: #ECFCCB;
  --lime-300: #D4F75E;
  --lime-400: #C6F432;
  --lime-500: #B5E61D;
  --lime-700: #4D7C0F;
  --lime-800: #3F6212;
  --lime-900: #262F12;
  --lime-950: #1F2A0A;

  /* --- Amber: аналог, нестандартна вага, сліди алергенів --- */
  --amber-50:  #FEF3E2;
  --amber-300: #F5B454;
  --amber-800: #9A4A06;
  --amber-950: #3A2A12;

  /* --- Red: бюджет, помилка, алерген у складі --- */
  --red-50:  #FDECEC;
  --red-400: #F87171;
  --red-600: #C2261F;
  --red-700: #A61F19;
  --red-950: #3B1616;

  /* --- Typography --- */
  --font-family-onest: 'Onest', system-ui, sans-serif;
  --font-family-inter: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;

  --font-weight-400: 400;
  --font-weight-500: 500;
  --font-weight-600: 600;
  --font-weight-700: 700;

  --font-size-12: 0.75rem;
  --font-size-13: 0.8125rem;
  --font-size-14: 0.875rem;
  --font-size-16: 1rem;
  --font-size-18: 1.125rem;
  --font-size-20: 1.25rem;
  --font-size-24: 1.5rem;
  --font-size-28: 1.75rem;
  --font-size-32: 2rem;
  --font-size-40: 2.5rem;

  --line-height-16: 1rem;
  --line-height-18: 1.125rem;
  --line-height-20: 1.25rem;
  --line-height-24: 1.5rem;
  --line-height-28: 1.75rem;
  --line-height-32: 2rem;
  --line-height-40: 2.5rem;
  --line-height-48: 3rem;

  /* --- Dimension: крок 4px (відступи й розміри) --- */
  --dim-0:  0;
  --dim-0-5: 0.125rem; /*  2px */
  --dim-1:  0.25rem;   /*  4px */
  --dim-2:  0.5rem;    /*  8px */
  --dim-3:  0.75rem;   /* 12px */
  --dim-4:  1rem;      /* 16px */
  --dim-5:  1.25rem;   /* 20px */
  --dim-6:  1.5rem;    /* 24px */
  --dim-8:  2rem;      /* 32px */
  --dim-10: 2.5rem;    /* 40px */
  --dim-11: 2.75rem;   /* 44px */
  --dim-12: 3rem;      /* 48px */
  --dim-14: 3.5rem;    /* 56px */
  --dim-16: 4rem;      /* 64px */
  --dim-18: 4.5rem;    /* 72px */
  --dim-20: 5rem;      /* 80px */
  --dim-24: 6rem;      /* 96px */
  --dim-42: 10.5rem;   /* 168px */
  --dim-70: 17.5rem;   /* 280px */
  --dim-80: 20rem;     /* 320px */
  --dim-100: 25rem;    /* 400px */
  --dim-120: 30rem;    /* 480px */

  /* --- Radius --- */
  --round-6:    6px;
  --round-10:   10px;
  --round-14:   14px;
  --round-20:   20px;
  --round-full: 9999px;

  /* --- Shadow --- */
  --shadow-1: 0 1px 2px rgba(24, 24, 27, 0.06);
  --shadow-2: 0 4px 12px rgba(24, 24, 27, 0.08);
  --shadow-3: 0 -4px 24px rgba(24, 24, 27, 0.12);
  --shadow-4: 0 16px 40px rgba(24, 24, 27, 0.16);

  /* --- Motion --- */
  --duration-0:   1ms;
  --duration-120: 120ms;
  --duration-200: 200ms;
  --duration-280: 280ms;
  --easing-decelerate: cubic-bezier(0.2, 0, 0, 1);
  --easing-accelerate: cubic-bezier(0.4, 0, 1, 1);

  /* --- Layer --- */
  --layer-0:  0;
  --layer-10: 10;
  --layer-20: 20;
  --layer-30: 30;
  --layer-40: 40;
  --layer-50: 50;

  /* --- Opacity --- */
  --opacity-40: 0.4;
}
```

**Breakpoints** не можна читати через `var()` у `@media`. Тому це константи, а не токени:

| Назва | Значення | Зміна макета |
|---|---|---|
| base | дизайн на 1440px | Два стовпці: список 400–480px ліворуч, карта праворуч. Контент max 1280px по центру, поле 32px |
| xl | `max-width: 1439px` | Контент на всю ширину, поле 32px |
| lg | `max-width: 1023px` | Один стовпець, ширші картки. Ліва панель → нижній sheet |
| md | `max-width: 767px` | Мобільна адаптація (перевірка на 375px): поле 16px, нижній sheet, safe-area |

Підхід **desktop-first**: базові стилі — десктоп, менші ширини — через `max-width`.

---

## 3. Semantic tokens

Назви semantic-токенів збігаються з MASTER, щоб специфікації MASTER працювали без змін.

```css
/* === SEMANTIC: LIGHT (MVP) === */
:root {
  color-scheme: light;

  /* --- Поверхні --- */
  --color-bg:         var(--graphite-25);
  --color-surface:    var(--graphite-0);
  --color-surface-2:  var(--graphite-75);
  --color-logo-plate: var(--graphite-0);   /* фон під логотипом мережі; білий в обох темах */
  --color-scrim:      var(--graphite-925-a48);

  /* --- Текст --- */
  --color-text:   var(--graphite-925);
  --color-text-2: var(--graphite-600);
  --color-text-3: var(--graphite-550);    /* мета: ціна/кг, відстань. Не на warning/danger-subtle */

  /* --- Межі --- */
  --color-border:        var(--graphite-100);   /* декоративна */
  --color-border-strong: var(--graphite-400);   /* поля, контроли: ≥3:1 */

  /* --- Акцент (єдиний) --- */
  --color-accent:        var(--lime-400);      /* лише заливка; як текст/межа на світлому — 1.3:1 */
  --color-accent-hover:  var(--lime-500);
  --color-accent-subtle: var(--lime-50);
  --color-accent-tint:   var(--lime-100);      /* декоративний фон hero; текст на ньому — text/text-2 */
  --color-on-accent:     var(--graphite-925);
  --color-accent-fg:     var(--graphite-925);  /* текст, іконки, межі з акцентним значенням */
  --color-ring:          var(--graphite-925);

  /* --- Економія (лише економія) --- */
  --color-savings:          var(--lime-700);
  --color-savings-strong:   var(--lime-800);
  --color-savings-subtle:   var(--lime-100);
  --color-savings-solid:    var(--graphite-925);  /* інверсна пігулка економії */
  --color-on-savings-solid: var(--lime-400);

  /* --- Попередження --- */
  --color-warning:        var(--amber-800);
  --color-warning-subtle: var(--amber-50);

  /* --- Небезпека --- */
  --color-danger:        var(--red-600);
  --color-danger-strong: var(--red-700);
  --color-danger-subtle: var(--red-50);

  /* --- Скелетон --- */
  --color-skeleton: var(--graphite-75);

  /* --- Шрифти --- */
  --font-display: var(--font-family-onest);
  --font-ui:      var(--font-family-inter);

  --weight-regular:  var(--font-weight-400);
  --weight-medium:   var(--font-weight-500);
  --weight-semibold: var(--font-weight-600);
  --weight-bold:     var(--font-weight-700);

  /* Текстові стилі: значення «size/line-height» для shorthand `font`.
     Використання: font: var(--weight-medium) var(--text-label) var(--font-ui); */
  --text-display:  var(--font-size-32)/var(--line-height-40);
  --text-h1:       var(--font-size-24)/var(--line-height-32);
  --text-h2:       var(--font-size-20)/var(--line-height-28);
  --text-price-lg: var(--font-size-28)/var(--line-height-32);
  --text-body-lg:  var(--font-size-18)/var(--line-height-28);
  --text-body:     var(--font-size-16)/var(--line-height-24);
  --text-label:    var(--font-size-14)/var(--line-height-20);
  --text-meta:     var(--font-size-13)/var(--line-height-18);
  --text-caption:  var(--font-size-12)/var(--line-height-16);

  /* --- Відступи --- */
  --space-2xs: var(--dim-0-5);  /*  2px: лише оптичні поправки */
  --space-xs:  var(--dim-1);    /*  4px */
  --space-sm:  var(--dim-2);    /*  8px */
  --space-ms:  var(--dim-3);    /* 12px: внутрішній відступ рядків і плашок */
  --space-md:  var(--dim-4);    /* 16px */
  --space-lg:  var(--dim-6);    /* 24px */
  --space-xl:  var(--dim-8);    /* 32px */
  --space-2xl: var(--dim-12);   /* 48px */
  --space-3xl: var(--dim-16);   /* 64px */
  --gutter:    var(--space-md); /* 32px від 1024px: див. media нижче */

  /* --- Розміри --- */
  --size-icon-sm:     var(--dim-4);   /* 16px */
  --size-icon-md:     var(--dim-5);   /* 20px */
  --size-icon-lg:     var(--dim-6);   /* 24px */
  --size-badge:       var(--dim-6);   /* 24px: висота бейджа */
  --size-chip:        var(--dim-10);  /* 40px: видима висота чипа */
  --size-touch:       var(--dim-11);  /* 44px: мінімальна зона натискання */
  --size-control:     var(--dim-12);  /* 48px: кнопки, поля */
  --size-touch-store: var(--dim-14);  /* 56px: режим «У магазині» */
  --size-mic-compact: var(--dim-18);  /* 72px */
  --size-mic:         var(--dim-24);  /* 96px */

  /* --- Радіуси --- */
  --radius-sm:   var(--round-6);
  --radius-md:   var(--round-10);
  --radius-lg:   var(--round-14);
  --radius-xl:   var(--round-20);
  --radius-full: var(--round-full);

  /* --- Тіні (плоско за замовчуванням) --- */
  --shadow-sm: var(--shadow-1);
  --shadow-md: var(--shadow-2);
  --shadow-lg: var(--shadow-3);
  --shadow-xl: var(--shadow-4);

  /* --- Рух --- */
  --dur-fast: var(--duration-120);
  --dur-base: var(--duration-200);
  --dur-slow: var(--duration-280);
  --ease-out: var(--easing-decelerate);
  --ease-in:  var(--easing-accelerate);

  /* --- Фокус --- */
  --focus-width:  var(--dim-0-5);
  --focus-offset: var(--dim-0-5);

  /* --- Шари --- */
  --z-base:    var(--layer-0);
  --z-sticky:  var(--layer-10);
  --z-sheet:   var(--layer-20);
  --z-popover: var(--layer-30);
  --z-modal:   var(--layer-40);
  --z-toast:   var(--layer-50);

  /* --- Стан --- */
  --opacity-disabled: var(--opacity-40);
}

@media (min-width: 1024px) {
  :root {
    --gutter: var(--space-xl);
    --text-display: var(--font-size-40)/var(--line-height-48);
  }
}

/* === SEMANTIC: DARK (готово, не в MVP) === */
[data-theme="dark"] {
  color-scheme: dark;

  --color-bg:         var(--graphite-950);
  --color-surface:    var(--graphite-900);
  --color-surface-2:  var(--graphite-850);
  --color-logo-plate: var(--graphite-0);

  --color-text:   var(--graphite-50);
  --color-text-2: var(--graphite-300);
  --color-text-3: var(--graphite-450);

  --color-border:        var(--graphite-800);
  --color-border-strong: var(--graphite-500);

  --color-accent:        var(--lime-400);
  --color-accent-hover:  var(--lime-300);
  --color-accent-subtle: var(--lime-900);
  --color-accent-tint:   var(--lime-900);
  --color-on-accent:     var(--graphite-925);
  --color-accent-fg:     var(--graphite-50);
  --color-ring:          var(--lime-400);

  --color-savings:          var(--lime-400);
  --color-savings-strong:   var(--lime-300);
  --color-savings-subtle:   var(--lime-950);
  --color-savings-solid:    var(--lime-950);
  --color-on-savings-solid: var(--lime-400);

  --color-warning:        var(--amber-300);
  --color-warning-subtle: var(--amber-950);

  --color-danger:        var(--red-400);
  --color-danger-strong: var(--red-400);      /* у MASTER немає; див. розділ 6 */
  --color-danger-subtle: var(--red-950);

  --color-skeleton: var(--graphite-850);

  /* Тіні замінюються межею */
  --shadow-sm: 0 0 0 1px var(--color-border);
  --shadow-md: 0 0 0 1px var(--color-border);
  --shadow-lg: 0 0 0 1px var(--color-border);
  --shadow-xl: 0 0 0 1px var(--color-border);
}

/* === SEMANTIC: REDUCED MOTION === */
@media (prefers-reduced-motion: reduce) {
  :root {
    --dur-fast: var(--duration-0);
    --dur-base: var(--duration-0);
    --dur-slow: var(--duration-0);
  }
}

/* === Утиліта для чисел === */
.num {
  font-family: var(--font-ui);
  font-variant-numeric: tabular-nums;
}
```

### Обмеження використання кольорів

| Токен | Дозволено | Заборонено |
|---|---|---|
| `--color-savings*` | «−75 ₴», «Економія 240 ₴», найдешевший варіант, найнижча ціна за кг. Завжди зі знаком «−» або словом «найдешевше» | CTA, успіх, «склад перевірено», чекбокси, вибраний стан, посилання |
| `--color-accent` (лайм) | Заливка: головна дія, вибраний стан, активний пін, мікрофон, виділення в заголовку | Текст, іконки чи межі на світлих поверхнях (1.3:1). Позначення економії |
| `--color-accent-fg` | Текст, іконки й межі з акцентним значенням: ghost-кнопки, «Замінити», вибраний чип, «Визначити автоматично» | — |
| `--color-warning*` | Аналог, нестандартна вага, «може містити сліди» | Помилки |
| `--color-danger*` | Бюджет перевищено, помилка, алерген у складі, «немає в жодній мережі» | Від'ємна різниця ціни (вона `savings`) |
| `--color-text-3` | Мета на `bg`, `surface`, `surface-2` | Текст на `warning-subtle` і `danger-subtle` (у темній темі 4.09:1). Там — `--color-text-2` |

---

## 4. Component tokens і специфікації

Усі блоки «Component tokens» нижче разом складають `components.css`.

Спільні правила для всіх компонентів:

- Будь-яке число (ціна, вага, відстань, час, кількість) — `--font-ui` + `tabular-nums` (клас `.num`).
- Фокус: `outline: var(--focus-width) solid var(--color-ring); outline-offset: var(--focus-offset);` лише на `:focus-visible`.
- Hover не зсуває макет: без `translate`, `scale`, без зміни товщини межі. Вибраний стан додає другу лінію через `box-shadow`, а не через `border-width`.
- Іконки Lucide, stroke 1.75, розміри 16 / 20 / 24. Декоративні — `aria-hidden="true"`.
- Усі клікабельні елементи мають `cursor: pointer`.
- Вкладені інтерактивні елементи заборонено. Якщо картка або рядок цілком клікабельні, дії винесено за їхні межі.

### 4.0 Button (базова)

Потрібна для дій усередині компонентів: «Замінити», «Спробувати знову», «Прибрати». Повна специфікація — у MASTER, розділ Buttons.

```css
/* === COMPONENT: Button === */
:root {
  --button-height:       var(--size-control);
  --button-height-sm:    var(--size-touch);
  --button-padding-x:    var(--space-lg);
  --button-padding-x-sm: var(--space-ms);
  --button-radius:       var(--radius-md);
  --button-gap:          var(--space-sm);
  --button-icon-size:    var(--size-icon-md);

  --button-primary-bg:       var(--color-accent);
  --button-primary-bg-hover: var(--color-accent-hover);
  --button-primary-fg:       var(--color-on-accent);

  --button-secondary-bg:       var(--color-surface);
  --button-secondary-bg-hover: var(--color-surface-2);
  --button-secondary-fg:       var(--color-text);
  --button-secondary-border:   var(--color-border-strong);

  --button-ghost-bg:       transparent;
  --button-ghost-bg-hover: var(--color-accent-subtle);
  --button-ghost-fg:       var(--color-accent-fg);
  --button-ghost-fg-hover: var(--color-accent-fg);

  --button-transition: background-color var(--dur-fast) var(--ease-out);
}
```

| Розмір | Висота | Padding X | Шрифт | Де |
|---|---|---|---|---|
| default | 48px | 24px | `--text-label` 500 | Основні дії екрана |
| sm | 44px | 12px | `--text-label` 500 | Дії в рядках і плашках («Замінити», «Прибрати») |

---

### 4.1 VoiceButton — кнопка голосу

**Призначення.** Запускає голосове введення списку на екрані 1. Рівноправна з текстовим полем, а не головна.

#### Component tokens

```css
/* === COMPONENT: VoiceButton === */
:root {
  --voice-size:            var(--size-mic);
  --voice-size-compact:    var(--size-mic-compact);
  --voice-size-inline:     var(--dim-12);          /* 48px, RequestComposer на десктопі */
  --voice-icon-size-inline: var(--size-icon-md);  /* 20px */
  --voice-icon-size:       var(--dim-8);          /* 32px; у MASTER, але не в шкалі іконок */
  --voice-icon-size-compact: var(--size-icon-lg);
  --voice-radius:          var(--radius-full);

  /* idle */
  --voice-bg:        var(--color-accent);
  --voice-bg-hover:  var(--color-accent-hover);
  --voice-bg-active: var(--color-accent-hover);
  --voice-fg:        var(--color-on-accent);

  /* listening */
  --voice-bg-listening:   var(--color-accent-hover);
  --voice-ring-color:     var(--color-accent-fg);
  --voice-ring-width:     var(--dim-0-5);
  --voice-ring-gap:       var(--space-sm);        /* відстань кільця від кнопки */
  --voice-ring-scale-min: 1;
  --voice-ring-scale-max: 1.15;

  /* processing */
  --voice-bg-processing: var(--color-accent);

  /* error: blocked (мікрофон заборонено або відсутній) */
  --voice-bg-blocked:     var(--color-surface-2);
  --voice-fg-blocked:     var(--color-text-2);
  --voice-border-blocked: var(--color-border-strong);

  /* статус і помилки під кнопкою */
  --voice-status-font:  var(--text-label);
  --voice-status-fg:    var(--color-text-2);
  --voice-error-fg:     var(--color-danger);
  --voice-message-gap:  var(--space-ms);
  --voice-status-min-height: var(--dim-5);      /* 20px: рядок статусу не стрибає */
  --voice-message-max-width: var(--dim-70);     /* 280px */

  /* рівень гучності для prefers-reduced-motion */
  --voice-level-width:  var(--size-mic);
  --voice-level-height: var(--space-xs);
  --voice-level-track:  var(--color-surface-2);
  --voice-level-fill:   var(--color-accent-fg);

  --voice-shadow-compact: var(--shadow-md);       /* лише плаваючий компактний варіант */
  --voice-transition: background-color var(--dur-fast) var(--ease-out),
                      transform var(--dur-fast) var(--ease-out);
}
```

#### Анатомія

```
          ╭──────────────╮      ← кільце рівня гучності (лише listening)
          │   ╭──────╮   │
          │   │  🎙  │   │      ← коло 96px, іконка 32px
          │   ╰──────╯   │
          ╰──────────────╯
             Слухаю…           ← статус, aria-live="polite"
    ┌─────────────────────────┐
    │ ⓘ Не почув. Спробуйте…  │ ← повідомлення про помилку (лише error)
    └─────────────────────────┘
```

(Іконки на схемі умовні. У коді — Lucide.)

#### Варіанти

| Варіант | Розмір | Іконка | Де |
|---|---|---|---|
| `default` | 96px | 32px | Екран 1, мобільна адаптація |
| `inline` | 48px | 20px | Екран 1, десктоп: усередині RequestComposer, поруч із «Знайти кошик». Токен `--voice-size-inline` (= `--dim-12`) |
| `compact` | 72px | 24px | Екран 2 («Додати голосом»), плаваюча кнопка з `--voice-shadow-compact` |

#### Стани

| Стан | Фон | Іконка | Статус під кнопкою | ARIA | Курсор |
|---|---|---|---|---|---|
| idle | `--voice-bg` | `Mic` | — | `aria-label="Почати голосове введення"`, `aria-pressed="false"` | pointer |
| hover | `--voice-bg-hover` | `Mic` | — | — | pointer |
| active (натиснуто) | `--voice-bg-active` | `Mic` | — | — | pointer |
| focus-visible | як idle + фокус-кільце 2px, offset 2px | `Mic` | — | — | pointer |
| listening | `--voice-bg-listening` + кільце | `Square` (стоп) | «Слухаю…» | `aria-label="Зупинити запис"`, `aria-pressed="true"` | pointer |
| processing | `--voice-bg-processing` | `LoaderCircle`, обертання | «Розбираю запит…» | `aria-busy="true"`, `aria-disabled="true"` | progress |
| error · retry | `--voice-bg` | `Mic` | Помилка `--voice-error-fg` + `CircleAlert` | `aria-label="Спробувати голосове введення ще раз"` | pointer |
| error · blocked | `--voice-bg-blocked`, межа 1px `--voice-border-blocked` | `MicOff` | Помилка + пояснення | `aria-disabled="true"`, `aria-describedby` → повідомлення | not-allowed |
| unsupported | **не рендериться** | — | Підказка біля поля (див. нижче) | — | — |

Переходи: колір фону — `--dur-fast`. Поява статусу й помилки — `opacity` за `--dur-base`.

#### Тексти помилок

| Причина (`SpeechRecognitionErrorEvent.error`) | Стан | Текст |
|---|---|---|
| `no-speech`, порожній результат | error · retry | «Не почув. Спробуйте ще раз або введіть текстом» |
| `aborted` (користувач зупинив до мовлення) | idle | — (не помилка) |
| `network` | error · retry | «Немає з'єднання. Голос тимчасово недоступний — введіть текстом» |
| `not-allowed`, `service-not-allowed` | error · blocked | «Доступ до мікрофона заборонено. Введіть список текстом або дозвольте мікрофон у налаштуваннях браузера» |
| `audio-capture` | error · blocked | «Мікрофон не знайдено. Введіть список текстом» |
| Web Speech API недоступний | unsupported | Біля поля вводу, `--color-text-2`, без іконки помилки: «Браузер не підтримує голос. Введіть список текстом» |
| processing довше 10 с | error · retry | «Не вдалося розібрати запит. Спробуйте ще раз або введіть текстом» |

Unsupported — це деградація, а не помилка. Тому цей текст не червоний.

#### Поведінка

- Натискання в idle — старт запису. Натискання в listening — стоп і перехід у processing.
- `Esc` у listening — скасування без обробки, повернення в idle.
- Фокус залишається на кнопці в усіх станах.
- Розпізнаний текст з'являється наживо в окремому блоці під кнопкою (`--text-body-lg`, `--color-text`). Цей блок не входить у компонент.
- Кільце: `transform: scale()` від `--voice-ring-scale-min` до `--voice-ring-scale-max` пропорційно гучності (RMS з `AnalyserNode`, оновлення не частіше за кадр). Без нескінченного декоративного пульсу.
- Після помилки retry поле вводу не очищується, текст користувача зберігається.

#### Доступність

- Статус («Слухаю…», «Розбираю запит…») — в окремому елементі з `aria-live="polite"`.
- Помилки — `role="alert"`, текст + іконка `CircleAlert`, не лише колір.
- Зона натискання: компактний варіант 72px, обидва варіанти ≥ 44px.
- `prefers-reduced-motion: reduce`: кільце статичне (scale 1). Під кнопкою смужка рівня: ширина `--voice-level-width`, висота `--voice-level-height`, заповнення `--voice-level-fill` по `transform: scaleX(level)`. Спінер не обертається, замість нього статичний `LoaderCircle` + текст статусу.

#### Адаптивність

| Ширина | Розміщення |
|---|---|
| < 1024px | Кнопка по центру над полем вводу, статус під кнопкою |
| ≥ 1024px | Кнопка ліворуч від поля, статус під кнопкою, ширина колонки кнопки 160px |

---

### 4.2 StoreCard — картка магазину

**Призначення.** Показує один варіант кошика на екрані 3: «Найближчий», «Найвигідніший» або «Smart Split» (2 магазини одним маршрутом). Ця сама картка в компактному варіанті показує магазин у спливній підказці піна на карті.

#### Component tokens

```css
/* === COMPONENT: StoreCard === */
:root {
  --store-card-bg:         var(--color-surface);
  --store-card-bg-pressed: var(--color-surface-2);
  --store-card-border:        var(--color-border);
  --store-card-border-hover:  var(--color-border-strong);
  --store-card-border-selected: var(--color-accent-fg);
  --store-card-shadow-selected: 0 0 0 1px var(--color-accent-fg), var(--shadow-sm);
  --store-card-radius:     var(--radius-lg);
  --store-card-padding:    var(--space-md);
  --store-card-gap:        var(--space-sm);
  --store-card-width-mobile: var(--dim-70);       /* 280px у горизонтальному snap-скролі */
  --store-card-min-height: var(--dim-42);         /* 168px: фіксована висота скелетона (CLS) */

  --store-card-title-font:  var(--text-h2);       /* Onest 600 */
  --store-card-title-fg:    var(--color-text);
  --store-card-total-font:  var(--text-price-lg); /* Inter 600 tnum */
  --store-card-total-fg:    var(--color-text);
  --store-card-meta-font:   var(--text-meta);
  --store-card-meta-fg:     var(--color-text-3);
  --store-card-chain-font:  var(--text-label);
  --store-card-chain-fg:    var(--color-text);

  /* рядок компромісу */
  --store-card-tradeoff-font:        var(--text-label);
  --store-card-tradeoff-savings-fg:  var(--color-savings);
  --store-card-tradeoff-fg:          var(--color-text-2);

  /* логотип мережі */
  --store-logo-size:   var(--size-icon-lg);       /* 24px */
  --store-logo-bg:     var(--color-logo-plate);
  --store-logo-border: var(--color-border);
  --store-logo-radius: var(--radius-sm);
  --store-logo-fallback-bg: var(--color-surface-2);
  --store-logo-fallback-fg: var(--color-text-2);

  --store-card-transition: border-color var(--dur-fast) var(--ease-out),
                           box-shadow var(--dur-fast) var(--ease-out),
                           background-color var(--dur-fast) var(--ease-out);
}
```

#### Анатомія (`option`)

```
┌───────────────────────────────────────────────┐
│ Найвигідніший                [↘ −240 ₴ до інших] │ ← назва варіанту (h2) + Savings-бейдж
│ [лого] АТБ · вул. Січових Стрільців, 12         │ ← логотип 24px, мережа, адреса (meta)
│                                                 │
│ 1 249,90 ₴                                      │ ← сума кошика, price-lg
│ −75 ₴ за +450 м                                 │ ← рядок компромісу
│ 650 м · 8 хв пішки  ·  13 з 13 товарів           │ ← meta
└───────────────────────────────────────────────┘
```

**Smart Split** замінює рядок мережі двома рядками з підсумком кожного магазину:

```
│ [лого] АТБ         7 товарів        612,40 ₴   │
│ [лого] Сільпо      6 товарів        598,10 ₴   │
│ 1 210,50 ₴                                      │
│ −115 ₴ за +1 магазин                             │
│ Маршрут 1,1 км · 15 хв пішки                     │
```

#### Варіанти

| Варіант | Вміст | Де |
|---|---|---|
| `option` | Повний вміст вище | Екран 3: sheet (мобільний), ліва колонка (десктоп) |
| `split` | `option` + два рядки магазинів | Екран 3, варіант Smart Split |
| `compact` | Логотип + мережа + адреса + сума + відстань, без назви варіанту й компромісу | Спливна підказка піна на карті, мінімальна висота 72px |

#### Стани

| Стан | Межа | Фон | Тінь | Інше |
|---|---|---|---|---|
| default | 1px `--store-card-border` | `--store-card-bg` | — | — |
| hover (pointer) | 1px `--store-card-border-hover` | `--store-card-bg` | — | — |
| pressed | 1px `--store-card-border-hover` | `--store-card-bg-pressed` | — | — |
| selected | 1px `--store-card-border-selected` | `--store-card-bg` | `--store-card-shadow-selected` | `aria-checked="true"`; пін на карті — accent |
| focus-visible | як поточний стан + фокус-кільце | — | — | — |
| partial (бракує товарів) | як default | — | — | Warning-бейдж «Немає 1 товару»; під сумою meta «Сума без 1 товару» |
| loading | — | `--color-skeleton` | — | Скелетон висотою `--store-card-min-height`, без тексту |

Selected виглядає як межа 2px, але ширина межі не змінюється: друга лінія — `box-shadow`. Тому вміст не зсувається.

#### Рядок компромісу

| Ситуація | Текст | Колір суми | Колір решти |
|---|---|---|---|
| Дешевше й далі | «−75 ₴ за +450 м» | `--store-card-tradeoff-savings-fg` | `--store-card-tradeoff-fg` |
| Дорожче й ближче | «+40 ₴, але на 600 м ближче» | `--store-card-tradeoff-fg` | `--store-card-tradeoff-fg` |
| Найдешевший і найближчий | «Найдешевший і найближчий» | — | `--store-card-tradeoff-fg` |
| Smart Split | «−115 ₴ за +1 магазин» | `--store-card-tradeoff-savings-fg` | `--store-card-tradeoff-fg` |

Різниця завжди рахується від варіанту «Найближчий». Знак — справжній мінус U+2212.

#### Правила вмісту

- Логотип мережі — лише з даних, на білій плашці `--store-logo-bg` з межею, щоб логотип із прозорим фоном не зливався з темною темою. Колір мережі ніде не використовується: ні в межі, ні у фоні, ні в тексті.
- Немає логотипа: монограма з першої літери мережі, `--store-logo-fallback-bg` / `--store-logo-fallback-fg`.
- Назва мережі й адреса — `--color-text` / `--color-text-3`. Адреса обрізається в один рядок з `…`.
- Сума — за весь кошик. Над картками завжди рядок «Порівнюємо весь кошик, а не окремі знижки» (не частина картки).
- Savings-бейдж «−240 ₴ до інших» — лише на найдешевшому варіанті. Не більше одного на екрані.
- Відстань: `450 м · 6 хв пішки`; від 1 000 м — `1,2 км`.

#### Поведінка

- Картки утворюють `role="radiogroup"` з `aria-label="Варіанти кошика"`. Кожна картка — `role="radio"`.
- Стрілки ↑↓ (вертикальний стек) і ←→ (горизонтальний скрол) змінюють вибір. `Space` вибирає.
- Вибір картки підсвічує пін на карті й центрує карту на маршруті. Вибір піна на карті вибирає картку.
- Дії «Маршрут» і «Деталі кошика» — **поза карткою**, у нижній панелі sheet для вибраного варіанту. Вкладених кнопок у картці немає.

#### Адаптивність

| Ширина | Розміщення |
|---|---|
| < 768px, sheet peek | Лише вибрана картка (за замовчуванням «Найвигідніший») |
| < 768px, sheet half | Горизонтальний snap-скрол, ширина картки `--store-card-width-mobile` |
| < 768px, sheet full | Вертикальний стек, ширина 100% |
| ≥ 1024px | Вертикальний стек у лівій колонці 400–480px |

---

### 4.3 BasketRow — рядок кошика

**Призначення.** Одна позиція кошика на екрані 4: що купуємо, скільки коштує пачка і кілограм, чи це аналог, чи пройшов склад фільтр.

#### Component tokens

```css
/* === COMPONENT: BasketRow === */
:root {
  --basket-row-bg:         var(--color-surface);
  --basket-row-divider:    var(--color-border);
  --basket-row-padding-y:  var(--space-ms);
  --basket-row-padding-x:  var(--space-md);
  --basket-row-gap:        var(--space-ms);
  --basket-row-min-height: var(--dim-20);          /* 80px: фото 56 + 2 × 12 */

  --basket-photo-size:   var(--size-touch-store);  /* 56px */
  --basket-photo-bg:     var(--color-surface-2);
  --basket-photo-radius: var(--radius-md);
  --basket-photo-placeholder-fg: var(--color-text-3);

  --basket-name-font:  var(--text-body);
  --basket-name-fg:    var(--color-text);
  --basket-brand-font: var(--text-meta);
  --basket-brand-fg:   var(--color-text-3);
  --basket-badges-gap: var(--space-sm);

  --basket-price-font:  var(--text-label);         /* Inter 600 tnum */
  --basket-price-fg:    var(--color-text);
  --basket-qty-font:    var(--text-meta);
  --basket-qty-fg:      var(--color-text-3);

  /* стан not-found */
  --basket-missing-price-fg: var(--color-text-3);

  /* таблиця на десктопі */
  --basket-table-row-height:  var(--dim-16);       /* 64px */
  --basket-table-head-font:   var(--text-meta);
  --basket-table-head-fg:     var(--color-text-2);
  --basket-table-head-bg:     var(--color-bg);
  --basket-table-compare-fg:  var(--color-text-2);
}
```

#### Анатомія (мобільний)

```
┌──────────────────────────────────────────────────────┐
│ ┌────┐  Молоко 2,5 %                        2 × 48,90 ₴ │ ← назва (body) · кількість × ціна (meta)
│ │фото│  Галичина · 870 г                       97,80 ₴ │ ← бренд + вага (meta) · сума позиції (label 600)
│ │56px│  [Без лактози] [870 г]           112,40 ₴/кг │ ← бейджі · UnitPrice inline
│ └────┘                                               │
│ ┌──────────────────────────────────────────────────┐ │
│ │ AnalogNotice (лише варіант analog)               │ │
│ └──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

- Права колонка вирівняна праворуч, `tabular-nums`. Ширина правої колонки — за вмістом, мінімум 96px.
- Кількість 1: рядок «2 × 48,90 ₴» не показується, сума позиції = ціна пачки.
- Назва — до 2 рядків, далі `…`. Повна назва — у деталях товару.
- Фото: `aspect-ratio: 1`, `object-fit: contain`, `loading="lazy"`, `alt=""` (назва вже є текстом). Немає фото — іконка `ImageOff` 24px, `--basket-photo-placeholder-fg`.

#### Варіанти

| Варіант | Відмінність |
|---|---|
| `default` | Як на схемі |
| `analog` | Під рядком — `AnalogNotice` (4.5) на всю ширину контенту; у рядку бейджів — нічого додатково |
| `not-found` | Фото → `PackageX`; ціна «—» `--basket-missing-price-fg`; бейдж Danger «Немає в жодній мережі»; дія ghost-sm «Прибрати». Сума кошика рахується без цієї позиції, і це сказано над списком |
| `budget-trim` | Стан «Бюджет перевищено»: праворуч дія ghost-sm «Прибрати» з сумою позиції «−97,80 ₴». Сума **не оливкова** (`--color-text-2`): це зменшення витрат, а не економія на ціні |

#### Стани

| Стан | Вигляд |
|---|---|
| default | Фон `--basket-row-bg`, межа знизу 1px `--basket-row-divider` (в останнього рядка відділу немає) |
| focus-visible (назва) | Фокус-кільце на кнопці-назві |
| updating (після «Замінити») | Права колонка → скелетон 96×40px, `aria-busy="true"` на рядку |
| removed | Рядок зникає (`opacity` за `--dur-base`); toast «Прибрано: Молоко 2,5 %» з дією «Повернути» 5 с |

#### Поведінка

- Рядок цілком **не** клікабельний. Назва — кнопка, що відкриває деталі товару (склад, джерело даних, інші пачки). Бейджі — окремі кнопки. Так немає вкладених інтерактивних елементів.
- Зміна кількості — у деталях товару, не в рядку.

#### Десктоп (≥ 1024px): таблиця

| Колонка | Вирівнювання | Вміст |
|---|---|---|
| Товар | ліворуч | Фото 40px, назва, бренд, бейджі |
| Пачка | праворуч | `48,90 ₴` + вага; нестандартна вага — Warning-бейдж |
| За кг | праворуч | `UnitPrice` inline |
| Варіант Б | праворуч | Ціна того самого або аналогічного товару, `--basket-table-compare-fg` |
| Варіант В | праворуч | Те саме |

- `<table>` з `<th scope="col">`, заголовок липкий (`position: sticky; z-index: var(--z-sticky)`), фон `--basket-table-head-bg`.
- Висота рядка `--basket-table-row-height`. AnalogNotice — окремий рядок `<tr>` з `colspan` під позицією.
- Найнижча ціна в рядку порівняння: `--weight-semibold` + прихований текст «найдешевше». Без оливкового в клітинках таблиці, щоб не перевантажувати.

---

### 4.4 UnitPrice — бейдж «ціна за 1 кг»

**Призначення.** Нормалізована ціна (за кг, л або шт) поруч із ціною пачки. Головний захист від шрінкфляції.

#### Component tokens

```css
/* === COMPONENT: UnitPrice === */
:root {
  /* inline (за замовчуванням) */
  --unit-price-font: var(--text-meta);
  --unit-price-fg:   var(--color-text-3);

  /* badge */
  --unit-price-badge-height:  var(--size-badge);
  --unit-price-badge-padding-x: var(--space-sm);
  --unit-price-badge-gap:     var(--space-xs);
  --unit-price-badge-radius:  var(--radius-sm);
  --unit-price-badge-bg:      var(--color-surface-2);
  --unit-price-badge-fg:      var(--color-text-2);
  --unit-price-badge-weight:  var(--weight-medium);

  /* lowest — найнижча ціна за кг серед порівнюваних */
  --unit-price-lowest-bg: var(--color-savings-subtle);
  --unit-price-lowest-fg: var(--color-savings-strong);
  --unit-price-icon-size: var(--size-icon-sm);

  /* нестандартна вага поруч */
  --unit-price-weight-bg: var(--color-warning-subtle);
  --unit-price-weight-fg: var(--color-warning);
}
```

#### Варіанти

| Варіант | Вигляд | Де |
|---|---|---|
| `inline` (default) | Текст `112,40 ₴/кг`, `--unit-price-font`, `--unit-price-fg` | Під або поруч із кожною ціною пачки: BasketRow, деталі товару, таблиця |
| `badge` | Пігулка 24px, `--unit-price-badge-bg` / `--unit-price-badge-fg` | Де ціна за кг — предмет порівняння: список інших пачок товару, вибір аналога |
| `lowest` | Пігулка 24px, `--unit-price-lowest-*`, іконка `TrendingDown` 16px, текст «112,40 ₴/кг · найдешевше» | Лише одна позиція в списку інших пачок або аналогів |
| `unknown` | Текст «— ₴/кг», `--unit-price-fg` | Немає ваги в даних. Не приховувати |

Нестандартна вага йде окремим Warning-бейджем **поруч**, а не всередині UnitPrice:

```
48,90 ₴                    ← PriceBlock: ціна пачки
112,40 ₴/кг  [870 г]        ← UnitPrice inline + бейдж ваги (warning)
```

#### Правила розрахунку і формату

| Тип товару | Одиниця | Приклад |
|---|---|---|
| Вагові та фасовані (г, кг) | ₴/кг | `112,40 ₴/кг` |
| Рідини (мл, л) | ₴/л | `48,90 ₴/л` |
| Штучні (яйця, хліб без ваги) | ₴/шт | `6,20 ₴/шт` |

- Ціна = ціна пачки ÷ нетто в кг (л, шт). Округлення до 0,01 за правилом half-up.
- Завжди за 1 кг, навіть для пачок по 50 г. Не «за 100 г»: інакше ціни в колонці не порівнюються.
- Формат: розділювач тисяч U+202F, десяткова кома, нерозривний пробіл перед `₴`, скісна риска без пробілів: `1 249,90 ₴/кг`.
- Стандартні ваги: 100, 200, 250, 500 г, 1 кг; 0,5 л, 1 л. Інша вага → Warning-бейдж ваги.

#### Доступність

- Скорочення «₴/кг» читачі екрана читають погано. Видимий текст — `112,40 ₴/кг`, для читача — `<span class="sr-only">112,40 гривні за кілограм</span>`, видимий текст з `aria-hidden="true"`.
- `lowest` має текст «найдешевше», а не лише оливковий колір.
- Бейдж не інтерактивний, тому зона натискання 44px не потрібна.

---

### 4.5 AnalogNotice — плашка аналога

**Призначення.** Пояснює, що Sayvy сам підставив аналог замість товару, якого немає, і дає змогу замінити його.

#### Component tokens

```css
/* === COMPONENT: AnalogNotice === */
:root {
  --analog-bg:        var(--color-warning-subtle);
  --analog-radius:    var(--radius-md);
  --analog-padding:   var(--space-ms);
  --analog-gap:       var(--space-sm);
  --analog-icon-size: var(--size-icon-sm);
  --analog-icon-fg:   var(--color-warning);

  --analog-title-font: var(--text-label);
  --analog-title-fg:   var(--color-warning);
  --analog-body-font:  var(--text-label);
  --analog-body-fg:    var(--color-text);
  --analog-meta-font:  var(--text-meta);
  --analog-meta-fg:    var(--color-text-2);      /* не text-3: у темній темі 4.09:1 */

  --analog-diff-fg:         var(--color-text-2);
  --analog-diff-savings-fg: var(--color-savings-strong); /* savings на цьому фоні = 4.57:1, strong = 6.50:1 */

  /* компактний бейдж «аналог» */
  --analog-badge-height:    var(--size-badge);
  --analog-badge-padding-x: var(--space-sm);
  --analog-badge-radius:    var(--radius-sm);
  --analog-badge-font:      var(--text-caption);
  --analog-badge-bg:        var(--color-warning-subtle);
  --analog-badge-fg:        var(--color-warning);
}
```

#### Анатомія (`inline`)

```
┌────────────────────────────────────────────────────────┐
│ ⇄  Аналог · замість «Молоко Ферма 2,5 %, 900 г»          │ ← іконка Replace + title (warning) + body (text)
│    Немає в Сільпо на Хрещатику. Та сама жирність,        │ ← причина (meta, text-2)
│    об'єм 870 г.                                          │
│    +4,20 ₴ до оригіналу                     [ Замінити ] │ ← різниця (meta) + ghost-sm кнопка
└────────────────────────────────────────────────────────┘
```

#### Варіанти

| Варіант | Вміст | Де |
|---|---|---|
| `inline` | Повна плашка | BasketRow (4.3), деталі товару |
| `badge` | Іконка `Replace` 16px + «аналог», `--analog-badge-*` | OptionCard, режим «У магазині», таблиця на десктопі. Натискання — відкриває деталі товару з повною плашкою |

#### Різниця в ціні

| Ситуація | Текст | Колір |
|---|---|---|
| Аналог дорожчий | «+4,20 ₴ до оригіналу» | `--analog-diff-fg` |
| Аналог дешевший | «−3,10 ₴ до оригіналу» | `--analog-diff-savings-fg` |
| Ціни оригіналу немає | рядок не показується | — |

Різниця рахується за 1 кг, якщо ваги пачок різні, і тоді так і написано: «+4,20 ₴/кг до оригіналу».

#### Стани

| Стан | Вигляд |
|---|---|
| default | Як на схемі |
| button hover / focus | Кнопка «Замінити»: фон `--button-ghost-bg-hover`, фокус-кільце |
| replacing | Кнопка `aria-busy="true"`, спінер замість іконки, текст «Замінити» залишається |
| replaced | Плашка зникає (`opacity`, `--dur-base`). Товар, вибраний користувачем, більше не позначається як аналог |

#### Поведінка

- «Замінити» відкриває вибір: bottom sheet на мобільному, поповер 400px на десктопі. Список альтернатив відсортовано за ціною за кг, у кожної — `UnitPrice badge`, у найдешевшої — `UnitPrice lowest`.
- Кнопки «Залишити» немає: якщо користувач нічого не робить, аналог залишається в кошику.
- Плашку не можна закрити хрестиком: інформація про підміну має залишатися видимою, поки товар у кошику.

#### Доступність

- Контейнер — звичайний блок, не `role="alert"`: плашка з'являється разом зі сторінкою, а не раптово.
- Слово «Аналог» є текстом, не лише кольором та іконкою. Іконка `aria-hidden="true"`.
- Кнопка: `aria-label="Замінити аналог для «Молоко Ферма 2,5 %, 900 г»"`, видимий текст «Замінити». Висота 44px.
- Контраст: `--color-accent-fg` на `--color-warning-subtle` = 16.14:1 (світла), 12.57:1 (темна).

---

### 4.6 AllergenBadge — бейдж алергену

**Призначення.** Показує результат перевірки складу щодо обмежень користувача (алергени, дієта) і пояснює натисканням, чому товар пройшов або не пройшов фільтр.

#### Component tokens

```css
/* === COMPONENT: AllergenBadge === */
:root {
  --allergen-height:     var(--size-badge);
  --allergen-hit-area:   var(--size-touch);    /* зона натискання через ::before */
  --allergen-padding-x:  var(--space-sm);
  --allergen-gap:        var(--space-xs);
  --allergen-radius:     var(--radius-sm);
  --allergen-font:       var(--text-caption);  /* Inter 500 */
  --allergen-icon-size:  var(--size-icon-sm);

  /* verified — склад перевірено */
  --allergen-verified-bg: var(--color-surface-2);
  --allergen-verified-fg: var(--color-text-2);

  /* unknown — склад невідомий */
  --allergen-unknown-bg:     var(--color-surface);
  --allergen-unknown-fg:     var(--color-text-2);
  --allergen-unknown-border: var(--color-border-strong);

  /* traces — може містити сліди */
  --allergen-traces-bg: var(--color-warning-subtle);
  --allergen-traces-fg: var(--color-warning);

  /* contains — містить алерген користувача */
  --allergen-contains-bg: var(--color-danger-subtle);
  --allergen-contains-fg: var(--color-danger-strong);

  --allergen-hover-overlay: var(--color-border);  /* межа 1px на hover */

  /* деталі */
  --allergen-details-bg:      var(--color-surface);
  --allergen-details-shadow:  var(--shadow-md);
  --allergen-details-radius:  var(--radius-md);
  --allergen-details-padding: var(--space-md);
  --allergen-details-width:   var(--dim-80);    /* 320px, поповер на десктопі */
  --allergen-details-font:    var(--text-label);
  --allergen-details-meta-fg: var(--color-text-2);
}
```

#### Варіанти

| Варіант | Фон / текст | Іконка | Приклад | Коли |
|---|---|---|---|---|
| `verified` | surface-2 / text-2 | `ShieldCheck` | «Без лактози» | Склад перевірено, обмеження виконано |
| `unknown` | surface / text-2, межа 1px dashed border-strong | `CircleHelp` | «Склад не вказано» | Немає складу в даних, а обмеження активне |
| `traces` | warning-subtle / warning | `TriangleAlert` | «Може містити горіхи» | Виробник пише «може містити сліди» |
| `contains` | danger-subtle / danger-strong | `CircleAlert` | «Містить глютен» | Алерген користувача у складі. Можливо лише для товару, доданого вручну |

**`verified` не оливковий і не лаймовий.** Оливковий — лише економія, лайм — лише дія (MASTER, правила 1–2).

#### Анатомія

```
 ╭─────────────────╮
 │ ⛉ Без лактози   │   ← висота 24px, іконка 16px, текст caption 500
 ╰─────────────────╯
 ┊  зона натискання 44px по висоті (::before, inset −10px 0)  ┊
```

#### Стани

| Стан | Вигляд |
|---|---|
| default | Фон і текст за варіантом |
| hover (pointer) | Додатково межа 1px `--allergen-hover-overlay` (через `box-shadow: inset`, без зсуву) |
| focus-visible | Фокус-кільце 2px, offset 2px |
| expanded | `aria-expanded="true"`, відкрито деталі |

#### Деталі (натисканням, не hover)

Мобільний — bottom sheet; десктоп — поповер `--allergen-details-width`.

```
Склад перевірено: без лактози
У складі немає: молоко, лактоза, вершки, сироватка, казеїн.
Джерело: склад з етикетки, дані мережі · оновлено 18.11.2026
```

- Перший рядок — повна назва перевірки (`--allergen-details-font`, `--color-text`).
- Другий — **причина**, чому товар пройшов або не пройшов фільтр.
- Третій — джерело й дата (`--allergen-details-meta-fg`, дата `tabular-nums`).
- Для `unknown`: «Склад не вказано в даних мережі. Перевірте етикетку в магазині».

#### Правила вмісту

- Видимий текст — коротка форма («Без лактози»). Повна форма («Склад перевірено: без лактози») — у деталях і в `aria-label`.
- У рядку кошика видно не більше 2 бейджів. Решта — кнопка «+2» того самого розміру й стилю `verified`, відкриває деталі товару.
- Порядок: `contains` → `traces` → `unknown` → `verified`.
- Словник алергенів — 14 алергенів ЄС українською (глютен, ракоподібні, яйця, риба, арахіс, соя, молоко, горіхи, селера, гірчиця, кунжут, сульфіти, люпин, молюски) + лактоза. Дієти (веганське, без цукру) — той самий компонент, варіант `verified`.

#### Доступність

- Бейдж — `<button>` з `aria-expanded` і `aria-controls`. `aria-label="Склад перевірено: без лактози. Показати пояснення"`.
- `Esc` закриває деталі й повертає фокус на бейдж.
- Між сусідніми бейджами 8px. Зона натискання розширюється лише по вертикалі, тож зони сусідніх бейджів не перекриваються.

---

### 4.7 CitySelect — вибір міста

**Призначення.** Задає місто, у якому шукаємо магазини. Головний шлях без геолокації (онбординг, відмова в дозволі) і перемикач міста в шапці.

#### Component tokens

```css
/* === COMPONENT: CitySelect === */
:root {
  /* поле */
  --city-label-font:  var(--text-label);
  --city-label-fg:    var(--color-text);
  --city-field-height:   var(--size-control);
  --city-field-padding-x: var(--space-ms);
  --city-field-gap:      var(--space-sm);
  --city-field-radius:   var(--radius-md);
  --city-field-bg:       var(--color-surface);
  --city-field-border:   var(--color-border-strong);
  --city-field-border-hover: var(--color-text-2);
  --city-field-border-open:  var(--color-accent-fg);
  --city-field-border-invalid: var(--color-danger);
  --city-field-font:     var(--text-body);       /* 16px — без зуму в iOS */
  --city-field-fg:       var(--color-text);
  --city-placeholder-fg: var(--color-text-3);
  --city-icon-size:      var(--size-icon-md);
  --city-icon-fg:        var(--color-text-2);

  /* компактний тригер у шапці */
  --city-trigger-height: var(--size-touch);
  --city-trigger-font:   var(--text-label);
  --city-trigger-bg-hover: var(--color-surface-2);

  /* список */
  --city-list-bg:      var(--color-surface);
  --city-list-border:  var(--color-border);
  --city-list-radius:  var(--radius-md);
  --city-list-shadow:  var(--shadow-md);
  --city-list-max-height: var(--dim-80);         /* 320px ≈ 6,5 рядка */
  --city-list-offset:  var(--space-xs);
  --city-list-z:       var(--z-popover);
  --city-panel-width:  var(--dim-80);           /* 320px: випадна панель compact ≥ 768px */

  --city-option-height:    var(--size-control);  /* 48px */
  --city-option-padding-x: var(--space-ms);
  --city-option-font:      var(--text-body);
  --city-option-meta-font: var(--text-meta);
  --city-option-meta-fg:   var(--color-text-3);
  --city-option-bg-active: var(--color-surface-2);       /* aria-activedescendant */
  --city-option-bg-selected: var(--color-accent-subtle);
  --city-option-fg-selected: var(--color-accent-fg);
  --city-option-locate-fg:   var(--color-accent-fg);

  --city-message-font: var(--text-meta);
  --city-hint-fg:      var(--color-text-2);
  --city-error-fg:     var(--color-danger);

  --city-chevron-transition: transform var(--dur-base) var(--ease-out);
}
```

#### Анатомія (`field`)

```
Місто                                         ← видимий label
┌───────────────────────────────────────────┐
│ ⌖  Київ                                 ⌄ │ ← MapPin · значення · ChevronDown
└───────────────────────────────────────────┘
┌───────────────────────────────────────────┐
│ ◎  Визначити автоматично                   │ ← LocateFixed, accent (лише якщо геолокація доступна)
├───────────────────────────────────────────┤
│ ✓  Київ            Київська обл.   6 мереж │ ← вибраний: accent-subtle + Check
│    Львів           Львівська обл.  5 мереж │
│    Одеса           Одеська обл.    5 мереж │
└───────────────────────────────────────────┘
Підказка або помилка                          ← meta
```

#### Варіанти

| Варіант | Вигляд | Де |
|---|---|---|
| `field` | Поле з label, висота 48px | Онбординг (крок геолокації після відмови), екран 3 «Немає магазинів поруч» |
| `compact` | Тригер у шапці: `MapPin` + «Київ» + `ChevronDown`, висота 44px, без рамки | Шапка екранів 1–3 |

#### Стани

| Стан | Межа | Інше |
|---|---|---|
| empty | `--city-field-border` | Placeholder «Почніть вводити назву», `--city-placeholder-fg` |
| hover | `--city-field-border-hover` | — |
| focus-visible | `--city-field-border-open` + фокус-кільце | — |
| open | `--city-field-border-open` | Список під полем, `ChevronDown` повернуто на 180° |
| filtering | `--city-field-border-open` | Список фільтрується на кожен символ |
| no-results | `--city-field-border-open` | У списку: «Поки не працюємо в місті „Ужгород“» + «Доступні: Київ, Львів, Одеса, Дніпро, Харків» (`--city-hint-fg`) |
| filled | `--city-field-border` | Значення `--city-field-fg` |
| detecting | `--city-field-border` | Іконка → `LoaderCircle`, текст «Визначаю місто…», `aria-busy="true"` |
| detect-failed | `--city-field-border` | Під полем, `--city-hint-fg`: «Не вдалося визначити місто. Оберіть зі списку». Це деградація, не помилка |
| invalid | `--city-field-border-invalid` | Під полем, `--city-error-fg` + `CircleAlert`: «Оберіть місто, щоб знайти магазини поруч» |
| disabled | `--city-field-border`, `opacity: var(--opacity-disabled)` | `cursor: not-allowed` |

#### Поведінка

- Пошук без урахування регістру, апострофа (’ ' ʼ), префікса «м.» і латиниці: «kyiv», «kiev», «lviv» знаходять «Київ», «Львів».
- Список — лише міста, де Sayvy має дані цін. Біля кожного — кількість мереж.
- «Визначити автоматично» — перший пункт, лише якщо дозвіл на геолокацію не відхилено. Після відмови пункт не показується.
- Вибір міста закриває список і зберігає місто на пристрої (`localStorage`, обгорнуто в `try/catch`).
- Після вибору міста з'являється поле адреси (вулиця, будинок) для розрахунку відстані. Поле адреси — окремий компонент.

#### Клавіатура (ARIA combobox 1.2)

| Клавіша | Дія |
|---|---|
| ↓ / ↑ | Відкрити список; рухати активний пункт |
| `Enter` | Вибрати активний пункт |
| `Esc` | Закрити список; повторне `Esc` очищує введений текст |
| `Home` / `End` | Курсор у полі на початок / кінець |
| `Tab` | Закрити список без вибору |

- Поле: `role="combobox"`, `aria-expanded`, `aria-controls`, `aria-activedescendant`, `aria-autocomplete="list"`.
- Список: `role="listbox"`; пункт: `role="option"`, `aria-selected`.
- Кількість результатів оголошується через `aria-live="polite"`: «Знайдено 3 міста».

#### Адаптивність

| Ширина | Список |
|---|---|
| < 768px | Повноекранний sheet: поле пошуку зверху, список під ним, кнопка «Закрити» 44px. Висота `100dvh`, нижній відступ `env(safe-area-inset-bottom)` |
| ≥ 768px | Випадний список під полем, `--city-list-max-height`, `z-index: var(--city-list-z)` |

---

### 4.8 AppHeader і RequestHero — шапка й екран 1

**Призначення.** Токени шапки застосунку та головного екрана «Запит». Додано 2026-11-21 під час верстки екрана 1 за прототипом `design/mocks/sayvy-prototype.html` (01 · Запит).

#### Component tokens

```css
/* === COMPONENT: AppHeader === */
:root {
  --header-height:        var(--dim-16);          /* 64px, десктоп */
  --header-height-mobile: var(--dim-14);          /* 56px */
  --header-gap:           var(--space-lg);
  --logo-font:            var(--text-h2);         /* Onest 700 */
  --logo-dot-size:        var(--space-sm);
  --logo-dot-bg:          var(--color-accent);

  --steps-font:           var(--text-label);
  --steps-fg:             var(--color-text-3);
  --steps-separator-fg:   var(--color-border-strong);
  --steps-current-bg:     var(--color-accent);
  --steps-current-fg:     var(--color-on-accent);

  --free-pill-font:   var(--text-label);
  --free-pill-bg:     var(--color-surface);
  --free-pill-border: var(--color-border);
}

/* === COMPONENT: RequestHero === */
:root {
  --hero-bg:             var(--color-accent-tint);
  --hero-radius:         var(--radius-xl);
  --hero-radius-mobile:  var(--radius-lg);
  --hero-padding:        var(--space-3xl);
  --hero-padding-mobile: var(--space-lg) var(--space-md);
  --hero-gap:            var(--space-2xl);
  --hero-title-font:     var(--text-display);     /* 40/48 десктоп, 32/40 мобільний */
  --hero-sub-font:       var(--text-body-lg);
  --hero-sub-fg:         var(--color-text-2);
  --hero-highlight-bg:   var(--color-accent);     /* виділення в заголовку = дія, не економія */
  --hero-highlight-fg:   var(--color-on-accent);

  /* композер: поле + голос + «Знайти кошик» */
  --composer-min-height:   var(--dim-16);         /* 64px */
  --composer-max-height:   var(--dim-42);         /* 168px = 6 рядків по 28px */
  --composer-mobile-min-height: var(--dim-18);    /* 72px = 3 рядки по 24px */
  --composer-bg:           var(--color-surface);
  --composer-border:       var(--color-accent-fg);
  --composer-border-width: var(--dim-0-5);
  --composer-border-invalid: var(--color-danger);
  --composer-radius:       var(--radius-lg);
  --composer-shadow:       var(--shadow-md);
  --composer-font:         var(--text-body-lg);
  --composer-font-mobile:  var(--text-body);      /* 16px — без зуму в iOS */
  --composer-placeholder-fg: var(--color-text-3);
  --composer-error-fg:     var(--color-danger);
  --composer-hint-fg:      var(--color-text-2);

  /* чипи-приклади */
  --example-height:       var(--size-touch);
  --example-padding-x:    var(--space-ms);
  --example-bg:           var(--color-surface);
  --example-border:       var(--color-border-strong);
  --example-bg-hover:     var(--color-accent-subtle);
  --example-border-hover: var(--color-accent-fg);
  --example-icon-fg:      var(--color-text-2);

  /* приклад результату */
  --preview-bg:          var(--color-surface);
  --preview-radius:      var(--radius-lg);
  --preview-shadow:      var(--shadow-md);
  --preview-padding:     var(--space-lg);
  --preview-caption-fg:  var(--color-text-3);
  --preview-row-border:  var(--color-border);
  --preview-row-radius:  var(--radius-md);
  --preview-best-bg:     var(--color-accent);
  --preview-best-border: var(--color-accent-fg);
  --preview-best-fg:     var(--color-on-accent);
  --preview-meta-fg:     var(--color-text-2);
  --preview-sum-font:    var(--text-body-lg);

  /* нижня панель на мобільному */
  --bottombar-bg:     var(--color-surface);
  --bottombar-border: var(--color-border);
  --bottombar-height: calc(var(--size-control) + 2 * var(--space-ms));
}
```

#### Поведінка

- Шапка: логотип, кроки потоку (лише ≥ 1024px), CitySelect `compact`, лічильник безкоштовних кошиків (лише ≥ 768px).
- Композер ≥ 1024px: поле + VoiceButton `inline` + «Знайти кошик» в одному рядку. `Enter` надсилає, `Shift+Enter` — новий рядок.
- < 1024px: VoiceButton `default` (96px) над полем, «Знайти кошик» у нижній панелі, закріпленій знизу з safe-area.
- Порожній запит: помилка під полем «Введіть або скажіть, що купити», фокус у полі.
- Голос дописує розпізнаний текст у поле наживо, текст, введений до запису, зберігається.

---

### 4.9 BasketEditor — екран 2 «Я зрозумів так»

**Призначення.** Список товарів зі степпером, поле «Додати товар» з підказками й обмеження (бюджет, склад, відстань). Додано 2026-11-21 під час верстки екрана 2 за прототипом `design/mocks/sayvy-prototype.html` (02 · Я зрозумів так, `#s2d` і `#s2`). Значення взято з прототипу, лише semantic-токени.

#### Component tokens

```css
/* === COMPONENT: BasketEditor (екран 2) === */
:root {
  /* панелі «Продукти» й «Обмеження» на десктопі */
  --panel-bg:      var(--color-surface);
  --panel-border:  var(--color-border);
  --panel-radius:  var(--radius-lg);
  --panel-padding: var(--space-lg);
  --panel-list-min: var(--dim-100);              /* 400px */
  --panel-list-max: var(--dim-120);              /* 480px */
  --said-fg:       var(--color-text-2);
  --panel-loading-min-height: var(--dim-80);     /* 320px: стан «Розбираю запит…» */

  /* рядок товару (десктоп) */
  --prow-min-height: var(--dim-14);              /* 56px */
  --prow-border:     var(--color-border);
  --prow-meta-fg:    var(--color-text-2);

  /* степпер кількості */
  --stepper-size:     var(--size-touch);
  --stepper-border:   var(--color-border-strong);
  --stepper-radius:   var(--radius-md);
  --stepper-bg-hover: var(--color-surface-2);

  /* чип товару (мобільний) */
  --pchip-height:       var(--size-chip);
  --pchip-bg:           var(--color-surface-2);
  --pchip-radius:       var(--radius-md);
  --pchip-qty-fg:       var(--color-text-2);
  --pchip-editing-ring: var(--color-accent-fg);

  /* поле «Додати товар» і підказки */
  --add-height:          var(--size-control);
  --add-border:          var(--color-border-strong);
  --add-border-focus:    var(--color-accent-fg);
  --add-radius:          var(--radius-md);
  --add-placeholder-fg:  var(--color-text-3);
  --suggest-bg:          var(--color-surface);
  --suggest-border:      var(--color-border);
  --suggest-radius:      var(--radius-md);
  --suggest-shadow:      var(--shadow-lg);
  --suggest-active-bg:   var(--color-surface-2);
  --suggest-meta-fg:     var(--color-text-2);
  --suggest-max-height:  var(--dim-80);          /* 320px */

  /* групи обмежень */
  --fset-border: var(--color-border);
  --hint-fg:     var(--color-text-2);
  --hint-font:   var(--text-meta);

  /* вибір: пресети бюджету, сегменти відстані, режим */
  --choice-height:       var(--size-touch);
  --choice-radius:       var(--radius-full);
  --choice-bg:           var(--color-surface);
  --choice-border:       var(--color-border-strong);
  --choice-border-hover: var(--color-accent-fg);
  --choice-on-bg:        var(--color-accent);
  --choice-on-fg:        var(--color-on-accent);
  --choice-on-border:    var(--color-accent-fg);
  --seg-min-height:      var(--dim-14);
  --seg-radius:          var(--radius-md);
  --seg-sub-fg:          var(--color-text-2);
  --seg-item-min:        var(--dim-16);          /* 64px */

  /* поле суми бюджету */
  --money-width:  var(--dim-42);                 /* 168px */
  --money-border: var(--color-border-strong);

  /* чекбокс складу */
  --check-size:      var(--dim-5);               /* 20px */
  --check-radius:    var(--radius-sm);
  --check-border:    var(--color-border-strong);
  --check-on-bg:     var(--color-accent);
  --check-on-border: var(--color-accent-fg);
  --check-mark-fg:   var(--color-on-accent);
  --check-col-min:   var(--dim-42);              /* 168px */

  /* чип обмеження (мобільний) */
  --cchip-height:   var(--size-chip);
  --cchip-bg:       var(--color-surface);
  --cchip-bg-hover: var(--color-surface-2);
  --cchip-border:   var(--color-border-strong);
}
```

#### Поведінка

- ≥ 1024px: дві панелі. Ліворуч «Продукти» (рядки зі степпером і ×, поле «Додати товар»), праворуч «Обмеження» і CTA «Знайти ціни · N товарів» під ними.
- < 1024px: товари чипами. Натискання на чип відкриває редактор зі степпером під списком, × прибирає товар. Обмеження йдуть під товарами, CTA — у нижній панелі.
- Степпер рахує пачки (або штуки для штучних товарів), від 1 до 99. Потреба для агента = кількість × пачка.
- «Додати товар»: ARIA combobox. Спершу канонічні категорії (локально), потім товари каталогу (`/catalog/prices`, пауза 300 мс, мінімум 2 символи), останнім — «Додати „текст“» як вільний запит. Якщо каталог недоступний, лишаються категорії й вільний текст.
- Склад: лише фільтри, які перевіряє каталог (цукор, лактоза, пальмова олія, власні марки). Товар із невідомим складом фільтр не проходить.
- Відстань: «Пішки / Авто» і радіус. Режим і радіус заповнюються з `VoiceResult.mode` і `radius_km`, `null` → пішки 2 км, авто 10 км. Зміна режиму повертає дефолтний радіус режиму.
- Порожній список: «Додайте товари, які треба купити», CTA неактивна.
- Вибраний стан пресетів, сегментів і чекбоксів — лайм + межа `accent-fg`, не лише колір (див. §5).

---

## 5. Перевірка контрастів

Розраховано за формулою WCAG 2.1 для пар, які використовують компоненти вище. Пари з MASTER не повторено.

| Пара | Світла | Темна | Де |
|---|---|---|---|
| `text-2` на `surface-2` | 6.82 | 6.02 | AllergenBadge verified, UnitPrice badge |
| `text-3` на `surface-2` | 5.25 | 4.57 | Мета в StoreCard pressed, CitySelect active option |
| `text-3` на `warning-subtle` | 5.42 | **4.09 ✗** | Заборонено → у AnalogNotice `text-2` |
| `text-2` на `warning-subtle` | 7.04 | 5.39 | AnalogNotice мета |
| `text-2` на `danger-subtle` | — | 6.24 | Деталі помилок |
| `accent-fg` на `warning-subtle` | 16.14 | 12.57 | «Замінити» в AnalogNotice |
| `accent-fg` на `accent-subtle` | 17.00 | 12.76 | CitySelect selected option, вибраний чип |
| `on-accent` на `accent` | 13.83 | 13.83 | Primary-кнопка, VoiceButton |
| `accent` як текст на `surface` | **1.28 ✗** | 13.39 | Заборонено у світлій темі → `accent-fg` |
| `savings` на `surface` | 4.99 | 13.39 | Рядок компромісу «−75 ₴ за +450 м» |
| `savings` на `bg` | 4.69 | 14.71 | Економія поза картками |
| `savings` на `warning-subtle` | 4.55 | 10.78 | Не використовується (на межі) |
| `savings-strong` на `warning-subtle` | 6.45 | 11.36 | AnalogNotice: аналог дешевший |
| `savings-strong` на `savings-subtle` | 6.52 | 12.39 | UnitPrice lowest |
| `on-savings-solid` на `savings-solid` | 13.83 | 11.76 | Savings-бейдж «−240 ₴ до інших» |
| `danger` на `danger-subtle` | 5.12 | 5.79 | AllergenBadge contains (темна) |
| `warning` на `surface` | 6.26 | 9.43 | Тексти warning поза бейджем |
| `warning` на `warning-subtle` | 5.7 (MASTER) | 7.59 | AllergenBadge traces, бейдж ваги |
| `on-accent` на `accent-hover` | 12.07 | 14.57 | VoiceButton listening |
| `ring` на `bg` (фокус, кільце голосу) | 16.64 | 14.71 | ≥ 3:1 для UI |
| `border-strong` на `bg` | 3.05 | — | CitySelect, VoiceButton blocked: ≥ 3:1, на межі |
| `border-strong` на `surface` | 3.24 | 3.26 | Поля |
| `text-3` на `bg` | 5.59 | 5.58 | Мета |

`accent-subtle` на `bg` = 1.02:1, а лайм `accent` на білому = 1.28:1. Тому вибраний стан ніколи не передається лише лаймом: завжди є межа `accent-fg` (чорнило), іконка `Check` або вага тексту.

---

## 6. Відхилення від MASTER і відкриті питання

### Що додано відносно MASTER

| Що | Чому |
|---|---|
| Темні `--color-savings-strong` і `--color-danger-strong` (= `lime-300`, `red-400`) | У MASTER їх немає для темної теми, а компоненти їх читають. Контраст 12.39 і 5.79 |
| `--color-accent-fg`, `--color-savings-solid`, `--color-on-savings-solid` | Лайм не читається як текст на світлому фоні, тож акцентний текст — чорнилом; головна економія — інверсною пігулкою |
| `--color-logo-plate` (білий в обох темах) | Логотипи мереж із прозорим фоном зникають на темному фоні |
| `--color-skeleton`, `--space-ms` (12px), `--space-2xs` (2px) | Внутрішні відступи рядків і плашок; оптичні поправки |
| `--size-*`, `--z-*`, `--focus-*`, `--opacity-disabled` | Розміри й шари з MASTER, винесені в токени |
| Заборона `text-3` на `warning-subtle` / `danger-subtle` | У темній темі 4.09:1 |

### Інтерпретації запиту

1. **«Картка магазину»** = картка варіанту кошика з MASTER (OptionCard) + компактний варіант для піна на карті. Якщо мався на увазі окремий список магазинів без варіантів кошика, потрібна окрема специфікація.
2. **«Бейдж ціна за 1 кг»**: MASTER показує ціну за кг як текст-мету, а не бейдж. Тут текст лишився варіантом за замовчуванням (`inline`). Бейдж (`badge`, `lowest`) — лише там, де ціна за кг є предметом порівняння.
3. **«Бейдж алергену»** має 4 варіанти. `contains` можливий лише для товару, який користувач додав сам: автоматичний підбір такий товар не пропонує.

### Відкриті питання

1. **VoiceButton blocked:** кнопка лишається видимою (`MicOff`) з поясненням, як увімкнути мікрофон. Альтернатива — ховати її, як у unsupported. Потрібне рішення продукту.
2. **Різниця для аналога:** рахуємо від ціни оригіналу в **іншій** мережі. Якщо оригіналу немає ніде, рядок різниці не показується. Підтвердити з бекендом, чи ця ціна доступна.
3. **Список міст:** які міста в MVP і скільки мереж у кожному. Зараз приклад: Київ, Львів, Одеса, Дніпро, Харків.
4. **Сума при частковій наявності:** картка показує «Сума без 1 товару». Як ранжувати варіанти з різною кількістю товарів — питання до логіки рекомендацій.
5. **`border-strong` на `bg` = 3.03:1** — проходить, але без запасу. Якщо поля стоятимуть на `bg`, а не на `surface`, варто затемнити `graphite-400` до `#868690` (3.37:1 на `bg`, 3.60:1 на `surface`).
