# Справочник по тестированию Dark Maximus

> **Дата последней редакции:** 15.11.2025 16:44

## Обзор

Справочная документация по pytest, Allure Framework и системе тестирования проекта Dark Maximus.

## Конфигурация pytest

### pytest.ini

Основная конфигурация pytest находится в `pytest.ini`:

```ini
[pytest]
# Пути для поиска тестов
testpaths = tests

# Паттерны для поиска тестовых файлов
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Исключить одноразовые скрипты из ad-hoc
norecursedirs = ad-hoc

# Опции pytest
addopts = 
    -v                          # Вербозный вывод
    --tb=short                  # Короткий traceback
    --strict-markers            # Строгий режим маркеров
    --disable-warnings          # Отключить предупреждения
    --alluredir=allure-results  # Директория для Allure результатов
    --ignore=tests/ad-hoc       # Игнорировать ad-hoc

# Маркеры для категоризации тестов
markers =
    unit: Unit tests (70% coverage)
    integration: Integration tests (20% coverage)
    e2e: End-to-end tests (10% coverage)
    database: Database tests
    bot: Bot tests
    slow: Slow running tests
    asyncio: Async tests

# Настройки asyncio для async тестов
asyncio_mode = auto
```

### Параметры addopts

- **`-v, --verbose`** — вербозный вывод
- **`--tb=short`** — короткий traceback (short, long, line, no)
- **`--strict-markers`** — строгий режим маркеров (ошибка при неизвестном маркере)
- **`--disable-warnings`** — отключить предупреждения
- **`--alluredir=allure-results`** — директория для результатов Allure
- **`--ignore=tests/ad-hoc`** — игнорировать указанные пути

## Маркеры pytest

### Доступные маркеры

Все маркеры должны быть зарегистрированы в `pytest.ini`:

```ini
markers =
    unit: Unit tests (70% coverage)
    integration: Integration tests (20% coverage)
    e2e: End-to-end tests (10% coverage)
    database: Database tests
    bot: Bot tests
    slow: Slow running tests
    asyncio: Async tests
```

### Использование маркеров

```python
# Один маркер
@pytest.mark.unit
def test_example():
    pass

# Несколько маркеров
@pytest.mark.unit
@pytest.mark.database
@pytest.mark.slow
def test_complex_operation():
    pass

# Маркер с параметрами
@pytest.mark.parametrize("value", [1, 2, 3])
def test_parametrized(value):
    pass
```

### Запуск тестов по маркерам

```bash
# Все unit-тесты
pytest -m unit

# Все тесты с маркером database
pytest -m database

# Комбинация (unit И database)
pytest -m "unit and database"

# Комбинация (unit ИЛИ integration)
pytest -m "unit or integration"

# Исключение (unit БЕЗ slow)
pytest -m "unit and not slow"
```

## Фикстуры pytest

### Общие фикстуры (conftest.py)

Все общие фикстуры находятся в `tests/conftest.py`:

#### temp_db

Создает временную SQLite БД с полной структурой таблиц.

```python
@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Создает временную БД для тестов с полной структурой таблиц"""
    # Создает временную БД
    # Патчит DB_FILE для использования временной БД
    # Возвращает Path к временной БД
```

**Использование:**

```python
@pytest.mark.unit
@pytest.mark.database
def test_user_operations(temp_db):
    """Тест использует временную БД"""
    # temp_db - Path к временной БД
    db = database.Database(str(temp_db))
    user = db.register_user_if_not_exists(123456789, "test_user", None, "Test User")
    assert user is not None
```

**Важно:** Всегда используйте `temp_db` вместо реальной БД `users.db`!

#### mock_bot

Мок для aiogram.Bot с асинхронными методами.

```python
@pytest.fixture
def mock_bot():
    """Мок для aiogram.Bot"""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.edit_message_text = AsyncMock()
    bot.answer_callback_query = AsyncMock()
    bot.delete_message = AsyncMock()
    return bot
```

**Использование:**

```python
@pytest.mark.unit
@pytest.mark.bot
def test_send_message(mock_bot):
    """Тест отправки сообщения"""
    send_welcome_message(mock_bot, 123456789)
    mock_bot.send_message.assert_called_once()
```

#### mock_xui_api

Мок для py3xui.Api.

