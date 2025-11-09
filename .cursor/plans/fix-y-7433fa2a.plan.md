<!-- 7433fa2a-c8e0-4d0a-9300-824798cfc363 a8bc2de1-e644-4a4a-aa0e-4c1eabf3bddc -->
# Исправление ошибки оплаты YooKassa

## Проблема

В функции `create_yookassa_payment_handler` (строка 4419) и аналогичной функции (строка ~4040) происходит `UnboundLocalError` при попытке использовать `get_setting`, так как локальный импорт на строке 4644 конфликтует с использованием функции на строках 4449 и 4462.

## Решение

Удалить дублирующие локальные импорты, так как `get_setting` уже импортирована глобально на строке 43.

## Изменения

### 1. Файл `src/shop_bot/bot/handlers.py`

- **Строка 4044**: Удалить `from src.shop_bot.data_manager.database import get_setting`
- **Строка 4644**: Удалить `from src.shop_bot.data_manager.database import get_setting`

### 2. Файл `CHANGELOG.md`

Добавить запись о патче с текущей датой и временем UTC+3:

- Тип: [Исправление]
- Область: (Платежи) handlers.py
- Описание: Устранена критическая ошибка UnboundLocalError при оплате через YooKassa

### 3. Файл `pyproject.toml`

Обновить версию (патч-версия)

### 4. Создать unit-тест `tests/test_yookassa_payment.py`

Тест должен:

- Подключаться к тестовому серверу YooKassa
- Использовать тестовые credentials из `bot_settings` (yookassa_test_shop_id, yookassa_test_secret_key)
- Создавать платеж от имени пользователя с telegram_id = 2206685
- Проверять, что платеж создается успешно без UnboundLocalError
- Проверять корректность использования get_setting
- Включать cleanup после теста

## Проверка

После исправления функция будет использовать глобальный импорт `get_setting`, что устранит конфликт области видимости. Unit-тест подтвердит работоспособность YooKassa платежей.

### To-dos

- [ ] Удалить локальные импорты get_setting на строках 4044 и 4644
- [ ] Добавить запись в CHANGELOG.md о патче
- [ ] Обновить версию в pyproject.toml