<!-- 7b11ddbc-fbeb-4b14-a424-4533ae35172d d59b224d-5027-48e8-9ebf-57956e2f3660 -->
# План: Добавление Flask-авторизации для docs и allure-homepage

## Цель

Добавить Flask-авторизацию с красивой страницей входа для двух сервисов:

- **docs** (порт 50001, домен docs.dark-maximus.com) - пользовательская документация
- **allure-homepage** (порт 50005, домен allure.dark-maximus.com) - Allure отчеты

## Архитектура решения

### 1. Для allure-homepage (50005)

- Добавить Flask-авторизацию прямо в существующее приложение
- Использовать те же функции из `src/shop_bot/data_manager/database.py`:
- `verify_admin_credentials()` для проверки логина/пароля
- `get_setting("panel_login")` и `get_setting("panel_password")` для получения учетных данных
- Добавить Flask sessions для хранения состояния авторизации
- Создать красивую страницу входа на основе `src/shop_bot/webhook_server/templates/login.html`

### 2. Для docs (50001)

- Создать новый Flask-прокси сервис, который будет:
- Проверять авторизацию
- Проксировать запросы к Nginx (docs контейнер) после успешной авторизации
- Заменить текущий Nginx контейнер на Flask-прокси + Nginx внутри
- Или создать отдельный Flask-сервис, который будет проксировать к существующему docs контейнеру

## Детальный план реализации

### Этап 1: Подготовка общих компонентов

#### 1.1 Создать общий модуль авторизации

- **Файл**: `src/shop_bot/webhook_server/auth_utils.py`
- **Содержимое**:
- Функция `login_required` декоратор (можно переиспользовать из `app.py`)
- Функция `init_flask_auth(app)` для инициализации Flask sessions
- Функция `verify_and_login(username, password)` для проверки и создания сессии

#### 1.2 Создать общий шаблон страницы входа

- **Файл**: `src/shop_bot/webhook_server/templates/auth/login.html`
- **Основа**: Использовать существующий `src/shop_bot/webhook_server/templates/login.html`
- **Адаптация**: Сделать универсальным (можно передавать название сервиса)

### Этап 2: Реализация авторизации для allure-homepage

#### 2.1 Обновить `apps/allure-homepage/app.py`

- Добавить импорты:
- `from flask import session, flash, url_for`
- `from functools import wraps`
- Импорт функций из `src/shop_bot/data_manager/database`
- Добавить настройку Flask sessions:
- `app.config['SECRET_KEY']` из переменной окружения
- `app.config['SESSION_TYPE'] = 'filesystem'`
- Инициализация `Session` из `flask_session`
- Добавить декоратор `@login_required`
- Добавить маршруты:
- `@app.route('/login', methods=['GET', 'POST'])` - страница входа
- `@app.route('/logout', methods=['POST'])` - выход
- Защитить все существующие маршруты декоратором `@login_required`:
- `/allure-docker-service/`
- `/allure-docker-service/projects`
- `/allure-docker-service/<path:path>`
- Исключить из авторизации:
- `/health` - healthcheck endpoint

#### 2.2 Создать шаблон страницы входа для allure-homepage

- **Файл**: `apps/allure-homepage/templates/login.html`
- **Основа**: Использовать стиль из `apps/allure-homepage/templates/index.html` (темная тема, акцентный зеленый)
- **Содержимое**: Форма входа с полями логин/пароль, обработка flash сообщений

#### 2.3 Обновить `apps/allure-homepage/Dockerfile`

- Добавить volume для sessions: `./sessions-allure:/app/sessions`
- Добавить переменную окружения `FLASK_SECRET_KEY`

#### 2.4 Обновить `docker-compose.yml`

- Добавить volume для sessions в сервис `allure-homepage`:
- `./sessions-allure:/app/sessions`
- Добавить переменную окружения:
- `FLASK_SECRET_KEY=${FLASK_SECRET_KEY}`

### Этап 3: Реализация авторизации для docs

#### 3.1 Создать Flask-прокси сервис для docs

- **Файл**: `apps/docs-proxy/app.py`
- **Структура**:
- Flask приложение с авторизацией
- Проксирование запросов к `http://docs:80` после успешной авторизации
- Использование `requests` для проксирования
- **Маршруты**:
- `/login` - страница входа
- `/logout` - выход
- `/<path:path>` - проксирование к docs контейнеру (с проверкой авторизации)
- `/health` - healthcheck (без авторизации)

