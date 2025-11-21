# Best Practices для написания тестов в Dark Maximus

> **Дата последней редакции:** 15.11.2025 16:44

## Обзор

Этот документ описывает лучшие практики написания тестов в проекте Dark Maximus, основанные на официальных рекомендациях pytest и опыте команды разработки.

## Организация тестов

### Структура тестов

Следуйте структуре проекта:

```
tests/
├── unit/                    # Unit-тесты (70% покрытия)
│   ├── test_database/      # Тесты операций с БД
│   ├── test_bot/           # Тесты бота
│   └── test_utils/         # Тесты утилит
├── integration/            # Интеграционные тесты (20%)
└── e2e/                    # E2E тесты (10%)
```

**Принципы:**
- Тесты находятся отдельно от исходного кода (`tests/` вне `src/`)
- Тесты организованы по модулям исходного кода
- Каждый тип тестов в своем каталоге

### Именование

**Файлы тестов:**
- Начинаются с `test_`: `test_user_operations.py`
- Отражают модуль и функциональность: `test_<module>_<functionality>.py`

**Функции тестов:**
- Начинаются с `test_`: `test_register_user_if_not_exists`
- Описывают что тестируется: `test_<what>_<condition>_<expected>`

**Классы тестов:**
- Начинаются с `Test`: `TestUserOperations`
- Отражают группу тестов: `Test<ModuleName>`

**Примеры:**

```python
# Файл: test_user_operations.py
class TestUserOperations:
    def test_register_user_if_not_exists(self, temp_db):
        """Тест регистрации нового пользователя"""
        pass
    
    def test_register_user_twice(self, temp_db):
        """Тест повторной регистрации пользователя"""
        pass
```

## Использование фикстур

### Всегда используйте `temp_db`

**КРИТИЧЕСКИ ВАЖНО:** Всегда используйте фикстуру `temp_db` вместо реальной БД `users.db`!

```python
# ✅ Правильно
@pytest.mark.unit
@pytest.mark.database
def test_user_creation(temp_db):
    """Тест создания пользователя"""
    db = database.Database(str(temp_db))
    user = db.register_user_if_not_exists(123456789, "test_user", None, "Test User")
    assert user is not None

# ❌ Неправильно
def test_user_creation():
    """Использует реальную БД - НЕ ДЕЛАТЬ ТАК!"""
    user = register_user_if_not_exists(123456789, "test_user", None, "Test User")
    assert user is not None
```

### Использование моков для внешних сервисов

Всегда используйте моки для внешних сервисов:

```python
# ✅ Правильно
@pytest.mark.unit
@pytest.mark.bot
def test_send_message(mock_bot):
    """Тест отправки сообщения"""
    from shop_bot.bot.handlers import send_welcome_message
    
    send_welcome_message(mock_bot, 123456789)
    
    mock_bot.send_message.assert_called_once()

# ❌ Неправильно
def test_send_message():
    """Использует реальный Telegram API - НЕ ДЕЛАТЬ ТАК!"""
    bot = Bot(token="real_token")
    send_welcome_message(bot, 123456789)
```

### Доступные фикстуры

Все общие фикстуры находятся в `tests/conftest.py`:

- **`temp_db`** — временная SQLite БД с полной структурой таблиц
- **`mock_bot`** — мок для aiogram.Bot
- **`mock_xui_api`** — мок для py3xui.Api
- **`mock_yookassa`** — мок для YooKassa Payment
- **`mock_cryptobot`** — мок для CryptoBot API
- **`mock_ton_connect`** — мок для TON Connect
- **`mock_heleket`** — мок для Heleket API
- **`sample_host`** — тестовый хост для БД
- **`sample_plan`** — тестовый план для БД
- **`sample_promo_code`** — тестовый промокод для БД

### Создание собственных фикстур

Если нужно создать фикстуру для конкретного модуля:

```python
# tests/unit/test_database/conftest.py
@pytest.fixture
def sample_user(temp_db):
    """Фикстура для тестового пользователя"""
    from shop_bot.data_manager.database import register_user_if_not_exists
    
    user_id = 123456789
    register_user_if_not_exists(user_id, "test_user", None, "Test User")
    return user_id
```

## Изоляция тестов

### Независимость тестов

Каждый тест должен быть независимым:

