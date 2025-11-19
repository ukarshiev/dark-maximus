<!-- 15cfc937-00dc-4df0-9f48-2ca95259d330 59c9d968-6588-446f-8246-d9f26dcd62a4 -->
# План реорганизации тестов из tests/ad-hoc

## Цель

Проанализировать 55 тестовых файлов из `tests/ad-hoc/`, удалить дубликаты, перенести полезные тесты в правильные каталоги и привести их к стандартам проекта согласно `testing-rules.mdc`.

## Этап 1: Анализ и категоризация тестов

### 1.1. Дублирующиеся тесты (удалить)

Следующие тесты полностью дублируют существующие автотесты:

**Файлы для удаления:**

- `tests/ad-hoc/test_message_templates.py` → дублирует `tests/unit/test_utils/test_message_templates.py` (более полная версия с Allure)
- `tests/ad-hoc/tests/test_html_validation.py` → дублирует `tests/unit/test_utils/test_template_validation.py`
- `tests/ad-hoc/tests/test_deeplink_fix.py` → есть `tests/unit/test_utils/test_deeplink.py` и `tests/integration/test_deeplink_flow.py`
- `tests/ad-hoc/tests/test_deeplink_base64.py` → дублирует тесты deeplink
- `tests/ad-hoc/tests/test_deeplink_comma_format.py` → дублирует тесты deeplink
- `tests/ad-hoc/tests/test_deeplink_new_user.py` → дублирует интеграционные тесты deeplink
- `tests/ad-hoc/tests/test_promo_deeplink_fix.py` → есть тесты промокодов в `tests/unit/test_database/test_promo_code_operations.py` и `tests/integration/test_vpn_purchase/test_promo_code_application.py`
- `tests/ad-hoc/tests/test_yookassa_integration.py` → есть `tests/integration/test_payments/test_yookassa_flow.py`
- `tests/ad-hoc/tests/test_yookassa_payment.py` → дублирует тесты YooKassa
- `tests/ad-hoc/tests/test_yookassa_webhook_fix.py` → дублирует тесты YooKassa
- `tests/ad-hoc/tests/test_extend_keyboard.py` → есть `tests/unit/test_bot/test_keyboard_generation.py`
- `tests/ad-hoc/tests/test_keys_management_keyboard.py` → дублирует тесты клавиатур

**Действия:**

1. Сравнить каждый файл с существующими тестами для подтверждения дублирования
2. Удалить подтвержденные дубликаты
3. Задокументировать причины удаления

### 1.2. Одноразовые/специфичные тесты (оставить в ad-hoc)

Эти тесты для конкретных случаев и не должны запускаться автоматически:

**Файлы для сохранения в ad-hoc:**

- `test_check_payment_30a29d3e.py`, `test_fix_payment_30a29d3e.py` - проверки конкретных платежей
- `test_payment_233_on_server.py` - проверка конкретного платежа
- `test_create_key_user_2206685.py`, `test_real_scenario_2206685.py` - тесты для конкретного пользователя
- `test_real_user.py` - тест с реальным пользователем
- `test_manual_yookassa_fix.py`, `test_manual_yookassa_fix_payment.py` - ручные исправления
- `test_check_payment_status.py`, `test_check_yookassa_payment.py` - проверки статусов платежей
- `test_compare_db.py`, `test_compare_versions.py` - сравнение БД
- `test_wal_sync.py` - одноразовая проверка WAL режима
- `test_config_fix.py` - одноразовое исправление конфигурации
- `test_get_setting.py` - одноразовая проверка настроек
- `test_copy_plans.py` - одноразовое копирование планов
- `test_group_edit_fix.py` - одноразовое исправление групп
- `test_host_code_search.py` - одноразовый поиск хостов
- `test_encoding.py` - одноразовая проверка кодировки
- `test_telegram_logger.py` - одноразовая проверка логгера
- `test_blockquote_fix.py` - одноразовое исправление blockquote
- `test_docker_promo.py` - одноразовый тест промокода в Docker
- `test_promo_fix.py` - одноразовое исправление промокодов
- `test_yookassa_reconfiguration.py` - одноразовая переконфигурация YooKassa

**Действия:**

1. Убедиться, что эти файлы остаются в `tests/ad-hoc/tests/`
2. Проверить, что они правильно игнорируются в `pytest.ini` и `conftest.py`

### 1.3. Потенциально полезные тесты (требуют анализа)

Эти тесты могут быть полезны, но требуют проверки на дублирование:

**Файлы для анализа:**

