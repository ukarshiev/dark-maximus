# 🎯 Промты для модернизации Dark Maximus

> **Файл с готовыми промтами** для работы с AI ассистентом в новых диалогах

## 📋 Как использовать

1. Скопируйте нужный промт
2. Вставьте в новый чат с AI
3. Добавьте контекст о текущем состоянии проекта
4. Следуйте инструкциям ассистента

---

## 🔄 Обновление зависимостей

### Flask обновление
```
Обнови Flask в проекте Dark Maximus с версии 3.1.1 до последней стабильной версии.

Контекст:
- Проект: Dark Maximus (Telegram-бот для продажи VPN)
- Текущая версия Flask: 3.1.1
- Файл конфигурации: pyproject.toml
- Основной файл: src/shop_bot/webhook_server/app.py

Задачи:
1. Проверь совместимость с текущим кодом
2. Обнови версию в pyproject.toml
3. Протестируй веб-панель после обновления
4. Исправь возможные breaking changes
5. Обнови документацию если нужно

Ожидаемый результат: Flask обновлен без потери функциональности
```

### YooKassa обновление
```
Обнови yookassa в проекте Dark Maximus с версии 3.5.0 до последней стабильной версии.

Контекст:
- Проект: Dark Maximus (Telegram-бот для продажи VPN)
- Текущая версия yookassa: 3.5.0
- Файл конфигурации: pyproject.toml
- Основные файлы: src/shop_bot/bot/handlers.py, src/shop_bot/webhook_server/app.py

Задачи:
1. Проверь совместимость API клиента
2. Обнови версию в pyproject.toml
3. Протестируй создание и обработку платежей
4. Исправь возможные изменения в структуре Payment объектов
5. Проверь webhook обработку

Ожидаемый результат: YooKassa работает с новой версией без ошибок
```

### aiogram обновление (КРИТИЧНО)
```
ОСТОРОЖНО обнови aiogram в проекте Dark Maximus с версии 3.21.0 до последней стабильной версии.

Контекст:
- Проект: Dark Maximus (Telegram-бот для продажи VPN)
- Текущая версия aiogram: 3.21.0
- Файл конфигурации: pyproject.toml
- Основные файлы: src/shop_bot/bot/handlers.py, src/shop_bot/bot/keyboards.py, src/shop_bot/bot/middlewares.py

ВНИМАНИЕ: Это критическое обновление с возможными breaking changes!

Задачи:
1. Изучи changelog aiogram 3.21.0 → последняя версия
2. Проверь совместимость с текущим кодом
3. Обнови версию в pyproject.toml
4. Исправь все breaking changes:
   - Изменения в структуре Update объектов
   - Новые требования к middleware
   - Изменения в FSM (Finite State Machine)
   - Изменения в обработчиках команд
5. Протестируй все команды бота
6. Проверь работу с Telegram API

Ожидаемый результат: Бот работает с новой версией aiogram без ошибок
```

---

## 🗄️ Работа с базой данных

### Оптимизация SQLite
```
Оптимизируй работу с SQLite в проекте Dark Maximus для улучшения производительности.

Контекст:
- Проект: Dark Maximus (Telegram-бот для продажи VPN)
- Текущая БД: SQLite (users.db)
- Основной файл: src/shop_bot/data_manager/database.py
- Проблемы: медленные запросы, блокировки при записи

Задачи:
1. Добавь connection pooling для уменьшения накладных расходов
2. Включи WAL режим для лучшей производительности:
   ```sql
   PRAGMA journal_mode=WAL;
   PRAGMA synchronous=NORMAL;
   PRAGMA cache_size=10000;
   PRAGMA temp_store=MEMORY;
   ```
3. Добавь недостающие индексы:
   - users: telegram_id, username, is_banned
   - vpn_keys: user_id, host_name, expiry_date, status
   - transactions: user_id, status, created_date
4. Создай асинхронные версии критических функций
5. Добавь кэширование часто запрашиваемых данных
6. Оптимизируй медленные запросы

Ожидаемый результат: Улучшение производительности БД на 50-70%
```

