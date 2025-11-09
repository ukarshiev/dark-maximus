<!-- 502bbdb5-cad8-4c9f-a263-75ca45dd1b64 ef438de8-f182-4d8b-bbd4-595692a1d59a -->
# Увеличение ширины колонок и адаптивность платёжных систем

## Изменения в CSS (`src/shop_bot/webhook_server/static/css/style.css`)

### 1. Расширить колонки до 700px

**Найти:** `.payment-systems-grid`

```css
.settings-section .payment-systems-grid {
    display: grid !important;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
    ...
}
```

**Изменить на:**

```css
.settings-section .payment-systems-grid {
    display: grid !important;
    grid-template-columns: repeat(2, 700px);
    gap: 40px;
    justify-content: center;
    max-width: 100%;
    margin: 0 auto;
}
```

### 2. Вернуть горизонтальное расположение галочек

**Найти:** `.form-group-checkbox`

```css
.form-group-checkbox {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-top: 15px;
}
```

**Изменить на:**

```css
.form-group-checkbox {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 10px;
    margin-top: 15px;
}
```

### 3. Добавить адаптивность

**После существующих медиа-запросов добавить:**

```css
/* Десктоп: 2 колонки по 700px */
@media (min-width: 1441px) {
    .settings-section .payment-systems-grid {
        grid-template-columns: repeat(2, 700px);
    }
}

/* Планшет: 2 колонки адаптивные */
@media (max-width: 1440px) and (min-width: 769px) {
    .settings-section .payment-systems-grid {
        grid-template-columns: repeat(2, 1fr);
        gap: 20px;
        padding: 0 20px;
    }
    
    .settings-section .payment-column {
        min-width: 350px;
    }
}

/* Мобилка: 1 колонка */
@media (max-width: 768px) {
    .settings-section .payment-systems-grid {
        grid-template-columns: 1fr;
        gap: 20px;
        padding: 0 10px;
    }
    
    .settings-section .payment-column {
        width: 100%;
        min-width: unset;
    }
    
    .form-group-checkbox {
        flex-wrap: wrap;
    }
}
```

## Расширение контейнера настроек

### Изменить ограничение ширины для платёжных систем

**В файле `src/shop_bot/webhook_server/templates/settings.html`**

**Найти inline стили (примерно строка 1311-1317):**

```css
#servers-tab > section.settings-section {
    width: clamp(600px, 90vw, 1500px);
    max-width: 1500px;
    ...
}
```

**Добавить правило для вкладки платёжных систем:**

```css
#payments-tab .settings-section {
    width: clamp(600px, 95vw, 1600px);
    max-width: 1600px;
    margin-left: auto;
    margin-right: auto;
}
```

## Результат

- **Десктоп (>1440px):** 2 колонки по 700px с отступом 40px между ними
- **Планшет (769-1440px):** 2 адаптивные колонки с минимальной шириной 350px
- **Мобилка (<768px):** 1 колонка на всю ширину экрана
- **Галочки:** горизонтально с текстом во всех чекбоксах `.form-group-checkbox`