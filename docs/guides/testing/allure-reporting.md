# Allure Framework в Dark Maximus

> **Дата последней редакции:** 20.11.2025 (обновлено после исправления проблемы с сохранением результатов)

## Обзор

Проект Dark Maximus использует **Allure Framework** для генерации красивых и информативных отчетов о тестировании. Allure интегрирован с pytest и автоматически генерирует отчеты при каждом запуске тестов.

## Установка инфраструктуры

### Автоматическая установка (Linux/macOS)

```bash
sudo ./install-autotest.sh
```

Скрипт автоматически:
1. Создает директории для результатов Allure
2. Проверяет наличие сервисов в `docker-compose.yml`
3. Собирает Docker образ для автотестов
4. Запускает сервисы `autotest` и `allure-service`
5. Ожидает готовности Allure Service

### Ручная установка (Windows)

```bash
# Создать директории
mkdir allure-results allure-report

# Собрать Docker образ
docker compose build autotest

# Запустить сервисы
docker compose up -d autotest allure-service

# Проверить статус
docker compose ps autotest allure-service
```

### Проверка установки

```bash
# Проверить статус контейнеров
docker compose ps autotest allure-service

# Проверить доступность Allure Service
curl http://localhost:50005/allure-docker-service/projects
```

## Архитектура Allure в проекте

### Компоненты

1. **Контейнер `autotest`** — запускает тесты и генерирует результаты
   - Образ: `Dockerfile.tests`
   - Содержит Python 3.11, pytest, Allure CLI
   - Volume-маппинги: `tests/`, `src/`, `allure-results/`, `allure-report/`

2. **Allure Homepage** — главная страница с навигацией
   - Образ: `apps/allure-homepage/Dockerfile`
   - Порт: `127.0.0.1:50005` (публичный)
   - Flask приложение, отображает главную страницу и проксирует запросы к allure-service
   - Предоставляет удобную навигацию к отчетам и API документации

3. **Allure Service** — веб-сервис для просмотра отчетов
   - Образ: `frankescobar/allure-docker-service:latest`
   - Порт: `127.0.0.1:50004` (внутренний, доступен только через allure-homepage)
   - Автоматически генерирует отчеты из `allure-results/`

### Конфигурация Allure Docker Service

Конфигурация Allure Docker Service находится в `docker-compose.yml`:

```yaml
allure-service:
  image: frankescobar/allure-docker-service:latest
  container_name: dark-maximus-allure
  ports:
    - '127.0.0.1:50004:5050'  # Внутренний порт (внешний:внутренний)
  volumes:
    - ./allure-results:/app/allure-docker-api/static/projects/default/results
    - ./allure-report:/app/allure-report
    - ./allure-reports:/app/allure-docker-api/static/projects
    - ./allure-categories.json:/app/allure-categories.json
  environment:
    - CHECK_RESULTS_EVERY_SECONDS=30  # Проверка каждые 30 секунд (оптимизировано)
    - KEEP_HISTORY=1
    - KEEP_HISTORY_LATEST=30  # Хранить последние 30 отчетов (оптимизировано)
    - ALLURE_PUBLIC_URL=http://localhost:50005
    - URL_PREFIX=/allure-docker-service
    - CATEGORIES_FILE=/app/allure-categories.json  # Путь к файлу категорий дефектов
  networks:
    - dark-maximus-network

allure-homepage:
  build:
    context: ./apps/allure-homepage
    dockerfile: Dockerfile
  container_name: dark-maximus-allure-homepage
  ports:
    - '127.0.0.1:50005:50005'  # Публичный порт
  environment:
    - ALLURE_SERVICE_URL=http://allure-service:5050
    - PORT=50005
  depends_on:
    - allure-service
  networks:
    - dark-maximus-network
```

**Важно:** Volume mapping `./allure-results:/app/allure-docker-api/static/projects/default/results` настроен согласно официальной документации allure-docker-service. Результаты тестов сохраняются в `./allure-results/` на хосте и автоматически доступны в правильной директории проекта внутри контейнера.

#### Переменные окружения

- **`CHECK_RESULTS_EVERY_SECONDS`** — интервал проверки новых результатов (секунды)
- **`KEEP_HISTORY`** — сохранять историю запусков (1 = включено, 0 = выключено)
- **`ALLURE_PUBLIC_URL`** — полный публичный URL сервиса (включая путь `/allure-docker-service`)
- **`URL_PREFIX`** — префикс URL для корректной обработки путей к ресурсам (обязателен при работе через обратный прокси или нестандартный путь)

**Важно:** Переменная `URL_PREFIX=/allure-docker-service` необходима для корректной работы графиков истории и относительных путей в отчетах. Без неё могут возникнуть проблемы с отображением графиков и переходами между отчетами.

### Директории

```
project/
├── allure-results/              # ТОЛЬКО В КОРНЕ! JSON результаты тестов
│   ├── *.json                  # Результаты каждого теста (*-result.json, *-container.json)
│   ├── executor.json           # Метаданные выполнения
│   ├── history/                # История для трендов
│   └── .gitkeep                # Сохраняет директорию в git
│
├── allure-report/              # Сгенерированные HTML отчеты (опционально)
│   └── .gitkeep                # Сохраняет директорию в git
│
├── tests/                      # Тесты проекта
│   ├── pytest.ini             # Конфигурация pytest
│   ├── conftest.py             # Фикстуры (динамически устанавливает путь к allure-results)
│   └── ...                     # НЕТ allure-results здесь!
│
└── allure-categories.json      # Правила категоризации дефектов
```