- `test_timezone_functions.py` - проверяет функции timezone в database.py
- `test_database_indexes.py` - проверяет создание индексов БД
- `test_user_cabinet_token.py` - проверяет создание токенов для личного кабинета
- `test_timezone_change.py` - проверяет изменение timezone пользователя
- `test_autorenew_notice.py` - проверяет уведомления об автопродлении
- `test_new_user_promo.py` - проверяет применение промокода для нового пользователя
- `test_extend_all.py`, `test_extend_db_subscription_link.py`, `test_extend_process_payment.py`, `test_extend_provision_mode.py`, `test_extend_yookassa_logic.py` - тесты для расширения функциональности
- `test_payment_method_normalized.py` - нормализация методов платежа
- `test_permanent_token.py` - постоянные токены
- `test_user_cabinet_domain.py` - домен личного кабинета
- `test_keyboard_webapp.py` - клавиатура с WebApp
- `test_web_interface_deeplink.py` - deeplink для веб-интерфейса
- `test_cabinet_token_functionality.py` - функциональность токенов кабинета

**Действия:**

1. Для каждого файла проверить наличие аналогичных тестов в `tests/unit/`, `tests/integration/`, `tests/e2e/`
2. Определить уникальность функциональности
3. Решить, стоит ли переносить в автотесты

## Этап 2: Удаление дубликатов

### 2.1. Подготовка к удалению

1. Создать резервную копию `tests/ad-hoc/tests/` (опционально, так как в git)
2. Задокументировать список удаляемых файлов с причинами

### 2.2. Удаление файлов

Удалить файлы из раздела 1.1 после подтверждения дублирования:

- Использовать `delete_file` для каждого файла
- Обновить `.gitignore` если необходимо

### 2.3. Проверка после удаления

1. Убедиться, что `pytest.ini` и `conftest.py` корректно игнорируют `ad-hoc`
2. Запустить `docker compose exec monitoring pytest --collect-only` для проверки, что удаленные тесты не собираются

## Этап 3: Анализ потенциально полезных тестов

### 3.1. Сравнение с существующими тестами

Для каждого файла из раздела 1.3:

1. Найти аналогичные тесты через `grep` и `codebase_search`
2. Сравнить покрытие функциональности
3. Определить, добавляет ли тест из ad-hoc уникальную ценность

### 3.2. Принятие решений

Для каждого теста:

- **Перенести** - если тест уникален и полезен для регрессионного тестирования
- **Удалить** - если полностью дублирует существующие тесты
- **Оставить в ad-hoc** - если это одноразовый/специфичный тест

## Этап 4: Перенос и рефакторинг тестов

### 4.1. Определение целевых каталогов

Для тестов, которые решено перенести:

**Unit-тесты (`tests/unit/`):**

- `test_timezone_functions.py` → `tests/unit/test_database/test_timezone_operations.py`
- `test_database_indexes.py` → `tests/unit/test_database/test_database_indexes.py`
- `test_user_cabinet_token.py` → `tests/unit/test_user_cabinet/test_cabinet_tokens.py` (если уникален)
- `test_payment_method_normalized.py` → `tests/unit/test_utils/test_payment_methods.py` (если уникален)

**Интеграционные тесты (`tests/integration/`):**

- `test_timezone_change.py` → проверить, не дублирует ли `tests/integration/test_timezone_integration.py`
- `test_autorenew_notice.py` → `tests/integration/test_auto_renewal/test_notification_buttons_flow.py` (если уникален)
- `test_new_user_promo.py` → `tests/integration/test_vpn_purchase/` (если уникален)

### 4.2. Рефакторинг тестов

Для каждого переносимого теста:

1. **Добавить импорты:**
   ```python
   import pytest
   import allure
   from pathlib import Path
   ```

2. **Добавить Allure аннотации:**

            - `@allure.epic("...")` - согласно правилам из `testing-rules.mdc`
            - `@allure.feature("...")` - согласно правилам из `testing-rules.mdc`
            - `@allure.label("package", "...")` - путь к модулю
            - `@allure.title("...")` - краткое описание на русском
            - `@allure.description("""...""")` - структурированное описание
            - `@allure.severity(allure.severity_level.NORMAL)` - уровень важности
            - `@allure.tag("...")` - теги для фильтрации
            - `@allure.story("...")` - для интеграционных/E2E тестов

3. **Добавить pytest маркеры:**

            - `@pytest.mark.unit` / `@pytest.mark.integration` / `@pytest.mark.e2e`
            - `@pytest.mark.database` - если использует БД
            - `@pytest.mark.bot` - если тестирует бота
            - `@pytest.mark.asyncio` - для async тестов

4. **Использовать фикстуры из conftest.py:**

            - Заменить прямое подключение к БД на `temp_db`
            - Использовать `mock_bot`, `mock_xui_api`, `mock_yookassa` вместо реальных API

5. **Привести к стандартам именования:**

            - Имена функций/классов на английском
            - Docstrings на русском
            - Соответствие паттернам `test_*` и `Test*`

