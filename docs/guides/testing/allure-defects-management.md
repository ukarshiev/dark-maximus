# Управление дефектами Allure

> **Дата последней редакции:** 15.01.2025 12:00

## Обзор

Это руководство описывает процесс работы с дефектами, обнаруженными в Allure отчётах тестирования проекта Dark Maximus.

## Статус исправлений

**Последнее обновление:** 15.01.2025

### ✅ Все задачи выполнены!

- **GitHub Issues:** 29 Issues созданы (#21-#49) ✅
- **Все критичные дефекты исправлены:** 22 дефекта ✅
- **Все тесты проходят:** 21 из 21 критичных тестов (100%) ✅

### Выполненные исправления

1. **Схема БД для промокодов** ✅
   - Добавлены все недостающие колонки в таблицу `promo_codes` в `tests/conftest.py`
   - Колонки: `vpn_plan_id`, `tariff_code`, `discount_amount`, `discount_percent`, `discount_bonus`, `usage_limit_per_bot`, `is_active`, `created_at`, `updated_at`, `burn_after_value`, `burn_after_unit`, `valid_until`, `target_group_ids`, `bot_username`

2. **Схема БД для ключей** ✅
   - Добавлено поле `keys_count` в таблицу `users`
   - Добавлено поле `telegram_chat_id` в таблицу `vpn_keys`
   - Исправлена дублирующаяся колонка `transaction_id` в таблице `transactions`

3. **Схема БД для групп пользователей** ✅
   - Добавлены поля `group_description` и `created_date` в таблицу `user_groups`

4. **Исправление функции log_transaction** ✅
   - Удалена попытка вставки `transaction_id` в PRIMARY KEY колонку
   - Функция теперь корректно работает с автоинкрементом

5. **Исправление тестов** ✅
   - `test_register_user_twice` - добавлены проверки на None
   - `test_deeplink_parameter_length_limit` - исправлены параметры функции
   - `test_sanitize_string_dangerous_chars` - исправлено ожидаемое значение
   - `test_record_promo_code_usage` - исправлена логика проверки статуса промокода

### Результаты тестирования

- **Исправлено критичных дефектов:** 22 (все критичные дефекты исправлены)
  - Регистрация пользователя: 4 теста ✅
  - Покупка VPN-ключа: 2 теста ✅
  - Оплата/транзакции: 3 теста ✅
  - Получение ключа: 3 теста ✅
  - Пополнение баланса: 1 тест ✅
  - Промокоды: 10 тестов ✅
- **Исправлено Test defects:** 4 (тесты схемы БД и валидации)
- **Проходят тесты:** 21 из 21 критичных тестов (100%)

## Структура процесса

### 1. Экспорт данных из Allure

Скрипт `tests/ad-hoc/export_allure_defects.py` экспортирует все дефекты из Allure отчёта:

```bash
python tests/ad-hoc/export_allure_defects.py
```

**Результат:**
- Файл `tests/ad-hoc/reports/allure-defects-export.json` с данными о всех дефектах
- Статистика: количество Product defects, Test defects, критичных дефектов

### 2. Анализ дефектов

Скрипт `tests/ad-hoc/analyze_allure_defects.py` анализирует экспортированные данные и создаёт структурированный отчёт:

```bash
python tests/ad-hoc/analyze_allure_defects.py
```

**Результат:**
- Файл `tests/ad-hoc/reports/allure-defects-report.md` с детальным анализом
- Группировка по модулям и приоритетам
- Рекомендации по исправлению

### 3. Создание GitHub Issues

Скрипт `tests/ad-hoc/create_github_issues.py` автоматически создаёт Issues для всех дефектов:

```bash
# Установите токен GitHub
$env:GITHUB_TOKEN='your-github-token'  # PowerShell
# или
export GITHUB_TOKEN='your-github-token'  # Bash

# Запустите скрипт
python tests/ad-hoc/create_github_issues.py
```

**Результат:**
- GitHub Issues для каждого дефекта
- Правильные labels (bug, test, critical, allure)
- Заполненные данные из Allure

**Режим DRY RUN:**
Если токен не установлен, скрипт работает в режиме DRY RUN и показывает, какие Issues были бы созданы.

## Категории дефектов

### Product defects

Реальные баги в коде, обнаруженные тестами. Требуют исправления кода.

**Автоматическая категоризация:**
- Статус: `failed`
- Ошибка содержит: `AssertionError`
- Стек трейс содержит: `assert.*is not None` или аналогичные проверки

### Test defects

Проблемы в самих тестах. Требуют исправления/удаления тестов.

**Автоматическая категоризация:**
- Статус: `broken`
- Ошибка содержит: `RuntimeError`, `TypeError`, `OperationalError`, `AttributeError`, `ValueError`, `KeyError`
- Или статус `failed` с ошибками: `unexpected keyword argument`, `no such table`, `got an unexpected`

## Приоритизация дефектов

### Критичные дефекты

Блокируют пользовательские операции. Исправляются в первую очередь:

1. **Регистрация пользователя** — `test_register_user_*`
2. **Покупка VPN-ключа** — `test_key_creation_*`
3. **Оплата** — `test_transaction_*`, `test_update_transaction_*`
4. **Получение ключа** — `test_get_*_key_*`
5. **Пополнение баланса** — `test_user_balance_*`
6. **Использование промокодов** — `test_promo_code_*`

### Важные дефекты

Влияют на функциональность, но не блокируют полностью.

### Некритичные дефекты

Косметические проблемы, не влияющие на основную функциональность.

## Автоматическая категоризация

Файл `allure-categories.json` в корне проекта содержит правила автоматической категоризации дефектов.

**Применение:**
```bash
allure generate allure-results -o allure-report --categories allure-categories.json
```

**Формат правил:**
```json
[
  {
    "name": "Product defects",
    "matchedStatuses": ["failed"],
    "messageRegex": ".*AssertionError.*",
    "traceRegex": ".*assert.*is not None.*"
  },
  {
    "name": "Test defects",
    "matchedStatuses": ["broken"],
    "messageRegex": ".*RuntimeError.*|.*TypeError.*"
  }
]
```

## Интеграция в CI/CD

CI/CD pipeline автоматически:

1. Запускает тесты с генерацией Allure результатов
2. Генерирует Allure отчёт с применением категорий
3. Анализирует дефекты
4. Создаёт отчёт о дефектах
5. Загружает артефакты (Allure отчёт и отчёт о дефектах)

**Файл:** `.github/workflows/ci.yml`

## Процесс исправления дефектов

### Для Product defects:

1. Изучить код в модуле, указанном в дефекте
2. Найти причину ошибки из стек трейса
3. Исправить баг в коде
4. Запустить тест: `pytest tests/path/to/test.py::test_name`
5. Проверить, что тест проходит
6. Обновить GitHub Issue (закрыть после исправления)

### Для Test defects:

1. Проанализировать тест
2. Определить причину:
   - **Неправильный тест** → исправить тест
   - **Устаревший тест** → обновить тест
   - **Флаки тест** → добавить retry или исправить условия
   - **Ненужный тест** → удалить тест
3. Исправить/удалить тест
4. Запустить тест и проверить результат
5. Обновить GitHub Issue

## Best Practices

### Allure

- Используйте `@allure.severity` для маркировки критичности тестов
- Используйте `@allure.label` для категоризации
- Добавляйте описания через `@allure.description`

### Pytest

- Используйте фикстуры для изоляции тестов
- Используйте маркеры для категоризации (`@pytest.mark.unit`, `@pytest.mark.database`)
- Избегайте зависимостей между тестами
- Используйте временные БД для тестов

### GitHub Issues

- Создавайте отдельный Issue для каждого дефекта
- Используйте правильные labels
- Добавляйте ссылки на Allure отчёт
- Закрывайте Issues после исправления

## Скрипты

### export_allure_defects.py

Экспортирует данные о дефектах из Allure отчёта в JSON.

**Использование:**
```bash
python tests/ad-hoc/export_allure_defects.py
```

**Требования:**
- Сгенерированный Allure отчёт в `allure-report/`

### analyze_allure_defects.py

Анализирует экспортированные данные и создаёт структурированный отчёт.

**Использование:**
```bash
python tests/ad-hoc/analyze_allure_defects.py
```

**Требования:**
- Файл `tests/ad-hoc/reports/allure-defects-export.json`

### create_github_issues.py

Создаёт GitHub Issues для всех дефектов.

**Использование:**
```bash
# Установите токен
$env:GITHUB_TOKEN='your-token'

# Запустите скрипт
python tests/ad-hoc/create_github_issues.py
```

**Требования:**
- GitHub токен в переменной окружения `GITHUB_TOKEN`
- Файл `tests/ad-hoc/reports/allure-defects-export.json`

## Мониторинг

После каждого запуска тестов:

1. Проверьте Allure отчёт: `http://localhost:50005/allure-docker-service/projects/default/reports/latest/index.html`
2. Проверьте категории дефектов
3. Проверьте отчёт о дефектах: `tests/ad-hoc/reports/allure-defects-report.md`
4. Создайте Issues для новых критичных дефектов

## Связанные документы

- [Обзор тестирования](README.md) — главная страница раздела тестирования
- [Структура тестов](testing-structure.md) — организация тестов по типам
- [Запуск тестов](running-tests.md) — инструкции по запуску тестов
- [Allure отчеты](allure-reporting.md) — работа с Allure Framework
- [Best Practices](best-practices.md) — рекомендации по написанию тестов
- [Справочник по тестированию](../../reference/testing-reference.md) — полный справочник
- [CI/CD Pipeline](../../architecture/ci-cd-pipeline.md)