**Важно:**
- Содержимое `allure-results/` и `allure-report/` игнорируется в `.gitignore`, но директории сохраняются через `.gitkeep`.
- **`allure-results/` должна быть ТОЛЬКО в корне проекта**, не в `tests/` или других поддиректориях.
- Путь к `allure-results/` устанавливается динамически в `conftest.py` через `pytest_configure`, что гарантирует правильный путь независимо от рабочей директории.

## Конфигурация отчетов

### Система выполнения тестов (executor.json)

Файл `allure-results/executor.json` содержит информацию о системе, которая запускает тесты. Этот файл автоматически отображается в разделе **"СИСТЕМА ВЫПОЛНЕНИЯ ТЕСТОВ"** в Allure Report.

**Структура файла:**

```json
{
  "reportName": "dark-maximus",
  "buildName": "dark-maximus-tests-2025-11-16-0704",
  "buildOrder": "1",
  "name": "Docker Compose Test Execution",
  "reportUrl": "../1/index.html",
  "buildUrl": "",
  "type": "local"
}
```

**Поля:**

- **`reportName`** — имя проекта в отчете (по умолчанию "dark-maximus")
- **`buildName`** — название сборки/запуска тестов (рекомендуется формат с датой: "dark-maximus-tests-YYYY-MM-DD-HHMM")
- **`buildOrder`** — порядковый номер сборки (можно использовать инкремент или дату)
- **`name`** — название системы выполнения (например, "Docker Compose Test Execution", "CI/CD Pipeline")
- **`reportUrl`** — относительный URL к отчету (обычно "../1/index.html")
- **`buildUrl`** — абсолютный URL к сборке в CI/CD (оставить пустым для локального запуска)
- **`type`** — тип исполнителя:
  - `"local"` — локальный запуск
  - `"jenkins"` — Jenkins CI/CD
  - `"teamcity"` — TeamCity
  - `"bamboo"` — Bamboo
  - `"gitlab"` — GitLab CI
  - `"github"` — GitHub Actions
  - `"azure"` — Azure DevOps

**Автоматическое обновление buildName:**

Для автоматического обновления `buildName` с текущей датой и временем можно использовать скрипт:

```bash
# PowerShell
$buildName = "dark-maximus-tests-$(Get-Date -Format 'yyyy-MM-dd-HHmm')"
$executor = @{
    reportName = "dark-maximus"
    buildName = $buildName
    buildOrder = "1"
    name = "Docker Compose Test Execution"
    reportUrl = "../1/index.html"
    buildUrl = ""
    type = "local"
} | ConvertTo-Json
Set-Content -Path "allure-results/executor.json" -Value $executor
```

```bash
# Bash
BUILD_NAME="dark-maximus-tests-$(date +%Y-%m-%d-%H%M)"
cat > allure-results/executor.json << EOF
{
  "reportName": "dark-maximus",
  "buildName": "$BUILD_NAME",
  "buildOrder": "1",
  "name": "Docker Compose Test Execution",
  "reportUrl": "../1/index.html",
  "buildUrl": "",
  "type": "local"
}
EOF
```

### Окружение (environment.properties)

Файл `allure-results/environment.properties` содержит информацию об окружении, на котором запускались тесты. Этот файл автоматически отображается в разделе **"ОКРУЖЕНИЕ"** в Allure Report.

**Структура файла:**

```properties
Python=3.11
pytest>=7.4.0
allure-pytest>=2.13.0
Allure CLI=2.24.1
OS=Linux (Debian-based slim)
Container=dark-maximus-autotest
Docker=28.5.2
aiogram=3.21.0
Flask=3.1.1
Network=dark-maximus-network
Test Framework=pytest
pytest-asyncio>=0.21.0
pytest-mock>=3.11.0
pytest-cov>=4.1.0
aiohttp=3.12.15
py3xui=0.4.0
aiosqlite=0.20.0
```

**Рекомендуемые поля:**

- **Версии технологий:** Python, pytest, allure-pytest, Allure CLI
- **Операционная система:** OS и её версия/дистрибутив
- **Инфраструктура:** Docker версия, название контейнера
- **Критичные зависимости:** версии основных библиотек (aiogram, Flask, aiohttp)
- **Сетевая конфигурация:** название сети Docker (если применимо)
- **Фреймворк тестирования:** pytest

**Формат:**

Файл использует формат `KEY=VALUE`, где:
- **KEY** — название параметра (без пробелов)
- **VALUE** — значение параметра

**Альтернативный формат (XML):**

Вместо `environment.properties` можно использовать `environment.properties.xml`:

```xml
<environment>
    <parameter>
        <key>Python</key>
        <value>3.11</value>
    </parameter>
    <parameter>
        <key>pytest</key>
        <value>>=7.4.0</value>
    </parameter>
</environment>
```

**Важно:**

1. Файлы `executor.json` и `environment.properties` должны находиться в директории `allure-results/`
2. Файлы должны быть созданы **до генерации отчета**, чтобы информация появилась в Allure Report
3. Allure Service автоматически подхватывает изменения при следующей генерации отчета
4. При использовании Docker Compose эти файлы можно создавать автоматически перед запуском тестов

**Создание файлов при запуске тестов:**

Для автоматического создания файлов при запуске тестов в Docker:

```bash
# Создать executor.json перед запуском тестов
docker compose exec autotest sh -c "
  BUILD_NAME=\"dark-maximus-tests-\$(date +%Y-%m-%d-%H%M)\"
  echo '{\"reportName\":\"dark-maximus\",\"buildName\":\"'\"\$BUILD_NAME\"'\",\"buildOrder\":\"1\",\"name\":\"Docker Compose Test Execution\",\"reportUrl\":\"../1/index.html\",\"buildUrl\":\"\",\"type\":\"local\"}' > /app/allure-results/executor.json
"
```

## Генерация отчетов

### Автоматическая генерация

При запуске тестов через pytest результаты автоматически сохраняются в `allure-results/`:

```bash
# Запуск тестов в Docker контейнере
docker compose exec autotest pytest

# Результаты автоматически сохраняются в allure-results/
# Allure Service автоматически генерирует отчеты
```

### Конфигурация pytest для Allure

В `pytest.ini` настроена интеграция с Allure:

```ini
[pytest]
addopts = 
    --alluredir=/app/allure-results
    ...
```

**Важно:** Путь к `allure-results/` устанавливается динамически в `tests/conftest.py` через хук `pytest_configure`, который переопределяет значение из `pytest.ini` на абсолютный путь от корня проекта. Это гарантирует правильный путь независимо от рабочей директории, из которой запускается pytest.

```python
# tests/conftest.py
def pytest_configure(config):
    """Настройка pytest перед запуском тестов"""
    allure_results_dir = project_root / "allure-results"
    allure_results_dir.mkdir(parents=True, exist_ok=True)
    config.option.alluredir = str(allure_results_dir)
```

### Параметры Allure

```bash
# Указать другую директорию для результатов
pytest --alluredir=./custom-results

# Просмотреть отчет локально (требует Allure CLI)
allure serve allure-results

# Сгенерировать статический отчет
allure generate allure-results -o allure-report
```

## Веб-интерфейс Allure

### Доступ к веб-интерфейсу

**Локальный доступ:**
- **Главная страница:** `http://localhost:50005/allure-docker-service/` — навигационная страница со ссылками на отчеты и API
- **Последний отчет Allure:** `http://localhost:50005/allure-docker-service/projects/default/reports/latest/index.html`
- **Swagger UI (API документация):** `http://localhost:50005/allure-docker-service/swagger-ui/`
- **API проектов:** `http://localhost:50005/allure-docker-service/projects`

**Внешний доступ (после настройки SSL):**
- `https://allure.dark-maximus.com/allure-docker-service/` — главная страница
- `https://allure.dark-maximus.com/allure-docker-service/projects/default/reports/latest/index.html` — последний отчет

### Функции веб-интерфейса

1. **Обзор результатов**
   - Общая статистика тестов
   - Графики успешности
   - Временные тренды

2. **Детали тестов**
   - Статус каждого теста
   - Время выполнения
   - Логи и стек-трейсы

3. **Категории дефектов**
   - Product defects — реальные баги в коде
   - Test defects — проблемы в самих тестах

4. **Фильтрация**
   - По статусу (passed, failed, broken, skipped)
   - По категориям
   - По маркерам pytest
   - По severity (CRITICAL, NORMAL, MINOR, TRIVIAL, BLOCKER)
   - По тегам (включая severity в тегах: "critical", "normal", "minor")

5. **История**
   - Сравнение результатов между запусками
   - Тренды успешности

## Категоризация дефектов

### Правила категоризации

Файл `allure-categories.json` содержит правила автоматической категоризации дефектов:

```json
[
  {
    "name": "Product defects",
    "matchedStatuses": ["failed"],
    "messageRegex": ".*AssertionError.*",
    "traceRegex": ".*assert.*is not None.*|.*assert.*==.*|.*assert.*!=.*"
  },
  {
    "name": "Test defects",
    "matchedStatuses": ["broken", "failed"],
    "messageRegex": ".*RuntimeError.*|.*TypeError.*|.*OperationalError.*|.*AttributeError.*|.*ValueError.*|.*KeyError.*|.*unexpected keyword argument.*|.*no such table.*|.*got an unexpected.*"
  },
  {
    "name": "Critical failures",
    "matchedStatuses": ["failed", "broken"],
    "messageRegex": ".*",
    "traceRegex": ".*"
  }
]
```

**Важно:** Категория "Test defects" объединяет все ошибки тестов (broken и failed статусы) в одну категорию для упрощения управления дефектами.

### Типы дефектов

#### Product defects
**Реальные баги в коде**, обнаруженные тестами. Требуют исправления кода.

**Характеристики:**
- Статус: `failed`
- Ошибка содержит: `AssertionError`
- Стек-трейс содержит: `assert.*is not None` или аналогичные проверки

#### Test defects
**Проблемы в самих тестах**. Требуют исправления/удаления тестов.

**Характеристики:**
- Статус: `broken` или `failed`
- Ошибка содержит: `RuntimeError`, `TypeError`, `OperationalError`, `AttributeError`, `ValueError`, `KeyError`
- Или ошибки: `unexpected keyword argument`, `no such table`, `got an unexpected`

### Применение категорий

Категории применяются автоматически при генерации отчетов через Allure Service. Для этого в `docker-compose.yml` настроена переменная окружения `CATEGORIES_FILE`, которая указывает путь к файлу категорий внутри контейнера:

```yaml
environment:
  - CATEGORIES_FILE=/app/allure-categories.json
```

Allure Service автоматически применяет категории из указанного файла при генерации отчетов. При ручной генерации отчетов можно использовать:

```bash
# Генерация отчета с категориями
allure generate allure-results -o allure-report --categories allure-categories.json
```

## Переменные окружения (Environment)

### Настройка Environment variables

