<!-- eb265aa0-374f-4dcd-af58-ef44fc2e4859 0f9967d1-42f8-45f9-a20e-f9aef4c9358f -->
# План исправления Dockerfile.tests и создания install-monitoring.sh

## Проблема с Dockerfile.tests

При сборке возникает ошибка:

```
error: error in 'egg_base' option: 'src' does not exist or is not a directory
```

**Причина:** При установке `-e ".[test]"` pip пытается установить пакет в editable mode, но:

- `pyproject.toml` ссылается на `readme = "README.md"` и `where = ["src"]`
- Файлы `README.md` и директория `src/` еще не скопированы в контейнер
- Установка происходит на строке 20, а копирование `src/` только на строке 24

## Исправление Dockerfile.tests

**Изменить порядок операций:**

1. Копировать `README.md`, `pyproject.toml` и `src/` ДО установки зависимостей
2. Установить зависимости после копирования всех необходимых файлов
3. Затем скопировать `tests/`

**Новый порядок:**

```dockerfile
# Копирование необходимых файлов для установки пакета
COPY README.md pyproject.toml ./
COPY src/ /app/src/

# Установка зависимостей (теперь src/ существует)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e ".[test]"

# Копирование тестов
COPY tests/ /app/tests/
```

**Файл:** `Dockerfile.tests`

## Переименование сервиса tests → monitoring

Переименовать сервис `tests` в `monitoring` для лучшей согласованности с названием скрипта `install-monitoring.sh` и более точного отражения назначения (не только тесты, но и мониторинг через Allure).

**Изменения:**

1. В `docker-compose.yml`: сервис `tests` → `monitoring`
2. В `nginx/nginx.conf` и `nginx/nginx-ssl.conf`: все упоминания `tests` сервиса → `monitoring`
3. Container name: `dark-maximus-tests` → `dark-maximus-monitoring`
4. Dockerfile можно оставить `Dockerfile.tests` (техническое имя) или переименовать в `Dockerfile.monitoring` (рекомендуется для консистентности)

**Файлы для изменения:**

- `docker-compose.yml`
- `nginx/nginx.conf`
- `nginx/nginx-ssl.conf`
- `deploy/nginx/dark-maximus.conf.tpl`

## Создание install-monitoring.sh

Отдельный скрипт для установки инфраструктуры мониторинга (сервисы `monitoring` и `allure-service`).

**Структура скрипта (аналогично install.sh и ssl-install.sh):**

1. **Проверка зависимостей:**

   - Docker и Docker Compose
   - Права root
   - Наличие проекта (docker-compose.yml)

2. **Определение директории проекта:**

   - По умолчанию `/opt/dark-maximus`
   - Если скрипт запущен из другой директории - переход в проект

3. **Сборка и запуск сервисов:**

   - Сборка `Dockerfile.tests` (или `Dockerfile.monitoring` после переименования)
   - Запуск сервисов `monitoring` и `allure-service` через docker compose
   - Проверка доступности Allure Service на `localhost:5050`

4. **Создание директорий:**

   - `allure-results/` и `allure-report/` если их нет

5. **Опционально - настройка Nginx (если нужно):**

   - Можно добавить упоминание, что для внешнего доступа нужен SSL через `ssl-install.sh`

**Использование:**

```bash
# Прямая установка
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install-monitoring.sh | sudo bash

# Или локально
sudo ./install-monitoring.sh
```

**Файл:** `install-monitoring.sh` (новый)

## Обновление deploy/nginx/dark-maximus.conf.tpl

Добавить конфигурацию для `tests.dark-maximus.com` в шаблон, который используется `ssl-install.sh`.

**Что добавить:**

1. Upstream `allure_backend` после других upstream
2. HTTP редирект на HTTPS для `tests.dark-maximus.com`
3. HTTPS server block для `tests.dark-maximus.com` с SSL сертификатами
4. Проксирование на `127.0.0.1:5050` (localhost для production)

**Файл:** `deploy/nginx/dark-maximus.conf.tpl`

## Структура файлов после реализации

```
.
├── Dockerfile.tests (исправлен порядок COPY)
├── install-monitoring.sh (новый)
├── deploy/nginx/
│   └── dark-maximus.conf.tpl (добавлена конфигурация для tests.dark-maximus.com)
└── docker-compose.yml (уже содержит сервисы tests и allure-service)
```

## Проверка после реализации

1. Успешная сборка `Dockerfile.tests` без ошибок
2. Запуск сервисов через `install-monitoring.sh`
3. Доступность Allure Service на `http://localhost:5050`
4. После `ssl-install.sh` - доступность `https://tests.dark-maximus.com`