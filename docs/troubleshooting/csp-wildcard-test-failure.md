# Исправление проблемы с тестом CSP wildcard на боевом сервере

> **Дата создания:** 17.11.2025  
> **Проблема:** Тест `test_csp_has_valid_wildcard_for_subdomains` не проходит на боевом сервере

## Проблема

Тест `tests.integration.test_user_cabinet.test_csp_headers.TestCSPHeaders#test_csp_has_valid_wildcard_for_subdomains` не проходит на боевом сервере, потому что Flask приложение использует CSP заголовки без wildcard паттерна, когда `server_environment` в БД установлен в `"development"`.

### Причина

1. **Тест обращается напрямую к Flask приложению** (минуя nginx):
   - Тест использует `http://localhost:50003/health` или `http://user-cabinet:50003/health`
   - Это прямое подключение к Flask контейнеру, не через nginx

2. **Flask приложение устанавливает разные CSP заголовки** в зависимости от `server_environment`:
   - Если `server_environment = "development"`: `frame-src = "'self' http: https:"` (БЕЗ wildcard паттерна)
   - Если `server_environment = "production"`: `frame-src = "'self' https://{help_domain} https://*.{main_domain} https:"` (С wildcard паттерном)

3. **Тест проверяет наличие wildcard паттерна** в `frame-src` и `connect-src`:
   - В development режиме `frame-src` не содержит wildcard паттерн
   - Тест падает с ошибкой о отсутствии wildcard паттерна

### Важно

- **Nginx всегда устанавливает wildcard паттерн** в CSP заголовках (независимо от режима)
- Но тест проверяет CSP заголовки Flask приложения (не nginx)
- Поэтому на боевом сервере нужно установить `server_environment = "production"`

## Диагностика

### Шаг 1: Проверить текущую настройку server_environment

**Вариант A: Через SQL запрос**

```bash
# Подключиться к базе данных на боевом сервере
cd /opt/dark-maximus
sqlite3 users.db "SELECT value FROM bot_settings WHERE key = 'server_environment';"
```

**Вариант B: Через диагностический скрипт**

```bash
# Запустить диагностический скрипт
cd /opt/dark-maximus
docker compose exec autotest python tests/ad-hoc/checks/check_csp_server_environment.py
```

**Вариант C: Через веб-панель**

1. Открыть веб-панель: `https://panel.dark-maximus.com` (или соответствующий домен)
2. Перейти в `/settings` → раздел "Глобальные параметры"
3. Проверить значение "Тип сервера"

### Шаг 2: Проверить CSP заголовки Flask приложения

```bash
# Проверить CSP заголовки напрямую от Flask приложения
curl -I http://localhost:50003/health | grep Content-Security-Policy
```

**Ожидаемый результат для production:**
```
Content-Security-Policy: ... frame-src 'self' https://help.dark-maximus.com https://*.dark-maximus.com https:; ...
```

**Если видите development режим:**
```
Content-Security-Policy: ... frame-src 'self' http: https:; ...
```

## Решение

### Шаг 1: Установить server_environment = 'production'

**Через веб-панель (рекомендуется):**

1. Открыть веб-панель: `https://panel.dark-maximus.com` (или соответствующий домен)
2. Перейти в `/settings` → раздел "Глобальные параметры"
3. Найти настройку "Тип сервера"
4. Установить значение `"production"`
5. Сохранить изменения

**Через SQL (альтернатива):**

```bash
cd /opt/dark-maximus
sqlite3 users.db "UPDATE bot_settings SET value = 'production' WHERE key = 'server_environment';"
```

### Шаг 2: Перезапустить user-cabinet контейнер

```bash
cd /opt/dark-maximus
docker compose restart user-cabinet
```

### Шаг 3: Проверить CSP заголовки

```bash
# Проверить CSP заголовки после перезапуска
curl -I http://localhost:50003/health | grep Content-Security-Policy
```

Убедитесь, что в заголовке присутствует wildcard паттерн `https://*.dark-maximus.com` (или соответствующий домен).

### Шаг 4: Запустить тест

```bash
cd /opt/dark-maximus
docker compose exec autotest pytest tests/integration/test_user_cabinet/test_csp_headers.py::TestCSPHeaders::test_csp_has_valid_wildcard_for_subdomains -v
```

Тест должен пройти успешно.

## Проверка результата

После исправления:

1. ✅ `server_environment` установлен в `"production"`
2. ✅ CSP заголовки Flask приложения содержат wildcard паттерн в `frame-src`
3. ✅ Тест `test_csp_has_valid_wildcard_for_subdomains` проходит успешно

## Дополнительная информация

### Почему это важно?

- В production режиме Flask приложение устанавливает правильные CSP заголовки с wildcard паттернами
- Это позволяет загружать subscription links с любых поддоменов (serv1, serv2, serv3 и т.д.)
- В development режиме используются более мягкие CSP заголовки для удобства разработки

### Связанные файлы

- `apps/user-cabinet/app.py` - Flask приложение, устанавливающее CSP заголовки
- `deploy/nginx/dark-maximus.conf.tpl` - Nginx конфигурация (всегда содержит wildcard)
- `tests/integration/test_user_cabinet/test_csp_headers.py` - Тест проверки CSP заголовков
- `tests/ad-hoc/checks/check_csp_server_environment.py` - Диагностический скрипт

## См. также

- [CSP и отображение IP клиента в личном кабинете](../reports/csp-ip-f8cd13bb.md)
- [Архитектура личного кабинета](../architecture/user-cabinet.md)

