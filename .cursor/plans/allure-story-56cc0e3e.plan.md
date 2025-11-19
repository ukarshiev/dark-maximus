<!-- 56cc0e3e-4ce5-431a-b0fa-ab775ecebf7e bf4a8eea-86e9-40f6-9fbc-f50236583286 -->
# Добавление @allure.story для группировки тестов в Behaviors

## Цель

Добавить декоратор `@allure.story` ко всем unit-тестам, которые отображаются в разделе "Функциональность" без группировки по story, чтобы они корректно группировались в разделе Behaviors Allure Report.

## Области изменений

### 1. tests/unit/test_allure_homepage/test_auth.py

Добавить `@allure.story` к 10 тестам авторизации Allure Homepage:

- `test_login_page_get` → "Авторизация: отображение страницы входа"
- `test_login_success` → "Авторизация: успешный вход"
- `test_login_failure` → "Авторизация: обработка неверных данных"
- `test_logout` → "Авторизация: выход из системы"
- `test_login_required_decorator` → "Авторизация: проверка доступа"
- `test_session_persistence` → "Авторизация: сохранение сессии"
- `test_health_check_no_auth` → "Healthcheck: доступность без авторизации"
- `test_proxy_after_auth` → "Проксирование: запросы после авторизации"
- `test_proxy_json_responses` → "Проксирование: обработка JSON ответов"
- `test_proxy_html_responses` → "Проксирование: обработка HTML ответов"

### 2. tests/unit/test_docs_proxy/test_auth.py

Добавить `@allure.story` к 9 тестам авторизации Docs Proxy:

- `test_login_page_get` → "Авторизация: отображение страницы входа"
- `test_login_success` → "Авторизация: успешный вход"
- `test_login_failure` → "Авторизация: обработка неверных данных"
- `test_logout` → "Авторизация: выход из системы"
- `test_login_required_decorator` → "Авторизация: проверка доступа"
- `test_session_persistence` → "Авторизация: сохранение сессии"
- `test_health_check_no_auth` → "Healthcheck: доступность без авторизации"
- `test_proxy_after_auth` → "Проксирование: запросы после авторизации"
- `test_proxy_headers` → "Проксирование: передача заголовков"

### 3. tests/unit/test_webhook_server/

Добавить `@allure.story` ко всем тестам веб-панели (15 файлов, ~72 теста):

**test_auth.py** (7 тестов):

- "Авторизация: вход в систему"
- "Авторизация: выход из системы"
- "Авторизация: проверка доступа"

**test_dashboard.py** (3 теста):

- "Dashboard: главная панель"
- "Dashboard: производительность"

**test_users.py** (8 тестов):

- "Управление пользователями: просмотр списка"
- "Управление пользователями: детали пользователя"
- "Управление пользователями: редактирование данных"
- "Управление пользователями: изменение баланса"
- "Управление пользователями: блокировка и разблокировка"
- "Управление пользователями: отзыв согласия"
- "Управление пользователями: сброс пробного периода"
- "Управление пользователями: удаление ключей"

**test_keys.py** (5 тестов):

- "Управление ключами: просмотр списка"
- "Управление ключами: операции с ключами"

**test_wiki.py** (4 теста):

- "Wiki: редактор страниц"
- "Wiki: редактирование страницы"
- "Wiki: создание страницы"
- "Wiki: удаление страницы"

**test_settings.py** (8 тестов):

- "Настройки: управление конфигурацией"

**test_notifications.py** (4 теста):

- "Уведомления: управление шаблонами"

**test_monitoring.py** (3 теста):

- "Мониторинг: проверка статуса"

**test_filters.py** (4 теста):

- "Фильтры: применение фильтров"

**test_support.py** (2 теста):

- "Поддержка: управление тикетами"

**test_transactions.py** (4 теста):

- "Транзакции: просмотр и управление"

**test_promo_codes.py** (5 тестов):

- "Промокоды: управление промокодами"

**test_ton_connect.py** (4 теста):

- "TON Connect: интеграция"

**test_instructions.py** (5 тестов):

- "Инструкции: управление инструкциями"

**test_documents.py** (6 тестов):

- "Документы: управление документами"

## Правила добавления story

1. **Формат**: `@allure.story("Название на русском языке")`
2. **Размещение**: Перед `@allure.title` или сразу после `@allure.tag`
3. **Стиль**: Описывает конкретный пользовательский сценарий или поведение системы
4. **Группировка**: Story должны логически группировать связанные тесты

## Примеры

```python
@allure.story("Авторизация: успешный вход")
@allure.title("Успешный вход в allure-homepage")
@allure.description("""...""")
@allure.severity(allure.severity_level.NORMAL)
@allure.tag("auth", "login", "success", "allure-homepage", "unit")
def test_login_success(self, temp_db, admin_credentials):
    # тест
```

## Проверка

После добавления всех story:

1. Запустить тесты: `docker compose exec monitoring pytest tests/unit/test_allure_homepage tests/unit/test_docs_proxy tests/unit/test_webhook_server -v`
2. Проверить группировку в Allure Report в разделе Behaviors
3. Убедиться, что все тесты корректно сгруппированы по story

### To-dos

- [ ] Добавить @allure.story к 10 тестам в tests/unit/test_allure_homepage/test_auth.py
- [ ] Добавить @allure.story к 9 тестам в tests/unit/test_docs_proxy/test_auth.py
- [ ] Добавить @allure.story к тестам в tests/unit/test_webhook_server/test_auth.py
- [ ] Добавить @allure.story к тестам в tests/unit/test_webhook_server/test_dashboard.py
- [ ] Добавить @allure.story к 8 тестам в tests/unit/test_webhook_server/test_users.py
- [ ] Добавить @allure.story к тестам в tests/unit/test_webhook_server/test_keys.py
- [ ] Добавить @allure.story к 4 тестам в tests/unit/test_webhook_server/test_wiki.py
- [ ] Добавить @allure.story к тестам в остальных файлах test_webhook_server (settings, notifications, monitoring, filters, support, transactions, promo_codes, ton_connect, instructions, documents)
- [ ] Запустить тесты и проверить группировку в Allure Report в разделе Behaviors