<!-- 0d558598-ff04-4142-a631-36e78dae7ba3 a0ccb889-1ff1-4c82-96b4-fd615fb04d4d -->
# План: Тесты для обработки устаревших callback queries

## Проблемы, которые нужно покрыть тестами

1. **manage_keys_handler** - нет тестов, ошибки с устаревшими callback queries не обнаруживаются
2. **Обработчик ошибок роутера** - логирует устаревшие callback queries как CRITICAL до обработки
3. **Моки не эмулируют реальное поведение** - всегда успешно выполняют callback.answer()

## Количество тестов для создания

### 1. Тесты для manage_keys_handler (новый файл: `tests/unit/test_bot/test_manage_keys_handler.py`)

**Количество: 4 теста**

- `test_manage_keys_success_with_keys` - успешный сценарий с ключами у пользователя
- `test_manage_keys_success_without_keys` - успешный сценарий без ключей
- `test_manage_keys_expired_callback_query` - обработка устаревшего callback query
- `test_manage_keys_other_telegram_bad_request` - обработка других TelegramBadRequest ошибок

### 2. Фикстура для устаревших callback queries (в `tests/conftest.py`)

**Количество: 1 фикстура**

- `expired_callback_query` - фикстура, которая создает мок CallbackQuery с эмуляцией TelegramBadRequest для устаревших queries

### 3. Тесты для обработчика ошибок роутера (новый файл: `tests/unit/test_bot/test_router_error_handler.py`)

**Количество: 4 теста**

- `test_error_handler_expired_callback_query` - обработка устаревшего callback query в error handler
- `test_error_handler_expired_callback_not_critical` - проверка, что устаревшие callback queries не логируются как CRITICAL
- `test_error_handler_other_callback_errors` - обработка других ошибок в callback query handlers
- `test_error_handler_message_handler_errors` - обработка ошибок в message handlers

### 4. Улучшение кода (в `src/shop_bot/bot/handlers.py`)

**Количество: 1 исправление**

- Исправить `user_router_error_handler` чтобы не логировать устаревшие callback queries как CRITICAL (проверять тип ошибки ДО логирования)

## Итого

- **Новых тестов: 8**
- **Новых фикстур: 1**
- **Исправлений кода: 1**

## Структура файлов

```
tests/
├── unit/
│   └── test_bot/
│       ├── test_manage_keys_handler.py (новый)
│       └── test_router_error_handler.py (новый)
└── conftest.py (обновление - добавление фикстуры)
```

## Детали реализации

### Фикстура expired_callback_query

- Создает мок CallbackQuery
- Настраивает `callback.answer()` чтобы выбрасывать `TelegramBadRequest` с сообщением "query is too old and response timeout expired or query ID is invalid"

### Тесты для manage_keys_handler

- Используют `temp_db`, `mock_bot`, `expired_callback_query`
- Проверяют корректную обработку всех сценариев
- Проверяют, что устаревшие callback queries обрабатываются без ошибок

### Тесты для обработчика ошибок роутера

- Используют моки для эмуляции различных ошибок
- Проверяют, что устаревшие callback queries не логируются как CRITICAL
- Проверяют корректную обработку других ошибок

### Исправление кода

- В `user_router_error_handler` добавить проверку типа ошибки ДО логирования как CRITICAL
- Если это `TelegramBadRequest` с сообщением об устаревшем callback query - логировать как DEBUG, а не CRITICAL

### To-dos

- [ ] Создать фикстуру expired_callback_query в tests/conftest.py для эмуляции устаревших callback queries
- [ ] Создать файл tests/unit/test_bot/test_manage_keys_handler.py с 4 тестами для manage_keys_handler
- [ ] Создать файл tests/unit/test_bot/test_router_error_handler.py с 4 тестами для обработчика ошибок роутера
- [ ] Исправить user_router_error_handler в src/shop_bot/bot/handlers.py чтобы не логировать устаревшие callback queries как CRITICAL