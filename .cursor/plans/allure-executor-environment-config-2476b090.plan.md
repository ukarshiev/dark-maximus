<!-- 2476b090-3a88-4bac-b53d-92c88919353f 34e1919c-1aac-44fe-a681-9e2bf53c8e5f -->
# Улучшение конфигурации Allure Report

## Цель

Настроить разделы "Система выполнения тестов" и "Окружение" в Allure Report согласно best practices, добавив полную информацию о системе выполнения и окружении.

## Изменения

### 1. Обновление executor.json

**Файл:** `allure-results/executor.json`

Текущий файл содержит минимальную конфигурацию. Обновим его с более информативными данными:

- `name`: Оставить "Automatic Execution" или изменить на более описательное (например, "Docker Compose Test Execution")
- `type`: Определить на основе наличия CI/CD (если нет CI/CD - использовать "local")
- `buildName`: Улучшить формат, добавив дату/время (например, "dark-maximus-tests-YYYY-MM-DD-HHMM")
- `buildOrder`: Автоматически инкрементировать или использовать текущую дату как порядковый номер
- `reportName`: Оставить "default" или использовать имя проекта "dark-maximus"
- `buildUrl`: Оставить пустым для локального запуска, или добавить URL CI/CD если используется
- `reportUrl`: Обновить если необходимо

**Пример улучшенной конфигурации:**

```json
{
  "reportName": "dark-maximus",
  "buildName": "dark-maximus-tests-2025-01-16-0658",
  "buildOrder": "1",
  "name": "Docker Compose Test Execution",
  "reportUrl": "../1/index.html",
  "buildUrl": "",
  "type": "local"
}
```

### 2. Создание environment.properties

**Файл:** `allure-results/environment.properties`

Создать новый файл с информацией об окружении:

- **Python**: 3.11 (из Dockerfile.tests)
- **pytest**: >=7.4.0 (из pyproject.toml)
- **allure-pytest**: >=2.13.0 (из pyproject.toml)
- **Allure CLI**: 2.24.1 (из Dockerfile.tests)
- **OS**: Linux (Alpine/Debian-based, из python:3.11-slim)
- **Container**: dark-maximus-monitoring (из docker-compose.yml)
- **Docker**: 28.5.2 (текущая версия)
- **aiogram**: 3.21.0 (из pyproject.toml)
- **Flask**: 3.1.1 (из pyproject.toml)
- **Network**: dark-maximus-network (из docker-compose.yml)

**Формат файла:**

```properties
Python=3.11
pytest>=7.4.0
allure-pytest>=2.13.0
Allure CLI=2.24.1
OS=Linux (Debian-based slim)
Container=dark-maximus-monitoring
Docker=28.5.2
aiogram=3.21.0
Flask=3.1.1
Network=dark-maximus-network
Test Framework=pytest
```

### 3. Обновление документации

**Файл:** `docs/guides/testing/allure-reporting.md`

Добавить раздел о настройке executor.json и environment.properties:

- Описание структуры executor.json
- Описание структуры environment.properties
- Примеры конфигурации
- Инструкции по автоматическому обновлению buildName/buildOrder при запуске тестов

## Технические детали

1. **executor.json** - JSON файл в директории `allure-results/`, автоматически читается Allure при генерации отчета
2. **environment.properties** - текстовый файл в директории `allure-results/`, автоматически отображается в разделе "Окружение"
3. Файлы должны быть созданы до генерации отчета, чтобы информация появилась в Allure Report
4. Для автоматического обновления buildName с датой/временем можно создать скрипт или использовать переменные окружения при запуске тестов

## Зависимости

- Файлы будут созданы в `allure-results/`, который уже существует и настроен в docker-compose.yml
- Allure Service автоматически подхватит изменения при следующей генерации отчета