Переменные окружения автоматически добавляются в Allure отчеты через создание файла `environment.properties` в директории `allure-results/`. Это выполняется в функции `pytest_configure` в файле `tests/conftest.py`:

```python
def pytest_configure(config):
    """Настройка pytest перед запуском тестов"""
    allure_results_dir = project_root / "allure-results"
    allure_results_dir.mkdir(parents=True, exist_ok=True)
    
    # Устанавливаем alluredir
    config.option.alluredir = str(allure_results_dir)
    
    # Создаем файл environment.properties для Allure отчетов
    environment_file = allure_results_dir / "environment.properties"
    with open(environment_file, "w", encoding="utf-8") as f:
        f.write(f"ENVIRONMENT={os.getenv('ENVIRONMENT', 'development')}\n")
        f.write(f"PYTHON_VERSION={sys.version.split()[0]}\n")
        f.write(f"PYTEST_VERSION={pytest.__version__}\n")
```

### Отображаемые переменные

В разделе **"Environment"** (Переменные окружения) в Allure отчетах отображаются:

- **ENVIRONMENT** — окружение выполнения тестов (`development`, `production`, `test`)
- **PYTHON_VERSION** — версия Python, используемая для запуска тестов
- **PYTEST_VERSION** — версия pytest, используемая для запуска тестов

### Добавление дополнительных переменных

Для добавления дополнительных переменных окружения в Allure отчеты, обновите функцию `pytest_configure` в `tests/conftest.py`, добавив новые строки в файл `environment.properties`:

```python
# Создаем файл environment.properties для Allure отчетов
environment_file = allure_results_dir / "environment.properties"
with open(environment_file, "w", encoding="utf-8") as f:
    f.write(f"ENVIRONMENT={os.getenv('ENVIRONMENT', 'development')}\n")
    f.write(f"PYTHON_VERSION={sys.version.split()[0]}\n")
    f.write(f"PYTEST_VERSION={pytest.__version__}\n")
    # Добавьте другие важные переменные
    f.write(f"CUSTOM_VAR={os.getenv('CUSTOM_VAR', 'default_value')}\n")
```

**Важно:** 
- Переменные окружения добавляются при каждом запуске тестов через создание файла `environment.properties` в директории `allure-results/`
- Файл автоматически создается при каждом запуске `pytest_configure`
- Все переменные отображаются в разделе "Environment" в Allure отчетах

## Отслеживание критичности тестов

### Уровни критичности

**ВАЖНО:** Severity (CRITICAL, NORMAL, MINOR) — это метаданные тестов, которые:
- **НЕ создают категории автоматически** — категории работают только для упавших тестов
- **Отображаются в деталях теста** — severity видно при открытии конкретного теста в разделе "Тест сюиты" или "Пакеты"
- **Используются для приоритизации** — помогают понять, какие тесты важнее исправить при падении

В проекте используются следующие уровни критичности:

- **CRITICAL** — критичные тесты, проверяющие основной функционал (регистрация, оплата, создание ключей)
  - Примеры: `test_yookassa_full_flow`, `test_cryptobot_full_flow`, `test_full_purchase_flow_new_user`
- **NORMAL** — обычные тесты, проверяющие стандартный функционал (валидация, обработка ошибок)
  - Примеры: `test_yookassa_webhook_processing`, `test_balance_topup_flow`
- **MINOR** — второстепенные тесты, проверяющие дополнительный функционал

### Как отслеживать критичность в Allure

**Важно:** Поисковая строка в Allure ищет только по **названиям тестов**, а не по тегам или severity. Для фильтрации по критичности используйте методы ниже.

#### 1. Через раздел "Метки:" (Tags)

**Важно:** В Allure интерфейсе теги не отображаются как отдельные кликабельные иконки для каждого тега. Вместо этого используется общий элемент `<div class="marks-toggle__item"></div>` для переключения отображения меток.

**Как использовать теги для фильтрации:**

1. Откройте Allure отчет: `http://localhost:50005/allure-docker-service/projects/default/reports/latest/index.html`
2. Перейдите в раздел **"Пакеты"** (Packages) или **"Тест сюиты"** (Test Suites)
3. Найдите колонку **"Метки:"** (Tags) в заголовке таблицы
4. **Кликните на элемент переключения меток** (marks-toggle__item), чтобы отобразить метки в списке тестов
5. **Просмотрите список тестов** - метки отображаются рядом с каждым тестом
6. **Вручную найдите тесты** с нужными тегами (`critical`, `normal`, `minor`)

**Ограничения:**
- Поисковая строка в Allure **не ищет по тегам**, только по названиям тестов
- Нет встроенного фильтра для выбора тегов severity
- Метки отображаются только в списке тестов, но не используются для автоматической фильтрации

#### 2. Через раздел "Функциональность" (Behaviors)

1. Перейдите в раздел **"Функциональность"** (Behaviors)
2. Тесты могут группироваться по severity автоматически (если настроено)
3. Включите отображение меток через элемент переключения меток
4. Просмотрите список тестов и найдите тесты с нужными тегами severity вручную

#### 3. Через фильтры по статусам

В Allure интерфейсе доступны фильтры:
- По статусу (passed, failed, broken, skipped) — через цветные блоки в разделе "Статусы:"
- По тегам — **вручную** через просмотр меток в списке тестов (после включения отображения меток)

**Важно:** Фильтрация по тегам severity в Allure работает **только визуально** - вы можете видеть, какие тесты имеют тег `critical`, `normal` или `minor`, но нет автоматического фильтра для их выбора.

#### 4. Через категории дефектов