```python
@pytest.fixture
def mock_xui_api():
    """Мок для py3xui.Api"""
    api = MagicMock()
    api.login = MagicMock()
    api.inbound.get_list = MagicMock(return_value=[mock_inbound])
    api.inbound.get_by_id = MagicMock(return_value=mock_inbound)
    api.inbound.update = MagicMock()
    api.client.update = MagicMock()
    api.client.delete = MagicMock()
    return api
```

**Использование:**

```python
@pytest.mark.unit
def test_create_key(mock_xui_api):
    """Тест создания ключа"""
    key = create_vpn_key(mock_xui_api, 123456789, "test-plan")
    assert key is not None
```

#### mock_yookassa

Мок для YooKassa Payment.

```python
@pytest.fixture
def mock_yookassa():
    """Мок для YooKassa Payment"""
    payment = MagicMock()
    payment.create = MagicMock(return_value={
        'id': 'test_payment_id',
        'status': 'pending',
        'confirmation': {'confirmation_url': 'https://yookassa.ru/test'}
    })
    return payment
```

**Использование:**

```python
@pytest.mark.integration
def test_yookassa_payment(mock_yookassa):
    """Тест создания платежа YooKassa"""
    payment = mock_yookassa.create(amount=100.0)
    assert payment['id'] == 'test_payment_id'
```

#### mock_cryptobot

Мок для CryptoBot API.

```python
@pytest.fixture
def mock_cryptobot():
    """Мок для CryptoBot API"""
    api = MagicMock()
    api.create_invoice = AsyncMock(return_value={
        'result': {
            'invoice_id': 'test_invoice_id',
            'pay_url': 'https://crypt.bot/test',
            'status': 'active'
        }
    })
    api.get_invoices = AsyncMock(return_value={
        'result': {
            'items': [{
                'invoice_id': 'test_invoice_id',
                'status': 'paid',
                'amount': '100.0'
            }]
        }
    })
    return api
```

#### mock_ton_connect

Мок для TON Connect.

```python
@pytest.fixture
def mock_ton_connect():
    """Мок для TON Connect"""
    connector = MagicMock()
    connector.connected = False
    connector.account = MagicMock()
    connector.account.address = 'test_address'
    connector.send_transaction = AsyncMock(return_value={
        'boc': 'test_boc',
        'transaction': {'hash': 'test_hash'}
    })
    connector.connect = AsyncMock()
    connector.disconnect = AsyncMock()
    return connector
```

#### mock_heleket

Мок для Heleket API.

```python
@pytest.fixture
def mock_heleket():
    """Мок для Heleket API"""
    api = MagicMock()
    api.create_invoice = AsyncMock(return_value={
        'id': 'test_invoice_id',
        'pay_url': 'https://heleket.com/test',
        'status': 'pending'
    })
    api.get_invoice = AsyncMock(return_value={
        'id': 'test_invoice_id',
        'status': 'paid',
        'amount': 100.0
    })
    return api
```

#### sample_host

Тестовый хост для БД.

```python
@pytest.fixture
def sample_host():
    """Тестовый хост для БД"""
    return {
        'host_name': 'test-host',
        'host_url': 'https://test.example.com:8443/configpanel',
        'host_username': 'admin',
        'host_pass': 'password',
        'host_inbound_id': 1,
        'host_code': 'test-code'
    }
```

#### sample_plan

Тестовый план для БД.

```python
@pytest.fixture
def sample_plan():
    """Тестовый план для БД"""
    return {
        'plan_id': 1,
        'host_name': 'test-host',
        'plan_name': 'Test Plan',
        'months': 1,
        'days': 0,
        'hours': 0,
        'price': 100.0,
        'traffic_gb': 0.0
    }
```

#### sample_promo_code

Тестовый промокод для БД.

```python
@pytest.fixture
def sample_promo_code():
    """Тестовый промокод для БД"""
    return {
        'promo_id': 1,
        'code': 'TESTPROMO',
        'bot': 'test_bot',
        'discount_amount': 10.0,
        'discount_percent': 0.0,
        'discount_bonus': 0.0,
        'is_active': 1,
        'usage_limit_per_bot': 1
    }
```

### Встроенные фикстуры pytest

- **`tmp_path`** — временная директория (Path)
- **`tmpdir`** — временная директория (LegacyPath)
- **`monkeypatch`** — патчинг переменных и функций
- **`capsys`** — захват stdout/stderr
- **`caplog`** — захват логов

## Команды pytest CLI

### Основные команды

