# Docker Архитектура dark-maximus

> Обновлено: 29.12.2024  
> Версия: 2.57.2

## 📦 Обзор

Проект использует **multi-stage Docker builds** для создания оптимизированных и безопасных контейнеров. Все сервисы упакованы в Docker и управляются через Docker Compose.

## 🏗️ Структура сервисов

### 1. **bot** - Основной Telegram бот

**Dockerfile**: `Dockerfile`  
**Порт**: 1488  
**Описание**: Основной сервис с Telegram ботом и веб-панелью управления.

**Особенности**:
- Multi-stage build (Node.js для Tailwind CSS + Python)
- Автоматическая сборка CSS из Tailwind
- Python 3.11-slim базовый образ
- Автоматическое развертывание админской документации

**Команды**:
```bash
# Сборка
docker compose build bot

# Запуск
docker compose up -d bot

# Логи
docker compose logs -f bot
```

### 2. **docs** - Пользовательская документация

**Dockerfile**: `Dockerfile.docs`  
**Порт**: 3001 (внутренний 8080)  
**Описание**: Статичная пользовательская документация на Nginx.

**Особенности**:
- Multi-stage build (Alpine + Nginx)
- Использует `nginxinc/nginx-unprivileged` для безопасности
- Не-root пользователь (nginx)
- Healthcheck endpoint
- Gzip сжатие
- Кэширование статики

**Команды**:
```bash
# Сборка
docker compose build docs

# Запуск
docker compose up -d docs

# Логи
docker compose logs -f docs
```

### 3. **codex-docs** - Админская документация

**Dockerfile**: `Dockerfile.codex-docs`  
**Порт**: 3002  
**Описание**: Интерактивная админская документация на базе Codex.docs.

**Особенности**:
- Multi-stage build
- Базовый образ: `ghcr.io/codex-team/codex.docs:v2.0.0-rc.8`
- WebSocket поддержка
- Healthcheck
- Volumes для данных и загрузок

**Команды**:
```bash
# Сборка
docker compose build codex-docs

# Запуск
docker compose up -d codex-docs

# Логи
docker compose logs -f codex-docs
```

## 🔧 Docker Compose конфигурация

### Основные настройки

```yaml
name: dark-maximus

services:
  bot:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - '1488:1488'
    volumes:
      - .:/app/project
      - /app/.venv
      - sessions_data:/app/sessions

  docs:
    build:
      context: .
      dockerfile: Dockerfile.docs
    ports:
      - '3001:8080'
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:8080/health"]

  codex-docs:
    build:
      context: .
      dockerfile: Dockerfile.codex-docs
    ports:
      - '3002:3000'
    volumes:
      - codex_uploads:/usr/src/app/uploads
      - codex_db:/usr/src/app/db
```

### Volumes

- `sessions_data` - Сессии Telegram бота
- `codex_uploads` - Загруженные файлы в Codex.docs
- `codex_db` - База данных Codex.docs

## 🚀 Управление контейнерами

### Запуск всех сервисов

```bash
docker compose up -d
```

### Перезапуск конкретного сервиса

```bash
# Перезапуск бота
docker compose restart bot

# Перезапуск документации
docker compose restart docs

# Перезапуск админской документации
docker compose restart codex-docs
```

### Просмотр статуса

```bash
# Статус всех контейнеров
docker compose ps

# Статус конкретного контейнера
docker compose ps bot
```

### Просмотр логов

```bash
# Все логи
docker compose logs -f

# Логи конкретного сервиса
docker compose logs -f bot
docker compose logs -f docs
docker compose logs -f codex-docs

# Последние 100 строк
docker compose logs --tail=100 bot
```

### Остановка

```bash
# Остановить все сервисы
docker compose down

# Остановить с удалением volumes
docker compose down -v
```

## 🔨 Сборка образов

### Полная пересборка

```bash
# Сборка всех сервисов
docker compose build --no-cache

# Сборка конкретного сервиса
docker compose build bot
docker compose build docs
docker compose build codex-docs
```

### Сборка с кэшем

```bash
docker compose build
```

## 📊 Мониторинг

### Использование ресурсов

```bash
# Использование ресурсов всеми контейнерами
docker stats

# Использование ресурсов конкретного контейнера
docker stats dark-maximus-bot
docker stats dark-maximus-docs
docker stats dark-maximus-codex-docs
```

### Healthcheck

Все сервисы имеют встроенные healthcheck:

```bash
# Проверка здоровья всех сервисов
docker compose ps

# Детальная информация о здоровье
docker inspect --format='{{.State.Health.Status}}' dark-maximus-bot
docker inspect --format='{{.State.Health.Status}}' dark-maximus-docs
docker inspect --format='{{.State.Health.Status}}' dark-maximus-codex-docs
```

## 🔍 Отладка

### Вход в контейнер

```bash
# Вход в контейнер бота
docker compose exec bot bash

# Вход в контейнер документации
docker compose exec docs sh

# Вход в контейнер админской документации
docker compose exec codex-docs sh
```

### Проверка конфигурации

```bash
# Проверка docker-compose.yml
docker compose config

# Проверка с выводом переменных
docker compose config --services
```

## 🧹 Очистка

### Удаление остановленных контейнеров

```bash
docker container prune
```

### Удаление неиспользуемых образов

```bash
docker image prune -a
```

### Полная очистка Docker

```bash
docker system prune -a --volumes
```

## 🔐 Безопасность

### Best Practices

1. **Не-root пользователи**: Все сервисы запускаются от непривилегированных пользователей
2. **Multi-stage builds**: Минимальные образы без build-зависимостей
3. **Healthchecks**: Автоматическая проверка здоровья сервисов
4. **Read-only volumes**: Документация монтируется как read-only
5. **Минимальные базовые образы**: Alpine Linux для минимального размера

### Обновление образов

```bash
# Обновление базовых образов
docker compose pull

# Пересборка с обновлением
docker compose build --pull
```

## 📈 Производительность

### Оптимизация сборки

1. **Layer caching**: Зависимости устанавливаются до копирования кода
2. **Multi-stage builds**: Исключение build-зависимостей из финального образа
3. **.dockerignore**: Исключение ненужных файлов из контекста сборки

### Размеры образов

Примерные размеры образов:
- `bot`: ~500 MB
- `docs`: ~50 MB
- `codex-docs`: ~300 MB

## 🛠️ Troubleshooting

### Контейнер не запускается

```bash
# Проверка логов
docker compose logs bot

# Проверка конфигурации
docker compose config

# Пересборка без кэша
docker compose build --no-cache bot
```

### Проблемы с портами

```bash
# Проверка занятых портов
netstat -tulpn | grep -E '1488|3001|3002'

# Освобождение портов
sudo lsof -ti:1488 | xargs kill -9
```

### Проблемы с volumes

```bash
# Список volumes
docker volume ls

# Информация о volume
docker volume inspect dark-maximus_sessions_data

# Удаление volume
docker volume rm dark-maximus_sessions_data
```

## 📚 Дополнительные ресурсы

- [Docker Multi-Stage Builds](https://docs.docker.com/build/building/multi-stage/)
- [Docker Compose Best Practices](https://docs.docker.com/compose/best-practices/)
- [Nginx Docker Image](https://hub.docker.com/_/nginx)
- [Codex.docs Documentation](https://github.com/codex-team/codex.docs)

---

*Последнее обновление: 29.12.2024*

