# ⚡ Быстрые команды для Dark Maximus

> **Готовые команды** для копирования в новые диалоги

## 🔄 Обновление зависимостей

### Flask
```
Обнови Flask с 3.1.1 до последней версии в Dark Maximus. Проверь совместимость с app.py и обнови pyproject.toml.
```

### YooKassa  
```
Обнови yookassa с 3.5.0 до последней версии в Dark Maximus. Проверь API совместимость и протестируй платежи.
```

### aiogram (КРИТИЧНО)
```
ОСТОРОЖНО обнови aiogram с 3.21.0 до последней версии в Dark Maximus. Проверь breaking changes и протестируй бота.
```

## 🗄️ База данных

### Оптимизация SQLite
```
Оптимизируй SQLite в Dark Maximus: добавь connection pooling, WAL режим, индексы и асинхронные функции.
```

### Миграция на PostgreSQL
```
Подготовь миграцию с SQLite на PostgreSQL в Dark Maximus: создай Docker конфиг, скрипт миграции и обнови database.py.
```

## 🏗️ Архитектура

### Разделение handlers.py
```
Разбей handlers.py (5645 строк) на модули в Dark Maximus: admin_handlers.py, user_handlers.py, payment_handlers.py, support_handlers.py.
```

### Создание сервисов
```
Создай сервисный слой в Dark Maximus: UserService, PaymentService, KeyService, NotificationService.
```

### Repository Pattern
```
Внедри Repository Pattern в Dark Maximus: создай UserRepository, KeyRepository, TransactionRepository.
```

## 🚀 Производительность

### Redis кэширование
```
Добавь Redis кэширование в Dark Maximus: обнови docker-compose.yml, создай cache_manager.py, добавь кэш для хостов и планов.
```

### Улучшение асинхронности
```
Улучши асинхронность в Dark Maximus: замени синхронные БД операции на асинхронные, добавь asyncio.gather(), оптимизируй webhook'и.
```

## 🔒 Безопасность

### Улучшение безопасности
```
Улучши безопасность Dark Maximus: добавь CSRF защиту, rate limiting, шифрование данных, аудит логи.
```

### Обработка ошибок
```
Улучши обработку ошибок в Dark Maximus: замени except Exception на конкретные исключения, создай кастомные исключения, добавь retry механизм.
```

## 🧪 Тестирование

### Unit тесты
```
Создай unit тесты для Dark Maximus: добавь pytest, создай структуру tests/, напиши тесты для database.py и handlers.py.
```

### CI/CD
```
Настрой CI/CD для Dark Maximus: создай GitHub Actions, добавь автоматические тесты, проверку качества кода, деплой.
```

## 📊 Мониторинг

### Продвинутый мониторинг
```
Добавь мониторинг в Dark Maximus: Prometheus метрики, Sentry интеграция, Grafana дашборд, health check endpoints.
```

## 📝 Документация

### Обновление документации
```
Обнови документацию Dark Maximus: README.md, API документация, CHANGELOG.md, руководство по развертыванию.
```

## 🎯 Финальная проверка

### Комплексная проверка
```
Проведи финальную проверку Dark Maximus: запусти тесты, проверь производительность, безопасность, обнови версию до 3.0.0.
```

---

## 📋 Контекст для всех команд

Добавляйте к любой команде:
```
Контекст: Dark Maximus v2.72.12, Python 3.11, Docker, SQLite, aiogram 3.21.0, Flask 3.1.1
```

---

**Версия**: 1.0  
**Дата**: 19.01.2025
