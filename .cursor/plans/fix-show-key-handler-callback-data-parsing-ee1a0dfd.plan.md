<!-- ee1a0dfd-62e1-4152-88ea-6d89ea53d181 86ab12bb-097e-4796-bde7-8a8a6b640d38 -->
# Исправление ошибки парсинга callback data в showkeyhandler

## Проблема

В логах повторяется ошибка:

```
ValueError: invalid literal for int() with base 10: 'auto'
```

Ошибка происходит в `src/shop_bot/bot/handlers.py:3424` в функции `show_key_handler`:

- `toggle_key_auto_renewal_handler` (строка 3607) вызывает `show_key_handler(callback)` после переключения автопродления
- `show_key_handler` ожидает callback data формата `show_key_{key_id}` и извлекает key_id как `int(callback.data.split("_")[2])`
- Но callback.data все еще содержит `toggle_key_auto_renewal_{key_id}`
- При split("_") получается `['toggle', 'key', 'auto', 'renewal', '123']`, и индекс [2] = 'auto' (не число)

## Решение

Изменить логику извлечения key_id в `show_key_handler` чтобы она работала с разными форматами callback data:

- Для `show_key_{key_id}` - использовать текущую логику
- Для `toggle_key_auto_renewal_{key_id}` - использовать последний элемент после split (как в `toggle_key_auto_renewal_handler`)

## Изменения

### Файл: `src/shop_bot/bot/handlers.py`

**Строка 3424:** Изменить логику извлечения key_id

Текущий код:

```python
key_id_to_show = int(callback.data.split("_")[2])
```

Новый код:

```python
# Извлекаем key_id из разных форматов callback data
parts = callback.data.split("_")
if callback.data.startswith("show_key_"):
    key_id_to_show = int(parts[2])
elif callback.data.startswith("toggle_key_auto_renewal_"):
    key_id_to_show = int(parts[-1])  # последний элемент
else:
    # Fallback: пытаемся извлечь из последнего элемента
    key_id_to_show = int(parts[-1])
```

## Анализ тестового покрытия

### Почему тесты не выявили проблему

1. **Отсутствует тест для `toggle_key_auto_renewal_handler`**:

   - В проекте нет unit-теста для обработчика `toggle_key_auto_renewal_handler`
   - Есть только тесты для функций БД (`test_key_auto_renewal.py`) и интеграционные тесты процесса автопродления (`test_auto_renewal_process.py`)
   - Но нет теста, который проверяет сам обработчик callback query

2. **Тест `test_show_key_button` не покрывает проблемный сценарий**:

   - Тест в `tests/integration/test_auto_renewal/test_notification_buttons_flow.py` тестирует только прямой вызов `show_key_handler` с форматом `show_key_{key_id}`
   - Тест не проверяет случай, когда `show_key_handler` вызывается из другого обработчика (например, из `toggle_key_auto_renewal_handler`)
   - Тест использует упрощенную версию обработчика, которая дублирует проблемную логику `int(callback.data.split("_")[2])`

3. **Отсутствует интеграционный тест полного flow**:

   - Нет теста, который проверяет полный цикл: нажатие кнопки автопродления → вызов `toggle_key_auto_renewal_handler` → вызов `show_key_handler` с неправильным форматом callback data

### Недостающие тесты

1. **Unit-тест для `toggle_key_auto_renewal_handler`**:

   - Проверка переключения статуса автопродления
   - Проверка вызова `show_key_handler` после переключения
   - Проверка обработки ошибок (ключ не найден, устаревший callback query)

2. **Интеграционный тест для вызова `show_key_handler` из `toggle_key_auto_renewal_handler`**:

   - Проверка, что `show_key_handler` корректно обрабатывает callback data формата `toggle_key_auto_renewal_{key_id}`
   - Проверка полного flow переключения автопродления и отображения ключа

## Тестирование

После исправления проверить:

1. Переключение автопродления ключа работает без ошибок
2. Отображение информации о ключе после переключения автопродления корректно
3. Обычное отображение ключа (через `show_key_{key_id}`) продолжает работать