### Миграция на PostgreSQL
```
Подготовь миграцию с SQLite на PostgreSQL в проекте Dark Maximus.

Контекст:
- Проект: Dark Maximus (Telegram-бот для продажи VPN)
- Текущая БД: SQLite (users.db)
- Целевая БД: PostgreSQL
- Основной файл: src/shop_bot/data_manager/database.py

Задачи:
1. Создай Dockerfile для PostgreSQL:
   ```dockerfile
   FROM postgres:15-alpine
   ENV POSTGRES_DB=dark_maximus
   ENV POSTGRES_USER=bot_user
   ENV POSTGRES_PASSWORD=secure_password
   ```
2. Обнови docker-compose.yml для добавления postgres сервиса
3. Создай скрипт миграции данных из SQLite в PostgreSQL
4. Обнови database.py для работы с PostgreSQL через asyncpg
5. Создай схему БД для PostgreSQL с правильными типами данных
6. Добавь connection pooling для PostgreSQL
7. Протестируй миграцию данных

Ожидаемый результат: Полная миграция на PostgreSQL с сохранением всех данных
```

---

## 🏗️ Архитектурные улучшения

### Разделение handlers.py
```
Разбей монолитный файл handlers.py (5645 строк) на модули в проекте Dark Maximus.

Контекст:
- Проект: Dark Maximus (Telegram-бот для продажи VPN)
- Проблемный файл: src/shop_bot/bot/handlers.py (5645 строк)
- Нужно разделить на логические модули

Задачи:
1. Создай структуру папок:
   ```
   src/shop_bot/bot/handlers/
   ├── __init__.py
   ├── base.py              # Базовые классы и декораторы
   ├── admin_handlers.py    # Админские команды
   ├── user_handlers.py     # Пользовательские команды
   ├── payment_handlers.py  # Обработка платежей
   ├── support_handlers.py  # Поддержка
   └── utils.py            # Вспомогательные функции
   ```

2. Раздели функции по файлам:
   - admin_handlers.py: все функции с @admin_router
   - user_handlers.py: все функции с @user_router
   - payment_handlers.py: функции обработки платежей
   - support_handlers.py: функции поддержки

3. Создай base.py с общими функциями:
   - Декораторы (@measure_performance, @subscription_required)
   - Вспомогательные функции
   - Общие обработчики ошибок

4. Обнови импорты в __init__.py
5. Убедись что все функции работают после разделения

Ожидаемый результат: handlers.py разделен на модули, код стал читаемым
```

### Создание сервисного слоя
```
Создай сервисный слой для выделения бизнес-логики в проекте Dark Maximus.

Контекст:
- Проект: Dark Maximus (Telegram-бот для продажи VPN)
- Проблема: бизнес-логика смешана с обработчиками
- Нужно создать сервисы для переиспользования логики

Задачи:
1. Создай структуру папок:
   ```
   src/shop_bot/services/
   ├── __init__.py
   ├── user_service.py      # Работа с пользователями
   ├── payment_service.py   # Обработка платежей
   ├── key_service.py       # Управление VPN ключами
   ├── notification_service.py # Уведомления
   └── base_service.py      # Базовый класс сервиса
   ```

2. Создай UserService:
   - create_user(), get_user(), update_user()
   - ban_user(), unban_user()
   - get_user_stats(), get_user_keys()

3. Создай PaymentService:
   - create_payment(), process_payment()
   - validate_payment(), refund_payment()
   - get_payment_methods()

4. Создай KeyService:
   - create_key(), get_key(), update_key()
   - revoke_key(), extend_key()
   - get_user_keys(), get_active_keys()

5. Обнови handlers для использования сервисов
6. Перенеси бизнес-логику из handlers в сервисы

Ожидаемый результат: Бизнес-логика выделена в сервисы, handlers стали легче
```

### Внедрение Repository Pattern
```
Внедри Repository Pattern для работы с базой данных в проекте Dark Maximus.

Контекст:
- Проект: Dark Maximus (Telegram-бот для продажи VPN)
- Проблема: прямые вызовы database.py из handlers
- Нужно создать абстракцию для работы с БД

Задачи:
1. Создай структуру папок:
   ```
   src/shop_bot/repositories/
   ├── __init__.py
   ├── base_repository.py   # Базовый класс
   ├── user_repository.py   # Работа с пользователями
   ├── key_repository.py    # Работа с ключами
   ├── transaction_repository.py # Работа с транзакциями
   └── settings_repository.py # Работа с настройками
   ```

2. Создай абстрактный BaseRepository:
   ```python
   class BaseRepository(ABC):
       @abstractmethod
       async def create(self, data: dict) -> Any:
           pass
       
       @abstractmethod
       async def get_by_id(self, id: int) -> Optional[Any]:
           pass
   ```

3. Создай конкретные репозитории:
   - UserRepository: CRUD операции для пользователей
   - KeyRepository: CRUD операции для VPN ключей
   - TransactionRepository: CRUD операции для транзакций

4. Обнови database.py для работы через репозитории
5. Обнови сервисы для использования репозиториев
6. Добавь dependency injection

Ожидаемый результат: Четкое разделение между БД и бизнес-логикой
```

