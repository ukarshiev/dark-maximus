<!-- ccbceafd-0e27-4f42-91aa-3722b9acb391 cb1c5335-f7fa-44ca-be59-ea585b50b53f -->
# Настройка Categories и Environment в Allure отчетах

## Проблемы

1. **Categories пустые** (0 items total) - Allure Service не использует `allure-categories.json` автоматически
2. **Environment пустые** (There are no environment variables) - переменные окружения не добавляются в отчеты

## Решение

### 1. Настройка Categories в docker-compose.yml

**Файл:** `docker-compose.yml` (строки 158-163)

Добавить переменную окружения `CATEGORIES_FILE` в секцию `environment` сервиса `allure-service`:

```yaml
environment:
  - CHECK_RESULTS_EVERY_SECONDS=30
  - KEEP_HISTORY=1
  - KEEP_HISTORY_LATEST=30
  - ALLURE_PUBLIC_URL=http://localhost:50005
  - URL_PREFIX=/allure-docker-service
  - CATEGORIES_FILE=/app/allure-categories.json  # Новая строка
```

### 2. Настройка Environment в conftest.py

**Файл:** `tests/conftest.py`

**Шаг 2.1:** Добавить импорт `allure` в начало файла (после строки 16):

```python
import allure
```

**Шаг 2.2:** Обновить функцию `pytest_configure` (строки 22-28), добавив вызов `allure.dynamic.environment()`:

```python
def pytest_configure(config):
    """Настройка pytest перед запуском тестов"""
    allure_results_dir = project_root / "allure-results"
    allure_results_dir.mkdir(parents=True, exist_ok=True)
    
    # Устанавливаем alluredir
    config.option.alluredir = str(allure_results_dir)
    
    # Добавляем переменные окружения в Allure отчеты
    allure.dynamic.environment(
        ENVIRONMENT=os.getenv("ENVIRONMENT", "development"),
        PYTHON_VERSION=sys.version.split()[0],
        PYTEST_VERSION=pytest.__version__,
    )
```

### 3. Обновление документации

**Файл:** `docs/guides/testing/allure-reporting.md`

Обновить раздел о конфигурации Allure Service, добавив информацию о переменной `CATEGORIES_FILE` и настройке environment variables через `conftest.py`.

### 4. Обновление CHANGELOG.md

**Файл:** `CHANGELOG.md`

Добавить новую запись в начало файла с описанием исправлений:

- Исправлена проблема с отображением Categories в Allure отчетах
- Добавлена настройка Environment variables в Allure отчеты

### 5. Обновление версии в pyproject.toml

**Файл:** `pyproject.toml`

Обновить версию проекта согласно правилам версионирования (patch bump для исправлений).

## Проверка после изменений

1. Перезапустить `allure-service`: `docker compose restart allure-service`
2. Запустить тесты для генерации новых результатов с environment variables
3. Проверить отображение Categories и Environment в Allure отчетах

## Зависимости

- Изменения в `docker-compose.yml` требуют перезапуска `allure-service`
- Изменения в `conftest.py` применяются при следующем запуске тестов

### To-dos

- [ ] Добавить переменную окружения CATEGORIES_FILE в docker-compose.yml для allure-service
- [ ] Добавить импорт allure в tests/conftest.py
- [ ] Добавить allure.dynamic.environment() в pytest_configure для отображения переменных окружения в Allure отчетах
- [ ] Обновить документацию allure-reporting.md с информацией о CATEGORIES_FILE и environment variables
- [ ] Добавить запись в CHANGELOG.md об исправлениях Categories и Environment
- [ ] Обновить версию в pyproject.toml (patch bump)