**ВАЖНО:** Категории в Allure работают **ТОЛЬКО для упавших тестов** (failed, broken). Если все тесты прошли — категории не отобразятся.

В разделе **"Категории"** (Categories) отображаются:
- **Product defects** — реальные баги в коде (упавшие тесты с AssertionError)
- **Test defects** — проблемы в тестах (упавшие тесты с ошибками типа RuntimeError, TypeError)
- **Critical failures** — все упавшие тесты (failed, broken) независимо от типа ошибки

**Ограничение:** Категории НЕ фильтруют по severity (CRITICAL, NORMAL, MINOR). Они показывают только упавшие тесты по типу ошибки.

### Статистика по критичности

**ВАЖНО:** Severity (CRITICAL, NORMAL, MINOR) отображается в Allure, но:
- **НЕ создает категории автоматически** — категории работают только для упавших тестов
- **НЕ фильтруется в категориях** — категории фильтруют только по типу ошибки, а не по severity
- **Отображается в других разделах** — severity видно в разделе "Тест сюиты" или "Пакеты" при просмотре отдельных тестов

**Где увидеть severity:**
1. Раздел **"Тест сюиты"** (Test Suites) — откройте конкретный тест, severity отображается в деталях
2. Раздел **"Пакеты"** (Packages) — откройте конкретный тест, severity отображается в деталях
3. Раздел **"Графики"** (Graphs) — может быть график по severity (если настроено)

**Как определить критичность тестов:**
- **CRITICAL** — тесты с `@allure.severity(allure.severity_level.CRITICAL)` — проверяют основной функционал (регистрация, оплата, создание ключей)
- **NORMAL** — тесты с `@allure.severity(allure.severity_level.NORMAL)` — проверяют стандартный функционал (валидация, обработка ошибок)
- **MINOR** — тесты с `@allure.severity(allure.severity_level.MINOR)` — проверяют дополнительный функционал

**Ограничение:** В Allure нет автоматического подсчета статистики по severity - это нужно делать вручную, просматривая каждый тест.

### Рекомендации

1. **Приоритизация исправлений:**
   - Сначала исправляйте критичные (CRITICAL) упавшие тесты
   - Затем обычные (NORMAL) тесты
   - В последнюю очередь второстепенные (MINOR) тесты

2. **Мониторинг:**
   - Регулярно проверяйте статус критичных тестов
   - Отслеживайте тренды успешности по уровням критичности
   - Используйте фильтры для быстрого поиска проблемных тестов

3. **Документация:**
   - Всегда указывайте severity при создании новых тестов
   - Добавляйте severity в теги для упрощения фильтрации
   - Обновляйте severity при изменении важности теста

## Интеграция с pytest

### Использование декораторов Allure

```python
import allure

@allure.epic("База данных")
@allure.feature("Операции с пользователями")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("Тест регистрации нового пользователя")
@allure.label("component", "database")
def test_register_user(temp_db):
    """Тест регистрации пользователя"""
    with allure.step("Регистрация пользователя"):
        register_user_if_not_exists(123456789, "test_user", None, "Test User")
    
    with allure.step("Проверка создания пользователя"):
        user = get_user(123456789)
        assert user is not None
```

### Доступные декораторы

- `@allure.epic(name)` — крупная функциональная область (обязательно для группировки)
- `@allure.feature(name)` — функциональность внутри epic (обязательно для группировки)
- `@allure.severity(level)` — критичность теста (BLOCKER, CRITICAL, NORMAL, MINOR, TRIVIAL)
- `@allure.description(text)` — описание теста
- `@allure.label(name, value)` — кастомная метка
- `@allure.title(title)` — заголовок теста в отчете
- `@allure.tag(tag1, tag2, ...)` — теги для фильтрации (включая severity: "critical", "normal", "minor")
- `@allure.step(step_name)` — шаг выполнения

### Правила выбора @allure.epic и @allure.feature

**КРИТИЧЕСКИ ВАЖНО:** Все тесты должны иметь декораторы `@allure.epic` и `@allure.feature` на уровне класса тестов для корректной группировки в Allure Report.

**Правила выбора Epic (категория):**

Epic определяется по расположению тестового файла:

| Расположение теста | @allure.epic |
|-------------------|--------------|
| `tests/unit/test_database/` | `"База данных"` |
| `tests/unit/test_bot/` | `"Обработчики бота"` |
| `tests/unit/test_webhook_server/` | `"Веб-панель"` |
| `tests/unit/test_utils/test_message_templates.py` | `"Форматирование сообщений"` |
| `tests/unit/test_utils/test_template_validation.py` | `"Валидация шаблонов"` |
| `tests/unit/test_utils/test_deeplink.py` | `"Утилиты"` |
| `tests/unit/test_user_cabinet/` | `"Личный кабинет"` |
| `tests/unit/test_security/` | `"Безопасность"` |
| `tests/unit/test_modules/` | `"Модули"` |
| `tests/integration/` | `"Интеграционные тесты"` |
| `tests/e2e/` | `"E2E тесты"` |

**Правила выбора Feature (подкатегория):**

Feature определяется по функциональности, которую тестирует класс или файл. Основные примеры:

- **База данных:** "Операции с пользователями", "Операции с ключами", "Реферальная программа", "Промокоды", "Транзакции", "Пробный период", "Операции с хостами", "Уведомления", "Автопродление", "Ссылки личного кабинета", "Нумерация ключей", "Блокировки БД", "Фильтрация планов"
- **Обработчики бота:** "Обработка команд", "Управление ключами", "Обработка платежей", "Промокоды", "Генерация клавиатур", "Обработка ошибок роутера"
- **Веб-панель:** "Авторизация", "Dashboard", "Управление пользователями", "Управление ключами", "Промокоды", "Настройки", "Уведомления", "Транзакции", "Фильтры", "Поддержка", "Wiki", "Мониторинг", "Документы", "Инструкции", "TON Connect"
- **Интеграционные тесты:** "Личный кабинет", "Автопродление", "Платежи", "Покупка VPN", "Пробный период", "Веб-панель", "Реферальная система", "Deeplink"

**Примеры правильного использования:**

```python
# tests/unit/test_database/test_user_operations.py
@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Операции с пользователями")
class TestUserOperations:
    @allure.title("Регистрация нового пользователя")
    def test_register_user(self, temp_db):
        # тест

# tests/integration/test_payments/test_yookassa_flow.py
@pytest.mark.integration
@pytest.mark.database
@allure.epic("Интеграционные тесты")
@allure.feature("Платежи")
class TestYooKassaFlow:
    @allure.title("Полный цикл оплаты через YooKassa")
    def test_yookassa_payment_flow(self, temp_db):
        # тест
```

**Важные правила:**

1. **Всегда добавляй `import allure`** в начале файла
2. **Декораторы добавляются на уровне класса**, перед `class Test*:`
3. **Для функций-тестов без класса** декораторы добавляются перед функцией
4. **Если файл содержит несколько классов**, каждый класс должен иметь свои декораторы
5. **Названия epic и feature на русском языке**, как в существующих тестах
6. **При создании нового тестового файла** сначала определи его расположение, затем выбери соответствующий epic и feature

