<!-- 506850b2-f326-4eb3-955f-9850f577a36e d519738a-3eb2-4d00-b076-21b61b2d9949 -->
# План устранения Product defects

**Дата:** 16.11.2025

**Версия:** 1.0.0

**Источник:** Allure Report - 44 Product defects

## Обзор

Product defects — это реальные баги в коде, обнаруженные тестами. Требуют исправления кода, а не тестов. Согласно Allure Report, обнаружено 44 Product defects.

## Стратегия устранения

### Этап 1: Анализ и классификация (1-2 часа)

1. **Экспорт актуальных данных из Allure**

   - Запустить `python tests/ad-hoc/export_allure_defects.py` для получения актуального списка
   - Проанализировать `tests/ad-hoc/reports/allure-defects-export.json`
   - Создать структурированный отчёт с группировкой по типам ошибок

2. **Классификация дефектов**

   - Разделить на критичные, важные и некритичные
   - Группировать по модулям: `database`, `bot`, `webhook_server`, `security`, `utils`
   - Группировать по функциональным областям: регистрация, платежи, ключи, баланс, промокоды

3. **Приоритизация**

   - Критичные (блокируют пользователей): регистрация, покупка VPN, оплата, получение ключа
   - Важные (влияют на функциональность): продление ключа, баланс, промокоды
   - Некритичные (косметические): валидация, санитизация

### Этап 2: Исправление критичных дефектов (4-6 часов)

**2.1. Регистрация пользователя** (приоритет: КРИТИЧНЫЙ)

- Файлы: `src/shop_bot/data_manager/database.py`
- Функция: `register_user_if_not_exists()`
- Типичные ошибки:
  - `AssertionError: assert None is not None` - функция не возвращает пользователя
  - Проверить логику создания пользователя в БД
  - Проверить обработку рефералов (`referrer_id`)
- Тесты: `test_register_user_if_not_exists`, `test_register_user_with_referrer`, `test_user_registration_flow`

**2.2. Транзакции и платежи** (приоритет: КРИТИЧНЫЙ)

- Файлы: `src/shop_bot/data_manager/database.py`
- Функции: `log_transaction()`, `update_transaction_status()`, `update_transaction_on_payment()`
- Типичные ошибки:
  - `AssertionError: assert None is not None` - транзакция не создаётся
  - `AssertionError: assert False is True` - обновление статуса не работает
- Проверить:
  - Структуру таблицы `transactions` в БД
  - Автоинкремент `transaction_id` (не пытаться вставлять вручную)
  - SQL запросы на корректность

**2.3. Создание и получение VPN ключей** (приоритет: КРИТИЧНЫЙ)

- Файлы: `src/shop_bot/data_manager/database.py`
- Функции: `create_key_with_stats_atomic()`, `get_or_create_permanent_token()`, `validate_permanent_token()`
- Типичные ошибки:
  - `AssertionError: Не удалось создать тестовый ключ` - ключ не создаётся
  - `AssertionError: assert None is not None` - функция возвращает None
- Проверить:
  - Структуру таблицы `vpn_keys` и `user_tokens`
  - Логику атомарного создания ключа
  - Обработку ошибок IntegrityError

**2.4. Баланс пользователя** (приоритет: КРИТИЧНЫЙ)

- Файлы: `src/shop_bot/data_manager/database.py`
- Функции: `get_user_balance()`, `update_user_balance()`
- Типичные ошибки:
  - `AssertionError: Баланс должен быть обновлен assert 0.0 == 500.0` - баланс не обновляется
- Проверить:
  - SQL запросы UPDATE для поля `balance` в таблице `users`
  - Транзакции при обновлении баланса

### Этап 3: Исправление важных дефектов (2-4 часа)

**3.1. Промокоды** (приоритет: ВАЖНЫЙ)

- Файлы: `src/shop_bot/data_manager/database.py`
- Функции: `create_promo_code()`, `get_promo_code_by_code()`, `apply_promo_code()`
- Типичные ошибки:
  - Проблемы со схемой БД (если есть) - уже исправлено в `tests/conftest.py`
  - Логика применения промокодов
- Проверить:
  - Использование промокодов в покупках
  - Валидацию промокодов

**3.2. Продление ключей и автообновление**

