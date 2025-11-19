# Структура тестов Dark Maximus

> **Дата последней редакции:** 15.11.2025 16:44

## Обзор

Тесты проекта Dark Maximus организованы по типу и модулю согласно лучшим практикам pytest. Структура обеспечивает четкое разделение между unit-тестами, интеграционными тестами, E2E тестами и одноразовыми скриптами.

## Общая структура каталога `tests/`

```
tests/
├── __init__.py
├── conftest.py              # Общие фикстуры (temp_db, моки)
├── pytest.ini               # Конфигурация pytest с Allure
├── run_tests.sh             # Скрипт запуска тестов (bash)
├── run_tests.ps1            # Скрипт запуска тестов (PowerShell)
│
├── unit/                    # Unit-тесты (70% покрытия)
│   ├── __init__.py
│   ├── test_database/       # Тесты операций с БД
│   ├── test_bot/            # Тесты бота (handlers, логика)
│   ├── test_utils/          # Тесты утилит
│   ├── test_security/       # Тесты безопасности
│   ├── test_modules/        # Тесты модулей
│   └── test_webhook_server/ # Тесты веб-сервера
│
├── integration/             # Интеграционные тесты (20%)
│   ├── __init__.py
│   ├── test_payments/       # Тесты платежных систем
│   ├── test_vpn_purchase/   # Тесты покупки VPN
│   ├── test_auto_renewal/   # Тесты авто-продления
│   ├── test_referral/       # Тесты реферальной программы
│   ├── test_trial/          # Тесты триала
│   ├── test_user_cabinet/   # Тесты пользовательского кабинета
│   ├── test_web_panel/      # Тесты веб-панели
│   └── test_deeplink_*.py   # Тесты deeplink
│
├── e2e/                     # End-to-End тесты (10%)
│   ├── __init__.py
│   ├── test_user_scenarios/ # Пользовательские сценарии
│   └── test_admin_scenarios/# Админские сценарии
│
└── ad-hoc/                  # Одноразовые скрипты и утилиты
    ├── __init__.py
    ├── tests/               # Одноразовые тесты (test_*.py)
    ├── checks/              # Одноразовые проверки (check_*.py)
    ├── migrations/          # Выполненные миграции БД (migrate_*.py)
    ├── utils/               # Утилиты (create_*, simulate_*, show_*)
    ├── final/               # Финальные проверки
    └── reports/             # Отчеты и результаты
```

## Типы тестов

### Unit-тесты (`tests/unit/`)

**Назначение:** Тестируют отдельные функции и модули изолированно

**Характеристики:**
- Быстрые (< 1 секунды каждый)
- Изолированные (не требуют внешних сервисов)
- Используют моки для всех зависимостей
- Используют временную БД через фикстуру `temp_db`

**Структура:**

```
tests/unit/
├── test_database/           # Тесты операций с БД
│   ├── test_user_operations.py      # CRUD операции с пользователями
│   ├── test_key_operations.py       # Операции с ключами VPN
│   ├── test_transaction_operations.py # Операции с транзакциями
│   ├── test_promo_code_operations.py  # Операции с промокодами
│   └── ...
│
├── test_bot/                # Тесты бота
│   ├── test_handlers.py              # Обработчики команд бота
│   ├── test_promo_code_logic.py      # Логика промокодов
│   └── test_keyboard_generation.py   # Генерация клавиатур
│
├── test_utils/              # Тесты утилит
│   ├── test_deeplink.py              # Утилиты для deeplink
│   └── test_timezone_utils.py        # Утилиты для timezone
│
├── test_security/           # Тесты безопасности
│   └── test_validators.py            # Валидаторы
│
└── test_webhook_server/     # Тесты веб-сервера
    ├── test_auth.py                  # Аутентификация
    ├── test_users.py                 # API пользователей
    ├── test_keys.py                  # API ключей
    └── ...
```

**Пример unit-теста:**

```python
@pytest.mark.unit
@pytest.mark.database
def test_register_user_if_not_exists(temp_db):
    """Тест регистрации нового пользователя"""
    telegram_id = 123456789
    username = "test_user"
    
    register_user_if_not_exists(telegram_id, username, None, "Test User")
    
    user = get_user(telegram_id)
    assert user is not None
    assert user['telegram_id'] == telegram_id
    assert user['username'] == username
```

