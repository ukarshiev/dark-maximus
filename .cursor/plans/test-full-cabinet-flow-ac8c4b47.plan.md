<!-- ac8c4b47-c507-42df-9e61-ab6257bd0e83 cae72905-5b9e-4356-9935-59dfdbed0f62 -->
# План исправления теста test_full_cabinet_flow

## Анализ проблем

### Проблема 1: Отсутствие аргумента referrer_id

**Место**: `tests/integration/test_user_cabinet/test_cabinet_flow.py:86`

**Ошибка**: `TypeError: register_user_if_not_exists() missing 1 required positional argument: 'referrer_id'`

**Причина**: Функция `register_user_if_not_exists(telegram_id: int, username: str, referrer_id, fullname: str = None)` требует обязательный позиционный аргумент `referrer_id`

**Решение**: Добавить аргумент `referrer_id=None` при вызове функции

### Проблема 2: Отсутствие патчинга DB_FILE

**Место**: `tests/integration/test_user_cabinet/test_cabinet_flow.py:73-127`

**Проблема**: Flask приложение может использовать реальную БД вместо временной, так как `database.DB_FILE` не патчится перед загрузкой приложения

**Причина**: В других тестах (`test_valid_cabinet_link_accessible`, `test_multiple_valid_links_not_broken`) явно патчится `database.DB_FILE`, но в `test_full_cabinet_flow` этого нет

**Решение**: Добавить патчинг `database.DB_FILE = temp_db` перед загрузкой Flask приложения, аналогично другим тестам

## Исправления

### Файл: tests/integration/test_user_cabinet/test_cabinet_flow.py

1. **Исправить строку 86**: Добавить аргумент `referrer_id=None`
   ```python
   register_user_if_not_exists(user_id, "test_user", referrer_id=None)
   ```

2. **Добавить патчинг DB_FILE в тест test_full_cabinet_flow** (после строки 82, перед использованием БД):
   ```python
   from shop_bot.data_manager import database
   
   # Патчим DB_FILE для использования временной БД
   original_db_file = database.DB_FILE
   database.DB_FILE = temp_db
   
   try:
       # ... весь код теста ...
   finally:
       database.DB_FILE = original_db_file
   ```


## Дополнительные проверки

Проверить другие тесты в том же файле на аналогичные проблемы:

- `test_cabinet_with_subscription_link` (строка 141) - уже исправлен
- `test_cabinet_without_subscription_link` (строка 190) - уже исправлен
- `test_cabinet_key_data_display` (строка 233) - уже исправлен
- `test_valid_cabinet_link_accessible` (строка 366) - нужно проверить
- `test_multiple_valid_links_not_broken` (строка 485) - нужно проверить

## Тестирование

После исправления запустить тест:

```bash
docker compose exec monitoring pytest tests/integration/test_user_cabinet/test_cabinet_flow.py::TestCabinetFlow::test_full_cabinet_flow -v
```

### To-dos

- [ ] Исправить строку 86: добавить referrer_id=None в register_user_if_not_exists
- [ ] Добавить патчинг database.DB_FILE перед загрузкой Flask приложения в test_full_cabinet_flow
- [ ] Проверить тесты test_valid_cabinet_link_accessible и test_multiple_valid_links_not_broken на аналогичные проблемы
- [ ] Запустить исправленный тест для проверки работоспособности