```python
# ✅ Правильно
@pytest.mark.unit
@pytest.mark.database
def test_register_user_1(temp_db):
    """Тест 1 - независимый"""
    register_user_if_not_exists(123456789, "user1", None, "User 1")
    user = get_user(123456789)
    assert user is not None

@pytest.mark.unit
@pytest.mark.database
def test_register_user_2(temp_db):
    """Тест 2 - независимый"""
    register_user_if_not_exists(123456790, "user2", None, "User 2")
    user = get_user(123456790)
    assert user is not None

# ❌ Неправильно
user_id = None  # Глобальная переменная - НЕ ДЕЛАТЬ ТАК!

@pytest.mark.unit
@pytest.mark.database
def test_register_user_1(temp_db):
    """Тест 1 - зависит от глобальной переменной"""
    global user_id
    user_id = 123456789
    register_user_if_not_exists(user_id, "user1", None, "User 1")

@pytest.mark.unit
@pytest.mark.database
def test_register_user_2(temp_db):
    """Тест 2 - зависит от test_register_user_1"""
    # Использует user_id из предыдущего теста - НЕ ДЕЛАТЬ ТАК!
    user = get_user(user_id)
    assert user is not None
```

### Очистка состояния

Фикстуры автоматически очищают состояние после каждого теста:

```python
@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Создает временную БД для тестов"""
    db_path = tmp_path / "test_users.db"
    # ... создание БД ...
    yield db_path
    # Автоматическая очистка после теста
```

## Маркеры pytest

### Обязательные маркеры

Все тесты должны иметь соответствующий маркер:

```python
# Unit-тесты
@pytest.mark.unit
@pytest.mark.database
def test_user_creation(temp_db):
    pass

# Интеграционные тесты
@pytest.mark.integration
def test_payment_flow(temp_db, mock_bot):
    pass

# E2E тесты
@pytest.mark.e2e
def test_full_user_scenario(temp_db):
    pass
```

### Доступные маркеры

Из `pytest.ini`:

- **`@pytest.mark.unit`** — Unit-тесты (70% покрытия)
- **`@pytest.mark.integration`** — Интеграционные тесты (20% покрытия)
- **`@pytest.mark.e2e`** — E2E тесты (10% покрытия)
- **`@pytest.mark.database`** — Тесты работы с БД
- **`@pytest.mark.bot`** — Тесты бота
- **`@pytest.mark.slow`** — Медленные тесты
- **`@pytest.mark.asyncio`** — Асинхронные тесты

### Комбинирование маркеров

```python
# Несколько маркеров
@pytest.mark.unit
@pytest.mark.database
@pytest.mark.slow
def test_complex_database_operation(temp_db):
    pass
```

### Запуск тестов по маркерам

```bash
# Только unit-тесты
pytest -m unit

# Только тесты с маркером database
pytest -m database

# Комбинация маркеров (unit И database)
pytest -m "unit and database"

# Комбинация маркеров (unit ИЛИ integration)
pytest -m "unit or integration"

# Исключение маркеров (unit БЕЗ slow)
pytest -m "unit and not slow"
```

## Структура тестов (AAA Pattern)

Используйте паттерн AAA (Arrange, Act, Assert):

```python
@pytest.mark.unit
@pytest.mark.database
def test_register_user_if_not_exists(temp_db):
    """Тест регистрации нового пользователя"""
    # Arrange: подготавливаем данные
    telegram_id = 123456789
    username = "test_user"
    fullname = "Test User"
    
    # Act: выполняем действие
    register_user_if_not_exists(telegram_id, username, None, fullname)
    
    # Assert: проверяем результат
    user = get_user(telegram_id)
    assert user is not None, "Пользователь должен быть создан"
    assert user['telegram_id'] == telegram_id
    assert user['username'] == username
    assert user['fullname'] == fullname
```

**Принципы:**
- **Arrange:** Подготовка данных и состояния
- **Act:** Выполнение действия, которое тестируется
- **Assert:** Проверка результата

## Именование и документация

### Docstrings для тестов

Всегда добавляйте docstrings для тестов:

```python
@pytest.mark.unit
@pytest.mark.database
def test_register_user_if_not_exists(temp_db):
    """Тест регистрации нового пользователя.
    
    Проверяет, что функция register_user_if_not_exists корректно
    создает нового пользователя в БД.
    """
    pass
```