#### 3.2 Создать шаблон страницы входа для docs-proxy

- **Файл**: `apps/docs-proxy/templates/login.html`
- **Основа**: Использовать стиль из веб-панели или создать новый в темной теме

#### 3.3 Создать Dockerfile для docs-proxy

- **Файл**: `apps/docs-proxy/Dockerfile`
- **Базовый образ**: `python:3.11-slim`
- **Зависимости**: Flask, flask-session, requests
- **Порт**: 50001

#### 3.4 Обновить docker-compose.yml

- Добавить новый сервис `docs-proxy`:
- Порт: `127.0.0.1:50001:50001`
- Volumes: `./sessions-docs:/app/sessions`, `./users.db:/app/users.db` (для доступа к БД)
- Environment: `FLASK_SECRET_KEY`, `DOCS_BACKEND_URL=http://docs:80`
- Depends_on: `docs`
- Оставить сервис `docs` без изменений (он будет доступен только внутри сети)

#### 3.5 Обновить Nginx конфигурацию

- **Файл**: `deploy/nginx/dark-maximus.conf.tpl`
- Обновить upstream `docs_backend`:
- Изменить с `127.0.0.1:50001` на проксирование к `docs-proxy` контейнеру
- Или оставить как есть, если docs-proxy будет доступен на localhost:50001

### Этап 4: Обновление конфигурации доменов

#### 4.1 Обновить Nginx конфигурацию для allure.dark-maximus.com

- **Файл**: `deploy/nginx/dark-maximus.conf.tpl`
- Добавить новый server block для `allure.dark-maximus.com`:
- HTTP редирект на HTTPS
- HTTPS сервер с SSL сертификатами
- Проксирование на `allure_backend` (127.0.0.1:50005)

#### 4.2 Обновить скрипты установки

- **Файл**: `install.sh` или `ssl-install.sh`
- Добавить переменную `ALLURE_DOMAIN=allure.dark-maximus.com`
- Обновить шаблоны конфигурации Nginx

### Этап 5: Создание автотестов

#### 5.1 Создать тесты для docs-proxy

- **Файл**: `tests/unit/test_docs_proxy/test_auth.py`
- **Структура**: Аналогично `tests/unit/test_webhook_server/test_auth.py`
- **Тесты**:
- `test_login_page_get` - отображение страницы входа
- `test_login_success` - успешный вход с корректными данными
- `test_login_failure` - неудачный вход с неверными данными
- `test_logout` - выход из системы и очистка сессии
- `test_login_required_decorator` - проверка редиректа на /login без авторизации
- `test_session_persistence` - сохранение сессии между запросами
- `test_health_check_no_auth` - healthcheck доступен без авторизации
- `test_proxy_after_auth` - проксирование запросов к docs после авторизации
- `test_proxy_headers` - правильная передача заголовков при проксировании
- **Фикстуры**: Использовать `temp_db` и `admin_credentials` из `conftest.py`
- **Allure аннотации**: Добавить `@allure.epic("Docs Proxy")`, `@allure.feature("Авторизация")`

#### 5.2 Создать тесты для allure-homepage

- **Файл**: `tests/unit/test_allure_homepage/test_auth.py`
- **Структура**: Аналогично `tests/unit/test_webhook_server/test_auth.py`
- **Тесты**:
- `test_login_page_get` - отображение страницы входа
- `test_login_success` - успешный вход с корректными данными
- `test_login_failure` - неудачный вход с неверными данными
- `test_logout` - выход из системы и очистка сессии
- `test_login_required_decorator` - проверка редиректа на /login без авторизации
- `test_session_persistence` - сохранение сессии между запросами
- `test_health_check_no_auth` - healthcheck доступен без авторизации
- `test_proxy_after_auth` - проксирование запросов к allure-service после авторизации
- `test_proxy_json_responses` - правильная обработка JSON ответов от allure-service
- `test_proxy_html_responses` - правильная обработка HTML ответов от allure-service
- **Фикстуры**: Использовать `temp_db` и `admin_credentials` из `conftest.py`
- **Allure аннотации**: Добавить `@allure.epic("Allure Homepage")`, `@allure.feature("Авторизация")`

#### 5.3 Создать директории для тестов

- `tests/unit/test_docs_proxy/` - директория для тестов docs-proxy
- `tests/unit/test_docs_proxy/__init__.py` - инициализация пакета
- `tests/unit/test_allure_homepage/` - директория для тестов allure-homepage
- `tests/unit/test_allure_homepage/__init__.py` - инициализация пакета