6. **Структурировать тесты:**

            - Использовать `allure.step()` для сложных тестов
            - Использовать `allure.attach()` для важных данных
            - Следовать паттерну Arrange-Act-Assert

### 4.3. Пример рефакторинга

Пример преобразования `test_timezone_functions.py`:

**До:**

```python
def test_feature_flag():
    enabled = is_timezone_feature_enabled()
    assert not enabled
```

**После:**

```python
@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Операции с timezone")
@allure.label("package", "src.shop_bot.database")
class TestTimezoneOperations:
    @allure.title("Проверка feature flag для timezone")
    @allure.description("""
    Проверяет, что feature flag для timezone по умолчанию выключен.
    
    **Что проверяется:**
 - Функция is_timezone_feature_enabled() возвращает False по умолчанию
    
    **Ожидаемый результат:**
    Feature flag должен быть выключен (False)
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timezone", "feature_flag", "unit", "database")
    def test_feature_flag(self, temp_db):
        """Тест feature flag для timezone"""
        with allure.step("Проверка feature flag"):
            enabled = is_timezone_feature_enabled()
            allure.attach(str(enabled), "Значение feature flag", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert not enabled, "Feature flag должен быть выключен по умолчанию"
```

## Этап 5: Проверка и валидация

### 5.1. Проверка структуры

1. Убедиться, что все перенесенные тесты находятся в правильных каталогах
2. Проверить, что `pytest.ini` корректно настроен
3. Проверить, что `conftest.py` правильно игнорирует `ad-hoc`

### 5.2. Запуск тестов

1. Запустить `docker compose exec monitoring pytest --collect-only` для проверки сбора тестов
2. Запустить `docker compose exec monitoring pytest tests/unit/ -m unit` для проверки unit-тестов
3. Запустить `docker compose exec monitoring pytest tests/integration/ -m integration` для проверки интеграционных тестов
4. Убедиться, что тесты из `ad-hoc` не запускаются

### 5.3. Проверка Allure отчетов

1. Запустить тесты с генерацией Allure отчетов
2. Проверить, что все перенесенные тесты имеют корректные аннотации
3. Проверить группировку тестов по epic, feature, story

## Этап 6: Документация

### 6.1. Обновление CHANGELOG.md

Добавить запись о реорганизации тестов:

- Удаление дубликатов
- Перенос полезных тестов
- Приведение к стандартам

### 6.2. Обновление документации (если необходимо)

Если были изменения в структуре тестов, обновить:

- `docs/guides/testing/` - если есть документация по тестированию
- `testing-rules.mdc` - если нужно добавить примеры

## Критерии успеха

1. Все дубликаты удалены
2. Полезные тесты перенесены в правильные каталоги
3. Все перенесенные тесты имеют Allure аннотации и pytest маркеры
4. Все тесты используют фикстуры из `conftest.py`
5. Тесты из `ad-hoc` не запускаются автоматически
6. Все тесты проходят успешно
7. Allure отчеты корректно отображают структуру тестов

## Риски и митигация

1. **Риск:** Удаление уникального теста

            - **Митигация:** Тщательный анализ каждого теста перед удалением

2. **Риск:** Поломка тестов при рефакторинге

            - **Митигация:** Постепенный рефакторинг с проверкой после каждого шага

3. **Риск:** Потеря важной функциональности

            - **Митигация:** Сравнение покрытия до и после реорганизации

### To-dos

- [ ] Проанализировать тесты из ad-hoc на дублирование с существующими автотестами. Сравнить каждый файл из списка дубликатов с существующими тестами для подтверждения.
- [ ] Удалить подтвержденные дубликаты из tests/ad-hoc/tests/ и tests/ad-hoc/. Задокументировать причины удаления.
- [ ] Проанализировать потенциально полезные тесты (test_timezone_functions.py, test_database_indexes.py и др.) на уникальность и необходимость переноса.
- [ ] Перенести test_timezone_functions.py в tests/unit/test_database/test_timezone_operations.py с добавлением Allure аннотаций, pytest маркеров и использованием фикстур.
- [ ] Перенести test_database_indexes.py в tests/unit/test_database/test_database_indexes.py с добавлением Allure аннотаций и pytest маркеров.
- [ ] Перенести остальные полезные тесты (test_user_cabinet_token.py, test_autorenew_notice.py и др.) в соответствующие каталоги с рефакторингом.
- [ ] Проверить структуру тестов, запустить pytest --collect-only и убедиться, что тесты из ad-hoc не собираются. Запустить тесты для проверки работоспособности.
- [ ] Обновить CHANGELOG.md с записью о реорганизации тестов, указав удаленные дубликаты и перенесенные тесты.