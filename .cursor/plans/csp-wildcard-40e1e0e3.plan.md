<!-- 40e1e0e3-d8d5-4b60-9b69-4b63a721bf8d eed84fac-76bc-4eb0-92e9-b8ce6890e04d -->
# Исправление теста CSP wildcard на боевом сервере

## Проблема

Тест `tests.integration.test_user_cabinet.test_csp_headers.TestCSPHeaders#test_csp_has_valid_wildcard_for_subdomains` не проходит на боевом сервере (ssh root@31.56.27.129), потому что Flask приложение использует CSP заголовки без wildcard паттерна, когда `server_environment` в БД установлен в `"development"`.

### Анализ проблемы

1. **В `apps/user-cabinet/app.py` (строки 94-103)**:

   - Если `is_development_server() == True`: используется `frame-src = "'self' http: https:"` (без wildcard паттерна)
   - Если `is_development_server() == False`: используется `frame-src = f"'self' https://{help_domain} https://*.{main_domain} https:"` (с wildcard паттерном)

2. **Функция `is_development_server()`** (в `src/shop_bot/data_manager/database.py`, строка 2930):

   - Проверяет настройку `server_environment` в БД
   - Возвращает `True` если `server_environment == "development"`

3. **Тест `test_csp_has_valid_wildcard_for_subdomains`** (строки 290-371):

   - Проверяет наличие wildcard паттерна `*.domain.com` или `https://*.domain.com` в CSP заголовках
   - Использует регулярное выражение `r'https?://\*\.|^\*\.'` для поиска паттерна
   - Если паттерн не найден, тест падает

### Причина

На боевом сервере настройка `server_environment` в БД установлена в `"development"`, что приводит к использованию CSP заголовков без wildcard паттерна. Тест ожидает wildcard паттерн, но его нет в development режиме.

## Решение

### Вариант 1: Исправить настройку server_environment на боевом сервере (рекомендуется)

1. **Проверить текущую настройку** на боевом сервере:
   ```sql
   SELECT value FROM bot_settings WHERE key = 'server_environment';
   ```

2. **Установить правильное значение** через веб-панель:

   - Перейти в `/settings` → раздел "Глобальные параметры" → "Тип сервера"
   - Установить значение `"production"`

3. **Перезапустить user-cabinet контейнер** для применения изменений:
   ```bash
   docker compose restart user-cabinet
   ```


### Вариант 2: Обновить тест для учета development режима

Если тест должен работать и в development режиме, нужно обновить тест, чтобы он:

1. Проверял текущий режим сервера через `is_development_server()`
2. Пропускал проверку wildcard паттерна в development режиме (или проверял наличие `https:` вместо wildcard)

## Файлы для изменения

- **Проверка на боевом сервере**: настройка `server_environment` в БД (`bot_settings` таблица)
- **Опционально**: `tests/integration/test_user_cabinet/test_csp_headers.py` - обновить тест для учета development режима

## Тестирование

После исправления:

1. Запустить тест на боевом сервере:
   ```bash
   docker compose exec autotest pytest tests/integration/test_user_cabinet/test_csp_headers.py::TestCSPHeaders::test_csp_has_valid_wildcard_for_subdomains -v
   ```

2. Проверить CSP заголовки напрямую:
   ```bash
   curl -I http://localhost:50003/health | grep Content-Security-Policy
   ```

3. Убедиться, что в CSP заголовках присутствует wildcard паттерн `https://*.dark-maximus.com` (или соответствующий домен)

## Рекомендация

Рекомендуется использовать **Вариант 1**, так как на боевом сервере должен быть установлен режим `"production"` для корректной работы CSP заголовков с wildcard паттернами для поддоменов.

### To-dos

- [ ] Проверить настройку server_environment в БД на боевом сервере через SQL запрос или веб-панель
- [ ] Установить server_environment = 'production' на боевом сервере через веб-панель (/settings → Глобальные параметры → Тип сервера)
- [ ] Перезапустить user-cabinet контейнер для применения изменений CSP заголовков
- [ ] Проверить CSP заголовки через curl и убедиться, что wildcard паттерн присутствует
- [ ] Запустить тест test_csp_has_valid_wildcard_for_subdomains на боевом сервере и убедиться, что он проходит