### Интеграционные тесты (`tests/integration/`)

**Назначение:** Тестируют взаимодействие нескольких компонентов

**Характеристики:**
- Тестируют полные flow (регистрация → покупка → получение ключа)
- Используют временную БД через фикстуру `temp_db`
- Используют моки для внешних сервисов (Telegram, 3X-UI, платежи)
- Могут быть медленнее unit-тестов

**Структура:**

```
tests/integration/
├── test_payments/           # Тесты платежных систем
│   ├── test_yookassa_flow.py        # Полный flow YooKassa
│   ├── test_cryptobot_flow.py       # Полный flow CryptoBot
│   ├── test_ton_connect_flow.py     # Полный flow TON Connect
│   ├── test_stars_flow.py           # Полный flow Telegram Stars
│   └── test_heleket_flow.py         # Полный flow Heleket
│
├── test_vpn_purchase/       # Тесты покупки VPN
│   ├── test_full_purchase_flow.py   # Полный flow покупки
│   ├── test_key_creation_flow.py    # Создание ключа
│   └── test_key_extension_flow.py   # Продление ключа
│
├── test_auto_renewal/       # Тесты авто-продления
│   ├── test_auto_renewal_process.py # Процесс авто-продления
│   └── test_auto_renewal_conditions.py # Условия авто-продления
│
├── test_referral/           # Тесты реферальной программы
│   └── test_referral_flow.py        # Flow реферальной программы
│
└── test_user_cabinet/       # Тесты пользовательского кабинета
    └── test_cabinet_flow.py         # Flow работы кабинета
```

**Пример интеграционного теста:**

```python
@pytest.mark.integration
@pytest.mark.database
class TestYooKassaFlow:
    """Интеграционные тесты для YooKassa"""
    
    def test_full_payment_flow(self, temp_db, mock_bot):
        """Тест полного flow от создания платежа до получения ключа"""
        # Arrange: создаем пользователя, план, транзакцию
        # Act: симулируем успешный платеж
        # Assert: проверяем создание ключа и статус транзакции
        pass
```

### E2E тесты (`tests/e2e/`)

**Назначение:** Тестируют полные пользовательские сценарии

**Характеристики:**
- Тестируют end-to-end сценарии от начала до конца
- Используют временную БД и моки внешних сервисов
- Могут быть самыми медленными тестами

**Структура:**

```
tests/e2e/
├── test_user_scenarios/     # Пользовательские сценарии
│   ├── test_new_user_purchase.py      # Новый пользователь покупает VPN
│   ├── test_user_trial_flow.py        # Пользователь использует триал
│   ├── test_user_key_extension.py     # Пользователь продлевает ключ
│   └── test_user_with_referral.py     # Пользователь с рефералом
│
└── test_admin_scenarios/    # Админские сценарии
    ├── test_admin_user_management.py  # Управление пользователями
    ├── test_admin_key_management.py   # Управление ключами
    └── test_admin_promo_management.py # Управление промокодами
```

**Пример E2E теста:**

```python
@pytest.mark.e2e
@pytest.mark.asyncio
class TestNewUserPurchase:
    """E2E тесты для нового пользователя"""
    
    async def test_new_user_registers_and_buys_vpn(self, temp_db):
        """Тест: новый пользователь регистрируется и покупает VPN"""
        # Полный сценарий от регистрации до получения ключа
        pass
```

### Одноразовые скрипты (`tests/ad-hoc/`)

**Назначение:** Одноразовые проверки, миграции, утилиты для отладки

**Важно:** Эти файлы **игнорируются** pytest при запуске тестов (см. `pytest.ini`)

**Структура:**

```
tests/ad-hoc/
├── tests/               # Одноразовые тесты (test_*.py)
│   ├── test_message_templates.py
│   └── ...
│
├── checks/              # Одноразовые проверки (check_*.py)
│   ├── check_timezone_feature.py
│   ├── check_promo_status.py
│   └── ...
│
├── migrations/          # Выполненные миграции БД (migrate_*.py)
│   ├── migrate_add_user_columns.py
│   └── migrate_database_schema.py
│
├── utils/               # Утилиты (create_*, simulate_*, show_*)
│   ├── create_demo_transaction.py
│   ├── simulate_new_user.py
│   └── show_transactions.py
│
├── final/               # Финальные проверки
│   └── final_verification.py
│
└── reports/             # Отчеты и результаты
    ├── allure-defects-report.md
    └── ...
```