```bash
# Запустить все тесты
pytest

# Запустить конкретный файл
pytest tests/unit/test_database/test_user_operations.py

# Запустить конкретный тест
pytest tests/unit/test_database/test_user_operations.py::test_register_user_if_not_exists

# Запустить конкретный класс
pytest tests/unit/test_database/test_user_operations.py::TestUserOperations
```

### Параметры вывода

```bash
# Вербозность
-v, --verbose              # Вербозный вывод
-vv                        # Очень вербозный вывод
-q, --quiet                # Тихий режим

# Вывод print()
-s, --capture=no           # Показать print() в тестах

# Traceback
--tb=short                 # Короткий traceback (по умолчанию)
--tb=long                  # Длинный traceback
--tb=line                  # Однострочный traceback
--tb=no                    # Без traceback
```

### Параметры остановки

```bash
# Остановка на первой ошибке
-x, --exitfirst

# Остановиться после N ошибок
--maxfail=N
```

### Параметры выбора тестов

```bash
# Запустить тесты, соответствующие выражению
-k EXPRESSION

# Запустить тесты с маркером
-m MARKEXPR

# Показать список тестов без запуска
--collect-only
```

### Параметры повторного запуска

```bash
# Запустить только упавшие тесты с последнего запуска
--lf, --last-failed

# Запустить упавшие тесты первыми
--ff, --failed-first
```

### Параметры Allure

```bash
# Директория для результатов Allure
--alluredir=DIR

# По умолчанию: allure-results
```

## Allure Framework

### Конфигурация

В `pytest.ini` настроена интеграция с Allure:

```ini
[pytest]
addopts = 
    --alluredir=allure-results  # Директория для результатов
```

### Декораторы Allure

```python
import allure

# Критичность теста
@allure.severity(allure.severity_level.CRITICAL)

# Описание теста
@allure.description("Тест регистрации нового пользователя")

# Кастомная метка
@allure.label("component", "database")

# Заголовок теста в отчете
@allure.title("Регистрация пользователя")
```

### Уровни критичности

```python
allure.severity_level.BLOCKER   # Блокирующий
allure.severity_level.CRITICAL  # Критичный
allure.severity_level.NORMAL    # Обычный
allure.severity_level.MINOR     # Маловажный
allure.severity_level.TRIVIAL   # Тривиальный
```

### Шаги (Steps)

```python
import allure

def test_with_steps(temp_db):
    """Тест с шагами"""
    with allure.step("Регистрация пользователя"):
        register_user_if_not_exists(123456789, "test_user", None, "Test User")
    
    with allure.step("Проверка создания пользователя"):
        user = get_user(123456789)
        assert user is not None
```

### Вложения (Attachments)

```python
import allure

def test_with_attachment(temp_db):
    """Тест с вложениями"""
    user = get_user(123456789)
    
    # Сохранить JSON
    import json
    allure.attach(
        json.dumps(user, indent=2),
        "User data",
        allure.attachment_type.JSON
    )
    
    # Сохранить текст
    allure.attach("Лог выполнения", "text/plain")
    
    # Сохранить PNG
    allure.attach("screenshot.png", allure.attachment_type.PNG)
```

### Типы вложений

```python
allure.attachment_type.TEXT      # Текст
allure.attachment_type.HTML      # HTML
allure.attachment_type.JSON      # JSON
allure.attachment_type.XML       # XML
allure.attachment_type.PNG       # PNG изображение
allure.attachment_type.JPG       # JPG изображение
allure.attachment_type.SVG       # SVG изображение
allure.attachment_type.PDF       # PDF документ
allure.attachment_type.MP4       # MP4 видео
```

## Категории дефектов Allure

### Конфигурация

Файл `allure-categories.json` содержит правила автоматической категоризации дефектов:

```json
[
  {
    "name": "Product defects",
    "matchedStatuses": ["failed"],
    "messageRegex": ".*AssertionError.*",
    "traceRegex": ".*assert.*is not None.*|.*assert.*==.*|.*assert.*!=.*"
  },
  {
    "name": "Test defects",
    "matchedStatuses": ["broken"],
    "messageRegex": ".*RuntimeError.*|.*TypeError.*|.*OperationalError.*|.*AttributeError.*|.*ValueError.*|.*KeyError.*"
  },
  {
    "name": "Test defects",
    "matchedStatuses": ["failed"],
    "messageRegex": ".*unexpected keyword argument.*|.*no such table.*|.*got an unexpected.*"
  }
]
```

