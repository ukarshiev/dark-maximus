## Перевод разделов панели на CSS Grid (эталон «Пользователи»)

Последнее обновление: 24.10.2025

Цель: унифицировать лейаут всех разделов под единую сетку (Grid) с корректным поведением на мобильных/планшетах и десктопе. Эталоном служит раздел `Пользователи`.

### 1. Разметка шаблона
В файле шаблона (например, `src/shop_bot/webhook_server/templates/{page}.html`):

```jinja2
{% extends "base.html" %}
{% block body_class %}{PAGE_CLASS}-page{% endblock %}
{% block container_class %}layout-grid{% endblock %}
```

Основной контент оставляем как есть. Желательно, чтобы таблицы/контент были в `section.settings-section.settings-section--fluid`.

### 2. Базовые стили (добавить в `static/css/style.css`)
Подставьте свой `{PAGE_CLASS}` (например: `transactions`, `keys`, `notifications`).

```css
/* === {PAGE_CLASS} — Desktop/Grid === */
body.{PAGE_CLASS}-page {
    display: grid;
    grid-template-rows: 55px 1fr;        /* header + контент */
    grid-template-areas: "header" "content";
    min-height: 100vh;
    --sidebar-w: 280px;                   /* ширина сайдбара по умолчанию */
}

.{PAGE_CLASS}-page .container.layout-grid {
    grid-area: content;
    display: grid;
    grid-template-columns: var(--sidebar-w) 1fr;
    grid-template-areas: "sidebar main";  /* header вне контейнера */
    width: 100%;
    min-height: 100%;
    margin: 0;
    padding: 0;
    background: transparent;
}

.{PAGE_CLASS}-page .sidebar {
    grid-area: sidebar;
    position: sticky;
    top: 55px;                            /* под шапкой */
    height: calc(100vh - 55px);
    overflow-y: auto;
    overflow-x: hidden;
}

.{PAGE_CLASS}-page .main-content {
    grid-area: main;
    margin-left: 0;
    min-width: 0;                         /* чтобы контент сжимался/скроллился */
    overflow: auto;
    padding-left: 10px;                   /* лёгкий внутренний отступ */
}

/* Убираем глобальные отступы контейнера под фикс‑шапкой только для этой страницы */
body.{PAGE_CLASS}-page > .container,
.{PAGE_CLASS}-page .container { margin-top: 0; }

/* Динамика ширины при сворачивании/скрытии сайдбара (как в users) */
.{PAGE_CLASS}-page .container.layout-grid:has(.sidebar.sidebar-collapsed) { --sidebar-w: 60px; }
.{PAGE_CLASS}-page .container.layout-grid:has(.sidebar.sidebar-hidden)   { --sidebar-w: 0px; }

/* Прячем логотип в шапке, когда сайдбар свёрнут/скрыт — бургер остаётся */
body.{PAGE_CLASS}-page:has(.container.layout-grid .sidebar.sidebar-collapsed) .menu-items-header--in-header .sidebar-logo,
body.{PAGE_CLASS}-page:has(.container.layout-grid .sidebar.sidebar-hidden)   .menu-items-header--in-header .sidebar-logo { display: none; }

/* Чистим отступы секции для полного прилипания таблиц к сетке */
.{PAGE_CLASS}-page .settings-section,
.{PAGE_CLASS}-page .settings-section.settings-section--fluid {
    padding-inline: 0;
    padding-top: 0;
    padding-bottom: 0;
    margin-bottom: 0;
}

/* На страницах грида padding у body:not(.admin-panel) должен быть 0 */
body.{PAGE_CLASS}-page:not(.admin-panel) { padding: 0 !important; }

/* === {PAGE_CLASS} — Mobile (≤599px): off‑canvas sidebar и один бургер === */
@media (max-width: 599px) {
    .{PAGE_CLASS}-page .container.layout-grid {
        grid-template-columns: 1fr;
        grid-template-rows: auto 1fr;
        grid-template-areas: "sidebar" "main"; /* header управляется на уровне body */
    }
    .{PAGE_CLASS}-page .sidebar {
        position: fixed;
        top: 55px;
        left: -100%;
        width: 100%;
        height: calc(100vh - 55px);
        overflow-y: auto;
        overflow-x: hidden;
        transition: left .3s ease;
        z-index: 1002;
    }
    .{PAGE_CLASS}-page .sidebar.sidebar-mobile-open { left: 0; }

    /* На мобильных один бургер: показываем #headerBurger, прячем боковой */
    .menu-items-header--in-header .sidebar-burger { display: none; }
    #headerBurger { display: flex !important; }
    .menu-items-header--in-header { width: auto; flex: 0 0 auto; }
}

/* === {PAGE_CLASS} — Tablet (600–899px): компактная шапка === */
@media (max-width: 899px) and (min-width: 600px) {
    .{PAGE_CLASS}-page .container.layout-grid {
        grid-template-columns: 1fr;      /* без жёсткого ряда header внутри контейнера */
        grid-template-rows: 1fr;
        grid-template-areas: "sidebar" "main";
    }
    .{PAGE_CLASS}-page .sidebar { top: 55px; height: calc(100vh - 55px); }

    .header-panel-left { min-width: 0; }
    .header-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .header-panel-right .button { padding: 6px 8px; min-width: 32px; }
    .header-panel-right .button span,
    .header-panel-right .button .button-text { display: none; }
}

/* === {PAGE_CLASS} — Desktop: левый блок в шапке фикс 280px (как у users) === */
/* Уже есть глобальные стили: .menu-items-header--in-header { width: 280px; flex: 0 0 280px; } */
```

### 3. Поведение бургеров
- На мобильных управляем сайдбаром через `#headerBurger` (добавление/удаление класса `.sidebar-mobile-open`).
- На десктопе остаётся текущая логика сворачивания/скрытия (`sidebar-collapsed`/`sidebar-hidden`).

### 4. Чек‑лист проверки
- 320/425: меню скрыто (off‑canvas), открывается по `#headerBurger`, нет пустой верхней полосы.
- 768 (600–899): заголовок с ellipsis, кнопки иконочные; нет зазора между шапкой и сайдбаром; высота меню `calc(100vh - 55px)`.
- ≥1200: ширина 280/60/0 в зависимости от состояния; логотип в шапке скрывается при свернутом/скрытом сайдбаре.

### 5. Версионирование и документы
- После перевода каждого раздела:
  - Добавьте запись в `CHANGELOG.md` (в начало) с текущим временем UTC+3; bump версии в `pyproject.toml` (патч/минор в зависимости от объёма).
  - При необходимости обновите/дополните документацию в `docs/` (дату редактирования — сверху файла).


