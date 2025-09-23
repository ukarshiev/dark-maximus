# База данных {{PROJECT_NAME}}

## Оглавление
- [Обзор](#обзор)
- [Схема базы данных](#схема-базы-данных)
- [Таблицы](#таблицы)
- [Индексы](#индексы)
- [Миграции](#миграции)
- [API работы с БД](#api-работы-с-бд)
- [Производительность](#производительность)
- [Резервное копирование](#резервное-копирование)
- [Мониторинг](#мониторинг)

## Обзор

Проект {{PROJECT_NAME}} использует SQLite в качестве основной базы данных для хранения:
- Пользователей и их профилей
- VPN-ключей и подписок
- Транзакций и платежей
- Настроек системы
- Уведомлений
- Серверов и тарифных планов

### Технические характеристики
- **Тип БД**: SQLite 3
- **Файл БД**: `users.db`
- **Кодировка**: UTF-8
- **Временная зона**: UTC+3 (Москва)
- **Путь к БД**: `/app/project/users.db` (в контейнере)

## Схема базы данных

### Диаграмма связей
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     users       │    │    vpn_keys     │    │  transactions   │
│                 │    │                 │    │                 │
│ telegram_id (PK)│◄───┤ user_id (FK)    │    │ user_id (FK)    │
│ username        │    │ key_id (PK)     │    │ transaction_id  │
│ total_spent     │    │ host_name       │    │ payment_id (UK) │
│ total_months    │    │ xui_client_uuid │    │ status          │
│ trial_used      │    │ key_email (UK)  │    │ amount_rub      │
│ agreed_to_terms │    │ expiry_date     │    │ payment_method  │
│ registration_date│    │ created_date    │    │ created_date    │
│ is_banned       │    │ protocol        │    │ metadata        │
│ referred_by     │    │ is_trial        │    └─────────────────┘
│ referral_balance│    └─────────────────┘
│ balance         │
└─────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    xui_hosts    │    │      plans      │    │ notifications   │
│                 │    │                 │    │                 │
│ host_name (PK)  │◄───┤ host_name (FK)  │    │ notification_id │
│ host_url        │    │ plan_id (PK)    │    │ user_id (FK)    │
│ host_username   │    │ plan_name       │    │ username        │
│ host_pass       │    │ months          │    │ type            │
│ host_inbound_id │    │ days            │    │ title           │
│ host_code       │    │ hours           │    │ message         │
└─────────────────┘    │ price           │    │ status          │
                       │ traffic_gb      │    │ meta            │
                       └─────────────────┘    │ created_date    │
                                              └─────────────────┘
```

## Таблицы

### 1. users - Пользователи
Основная таблица для хранения информации о пользователях Telegram.

```sql
CREATE TABLE users (
    telegram_id INTEGER PRIMARY KEY,           -- ID пользователя в Telegram
    username TEXT,                             -- Имя пользователя
    total_spent REAL DEFAULT 0,                -- Общая сумма потраченных средств
    total_months INTEGER DEFAULT 0,            -- Общее количество месяцев подписки
    trial_used BOOLEAN DEFAULT 0,              -- Использован ли пробный период
    agreed_to_terms BOOLEAN DEFAULT 0,         -- Согласие с условиями
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Дата регистрации
    is_banned BOOLEAN DEFAULT 0,               -- Заблокирован ли пользователь
    referred_by INTEGER,                       -- ID пользователя, который пригласил
    referral_balance REAL DEFAULT 0,           -- Реферальный баланс
    referral_balance_all REAL DEFAULT 0,       -- Общий реферальный баланс
    balance REAL DEFAULT 0                     -- Основной баланс пользователя
);
```

**Индексы:**
- `PRIMARY KEY (telegram_id)`
- `INDEX idx_users_referred_by (referred_by)`
- `INDEX idx_users_registration_date (registration_date)`

### 2. vpn_keys - VPN ключи
Таблица для хранения VPN-ключей пользователей.

```sql
CREATE TABLE vpn_keys (
    key_id INTEGER PRIMARY KEY AUTOINCREMENT,  -- Уникальный ID ключа
    user_id INTEGER NOT NULL,                  -- ID пользователя (FK)
    host_name TEXT NOT NULL,                   -- Имя сервера
    xui_client_uuid TEXT NOT NULL,             -- UUID клиента в 3x-ui
    key_email TEXT NOT NULL UNIQUE,            -- Email ключа (уникальный)
    expiry_date TIMESTAMP,                     -- Дата истечения
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Дата создания
    connection_string TEXT,                    -- Строка подключения
    plan_name TEXT,                            -- Название тарифа
    price REAL,                                -- Цена ключа
    protocol TEXT DEFAULT 'vless',             -- Протокол (vless, vmess, etc.)
    is_trial INTEGER DEFAULT 0,                -- Пробный ключ
    status TEXT,                               -- Статус ключа
    remaining_seconds INTEGER,                 -- Оставшиеся секунды
    start_date TIMESTAMP,                      -- Дата начала действия
    quota_total_gb REAL,                      -- Общий лимит трафика (ГБ)
    traffic_down_bytes INTEGER,                -- Скачано байт
    quota_remaining_bytes INTEGER              -- Оставшийся трафик (байты)
);
```

**Индексы:**
- `PRIMARY KEY (key_id)`
- `UNIQUE INDEX uk_vpn_keys_email (key_email)`
- `INDEX idx_vpn_keys_user_id (user_id)`
- `INDEX idx_vpn_keys_host_name (host_name)`
- `INDEX idx_vpn_keys_expiry_date (expiry_date)`

### 3. transactions - Транзакции
Таблица для хранения всех транзакций и платежей.

```sql
CREATE TABLE transactions (
    username TEXT,                             -- Имя пользователя
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT, -- ID транзакции
    payment_id TEXT UNIQUE NOT NULL,           -- ID платежа (уникальный)
    user_id INTEGER NOT NULL,                  -- ID пользователя (FK)
    status TEXT NOT NULL,                      -- Статус (pending, paid, failed)
    amount_rub REAL NOT NULL,                  -- Сумма в рублях
    amount_currency REAL,                      -- Сумма в валюте платежа
    currency_name TEXT,                        -- Название валюты
    payment_method TEXT,                       -- Способ оплаты
    metadata TEXT,                             -- Метаданные (JSON)
    transaction_hash TEXT,                     -- Хеш транзакции
    payment_link TEXT,                         -- Ссылка на оплату
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- Дата создания
);
```

**Индексы:**
- `PRIMARY KEY (transaction_id)`
- `UNIQUE INDEX uk_transactions_payment_id (payment_id)`
- `INDEX idx_transactions_user_id (user_id)`
- `INDEX idx_transactions_status (status)`
- `INDEX idx_transactions_created_date (created_date)`

### 4. bot_settings - Настройки бота
Таблица для хранения конфигурации системы.

```sql
CREATE TABLE bot_settings (
    key TEXT PRIMARY KEY,                      -- Ключ настройки
    value TEXT                                 -- Значение настройки
);
```

**Основные настройки:**
- `panel_login`, `panel_password` - Данные для 3x-ui панели
- `telegram_bot_token` - Токен Telegram бота
- `yookassa_shop_id`, `yookassa_secret_key` - Настройки YooKassa
- `cryptobot_token` - Токен CryptoBot
- `ton_wallet_address`, `tonapi_key` - Настройки TON
- `referral_percentage`, `referral_discount` - Настройки рефералов

### 5. notifications - Уведомления
Таблица для хранения уведомлений пользователям.

```sql
CREATE TABLE notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT, -- ID уведомления
    user_id INTEGER,                           -- ID пользователя (FK)
    username TEXT,                             -- Имя пользователя
    type TEXT,                                 -- Тип уведомления
    title TEXT,                                -- Заголовок
    message TEXT,                              -- Текст сообщения
    status TEXT,                               -- Статус (sent, failed, pending)
    meta TEXT,                                 -- Метаданные (JSON)
    key_id INTEGER,                            -- ID связанного ключа
    marker_hours INTEGER,                      -- Часы для маркера
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- Дата создания
);
```

**Индексы:**
- `PRIMARY KEY (notification_id)`
- `INDEX idx_notifications_user_id (user_id)`
- `INDEX idx_notifications_type (type)`
- `INDEX idx_notifications_status (status)`
- `INDEX idx_notifications_created_date (created_date)`

### 6. xui_hosts - VPN серверы
Таблица для хранения информации о VPN серверах.

```sql
CREATE TABLE xui_hosts (
    host_name TEXT NOT NULL,                   -- Имя сервера (PK)
    host_url TEXT NOT NULL,                    -- URL сервера
    host_username TEXT NOT NULL,               -- Логин для 3x-ui
    host_pass TEXT NOT NULL,                   -- Пароль для 3x-ui
    host_inbound_id INTEGER NOT NULL,          -- ID входящего соединения
    host_code TEXT                             -- Код сервера
);
```

**Индексы:**
- `PRIMARY KEY (host_name)`
- `INDEX idx_xui_hosts_code (host_code)`

### 7. plans - Тарифные планы
Таблица для хранения тарифных планов подписки.

```sql
CREATE TABLE plans (
    plan_id INTEGER PRIMARY KEY AUTOINCREMENT, -- ID тарифа
    host_name TEXT NOT NULL,                   -- Имя сервера (FK)
    plan_name TEXT NOT NULL,                   -- Название тарифа
    months INTEGER NOT NULL,                   -- Количество месяцев
    days INTEGER DEFAULT 0,                    -- Дополнительные дни
    hours INTEGER DEFAULT 0,                   -- Дополнительные часы
    price REAL NOT NULL,                       -- Цена тарифа
    traffic_gb REAL DEFAULT 0,                 -- Лимит трафика (ГБ)
    FOREIGN KEY (host_name) REFERENCES xui_hosts (host_name)
);
```

**Индексы:**
- `PRIMARY KEY (plan_id)`
- `INDEX idx_plans_host_name (host_name)`
- `INDEX idx_plans_price (price)`

### 8. support_threads - Потоки поддержки
Таблица для связи пользователей с потоками поддержки.

```sql
CREATE TABLE support_threads (
    user_id INTEGER PRIMARY KEY,               -- ID пользователя (PK)
    thread_id INTEGER NOT NULL                 -- ID потока поддержки
);
```

**Индексы:**
- `PRIMARY KEY (user_id)`
- `UNIQUE INDEX uk_support_threads_thread_id (thread_id)`

## Индексы

### Основные индексы для производительности

```sql
-- Индексы для быстрого поиска пользователей
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_is_banned ON users(is_banned);

-- Индексы для работы с ключами
CREATE INDEX idx_vpn_keys_protocol ON vpn_keys(protocol);
CREATE INDEX idx_vpn_keys_is_trial ON vpn_keys(is_trial);

-- Индексы для аналитики
CREATE INDEX idx_transactions_payment_method ON transactions(payment_method);
CREATE INDEX idx_transactions_amount_rub ON transactions(amount_rub);

-- Составные индексы
CREATE INDEX idx_vpn_keys_user_expiry ON vpn_keys(user_id, expiry_date);
CREATE INDEX idx_transactions_user_status ON transactions(user_id, status);
```

## Миграции

### Система миграций
Проект использует встроенную систему миграций в файле `database.py`.

### Основные миграции

#### v1.0 - Базовая структура
```sql
-- Создание основных таблиц
CREATE TABLE users (...);
CREATE TABLE vpn_keys (...);
CREATE TABLE transactions (...);
CREATE TABLE bot_settings (...);
```

#### v2.0 - Реферальная система
```sql
-- Добавление реферальных полей
ALTER TABLE users ADD COLUMN referred_by INTEGER;
ALTER TABLE users ADD COLUMN referral_balance REAL DEFAULT 0;
ALTER TABLE users ADD COLUMN referral_balance_all REAL DEFAULT 0;
```

#### v2.1 - Баланс пользователей
```sql
-- Добавление баланса
ALTER TABLE users ADD COLUMN balance REAL DEFAULT 0;
```

#### v2.2 - Расширенные ключи
```sql
-- Добавление полей для ключей
ALTER TABLE vpn_keys ADD COLUMN connection_string TEXT;
ALTER TABLE vpn_keys ADD COLUMN plan_name TEXT;
ALTER TABLE vpn_keys ADD COLUMN price REAL;
ALTER TABLE vpn_keys ADD COLUMN protocol TEXT DEFAULT 'vless';
ALTER TABLE vpn_keys ADD COLUMN is_trial INTEGER DEFAULT 0;
```

#### v2.3 - Система уведомлений
```sql
-- Создание таблицы уведомлений
CREATE TABLE notifications (...);
```

#### v2.4 - Трафик и квоты
```sql
-- Добавление полей трафика
ALTER TABLE vpn_keys ADD COLUMN quota_total_gb REAL;
ALTER TABLE vpn_keys ADD COLUMN traffic_down_bytes INTEGER;
ALTER TABLE vpn_keys ADD COLUMN quota_remaining_bytes INTEGER;
```

### Запуск миграций
```python
from shop_bot.data_manager.database import run_migration

# Миграции запускаются автоматически при инициализации БД
run_migration()
```

## API работы с БД

### Основные функции

#### Пользователи
```python
# Создание пользователя
def register_user_if_not_exists(telegram_id: int, username: str, referrer_id: int = None)

# Получение пользователя
def get_user(telegram_id: int) -> dict

# Обновление баланса
def add_to_user_balance(user_id: int, amount: float) -> bool

# Реферальная система
def add_to_referral_balance(user_id: int, amount: float)
def get_referral_balance(user_id: int) -> float
```

#### VPN ключи
```python
# Создание ключа
def add_new_key(user_id: int, host_name: str, xui_client_uuid: str, 
                key_email: str, expiry_timestamp_ms: int, **kwargs) -> int

# Получение ключей пользователя
def get_user_keys(user_id: int) -> list[dict]

# Обновление информации о ключе
def update_key_info(key_id: int, new_xui_uuid: str, new_expiry_ms: int)
```

#### Транзакции
```python
# Создание транзакции
def create_pending_transaction(payment_id: str, user_id: int, 
                              amount_rub: float, metadata: dict) -> int

# Обновление статуса
def update_transaction_status(payment_id: str, status: str, tx_hash: str = None) -> bool

# Получение транзакций с пагинацией
def get_paginated_transactions(page: int = 1, per_page: int = 15) -> tuple[list[dict], int]
```

#### Настройки
```python
# Получение настройки
def get_setting(key: str) -> str

# Получение всех настроек
def get_all_settings() -> dict

# Обновление настройки
def update_setting(key: str, value: str)
```

### Примеры использования

```python
from shop_bot.data_manager.database import (
    register_user_if_not_exists, get_user, add_new_key, 
    create_pending_transaction, get_all_settings
)

# Регистрация пользователя
register_user_if_not_exists(12345, "testuser", referrer_id=67890)

# Получение данных пользователя
user = get_user(12345)
if user:
    print(f"Пользователь: {user['username']}, баланс: {user['balance']}")

# Создание VPN ключа
key_id = add_new_key(
    user_id=12345,
    host_name="server1",
    xui_client_uuid="uuid-123",
    key_email="user@example.com",
    expiry_timestamp_ms=1640995200000,  # 1 января 2022
    connection_string="vless://...",
    plan_name="Базовый",
    price=299.0
)

# Создание транзакции
transaction_id = create_pending_transaction(
    payment_id="payment_123",
    user_id=12345,
    amount_rub=299.0,
    metadata={"plan_name": "Базовый", "host_name": "server1"}
)
```

## Производительность

### Оптимизация запросов

#### 1. Использование индексов
```sql
-- ✅ Хорошо - использует индекс
SELECT * FROM users WHERE telegram_id = 12345;

-- ❌ Плохо - полное сканирование таблицы
SELECT * FROM users WHERE username LIKE '%test%';
```

#### 2. Ограничение результатов
```sql
-- ✅ Хорошо - ограничение результатов
SELECT * FROM transactions ORDER BY created_date DESC LIMIT 20;

-- ❌ Плохо - загрузка всех записей
SELECT * FROM transactions ORDER BY created_date DESC;
```

#### 3. Выборка только нужных полей
```sql
-- ✅ Хорошо - только нужные поля
SELECT telegram_id, username, balance FROM users WHERE is_banned = 0;

-- ❌ Плохо - все поля
SELECT * FROM users WHERE is_banned = 0;
```

### Мониторинг производительности

#### Медленные запросы
```python
import time
import logging

def log_slow_queries(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        if execution_time > 1.0:  # Запросы дольше 1 секунды
            logging.warning(f"Медленный запрос {func.__name__}: {execution_time:.2f}s")
        
        return result
    return wrapper

@log_slow_queries
def get_user_transactions(user_id: int):
    # Выполнение запроса
    pass
```

## Резервное копирование

### Автоматическое резервное копирование
```python
import shutil
from datetime import datetime

def backup_database():
    """Создание резервной копии базы данных."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"users_backup_{timestamp}.db"
    
    try:
        shutil.copy2(DB_FILE, f"backups/{backup_name}")
        logging.info(f"Резервная копия создана: {backup_name}")
        return True
    except Exception as e:
        logging.error(f"Ошибка создания резервной копии: {e}")
        return False
```

### Восстановление из резервной копии
```python
def restore_database(backup_file: str):
    """Восстановление базы данных из резервной копии."""
    try:
        shutil.copy2(backup_file, DB_FILE)
        logging.info(f"База данных восстановлена из {backup_file}")
        return True
    except Exception as e:
        logging.error(f"Ошибка восстановления базы данных: {e}")
        return False
```

## Мониторинг

### Метрики для отслеживания

#### 1. Размер базы данных
```python
import os

def get_database_size():
    """Получение размера файла базы данных."""
    if os.path.exists(DB_FILE):
        size_bytes = os.path.getsize(DB_FILE)
        size_mb = size_bytes / (1024 * 1024)
        return size_mb
    return 0
```

#### 2. Количество записей
```python
def get_database_stats():
    """Получение статистики базы данных."""
    stats = {}
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        
        # Количество пользователей
        cursor.execute("SELECT COUNT(*) FROM users")
        stats['users_count'] = cursor.fetchone()[0]
        
        # Количество активных ключей
        cursor.execute("SELECT COUNT(*) FROM vpn_keys WHERE expiry_date > datetime('now')")
        stats['active_keys_count'] = cursor.fetchone()[0]
        
        # Количество транзакций
        cursor.execute("SELECT COUNT(*) FROM transactions")
        stats['transactions_count'] = cursor.fetchone()[0]
        
        # Общая сумма транзакций
        cursor.execute("SELECT SUM(amount_rub) FROM transactions WHERE status = 'paid'")
        stats['total_revenue'] = cursor.fetchone()[0] or 0
    
    return stats
```

#### 3. Мониторинг производительности
```python
def monitor_database_health():
    """Мониторинг состояния базы данных."""
    health_status = {
        'database_exists': os.path.exists(DB_FILE),
        'database_size_mb': get_database_size(),
        'can_connect': False,
        'tables_count': 0
    }
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            health_status['can_connect'] = True
            
            # Количество таблиц
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            health_status['tables_count'] = cursor.fetchone()[0]
            
    except Exception as e:
        logging.error(f"Ошибка подключения к БД: {e}")
    
    return health_status
```

---

*Документация создана {{DATE}}*
*Владелец проекта: {{OWNER}}*