## Организация тестов по модулям

### Связь тестов с исходным кодом

Тесты организованы по модулям исходного кода:

```
src/shop_bot/
├── data_manager/
│   └── database.py              ← tests/unit/test_database/
│
├── bot/
│   ├── handlers.py              ← tests/unit/test_bot/test_handlers.py
│   └── logic.py                 ← tests/unit/test_bot/
│
├── utils/
│   └── deeplink.py              ← tests/unit/test_utils/test_deeplink.py
│
└── webhook_server/
    └── app.py                   ← tests/unit/test_webhook_server/
```

### Принципы именования

**Файлы тестов:**
- `test_*.py` — все файлы тестов начинаются с `test_`
- `test_<module>_<functionality>.py` — пример: `test_user_operations.py`

**Функции тестов:**
- `test_<what>_<condition>_<expected>` — пример: `test_register_user_if_not_exists`

**Классы тестов:**
- `Test<ModuleName>` — пример: `TestUserOperations`

## Маркеры pytest

Все тесты должны иметь соответствующий маркер:

```python
@pytest.mark.unit              # Unit-тесты
@pytest.mark.integration       # Интеграционные тесты
@pytest.mark.e2e               # E2E тесты
@pytest.mark.database          # Тесты работы с БД
@pytest.mark.bot               # Тесты бота
@pytest.mark.slow              # Медленные тесты
@pytest.mark.asyncio           # Асинхронные тесты
```

**Использование:**

```python
# Пример unit-теста
@pytest.mark.unit
@pytest.mark.database
def test_user_creation(temp_db):
    # тест

# Пример интеграционного теста
@pytest.mark.integration
def test_deeplink_flow(temp_db):
    # тест
```

## Фикстуры (conftest.py)

Все общие фикстуры находятся в `tests/conftest.py`:

- **`temp_db`** — создает временную SQLite БД с полной структурой таблиц
- **`mock_bot`** — мок для aiogram.Bot
- **`mock_xui_api`** — мок для py3xui.Api
- **`mock_yookassa`** — мок для YooKassa Payment
- **`mock_cryptobot`** — мок для CryptoBot API
- **`mock_ton_connect`** — мок для TON Connect
- **`mock_heleket`** — мок для Heleket API
- **`sample_host`** — тестовый хост для БД
- **`sample_plan`** — тестовый план для БД
- **`sample_promo_code`** — тестовый промокод для БД

**Важно:** Всегда используйте фикстуру `temp_db` вместо реальной БД `users.db`!

## Игнорирование тестов

Следующие каталоги игнорируются pytest (см. `pytest.ini`):

- `tests/ad-hoc/` — одноразовые скрипты
- `tests/ad-hoc/tests/` — одноразовые тесты (через `pytest_ignore_collect`)

## Статистика тестов

**Текущее состояние:**
- **Unit-тесты:** ~44 файла
- **Интеграционные тесты:** ~28 файлов
- **E2E тесты:** ~10 файлов
- **Ad-hoc:** ~133 файла (не запускаются автоматически)

**Покрытие по типам:**
- **Unit:** ~70% всех тестов
- **Integration:** ~20% всех тестов
- **E2E:** ~10% всех тестов

## Рекомендации

1. **Новые тесты:** Размещайте в соответствующем каталоге (`unit/`, `integration/`, `e2e/`)
2. **Одноразовые скрипты:** Размещайте в `ad-hoc/` (они не запускаются автоматически)
3. **Используйте маркеры:** Всегда добавляйте соответствующий маркер `@pytest.mark.*`
4. **Используйте фикстуры:** Используйте `temp_db` вместо реальной БД
5. **Изоляция:** Каждый тест должен быть независимым

## См. также

- [Запуск тестов](running-tests.md) — как запускать тесты
- [Best Practices](best-practices.md) — рекомендации по написанию тестов
- [Справочник по тестированию](../../reference/testing-reference.md) — полный справочник

---

**Версия:** 1.0  
**Последнее обновление:** 15.11.2025 16:44  
**Автор:** Dark Maximus Team

