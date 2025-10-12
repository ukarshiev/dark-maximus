# Правила архитектуры Dark Maximus

## Оглавление
- [Общие принципы](#общие-принципы)
- [Структура проекта](#структура-проекта)
- [Правила кодирования](#правила-кодирования)
- [Паттерны проектирования](#паттерны-проектирования)
- [Управление зависимостями](#управление-зависимостями)
- [Обработка ошибок](#обработка-ошибок)
- [Логирование](#логирование)
- [Тестирование](#тестирование)
- [Безопасность](#безопасность)
- [Производительность](#производительность)

## Общие принципы

### 1. Принцип единственной ответственности (SRP)
Каждый модуль, класс и функция должны иметь только одну причину для изменения.

```python
# ✅ Правильно - класс отвечает только за работу с пользователями
class UserManager:
    def create_user(self, user_data):
        pass
    
    def get_user(self, user_id):
        pass

# ❌ Неправильно - класс смешивает работу с пользователями и платежами
class UserPaymentManager:
    def create_user(self, user_data):
        pass
    
    def process_payment(self, payment_data):
        pass
```

### 2. Принцип открытости/закрытости (OCP)
Модули должны быть открыты для расширения, но закрыты для модификации.

```python
# ✅ Правильно - используем абстракцию для расширения
class PaymentProcessor:
    def process(self, payment_data):
        pass

class YooKassaProcessor(PaymentProcessor):
    def process(self, payment_data):
        # Реализация для YooKassa
        pass

class CryptoBotProcessor(PaymentProcessor):
    def process(self, payment_data):
        # Реализация для CryptoBot
        pass
```

### 3. Принцип подстановки Лисков (LSP)
Объекты производных классов должны заменять объекты базовых классов.

### 4. Принцип разделения интерфейсов (ISP)
Клиенты не должны зависеть от интерфейсов, которые они не используют.

### 5. Принцип инверсии зависимостей (DIP)
Модули высокого уровня не должны зависеть от модулей низкого уровня.

## Структура проекта

### Общая организация
```
src/shop_bot/
├── __init__.py                 # Инициализация пакета
├── __main__.py                 # Точка входа
├── config.py                   # Конфигурация
├── bot_controller.py           # Контроллер бота
├── ton_monitor.py              # Мониторинг TON
├── bot/                        # Telegram Bot
│   ├── __init__.py
│   ├── handlers.py             # Обработчики команд
│   ├── keyboards.py            # Клавиатуры
│   └── middlewares.py          # Промежуточное ПО
├── data_manager/               # Управление данными
│   ├── __init__.py
│   ├── database.py             # Работа с БД
│   └── scheduler.py            # Планировщик
├── modules/                    # Модули интеграции
│   ├── __init__.py
│   └── xui_api.py              # API 3x-ui
└── webhook_server/             # Веб-панель
    ├── __init__.py
    ├── app.py                  # Flask приложение
    ├── templates/              # HTML шаблоны
    └── static/                 # Статические файлы
```

### Правила именования

#### Файлы и каталоги
- Используйте `snake_case` для файлов Python
- Используйте `kebab-case` для HTML/CSS файлов
- Каталоги в `snake_case`

#### Классы
```python
# ✅ Правильно
class UserManager:
    pass

class PaymentProcessor:
    pass

# ❌ Неправильно
class userManager:
    pass

class payment_processor:
    pass
```

#### Функции и переменные
```python
# ✅ Правильно
def get_user_balance(user_id):
    pass

user_balance = 0.0

# ❌ Неправильно
def GetUserBalance(userId):
    pass

userBalance = 0.0
```

#### Константы
```python
# ✅ Правильно
MAX_RETRY_ATTEMPTS = 3
DEFAULT_TIMEOUT = 30

# ❌ Неправильно
maxRetryAttempts = 3
default_timeout = 30
```

## Правила кодирования

### 1. Импорты
```python
# ✅ Правильно - группировка и сортировка
import os
import sys
from datetime import datetime
from typing import Optional, List

import sqlite3
from flask import Flask, request

from shop_bot.config import settings
from shop_bot.data_manager.database import get_user
```

### 2. Документация
```python
def create_user(telegram_id: int, username: str, referrer_id: Optional[int] = None) -> bool:
    """
    Создает нового пользователя в системе.
    
    Args:
        telegram_id: Уникальный ID пользователя в Telegram
        username: Имя пользователя в Telegram
        referrer_id: ID пользователя, который пригласил (опционально)
        
    Returns:
        bool: True если пользователь создан успешно, False в противном случае
        
    Raises:
        DatabaseError: При ошибке работы с базой данных
    """
    pass
```

### 3. Типизация
```python
from typing import Optional, List, Dict, Union

def get_user_keys(user_id: int) -> List[Dict[str, Union[str, int, float]]]:
    """Возвращает список ключей пользователя с типизацией."""
    pass

def process_payment(
    amount: float, 
    currency: str, 
    payment_method: str
) -> Optional[Dict[str, str]]:
    """Обрабатывает платеж с указанием типов."""
    pass
```

### 4. Обработка исключений
```python
# ✅ Правильно - конкретные исключения
try:
    result = database_operation()
except sqlite3.IntegrityError as e:
    logger.error(f"Ошибка целостности данных: {e}")
    return False
except sqlite3.OperationalError as e:
    logger.error(f"Ошибка операции с БД: {e}")
    return False
except Exception as e:
    logger.error(f"Неожиданная ошибка: {e}")
    return False

# ❌ Неправильно - общий except
try:
    result = database_operation()
except Exception as e:
    logger.error(f"Ошибка: {e}")
    return False
```

## Паттерны проектирования

### 1. Singleton для конфигурации
```python
class Config:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.load_settings()
            self.initialized = True
```

### 2. Factory для платежных систем
```python
class PaymentProcessorFactory:
    @staticmethod
    def create_processor(payment_type: str) -> PaymentProcessor:
        processors = {
            'yookassa': YooKassaProcessor,
            'cryptobot': CryptoBotProcessor,
            'ton': TONProcessor,
            'stars': StarsProcessor
        }
        
        processor_class = processors.get(payment_type)
        if not processor_class:
            raise ValueError(f"Неподдерживаемый тип платежа: {payment_type}")
        
        return processor_class()
```

### 3. Observer для уведомлений
```python
class NotificationObserver:
    def __init__(self):
        self._observers = []
    
    def attach(self, observer):
        self._observers.append(observer)
    
    def notify(self, event_data):
        for observer in self._observers:
            observer.update(event_data)
```

### 4. Repository для работы с данными
```python
class UserRepository:
    def __init__(self, db_connection):
        self.db = db_connection
    
    def create(self, user_data: Dict) -> bool:
        """Создает пользователя в БД."""
        pass
    
    def get_by_id(self, user_id: int) -> Optional[Dict]:
        """Получает пользователя по ID."""
        pass
    
    def update(self, user_id: int, user_data: Dict) -> bool:
        """Обновляет данные пользователя."""
        pass
```

## Управление зависимостями

### 1. Инверсия зависимостей
```python
# ✅ Правильно - зависимость через интерфейс
class PaymentService:
    def __init__(self, payment_processor: PaymentProcessor):
        self.processor = payment_processor
    
    def process_payment(self, amount: float):
        return self.processor.process(amount)

# ❌ Неправильно - прямая зависимость
class PaymentService:
    def __init__(self):
        self.processor = YooKassaProcessor()
    
    def process_payment(self, amount: float):
        return self.processor.process(amount)
```

### 2. Dependency Injection
```python
class BotController:
    def __init__(
        self, 
        user_repository: UserRepository,
        payment_service: PaymentService,
        notification_service: NotificationService
    ):
        self.user_repo = user_repository
        self.payment_service = payment_service
        self.notification_service = notification_service
```

## Обработка ошибок

### 1. Иерархия исключений
```python
class ShopBotError(Exception):
    """Базовое исключение для приложения."""
    pass

class DatabaseError(ShopBotError):
    """Ошибки работы с базой данных."""
    pass

class PaymentError(ShopBotError):
    """Ошибки обработки платежей."""
    pass

class ValidationError(ShopBotError):
    """Ошибки валидации данных."""
    pass
```

### 2. Обработка в контроллерах
```python
async def handle_payment_command(message: Message):
    try:
        # Логика обработки платежа
        result = await process_payment(message)
        await message.answer("Платеж обработан успешно")
    except ValidationError as e:
        await message.answer(f"Ошибка валидации: {e}")
    except PaymentError as e:
        await message.answer(f"Ошибка платежа: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка в handle_payment_command: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")
```

## Логирование

### 1. Конфигурация логирования
```python
import logging

# Настройка логгера
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
```

### 2. Уровни логирования
```python
# DEBUG - детальная информация для отладки
logger.debug(f"Обработка пользователя {user_id}")

# INFO - общая информация о работе
logger.info(f"Пользователь {user_id} успешно зарегистрирован")

# WARNING - предупреждения о потенциальных проблемах
logger.warning(f"Пользователь {user_id} превысил лимит попыток")

# ERROR - ошибки, не останавливающие работу
logger.error(f"Ошибка обработки платежа для пользователя {user_id}")

# CRITICAL - критические ошибки, останавливающие работу
logger.critical(f"Критическая ошибка базы данных: {error}")
```

## Тестирование

### 1. Структура тестов
```
tests/
├── unit/                    # Модульные тесты
│   ├── test_database.py
│   ├── test_payment.py
│   └── test_handlers.py
├── integration/             # Интеграционные тесты
│   ├── test_api_integration.py
│   └── test_payment_flow.py
└── fixtures/                # Тестовые данные
    ├── users.json
    └── payments.json
```

### 2. Примеры тестов
```python
import pytest
from unittest.mock import Mock, patch
from shop_bot.data_manager.database import create_user

class TestUserCreation:
    def test_create_user_success(self):
        """Тест успешного создания пользователя."""
        with patch('sqlite3.connect') as mock_connect:
            mock_cursor = Mock()
            mock_connect.return_value.cursor.return_value = mock_cursor
            
            result = create_user(12345, "testuser")
            
            assert result is True
            mock_cursor.execute.assert_called_once()
    
    def test_create_user_database_error(self):
        """Тест обработки ошибки базы данных."""
        with patch('sqlite3.connect') as mock_connect:
            mock_connect.side_effect = sqlite3.Error("Database error")
            
            result = create_user(12345, "testuser")
            
            assert result is False
```

## Безопасность

### 1. Валидация входных данных
```python
def validate_user_input(data: Dict) -> bool:
    """Валидация пользовательских данных."""
    required_fields = ['telegram_id', 'username']
    
    for field in required_fields:
        if field not in data:
            raise ValidationError(f"Отсутствует обязательное поле: {field}")
    
    if not isinstance(data['telegram_id'], int) or data['telegram_id'] <= 0:
        raise ValidationError("Некорректный telegram_id")
    
    return True
```

### 2. Защита от SQL-инъекций
```python
# ✅ Правильно - параметризованные запросы
def get_user_by_id(user_id: int):
    cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,))

# ❌ Неправильно - конкатенация строк
def get_user_by_id(user_id: int):
    cursor.execute(f"SELECT * FROM users WHERE telegram_id = {user_id}")
```

### 3. Хеширование паролей
```python
import hashlib
import secrets

def hash_password(password: str) -> str:
    """Хеширование пароля с солью."""
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}:{password_hash.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """Проверка пароля."""
    salt, stored_hash = hashed.split(':')
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return password_hash.hex() == stored_hash
```

## Производительность

### 1. Кэширование
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_user_settings(user_id: int) -> Dict:
    """Кэширование настроек пользователя."""
    return database.get_user_settings(user_id)
```

### 2. Асинхронность
```python
import asyncio
import aiohttp

async def process_multiple_payments(payments: List[Dict]) -> List[Dict]:
    """Асинхронная обработка множественных платежей."""
    async with aiohttp.ClientSession() as session:
        tasks = [process_single_payment(session, payment) for payment in payments]
        results = await asyncio.gather(*tasks)
    return results
```

### 3. Оптимизация запросов к БД
```python
# ✅ Правильно - один запрос с JOIN
def get_users_with_keys():
    cursor.execute("""
        SELECT u.*, COUNT(k.key_id) as keys_count
        FROM users u
        LEFT JOIN vpn_keys k ON u.telegram_id = k.user_id
        GROUP BY u.telegram_id
    """)

# ❌ Неправильно - N+1 запросов
def get_users_with_keys():
    users = get_all_users()
    for user in users:
        user['keys_count'] = count_user_keys(user['telegram_id'])
```

---

*Документация обновлена: 29.09.2025*
*Владелец проекта: ukarshiev*