---

## 🚀 Производительность и масштабирование

### Добавление Redis кэширования
```
Добавь Redis кэширование для улучшения производительности в проекте Dark Maximus.

Контекст:
- Проект: Dark Maximus (Telegram-бот для продажи VPN)
- Проблема: частые запросы к БД, медленная загрузка данных
- Решение: добавить Redis кэширование

Задачи:
1. Добавь Redis в docker-compose.yml:
   ```yaml
   redis:
     image: redis:7-alpine
     container_name: dark-maximus-redis
     ports:
       - "127.0.0.1:6379:6379"
     volumes:
       - redis_data:/data
   ```

2. Установи redis-py в pyproject.toml:
   ```
   redis = "^5.0.0"
   aioredis = "^2.0.0"
   ```

3. Создай src/shop_bot/cache/:
   ```
   src/shop_bot/cache/
   ├── __init__.py
   ├── redis_client.py    # Redis клиент
   ├── cache_manager.py   # Менеджер кэша
   └── decorators.py      # Декораторы для кэширования
   ```

4. Добавь кэширование для:
   - Список хостов и планов (TTL: 1 час)
   - Данные пользователей (TTL: 30 минут)
   - Настройки бота (TTL: 1 час)
   - Статистика (TTL: 15 минут)

5. Создай декораторы для кэширования:
   ```python
   @cache_result(ttl=3600)
   async def get_all_hosts():
       pass
   ```

6. Обнови сервисы для использования кэша

Ожидаемый результат: Уменьшение нагрузки на БД на 60-80%
```

### Улучшение асинхронности
```
Улучши асинхронность в проекте Dark Maximus для повышения производительности.

Контекст:
- Проект: Dark Maximus (Telegram-бот для продажи VPN)
- Проблема: блокирующие операции, медленная обработка запросов
- Нужно оптимизировать асинхронный код

Задачи:
1. Замени все синхронные операции БД на асинхронные:
   - Используй aiosqlite вместо sqlite3
   - Добавь async/await для всех БД операций
   - Создай асинхронные версии функций

2. Добавь asyncio.gather() для параллельных операций:
   ```python
   # Вместо последовательных вызовов
   user = await get_user(user_id)
   keys = await get_user_keys(user_id)
   
   # Используй параллельные вызовы
   user, keys = await asyncio.gather(
       get_user(user_id),
       get_user_keys(user_id)
   )
   ```

3. Оптимизируй обработку webhook'ов:
   - Добавь очередь для обработки платежей
   - Используй asyncio.create_task() для фоновых задач
   - Добавь rate limiting для внешних API

4. Добавь connection pooling для БД:
   - Создай пул соединений
   - Переиспользуй соединения
   - Добавь timeout для операций

5. Оптимизируй обработку файлов:
   - Используй aiofiles для работы с файлами
   - Добавь асинхронную загрузку изображений

Ожидаемый результат: Улучшение производительности на 40-60%
```

---

## 🔒 Безопасность и надежность

### Улучшение безопасности
```
Улучши безопасность проекта Dark Maximus.

Контекст:
- Проект: Dark Maximus (Telegram-бот для продажи VPN)
- Проблемы: отсутствие CSRF защиты, слабая валидация данных
- Нужно усилить безопасность

Задачи:
1. Добавь CSRF защиту для веб-панели:
   ```python
   from flask_wtf.csrf import CSRFProtect
   csrf = CSRFProtect(app)
   ```

2. Улучши валидацию входных данных:
   - Создай валидаторы для всех форм
   - Добавь санитизацию HTML
   - Проверяй типы данных и диапазоны

3. Добавь rate limiting для API endpoints:
   ```python
   from flask_limiter import Limiter
   limiter = Limiter(app, key_func=get_remote_address)
   
   @app.route('/api/payment', methods=['POST'])
   @limiter.limit("10 per minute")
   def create_payment():
       pass
   ```

4. Шифруй чувствительные данные в БД:
   - Пароли уже хешированы (bcrypt)
   - Добавь шифрование для токенов
   - Используй Fernet для шифрования

5. Добавь аудит логи для критических операций:
   - Логирование всех платежей
   - Логирование изменений настроек
   - Логирование действий администраторов

6. Улучши обработку сессий:
   - Добавь timeout для сессий
   - Используй secure cookies
   - Добавь проверку IP адресов

Ожидаемый результат: Повышение уровня безопасности до production-ready
```