### Описательные сообщения в assert

Используйте описательные сообщения в assert:

```python
# ✅ Правильно
assert user is not None, "Пользователь должен быть создан"
assert user['balance'] == 100.0, f"Баланс должен быть 100.0, получено {user['balance']}"

# ❌ Неправильно
assert user is not None
assert user['balance'] == 100.0
```

## Работа с асинхронными тестами

### Использование `@pytest.mark.asyncio`

Для асинхронных тестов используйте `@pytest.mark.asyncio`:

```python
@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.bot
async def test_send_message_async(mock_bot):
    """Тест асинхронной отправки сообщения"""
    from shop_bot.bot.handlers import send_welcome_message_async
    
    await send_welcome_message_async(mock_bot, 123456789)
    
    mock_bot.send_message.assert_called_once()
```

### Использование `AsyncMock`

Для моков асинхронных функций используйте `AsyncMock`:

```python
from unittest.mock import AsyncMock

@pytest.fixture
def mock_bot():
    """Мок для aiogram.Bot с асинхронными методами"""
    from unittest.mock import MagicMock, AsyncMock
    
    bot = MagicMock()
    bot.send_message = AsyncMock()  # Асинхронный метод
    bot.edit_message_text = AsyncMock()
    return bot
```

## Параметризация тестов

Используйте `@pytest.mark.parametrize` для тестирования разных сценариев:

```python
@pytest.mark.parametrize("user_id,username,expected", [
    (123456789, "user1", True),
    (123456790, "user2", True),
    (None, "user3", False),  # Невалидный user_id
])
@pytest.mark.unit
@pytest.mark.database
def test_register_user(temp_db, user_id, username, expected):
    """Параметризованный тест регистрации пользователя"""
    if expected:
        register_user_if_not_exists(user_id, username, None, "Test User")
        user = get_user(user_id)
        assert user is not None
    else:
        with pytest.raises(ValueError):
            register_user_if_not_exists(user_id, username, None, "Test User")
```

## Обработка исключений

Используйте `pytest.raises` для проверки исключений:

```python
@pytest.mark.unit
@pytest.mark.database
def test_register_user_with_invalid_data(temp_db):
    """Тест регистрации пользователя с невалидными данными"""
    with pytest.raises(ValueError, match="Invalid user_id"):
        register_user_if_not_exists(None, "user", None, "User")
```

## Использование Allure

### Декораторы Allure

Используйте декораторы Allure для улучшения отчетов:

```python
import allure

@allure.severity(allure.severity_level.CRITICAL)
@allure.description("Тест регистрации нового пользователя")
@allure.label("component", "database")
@pytest.mark.unit
@pytest.mark.database
def test_register_user_if_not_exists(temp_db):
    """Тест регистрации пользователя"""
    with allure.step("Регистрация пользователя"):
        register_user_if_not_exists(123456789, "test_user", None, "Test User")
    
    with allure.step("Проверка создания пользователя"):
        user = get_user(123456789)
        assert user is not None
```

### Attachments (вложения)

Добавляйте вложения для отладки:

```python
import allure

@pytest.mark.unit
@pytest.mark.database
def test_with_attachment(temp_db):
    """Тест с вложением"""
    user = get_user(123456789)
    
    # Сохранить JSON данные
    import json
    allure.attach(
        json.dumps(user, indent=2),
        "User data",
        allure.attachment_type.JSON
    )
    
    assert user is not None
```

## Покрытие тестов

### Целевое покрытие

- **Unit-тесты:** ~70% покрытия
- **Интеграционные тесты:** ~20% покрытия
- **E2E тесты:** ~10% покрытия

### Проверка покрытия

```bash
# Запустить тесты с покрытием (требует pytest-cov)
pytest --cov=src --cov-report=html

# Открыть отчет покрытия
open htmlcov/index.html
```

## Рекомендации

### DO (Делать)

1. ✅ Используйте `temp_db` для всех тестов с БД
2. ✅ Используйте моки для внешних сервисов
3. ✅ Добавляйте маркеры ко всем тестам
4. ✅ Используйте структуру AAA (Arrange, Act, Assert)
5. ✅ Добавляйте docstrings к тестам
6. ✅ Используйте описательные сообщения в assert
7. ✅ Делайте тесты независимыми
8. ✅ Используйте параметризацию для похожих тестов

