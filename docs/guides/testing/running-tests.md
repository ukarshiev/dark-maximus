# Запуск тестов в Dark Maximus

> **Дата последней редакции:** 15.11.2025 16:44

## Обзор

Тесты в проекте Dark Maximus можно запускать несколькими способами: локально, в Docker контейнере или через Nx. Рекомендуется использовать Docker контейнер для согласованности окружения и автоматической генерации Allure отчетов.

## Способы запуска тестов

### 1. Запуск в Docker контейнере (рекомендуется)

**Преимущества:**
- Изолированное окружение
- Автоматическая генерация Allure отчетов
- Не требует установки зависимостей локально

#### Установка инфраструктуры

```bash
# Linux/macOS
sudo ./install-autotest.sh

# Windows (PowerShell)
docker compose build autotest
docker compose up -d autotest allure-service
```

#### Запуск всех тестов

```bash
docker compose exec autotest pytest
```

#### Запуск конкретных категорий тестов

```bash
# Только unit-тесты
docker compose exec autotest pytest tests/unit/ -m unit

# Только интеграционные тесты
docker compose exec autotest pytest tests/integration/ -m integration

# Только E2E тесты
docker compose exec autotest pytest tests/e2e/ -m e2e

# Тесты с маркером database
docker compose exec autotest pytest -m database

# Тесты с маркером bot
docker compose exec autotest pytest -m bot
```

#### Запуск конкретных тестов

```bash
# Конкретный файл
docker compose exec autotest pytest tests/unit/test_database/test_user_operations.py

# Конкретный тест
docker compose exec autotest pytest tests/unit/test_database/test_user_operations.py::test_register_user_if_not_exists

# Конкретный класс тестов
docker compose exec autotest pytest tests/unit/test_database/test_user_operations.py::TestUserOperations
```

#### Параметры pytest

```bash
# Вербозный вывод
docker compose exec autotest pytest -v

# Очень вербозный вывод
docker compose exec autotest pytest -vv

# Остановка на первой ошибке
docker compose exec autotest pytest -x

# Показать print() в тестах
docker compose exec autotest pytest -s

# Вывести только имена тестов
docker compose exec autotest pytest --collect-only

# Запуск только упавших тестов с последнего запуска
docker compose exec autotest pytest --lf
```

#### Просмотр результатов

```bash
# Логи контейнера
docker compose logs -f autotest

# Веб-интерфейс Allure отчетов
# Откройте в браузере: http://localhost:50005/allure-docker-service/projects/default/reports/latest/index.html
```

### 2. Локальный запуск (требует установки зависимостей)

**Требования:**
- Python 3.11+
- Установленные зависимости из `pyproject.toml`

#### Установка зависимостей

```bash
# Создать виртуальное окружение
python -m venv venv

# Активировать виртуальное окружение
# Linux/macOS
source venv/bin/activate
# Windows
venv\Scripts\activate

# Установить зависимости
pip install -e ".[test]"
```

#### Запуск тестов

```bash
# Все тесты
pytest tests/

# Используя скрипт (bash)
./tests/run_tests.sh

# Используя скрипт (PowerShell)
.\tests\run_tests.ps1

# С параметрами pytest
pytest tests/ -v -x
```

#### Генерация Allure отчетов (локально)

```bash
# Запустить тесты с генерацией результатов
pytest tests/ --alluredir=allure-results

# Просмотреть отчет (требует установки Allure CLI)
allure serve allure-results
```

### 3. Запуск через Nx

Проект использует Nx для управления монорепозиторием:

```bash
# Запустить тесты через Nx
npx nx test bot

# Запустить тесты для всех проектов
npx nx run-many --target=test --all
```

**Примечание:** Nx команда `test` запускает pytest локально, без Docker.

## Скрипты запуска тестов

### run_tests.sh (bash)

Скрипт для запуска тестов с генерацией Allure отчетов:

```bash
#!/bin/bash
# Скрипт запуска тестов с генерацией Allure отчетов
# Использование: ./run_tests.sh [опции pytest]

pytest --alluredir=allure-results "$@"

if [ $? -eq 0 ]; then
    echo "✅ Тесты успешно выполнены. Результаты сохранены в allure-results/"
    echo "📊 Для просмотра отчета запустите: allure serve allure-results"
else
    echo "❌ Тесты завершились с ошибками. Проверьте allure-results/ для деталей."
    exit 1
fi
```

**Использование:**

```bash
# Запустить все тесты
./tests/run_tests.sh

# Запустить с параметрами
./tests/run_tests.sh -v -x

# Запустить только unit-тесты
./tests/run_tests.sh tests/unit/ -m unit
```

### run_tests.ps1 (PowerShell)

Скрипт для запуска тестов в Windows:

```powershell
# Скрипт запуска тестов с генерацией Allure отчетов
# Использование: .\run_tests.ps1 [опции pytest]

param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$PytestArgs
)

$allureResults = Join-Path $PSScriptRoot "..\allure-results"
pytest --alluredir=$allureResults $PytestArgs

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Тесты успешно выполнены. Результаты сохранены в allure-results/" -ForegroundColor Green
    Write-Host "📊 Для просмотра отчета запустите: allure serve allure-results" -ForegroundColor Cyan
} else {
    Write-Host "❌ Тесты завершились с ошибками. Проверьте allure-results/ для деталей." -ForegroundColor Red
    exit 1
}
```

**Использование:**

```powershell
# Запустить все тесты
.\tests\run_tests.ps1

# Запустить с параметрами
.\tests\run_tests.ps1 -v -x

# Запустить только unit-тесты
.\tests\run_tests.ps1 tests/unit/ -m unit
```

## Параметры pytest

### Основные параметры

```bash
# Вербозность
-v, --verbose              # Вербозный вывод
-vv                        # Очень вербозный вывод
-q, --quiet                # Тихий режим

# Остановка
-x, --exitfirst            # Остановиться на первой ошибке
--maxfail=N                # Остановиться после N ошибок

# Выбор тестов
-k EXPRESSION              # Запустить тесты, соответствующие выражению
-m MARKEXPR                # Запустить тесты с маркером
--collect-only             # Показать список тестов без запуска

# Вывод
-s, --capture=no           # Показать print() в тестах
--tb=short                 # Короткий traceback (по умолчанию)
--tb=long                  # Длинный traceback
--tb=line                  # Однострочный traceback
--tb=no                    # Без traceback

# Повторный запуск
--lf, --last-failed        # Запустить только упавшие тесты с последнего запуска
--ff, --failed-first       # Запустить упавшие тесты первыми

# Allure
--alluredir=DIR            # Директория для результатов Allure (по умолчанию: allure-results)
```

### Примеры использования параметров

```bash
# Запустить тесты, содержащие "user" в названии
docker compose exec autotest pytest -k user

# Запустить только unit-тесты с маркером database
docker compose exec autotest pytest -m "unit and database"

# Запустить тесты с коротким traceback и остановкой на первой ошибке
docker compose exec autotest pytest -x --tb=short

# Показать print() в тестах
docker compose exec autotest pytest -s

# Запустить только упавшие тесты с последнего запуска
docker compose exec autotest pytest --lf
```

## Конфигурация pytest (pytest.ini)

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
    -v
    --tb=short
    --strict-markers
    --disable-warnings
    --alluredir=allure-results
    --ignore=tests/ad-hoc

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

**Примечание:** Параметры из `pytest.ini` применяются автоматически, но могут быть переопределены параметрами командной строки.

## Проверка статуса тестов

### Проверка статуса контейнеров

```bash
# Статус всех контейнеров
docker compose ps

# Статус контейнеров мониторинга
docker compose ps autotest allure-service

# Запустить контейнеры, если они остановлены
docker compose up -d autotest allure-service

# Остановить контейнеры
docker compose stop autotest allure-service
```

### Просмотр логов

```bash
# Логи контейнера autotest
docker compose logs -f autotest

# Логи Allure Service
docker compose logs -f allure-service

# Логи обоих контейнеров
docker compose logs -f autotest allure-service

# Последние 100 строк логов
docker compose logs --tail=100 autotest
```

## Решение проблем

### Контейнер не запускается

```bash
# Проверить логи
docker compose logs autotest

# Пересобрать контейнер
docker compose build --no-cache autotest

# Перезапустить контейнеры
docker compose restart autotest
```

### Тесты не находятся

```bash
# Проверить, что тесты в правильном месте
ls tests/unit/

# Проверить конфигурацию pytest
cat pytest.ini

# Запустить с вербозным выводом
docker compose exec autotest pytest --collect-only -v
```

### Ошибки импорта

```bash
# Проверить, что src/ доступен
docker compose exec autotest ls /app/src

# Проверить PYTHONPATH
docker compose exec autotest python -c "import sys; print(sys.path)"
```

## Рекомендации

1. **Используйте Docker:** Для согласованности окружения и автоматической генерации Allure отчетов
2. **Используйте маркеры:** Для категоризации и выборочного запуска тестов
3. **Проверяйте логи:** При ошибках проверяйте логи контейнеров
4. **Запускайте часто:** Запускайте тесты часто для раннего обнаружения проблем

## См. также

- [Структура тестов](testing-structure.md) — организация тестов
- [Allure отчеты](allure-reporting.md) — работа с Allure Framework
- [Best Practices](best-practices.md) — рекомендации по написанию тестов
- [Справочник по тестированию](../../reference/testing-reference.md) — полный справочник

---

**Версия:** 1.0  
**Последнее обновление:** 15.11.2025 16:44  
**Автор:** Dark Maximus Team

