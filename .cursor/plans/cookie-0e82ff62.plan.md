<!-- 0e82ff62-83ea-451b-a5d7-567cc8135d51 ea0f84da-aebf-4bac-89f9-0c933d295275 -->
# Исправление конфликта cookie для всех сервисов с авторизацией

## Проблема

Все сервисы, использующие `init_flask_auth()`, получают одинаковое имя cookie `panel_session`, что может вызывать конфликты при использовании одинакового `FLASK_SECRET_KEY`.

## Решение

Добавить опциональный параметр `cookie_name` в функцию `init_flask_auth()`, чтобы каждый сервис мог задать уникальное имя cookie.

## Изменения

### 1. Обновление `src/shop_bot/webhook_server/auth_utils.py`

- Добавить параметр `cookie_name` в функцию `init_flask_auth()` (по умолчанию `'panel_session'`)
- Использовать этот параметр вместо жестко заданного значения

### 2. Обновление `apps/docs-proxy/app.py`

- После вызова `init_flask_auth()` установить `app.config['SESSION_COOKIE_NAME'] = 'docs_session'`

### 3. Обновление `apps/allure-homepage/app.py`

- После вызова `init_flask_auth()` установить `app.config['SESSION_COOKIE_NAME'] = 'allure_session'`

### 4. Обновление `src/shop_bot/webhook_server/app.py`

- Оставить как есть (использует дефолтное значение `'panel_session'`)

## Итоговые имена cookie

- `bot` (webhook_server): `panel_session` (порт 50000)
- `docs-proxy`: `docs_session` (порт 50001)
- `allure-homepage`: `allure_session` (порт 50005)
- `user-cabinet`: `cabinet_session` (порт 50003) - уже исправлено

## Тестирование

После изменений перезапустить все сервисы и проверить, что сессии не конфликтуют между сервисами.

### To-dos

- [ ] Добавить параметр cookie_name в init_flask_auth() с дефолтным значением 'panel_session'
- [ ] Установить SESSION_COOKIE_NAME = 'docs_session' в apps/docs-proxy/app.py после init_flask_auth()
- [ ] Установить SESSION_COOKIE_NAME = 'allure_session' в apps/allure-homepage/app.py после init_flask_auth()
- [ ] Перезапустить все сервисы для применения изменений