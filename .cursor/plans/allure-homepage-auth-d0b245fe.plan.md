<!-- d0b245fe-359e-411a-8561-a6b048bf0cdd a7968977-c4ba-4224-bcdc-3e087a56d4ba -->
# План исправления тестов allure-homepage авторизации

## Проблемы

1. **TemplateNotFound: login.html** - в большинстве тестов не настроен путь к шаблонам
2. **Неправильное мокирование `verify_and_login`** - функция импортируется из другого модуля
3. **Неправильное мокирование `requests`** - в тестах проксирования
4. **Проблемы с сессиями** - нужно правильно настроить для тестов

## Решение

### 1. Добавить настройку путей к шаблонам во все тесты

В файле `tests/unit/test_allure_homepage/test_auth.py`:

- Добавить настройку `app.jinja_loader.searchpath` во все тесты, которые используют шаблоны
- Использовать путь: `project_root / "apps" / "allure-homepage" / "templates"`

### 2. Исправить мокирование `verify_and_login`

- Функция импортируется из `shop_bot.webhook_server.auth_utils`
- Нужно мокировать её в модуле `allure_homepage_app`, где она используется
- Или патчить модуль `shop_bot.webhook_server.auth_utils` напрямую

### 3. Исправить мокирование `requests` в тестах проксирования

- В тестах `test_proxy_after_auth`, `test_proxy_json_responses`, `test_proxy_html_responses`
- Нужно правильно мокировать модуль `requests` из `allure_homepage_app`

### 4. Настроить сессии для тестов

- Убедиться, что `init_flask_auth` правильно работает в тестовом окружении
- Возможно, нужно мокировать или настроить директорию для сессий

## Файлы для изменения

- `tests/unit/test_allure_homepage/test_auth.py` - исправить все тесты

## Шаги реализации

1. Добавить вспомогательную функцию для настройки app с шаблонами
2. Исправить все тесты, добавив настройку путей к шаблонам
3. Исправить мокирование `verify_and_login` во всех тестах
4. Исправить мокирование `requests` в тестах проксирования
5. Запустить тесты и проверить результаты в Allure

### To-dos

- [ ] Добавить вспомогательную функцию для настройки app с шаблонами в test_auth.py
- [ ] Исправить test_login_success: добавить настройку шаблонов и правильное мокирование verify_and_login
- [ ] Исправить test_login_failure: добавить настройку шаблонов и правильное мокирование verify_and_login
- [ ] Исправить test_logout: добавить настройку шаблонов и правильное мокирование verify_and_login
- [ ] Исправить test_login_required_decorator: добавить настройку шаблонов и правильное мокирование verify_and_login
- [ ] Исправить test_session_persistence: добавить настройку шаблонов и правильное мокирование verify_and_login
- [ ] Исправить test_proxy_after_auth: добавить настройку шаблонов, мокирование verify_and_login и requests
- [ ] Исправить test_proxy_json_responses: добавить настройку шаблонов, мокирование verify_and_login и requests
- [ ] Исправить test_proxy_html_responses: добавить настройку шаблонов, мокирование verify_and_login и requests
- [ ] Запустить все тесты и проверить результаты в Allure отчете