- Файлы: `src/shop_bot/data_manager/database.py`
- Функции: `update_key_info()`, `extend_key()`
- Типичные ошибки:
  - `TypeError: missing required positional arguments` - не хватает параметров
- Проверить:
  - Сигнатуры функций и вызовы
  - Обновление `expiry_date` и `expiry_timestamp_ms`

**3.3. Статистика пользователя**

- Файлы: `src/shop_bot/data_manager/database.py`
- Функции: `update_user_stats()`, `increment_keys_count()`
- Проверить:
  - Обновление полей `total_spent`, `total_months`, `keys_count`

### Этап 4: Исправление некритичных дефектов (1-2 часа)

**4.1. Валидация и санитизация**

- Файлы: `src/shop_bot/utils/validators.py`
- Функции: `sanitize_string()`
- Типичные ошибки:
  - `AssertionError: assert 'testalert(xss)' == 'testalertxss'` - санитизация не удаляет скобки
- Проверить:
  - Регулярные выражения для очистки опасных символов

**4.2. WAL режим БД** (уточнено: WAL был отключён намеренно, но проверка не везде)

- Файлы:
  - `src/shop_bot/data_manager/database.py` - все функции, работающие с БД
  - `tests/unit/test_database/test_locks.py` - тест `test_wal_mode_in_run_migration`
- Контекст: WAL режим был намеренно отключён, везде должен быть DELETE режим (см. `docs/reference/database.md`)
- Типичные ошибки:
  - `AssertionError: journal_mode should be WAL, got delete` - тест проверяет WAL, но должен проверять DELETE
  - Возможны места, где WAL всё ещё устанавливается вместо DELETE
- Проверить:
  - Все места, где выполняется `PRAGMA journal_mode=WAL` - должны быть `PRAGMA journal_mode=DELETE`
  - Тест `test_wal_mode_in_run_migration` - должен проверять DELETE, а не WAL (уже исправлен в строке 249)
  - Все функции в `database.py`, работающие с БД - должны устанавливать DELETE режим
  - `async_database.py` - проверить, что использует DELETE (уже проверено: использует)
- Исправить:
  - Найти и исправить все места, где устанавливается WAL вместо DELETE
  - Убедиться, что `run_migration()` и все функции устанавливают DELETE режим
  - Проверить, что тест корректно проверяет DELETE режим

### Этап 5: Тестирование и проверка (2-3 часа)

1. **Запуск тестов после каждого исправления**
   ```bash
   pytest tests/unit/test_database/ -v
   pytest tests/unit/test_bot/ -v
   ```

2. **Проверка конкретных тестов**
   ```bash
   pytest tests/unit/test_database/test_user_operations.py::test_register_user_if_not_exists -v
   pytest tests/unit/test_database/test_transaction_operations.py::test_log_transaction -v
   ```

3. **Генерация Allure отчёта**
   ```bash
   pytest tests/ --alluredir=allure-results
   # Проверить в http://localhost:5050
   ```

4. **Обновление документации**

   - Обновить `tests/ad-hoc/reports/allure-defects-report.md`
   - Обновить `docs/guides/testing/allure-defects-management.md`
   - Создать/обновить GitHub Issues

### Этап 6: Создание GitHub Issues (1 час)

Для каждого исправленного дефекта:

- Создать Issue (если ещё не создан)
- Указать тип: `Product defect`
- Указать приоритет: критичный/важный/некритичный
- Добавить ссылку на Allure отчёт
- Закрыть Issue после исправления

## Критичные файлы для изменения

1. `src/shop_bot/data_manager/database.py` - основная логика БД
2. `tests/conftest.py` - структура тестовой БД (если нужны изменения схемы)
3. `src/shop_bot/utils/validators.py` - валидация и санитизация

## Метрики успеха

- Количество Product defects: 44 → 0
- Все критичные тесты проходят: 100%
- Allure Report показывает 0 Product defects в категории "Product defects"

## Рекомендации

1. **Начните с экспорта актуальных данных** - старый отчёт может быть устаревшим
2. **Исправляйте по модулям** - сначала `database`, потом `bot`, потом остальное
3. **Тестируйте после каждого исправления** - чтобы не создавать новые дефекты
4. **Используйте фикстуру `temp_db`** - никогда не тестируйте на реальной БД
5. **Ведите лог исправлений** - обновляйте отчёт о дефектах