Подробнее см. [Правила организации тестирования](../../../.cursor/rules/testing-rules.mdc#правила-выбора-allureepic-и-allurefeature).

### Использование severity в тегах

Для упрощения фильтрации в Allure интерфейсе, severity также добавляется в теги:

```python
@allure.severity(allure.severity_level.CRITICAL)
@allure.tag("payments", "yookassa", "integration", "critical")
def test_payment():
    """Тест оплаты"""
    pass
```

Это позволяет фильтровать тесты по severity через теги в разделе "Пакеты" или "Функциональность".

### Attachments (вложения)

```python
import allure

def test_with_attachment(temp_db):
    # Сохранить скриншот
    allure.attach("screenshot.png", allure.attachment_type.PNG)
    
    # Сохранить текст
    allure.attach("Лог выполнения", "text/plain")
    
    # Сохранить JSON
    allure.attach(json.dumps(data, indent=2), "JSON", allure.attachment_type.JSON)
```

## Работа с дефектами

### Экспорт дефектов

Скрипт `tests/ad-hoc/export_allure_defects.py` экспортирует все дефекты из Allure отчёта:

```bash
python tests/ad-hoc/export_allure_defects.py
```

**Результат:**
- Файл `tests/ad-hoc/reports/allure-defects-export.json` с данными о всех дефектах
- Статистика: количество Product defects, Test defects, критичных дефектов

### Анализ дефектов

Скрипт `tests/ad-hoc/analyze_allure_defects.py` анализирует экспортированные данные:

```bash
python tests/ad-hoc/analyze_allure_defects.py
```

**Результат:**
- Файл `tests/ad-hoc/reports/allure-defects-report.md` с детальным анализом
- Группировка по модулям и приоритетам
- Рекомендации по исправлению

### Создание GitHub Issues

Скрипт `tests/ad-hoc/create_github_issues.py` автоматически создаёт Issues для всех дефектов:

```bash
# Установите токен GitHub
$env:GITHUB_TOKEN='your-github-token'  # PowerShell
# или
export GITHUB_TOKEN='your-github-token'  # Bash

# Запустите скрипт
python tests/ad-hoc/create_github_issues.py
```

**Результат:**
- GitHub Issues для каждого дефекта
- Правильные labels (bug, test, critical, allure)
- Заполненные данные из Allure

**Режим DRY RUN:**
Если токен не установлен, скрипт работает в режиме DRY RUN и показывает, какие Issues были бы созданы.

Подробнее см. [Управление дефектами Allure](allure-defects-management.md).

## Интеграция в CI/CD

### GitHub Actions

CI/CD pipeline автоматически:
1. Запускает тесты с генерацией Allure результатов
2. Генерирует Allure отчёт с применением категорий
3. Анализирует дефекты
4. Создаёт отчёт о дефектах
5. Загружает артефакты (Allure отчёт и отчёт о дефектах)

**Файл:** `.github/workflows/ci.yml`

### Локальная интеграция

```bash
# Скрипт для cron (запуск тестов по расписанию)
#!/bin/bash
cd /path/to/project
docker compose exec autotest pytest
```

## Внешний доступ через SSL

После настройки SSL через `ssl-install.sh`:

```bash
sudo ./ssl-install.sh domain.com
```

Allure отчеты будут доступны по адресу:
- `https://allure.dark-maximus.com/allure-docker-service/projects/default/reports/latest/index.html`

## Управление контейнерами

### Команды управления

```bash
# Запустить сервисы
docker compose up -d autotest allure-service

# Остановить сервисы
docker compose stop autotest allure-service

# Перезапустить сервисы
docker compose restart autotest allure-service

# Просмотреть логи
docker compose logs -f autotest allure-service

# Проверить статус
docker compose ps autotest allure-service
```

### Пересборка контейнеров

```bash
# Пересобрать контейнер autotest
docker compose build --no-cache autotest

# Перезапустить после пересборки
docker compose up -d autotest
```

## Известные проблемы и ограничения

### Проблема с отображением названий тестов (пробелы в UI)

**Симптомы:**
- В интерфейсе Allure отображаются названия тестов с пробелами вместо точек: "unit.te t_webhook_ erver" вместо "unit.test_webhook_server"
- Категории отображаются некорректно: "Te t defect" вместо "Test defect"
- Заголовки разделов отображаются с лишними пробелами: "Retrie  trend" вместо "Retry trend"

**Причина:**
Проблема связана с версией Allure Report 2.35.1 и её фронтендом. JSON данные корректны, проблема только в визуальном отображении.

**Влияние:**
- Не критично для работы - данные корректны, отчёты генерируются успешно
- Ухудшает UX при чтении названий тестов
- Не влияет на функциональность отчётов

**Возможные решения:**
1. Обновить Allure Docker Service до более новой версии (когда будет доступна)
2. Использовать `@allure.title` для читаемых названий тестов (рекомендуется)
3. Дождаться исправления в Allure Report

**Статус:** Известная проблема, не блокирует работу.

### Несоответствие версий Allure

**Установленные версии:**
- Allure Report в allure-service: 2.35.1
- allure-pytest: 2.15.0
- Allure CLI в Dockerfile.tests: 2.24.1

**Влияние:**
Минимальное - все версии совместимы, но рекомендуется синхронизировать версии для оптимальной работы.

## Решение проблем

### Allure Service не запускается

```bash
# Проверить логи
docker compose logs allure-service

# Проверить доступность порта
curl http://localhost:50005

# Перезапустить сервис
docker compose restart allure-service
```

### Отчеты не генерируются

```bash
# Проверить наличие результатов
ls allure-results/

# Проверить, что тесты запускались
docker compose logs autotest | grep pytest

# Проверить права доступа
chmod 755 allure-results allure-report
```

### Результаты не отображаются в веб-интерфейсе

```bash
# Проверить, что Allure Service видит результаты
curl http://localhost:50005/allure-docker-service/projects

# Проверить volume-маппинги
docker compose config | grep allure

# Перезапустить Allure Service
docker compose restart allure-service
```

### `/latest/index.html` возвращает JSON вместо HTML

**Симптомы:**
- При запросе к `http://localhost:50005/allure-docker-service/projects/default/reports/latest/index.html` возвращается JSON с метаданными проекта вместо HTML-отчета
- В ответе видна структура: `{"data": {"project": {"reports_id": ["9", "8", "7", ...]}}}`

**Причина:**
Симлинк `/latest` не указывает на существующий отчет, и Allure Docker Service обрабатывает запрос как API endpoint вместо статического файла.

**Решение:**
В проекте реализована автоматическая обработка этой проблемы:

1. **Allure Homepage автоматически обрабатывает эту ситуацию:**
   - При запросе к `/latest/index.html` проверяется Content-Type ответа
   - Если получен JSON вместо HTML, выполняется запрос к API для получения списка отчетов
   - Извлекается ID последнего отчета из массива `reports_id` (первый элемент - самый новый)
   - Выполняется автоматический редирект на конкретный отчет: `/projects/default/reports/{latest_id}/index.html`

2. **Если автоматический редирект не работает:**
   - Проверьте логи allure-homepage: `docker compose logs allure-homepage`
   - Убедитесь, что API доступен: `curl http://localhost:50005/allure-docker-service/projects/default/reports`
   - Попробуйте открыть конкретный отчет из списка вручную

3. **Ручное решение:**
   ```bash
   # Получить список отчетов через API
   curl http://localhost:50005/allure-docker-service/projects/default/reports
   
   # Открыть последний отчет вручную (замените {id} на ID из списка)
   # Откройте в браузере: http://localhost:50005/allure-docker-service/projects/default/reports/{id}/index.html
   ```

**Примечание:** Эта проблема обычно возникает сразу после запуска тестов, когда отчет еще не был сгенерирован или симлинк `/latest` еще не создан. Автоматический редирект решает эту проблему без участия пользователя.

### Проблемы с путями и графиками

Если графики истории не открываются или возникают проблемы с переходами:

1. **Проверьте переменные окружения:**
   ```bash
   docker compose exec allure-service env | Select-String -Pattern "ALLURE|URL"
   ```
   Убедитесь, что установлены:
   - `ALLURE_PUBLIC_URL=http://localhost:50005/allure-docker-service`
   - `URL_PREFIX=/allure-docker-service`

2. **Перезапустите контейнер:**
   ```bash
   docker compose restart allure-service
   ```

3. **Проверьте логи:**
   ```bash
   docker compose logs allure-service | Select-String -Pattern "error|Error|ERROR"
   ```

4. **Очистите кэш браузера** или откройте в режиме инкогнито

### Пустые отчеты (0 тестовых сценариев)

**Симптомы:**
- В Allure Report отображается "0 тестовых сценариев"
- Отчеты генерируются (BUILD_ORDER увеличивается), но не содержат тестов
- В разделе "ТЕСТ СЮИТЫ" показывается "Всего 0 элементов"
- В тренде видно падение до нуля после определенного номера отчета

**Причина:**
В директории `allure-results/` отсутствуют файлы результатов тестов (`*-result.json`, `*-container.json`). Allure Service генерирует отчеты даже без результатов, что приводит к отображению пустых отчетов.

**Возможные причины:**

1. **🚨 КРИТИЧЕСКАЯ ПРОБЛЕМА: Использование флага `-T` при запуске pytest (ИСПРАВЛЕНО 20.11.2025):**
   - **Симптом:** При использовании `docker compose exec -T autotest pytest` результаты не сохраняются в `allure-results/`
   - **Причина:** Флаг `-T` отключает TTY (псевдотерминал), что приводит к тому, что allure-pytest не может корректно сохранить результаты
   - **Решение:** **НЕ используй флаг `-T`** при запуске pytest:
     ```powershell
     # ❌ НЕПРАВИЛЬНО (результаты не сохранятся)
     docker compose exec -T autotest pytest
     
     # ✅ ПРАВИЛЬНО (результаты сохранятся)
     docker compose exec autotest pytest
     
     # ✅ РЕКОМЕНДУЕТСЯ (используй готовый скрипт)
     .\tests\run_tests.ps1
     ```
   - **Диагностика:** Проверить количество результатов после запуска:
     ```powershell
     docker compose exec autotest sh -c "find /app/allure-results -name '*-result.json' -type f | wc -l"
     ```
     Если результат `0` после запуска тестов — проверь, не используешь ли ты флаг `-T`.

2. **Неправильная структура директорий:**
   - Результаты сохраняются в `tests/allure-results/` вместо корневой `allure-results/`
   - Решение: переместить результаты из неправильных директорий в корневую `allure-results/`
   - Убедиться, что `conftest.py` правильно устанавливает путь через `pytest_configure`

3. **Неправильный путь к allure-results в pytest.ini:**
   - Относительный путь может указывать на неправильную директорию в зависимости от рабочей директории
   - Решение: путь устанавливается динамически в `conftest.py` через `pytest_configure`, который переопределяет значение из `pytest.ini` на абсолютный путь от корня проекта

4. **Тесты не запускались:**
   - Результаты не сохраняются, если тесты не были запущены
   - Решение: запустить тесты `docker compose exec autotest pytest`

5. **Проблема с volume-маппингом:**
   - Результаты сохраняются в неправильную директорию
   - Решение: проверить volume-маппинги в `docker-compose.yml`

6. **Результаты очищаются до генерации отчета:**
   - Скрипт очистки удаляет результаты до генерации отчета
   - Решение: очистка должна происходить ПЕРЕД запуском тестов

**Диагностика:**

1. **Проверить наличие результатов:**
   ```powershell
   # PowerShell
   .\tests\ad-hoc\check_allure_results.ps1
   
   # Или вручную
   Get-ChildItem allure-results -Filter *-result.json
   ```

2. **Проверить содержимое allure-results в контейнере:**
   ```bash
   docker compose exec autotest ls -la /app/allure-results
   ```

3. **Проверить конфигурацию pytest:**
   ```bash
   docker compose exec autotest cat /app/pytest.ini | grep alluredir
   ```
   Должно быть: `--alluredir=/app/allure-results`.
   
   Путь дополнительно переопределяется в `conftest.py` на абсолютный `/app/allure-results` в контейнере.

4. **Проверить volume-маппинги:**
   ```bash
   docker compose config | Select-String -Pattern "allure-results"
   ```

**Решение:**

1. **Проверить структуру директорий:**
   - Убедиться, что `allure-results/` находится только в корне проекта, не в `tests/`
   - Переместить результаты из неправильных директорий (`tests/allure-results/`, `tests/{env:ALLURE_RESULTS_DIR:`) в корневую `allure-results/`

2. **Проверить конфигурацию pytest:**
   - В `pytest.ini` должен быть путь `--alluredir=/app/allure-results`
   - В `tests/conftest.py` должен быть хук `pytest_configure`, который устанавливает абсолютный путь от корня проекта

2. **Запустить тесты:**
   ```bash
   docker compose exec autotest pytest
   ```

3. **Проверить результаты:**
   ```powershell
   .\tests\ad-hoc\check_allure_results.ps1
   ```

4. **Если результаты отсутствуют, проверить логи:**
   ```bash
   docker compose logs autotest | Select-String -Pattern "allure|result"
   ```

**Профилактика:**

1. **Использовать скрипт проверки после запуска тестов:**
   ```powershell
   # После запуска тестов
   .\tests\ad-hoc\check_allure_results.ps1
   ```

2. **Проверять наличие результатов после каждого запуска тестов:**
   ```bash
   docker compose exec autotest sh -c "ls -la /app/allure-results/*-result.json | wc -l"
   ```

3. **Мониторить логи Allure Service:**
   ```bash
   docker compose logs allure-service | Select-String -Pattern "BUILD_ORDER|results"
   ```

**Важно:**
- Allure Service генерирует отчеты даже без результатов тестов (это нормальное поведение)
- Проблема в том, что результаты не сохраняются, а не в генерации отчетов
- Всегда проверяйте наличие результатов перед просмотром отчетов

## Рекомендации

1. **Регулярно просматривайте отчеты:** Проверяйте результаты тестов после каждого запуска
2. **Используйте категории:** Используйте категории дефектов для приоритизации исправлений
3. **Создавайте Issues:** Автоматически создавайте GitHub Issues для дефектов
4. **Мониторьте тренды:** Отслеживайте изменения успешности тестов со временем

## См. также

- [Управление дефектами Allure](allure-defects-management.md) — работа с дефектами из Allure отчетов
- [Запуск тестов](running-tests.md) — инструкции по запуску тестов
- [Справочник по тестированию](../../reference/testing-reference.md) — полный справочник по Allure

---

**Версия:** 1.2  
**Последнее обновление:** 17.11.2025  
**Автор:** Dark Maximus Team