### Улучшение обработки ошибок
```
Улучши обработку ошибок в проекте Dark Maximus.

Контекст:
- Проект: Dark Maximus (Telegram-бот для продажи VPN)
- Проблема: 504 вхождения "except Exception:", игнорирование ошибок
- Нужно создать централизованную обработку ошибок

Задачи:
1. Замени все except Exception: на конкретные исключения:
   ```python
   # Вместо
   except Exception as e:
       logger.error(f"Error: {e}")
   
   # Используй
   except (ValueError, TypeError) as e:
       logger.error(f"Validation error: {e}")
   except DatabaseError as e:
       logger.error(f"Database error: {e}")
   except PaymentError as e:
       logger.error(f"Payment error: {e}")
   ```

2. Создай кастомные исключения:
   ```python
   class DarkMaximusError(Exception):
       pass
   
   class PaymentError(DarkMaximusError):
       pass
   
   class DatabaseError(DarkMaximusError):
       pass
   
   class ValidationError(DarkMaximusError):
       pass
   ```

3. Создай централизованный обработчик ошибок:
   ```python
   @app.errorhandler(DarkMaximusError)
   def handle_custom_error(error):
       logger.error(f"Custom error: {error}")
       return jsonify({"error": str(error)}), 400
   ```

4. Добавь retry механизм для внешних API:
   ```python
   from tenacity import retry, stop_after_attempt, wait_exponential
   
   @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
   async def call_external_api():
       pass
   ```

5. Улучши логирование ошибок с контекстом:
   - Добавь request_id для трассировки
   - Логируй пользователя и действие
   - Добавь stack trace для критических ошибок

Ожидаемый результат: Надежная обработка ошибок с детальным логированием
```

---

## 🧪 Тестирование

### Создание unit тестов
```
Создай unit тесты для проекта Dark Maximus.

Контекст:
- Проект: Dark Maximus (Telegram-бот для продажи VPN)
- Текущее покрытие: 0%
- Целевое покрытие: 80%+

Задачи:
1. Добавь зависимости в pyproject.toml:
   ```
   pytest = "^7.4.0"
   pytest-asyncio = "^0.21.0"
   pytest-mock = "^3.11.0"
   pytest-cov = "^4.1.0"
   ```

2. Создай структуру тестов:
   ```
   tests/
   ├── __init__.py
   ├── conftest.py        # Конфигурация pytest
   ├── unit/              # Unit тесты
   │   ├── test_database.py
   │   ├── test_handlers.py
   │   ├── test_services.py
   │   └── test_utils.py
   ├── integration/       # Интеграционные тесты
   │   ├── test_api.py
   │   ├── test_bot.py
   │   └── test_payments.py
   └── fixtures/          # Тестовые данные
       ├── users.json
       └── keys.json
   ```

3. Напиши тесты для database.py:
   - Тесты CRUD операций
   - Тесты валидации данных
   - Тесты обработки ошибок

4. Напиши тесты для handlers.py:
   - Тесты команд бота
   - Тесты обработки платежей
   - Тесты админских функций

5. Настрой GitHub Actions для запуска тестов:
   ```yaml
   name: Tests
   on: [push, pull_request]
   jobs:
     test:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v3
         - name: Set up Python
           uses: actions/setup-python@v4
           with:
             python-version: '3.11'
         - name: Install dependencies
           run: pip install -e .
         - name: Run tests
           run: pytest --cov=src tests/
   ```

Ожидаемый результат: Покрытие тестами 80%+ с автоматическим запуском
```

---

## 📊 Мониторинг и логирование