### DON'T (Не делать)

1. ❌ Не используйте реальную БД `users.db` в тестах
2. ❌ Не вызывайте реальные внешние API (Telegram, платежи) без моков
3. ❌ Не используйте глобальные переменные между тестами
4. ❌ Не создавайте зависимости между тестами
5. ❌ Не пишите медленные тесты без маркера `@pytest.mark.slow`
6. ❌ Не оставляйте тесты без маркеров
7. ❌ Не пишите тесты без docstrings
8. ❌ Не используйте "магические" числа без объяснения

## Примеры

### Хороший пример unit-теста

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для операций с пользователями в БД
"""

import pytest
import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import (
    register_user_if_not_exists,
    get_user,
)

@pytest.mark.unit
@pytest.mark.database
class TestUserOperations:
    """Тесты для операций с пользователями"""

    def test_register_user_if_not_exists(self, temp_db):
        """Тест регистрации нового пользователя.
        
        Проверяет, что функция register_user_if_not_exists корректно
        создает нового пользователя в БД.
        """
        # Arrange
        telegram_id = 123456789
        username = "test_user"
        fullname = "Test User"
        
        # Act
        register_user_if_not_exists(telegram_id, username, None, fullname)
        
        # Assert
        user = get_user(telegram_id)
        assert user is not None, "Пользователь должен быть создан"
        assert user['telegram_id'] == telegram_id
        assert user['username'] == username
        assert user['fullname'] == fullname

    def test_register_user_twice(self, temp_db):
        """Тест повторной регистрации пользователя.
        
        Проверяет, что повторная регистрация не дублирует пользователя.
        """
        # Arrange
        telegram_id = 123456790
        username = "test_user2"
        
        # Act
        register_user_if_not_exists(telegram_id, username, None, "Test User 2")
        user1 = get_user(telegram_id)
        register_user_if_not_exists(telegram_id, username, None, "Test User 2")
        user2 = get_user(telegram_id)
        
        # Assert
        assert user1 is not None
        assert user2 is not None
        assert user1['telegram_id'] == user2['telegram_id'], "Пользователь не должен дублироваться"
```

### Хороший пример интеграционного теста

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты для YooKassa
"""

import pytest
from unittest.mock import patch, MagicMock

@pytest.mark.integration
@pytest.mark.database
class TestYooKassaFlow:
    """Интеграционные тесты для YooKassa"""

    def test_full_payment_flow(self, temp_db, mock_bot, sample_host, sample_plan):
        """Тест полного flow от создания платежа до получения ключа.
        
        Проверяет интеграцию между:
        - Созданием платежа в YooKassa
        - Обработкой webhook от YooKassa
        - Созданием VPN ключа
        - Уведомлением пользователя
        """
        # Arrange
        user_id = 123456789
        register_user_if_not_exists(user_id, "test_user", None, "Test User")
        
        # Act
        with patch('shop_bot.modules.yookassa.YooKassa.create_payment') as mock_create:
            mock_create.return_value = {
                'id': 'test_payment_id',
                'status': 'pending',
                'confirmation': {'confirmation_url': 'https://yookassa.ru/test'}
            }
            
            # Симулируем создание платежа
            payment_id = create_yookassa_payment(user_id, sample_plan['plan_id'])
            
            # Симулируем успешный платеж через webhook
            process_yookassa_webhook({
                'event': 'payment.succeeded',
                'object': {'id': payment_id, 'status': 'succeeded'}
            })
        
        # Assert
        key = get_user_keys(user_id)[0]
        assert key is not None, "VPN ключ должен быть создан"
        mock_bot.send_message.assert_called_once()
```

## См. также

- [Структура тестов](testing-structure.md) — организация тестов
- [Запуск тестов](running-tests.md) — инструкции по запуску тестов
- [Allure отчеты](allure-reporting.md) — работа с Allure Framework
- [Справочник по тестированию](../../reference/testing-reference.md) — полный справочник

---

**Версия:** 1.0  
**Последнее обновление:** 15.11.2025 16:44  
**Автор:** Dark Maximus Team