#### 5.4 Обновить conftest.py (если нужно)

- Проверить наличие фикстур `admin_credentials` и `temp_db`
- При необходимости добавить фикстуры для создания тестовых Flask приложений docs-proxy и allure-homepage

### Этап 6: Ручное тестирование и документация

#### 6.1 Ручное тестирование

- Проверить авторизацию на обоих сервисах в браузере
- Проверить редирект на страницу входа при неавторизованном доступе
- Проверить работу после авторизации
- Проверить выход из системы
- Проверить healthcheck endpoints (должны работать без авторизации)
- Проверить проксирование запросов для обоих сервисов

#### 6.2 Обновление документации

- Обновить `docs/architecture/docker-architecture.md` с информацией о новых сервисах
- Обновить `CHANGELOG.md` с описанием изменений
- Добавить информацию о тестах в `docs/guides/testing/`

## Файлы для изменения

### Новые файлы:

1. `src/shop_bot/webhook_server/auth_utils.py` - общие утилиты авторизации
2. `apps/docs-proxy/app.py` - Flask-прокси для docs
3. `apps/docs-proxy/Dockerfile` - Dockerfile для docs-proxy
4. `apps/docs-proxy/templates/login.html` - страница входа для docs
5. `apps/docs-proxy/requirements.txt` - зависимости для docs-proxy
6. `apps/allure-homepage/templates/login.html` - страница входа для allure

### Изменяемые файлы:

1. `apps/allure-homepage/app.py` - добавление авторизации
2. `apps/allure-homepage/Dockerfile` - добавление volumes для sessions
3. `docker-compose.yml` - добавление сервиса docs-proxy, обновление allure-homepage
4. `deploy/nginx/dark-maximus.conf.tpl` - добавление конфигурации для allure.dark-maximus.com
5. `docs/architecture/docker-architecture.md` - обновление документации
6. `CHANGELOG.md` - запись об изменениях

## Важные моменты

1. **Безопасность**: Использовать те же учетные данные из БД (`panel_login`, `panel_password`)
2. **Sessions**: Хранить сессии в файловой системе (как в веб-панели)
3. **Healthcheck**: Endpoints `/health` должны быть доступны без авторизации
4. **Стиль**: Страницы входа должны соответствовать темной теме проекта с акцентным зеленым цветом `#008771`
5. **Проксирование**: Для docs-proxy важно правильно передавать все заголовки и параметры запроса

## Best Practices (из Flask документации)

### Безопасность сессий

- Использовать `SECRET_KEY` из переменных окружения (не хардкодить)
- Использовать `SESSION_COOKIE_SECURE=True` для HTTPS (в production)
- Использовать `SESSION_COOKIE_HTTPONLY=True` для защиты от XSS
- Использовать `SESSION_COOKIE_SAMESITE='Lax'` для защиты от CSRF
- Установить разумный `PERMANENT_SESSION_LIFETIME` (например, 30 дней)

### Обработка прокси (ProxyFix)

- Для сервисов за reverse proxy использовать `ProxyFix` middleware из `werkzeug.middleware.proxy_fix`
- Правильно настроить `X-Forwarded-*` заголовки
- Использовать `X-Forwarded-Proto` для определения HTTPS

### Защита от атак

- Использовать rate limiting для страницы входа (как в веб-панели)
- Валидировать и санитизировать входные данные
- Использовать CSRF защиту (если требуется)
- Правильно обрабатывать ошибки (не раскрывать внутреннюю информацию)

### Проксирование запросов

- Правильно передавать все заголовки запроса
- Сохранять оригинальный Host заголовок
- Правильно обрабатывать redirect'ы от проксируемого сервиса
- Использовать streaming для больших файлов (если нужно)

## Источники информации

- Flask Security: https://flask.palletsprojects.com/en/stable/web-security/
- Flask Sessions API: https://flask.palletsprojects.com/en/stable/api/#sessions
- Flask Proxy Fix: https://flask.palletsprojects.com/en/stable/deploying/proxy_fix/
- Flask Nginx Configuration: https://flask.palletsprojects.com/en/stable/deploying/nginx/

## Порядок выполнения

1. Создать общие компоненты (auth_utils.py, общий шаблон)
2. Реализовать авторизацию для allure-homepage (проще, так как уже Flask)
3. Реализовать Flask-прокси для docs
4. Обновить конфигурацию Docker и Nginx
5. Протестировать оба сервиса
6. Обновить документацию