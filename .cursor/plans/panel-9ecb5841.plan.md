<!-- 9ecb5841-4d94-4ea6-a467-0743d8cdf114 1eec4de0-a9a2-4489-9d8a-44a1288ed18c -->
# Исправление критических ошибок в логах

## Проблемы

1. **IndentationError в `database.py` на строке 6063**: Неправильный отступ у `return item`
2. **TemplateAssertionError для `panel_iso`**: Фильтр не загружается из-за краша приложения при импорте `database.py`

## Решение

### 1. Исправить отступы в `src/shop_bot/data_manager/database.py`

В функции `get_notification_by_id` (строки 6060-6063):

**Текущий код (неправильно):**

```python
        # Normalize created_date
        item['created_date'] = _parse_db_datetime(item.get('created_date'))

            return item
```

**Исправленный код:**

```python
            # Normalize created_date
            item['created_date'] = _parse_db_datetime(item.get('created_date'))

            return item
```

Строки 6060-6063 должны иметь отступ в 12 пробелов (3 уровня), так как они находятся внутри блока `if row:` (строка 6032).

### 2. Перезапустить сервис

После исправления отступов перезапустить бота командой:

```bash
npx nx serve bot
```

## Ожидаемый результат

- Приложение успешно запустится без `IndentationError`
- Фильтр `panel_iso` будет корректно зарегистрирован
- Страница `/users` будет работать без ошибок