### Типы дефектов

- **Product defects** — реальные баги в коде
- **Test defects** — проблемы в самих тестах

### Применение категорий

Категории применяются автоматически при генерации отчетов Allure Service.

## Allure Service API

### Доступ к API

- **Swagger UI:** `http://localhost:50005`
- **API проектов:** `http://localhost:50005/allure-docker-service/projects`

### Основные endpoints

```
GET  /allure-docker-service/projects
GET  /allure-docker-service/projects/{project}/reports
GET  /allure-docker-service/projects/{project}/reports/latest
POST /allure-docker-service/projects/{project}/generate-report
```

## Работа с временной БД

### Использование temp_db

```python
@pytest.mark.unit
@pytest.mark.database
def test_user_operations(temp_db):
    """Тест использует временную БД"""
    # temp_db - Path к временной БД
    from shop_bot.data_manager import database
    
    # Используем временную БД
    db = database.Database(str(temp_db))
    
    # Выполняем операции
    user = db.register_user_if_not_exists(123456789, "test_user", None, "Test User")
    
    # Проверяем результат
    assert user is not None
```

### Структура временной БД

Временная БД создается с полной структурой таблиц:

- `users` — пользователи
- `vpn_keys` — ключи VPN
- `transactions` — транзакции
- `promo_codes` — промокоды
- `promo_code_usage` — использование промокодов
- `plans` — планы VPN
- `xui_hosts` — хосты 3X-UI
- `notifications` — уведомления
- `user_tokens` — токены пользователей
- `user_groups` — группы пользователей
- `bot_settings` — настройки бота
- `backup_settings` — настройки резервного копирования
- `migration_history` — история миграций

## Асинхронные тесты

### Использование @pytest.mark.asyncio

```python
import pytest

@pytest.mark.asyncio
@pytest.mark.unit
async def test_async_function(mock_bot):
    """Асинхронный тест"""
    await send_welcome_message(mock_bot, 123456789)
    mock_bot.send_message.assert_called_once()
```

### AsyncMock для моков

```python
from unittest.mock import AsyncMock

@pytest.fixture
def mock_bot():
    """Мок с асинхронными методами"""
    bot = MagicMock()
    bot.send_message = AsyncMock()  # Асинхронный метод
    return bot
```

## Параметризация тестов

### @pytest.mark.parametrize

```python
@pytest.mark.parametrize("user_id,username,expected", [
    (123456789, "user1", True),
    (123456790, "user2", True),
    (None, "user3", False),
])
@pytest.mark.unit
@pytest.mark.database
def test_register_user(temp_db, user_id, username, expected):
    """Параметризованный тест"""
    if expected:
        register_user_if_not_exists(user_id, username, None, "Test User")
        user = get_user(user_id)
        assert user is not None
    else:
        with pytest.raises(ValueError):
            register_user_if_not_exists(user_id, username, None, "Test User")
```

## Обработка исключений

### pytest.raises

```python
import pytest

@pytest.mark.unit
@pytest.mark.database
def test_register_user_with_invalid_data(temp_db):
    """Тест обработки исключения"""
    with pytest.raises(ValueError, match="Invalid user_id"):
        register_user_if_not_exists(None, "user", None, "User")
```

### Типы исключений

```python
# Проверка типа исключения
with pytest.raises(ValueError):
    function_that_raises_value_error()

# Проверка сообщения исключения
with pytest.raises(ValueError, match="Invalid"):
    function_that_raises_value_error()

# Проверка нескольких исключений
with pytest.raises((ValueError, TypeError)):
    function_that_raises_exception()
```

## Полезные ресурсы

- [Официальная документация pytest](https://docs.pytest.org/)
- [Официальная документация Allure](https://github.com/allure-framework/allure-python)
- [Best Practices pytest](https://docs.pytest.org/en/stable/explanation/goodpractices.html)
- [Структура тестов](../guides/testing/testing-structure.md)
- [Запуск тестов](../guides/testing/running-tests.md)
- [Best Practices](../guides/testing/best-practices.md)

## См. также

- [Руководства по тестированию](../guides/testing/) — практические инструкции
- [Архитектура проекта](../architecture/project-info.md) — общая информация

---

**Версия:** 1.0  
**Последнее обновление:** 15.11.2025 16:44  
**Автор:** Dark Maximus Team

