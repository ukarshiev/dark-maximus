<!-- ff7a13a1-a45e-4bad-b877-b70588973a6c c4684907-4e81-4c40-99cc-1e4eeb894661 -->
# Исправление тестов CSP заголовков для user-cabinet

## Проблемы

1. **test_csp_no_invalid_wildcard_patterns** - получает 401 вместо 200, потому что user-cabinet требует токен для доступа к `/`
2. **test_csp_has_valid_wildcard_for_subdomains** - не проверяет наличие wildcard паттерна (только логирует информацию)

## Решение

### 1. Исправление доступа к endpoint

Проблема: Тест делает запрос к `base_url` (который равен `/`), но user-cabinet требует токен для доступа к главной странице.

Решение: Использовать `/health` endpoint для проверки CSP заголовков, так как:

- `/health` не требует токена (возвращает 200)
- CSP заголовки устанавливаются в nginx с флагом `always`, поэтому они должны быть доступны для всех ответов

### 2. Исправление проверки wildcard паттернов

Проблема: Второй тест не делает assert для проверки наличия wildcard паттерна.

Решение: Добавить assert для проверки наличия валидного wildcard паттерна в `frame-src` и `connect-src`.

### 3. Проверка CSP конфигурации в nginx

Текущая конфигурация в `deploy/nginx/dark-maximus.conf.tpl:290`:

```
connect-src 'self' https://api.2ip.ru https://${HELP_DOMAIN} https://*.${MAIN_DOMAIN}; frame-src 'self' https://${HELP_DOMAIN} https://*.${MAIN_DOMAIN};
```

Паттерн `https://*.${MAIN_DOMAIN}` валидный согласно CSP спецификации (wildcard может использоваться для поддоменов).

## Изменения

### Файл: `tests/integration/test_user_cabinet/test_csp_headers.py`

1. **test_csp_no_invalid_wildcard_patterns**:

   - Изменить запрос с `base_url` на `health_url` (или использовать `/health` endpoint)
   - Убедиться, что проверка CSP заголовков работает для 200 ответа

2. **test_csp_has_valid_wildcard_for_subdomains**:

   - Добавить assert для проверки наличия wildcard паттерна в `frame-src`
   - Добавить assert для проверки наличия wildcard паттерна в `connect-src`
   - Изменить запрос на `health_url` для доступа без токена

## Тестирование

После исправления:

1. Запустить тесты: `docker compose exec autotest pytest tests/integration/test_user_cabinet/test_csp_headers.py -v`
2. Проверить отчет в Allure: `http://localhost:5050/allure-docker-service/projects/default/reports/latest/index.html`
3. Убедиться, что оба теста проходят успешно

### To-dos

- [ ] Изменить тесты для использования /health endpoint вместо base_url, чтобы избежать 401 ошибки
- [ ] Добавить assert проверки для наличия валидного wildcard паттерна в test_csp_has_valid_wildcard_for_subdomains
- [ ] Проверить, что CSP конфигурация в nginx содержит правильные директивы frame-src и connect-src с wildcard паттернами
- [ ] Запустить тесты и проверить отчет в Allure для подтверждения исправлений