### Добавление продвинутого мониторинга
```
Добавь продвинутый мониторинг в проект Dark Maximus.

Контекст:
- Проект: Dark Maximus (Telegram-бот для продажи VPN)
- Текущий мониторинг: базовое логирование
- Нужно добавить метрики и алерты

Задачи:
1. Добавь Prometheus метрики:
   ```python
   from prometheus_client import Counter, Histogram, Gauge
   
   # Метрики
   request_count = Counter('http_requests_total', 'Total HTTP requests')
   request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration')
   active_users = Gauge('active_users', 'Number of active users')
   ```

2. Интегрируй Sentry для отслеживания ошибок:
   ```python
   import sentry_sdk
   from sentry_sdk.integrations.flask import FlaskIntegration
   
   sentry_sdk.init(
       dsn="YOUR_SENTRY_DSN",
       integrations=[FlaskIntegration()],
       traces_sample_rate=1.0
   )
   ```

3. Создай дашборд для мониторинга:
   - Grafana дашборд с метриками
   - Графики производительности
   - Алерты для критических ошибок

4. Добавь health check endpoints:
   ```python
   @app.route('/health')
   def health_check():
       return {"status": "healthy", "timestamp": datetime.now()}
   
   @app.route('/metrics')
   def metrics():
       return generate_latest()
   ```

5. Настрой логирование в структурированном формате:
   ```python
   import structlog
   
   logger = structlog.get_logger()
   logger.info("User action", user_id=123, action="payment", amount=100)
   ```

Ожидаемый результат: Полный мониторинг системы с алертами
```

---

## 📝 Документация

### Обновление документации
```
Обнови документацию проекта Dark Maximus после модернизации.

Контекст:
- Проект: Dark Maximus (Telegram-бот для продажи VPN)
- Текущая версия: 2.72.12
- Нужно обновить документацию с новыми возможностями

Задачи:
1. Обнови README.md:
   - Добавь новые возможности
   - Обнови инструкции по установке
   - Добавь информацию о тестах
   - Обнови список зависимостей

2. Создай API документацию:
   - Описание всех endpoints
   - Примеры запросов и ответов
   - Коды ошибок
   - Аутентификация

3. Обнови CHANGELOG.md:
   - Добавь все изменения
   - Укажи breaking changes
   - Добавь информацию о миграции

4. Создай руководство по развертыванию:
   - Docker deployment
   - Production настройки
   - Мониторинг и логирование
   - Backup и восстановление

5. Добавь диаграммы архитектуры:
   - Общая схема системы
   - Диаграмма базы данных
   - Схема API
   - Диаграмма развертывания

Ожидаемый результат: Полная и актуальная документация
```

---

## 🎯 Финальная проверка

### Комплексная проверка проекта
```
Проведи финальную проверку проекта Dark Maximus после модернизации.

Контекст:
- Проект: Dark Maximus (Telegram-бот для продажи VPN)
- Выполнены все этапы модернизации
- Нужно проверить готовность к production

Задачи:
1. Запусти все тесты и убедись что они проходят:
   ```bash
   pytest --cov=src tests/
   ```

2. Проверь производительность под нагрузкой:
   - Нагрузочное тестирование API
   - Тестирование базы данных
   - Проверка времени отклика

3. Проверь безопасность:
   - Сканирование уязвимостей
   - Проверка зависимостей
   - Аудит кода

4. Обнови версию в pyproject.toml:
   ```
   version = "3.0.0"  # Major version после модернизации
   ```

5. Создай релиз с тегами:
   ```bash
   git tag -a v3.0.0 -m "Major modernization release"
   git push origin v3.0.0
   ```

6. Проверь развертывание:
   - Docker build
   - Docker compose up
   - Проверка всех сервисов

Ожидаемый результат: Проект готов к production с версией 3.0.0
```

---

## 📋 Чек-лист готовности

### Перед началом работы:
- [ ] Создал backup текущего состояния
- [ ] Создал новую ветку для изменений
- [ ] Проверил текущее состояние проекта
- [ ] Подготовил тестовое окружение

### После выполнения задачи:
- [ ] Протестировал изменения
- [ ] Обновил документацию
- [ ] Зафиксировал изменения в git
- [ ] Обновил CHANGELOG.md
- [ ] Проверил что ничего не сломалось

### Критерии успеха:
- [ ] Код работает без ошибок
- [ ] Тесты проходят
- [ ] Производительность улучшилась
- [ ] Безопасность усилена
- [ ] Документация обновлена

---

**Последнее обновление**: 19.01.2025  
**Версия промтов**: 1.0
