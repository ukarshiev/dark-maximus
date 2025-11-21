<!-- 0be4c798-1a63-4910-a421-381e7e11ff46 413a886b-1733-4d2f-bff3-990ca93e0da3 -->
# Исправление CSP для личного кабинета

## Проблема

В файле `deploy/nginx/dark-maximus.conf.tpl` на строке 290 используется невалидный wildcard паттерн `https://serv*.${MAIN_DOMAIN}` в директивах CSP `connect-src` и `frame-src`. CSP не поддерживает wildcard в середине домена, что приводит к ошибке `ERR_BLOCKED_BY_CSP` при попытке загрузить subscription link (например, `https://serv1.dark-maximus.com/subs/...`) в iframe на вкладке "Подключение" личного кабинета.

## Решение

Заменить невалидный паттерн `https://serv*.${MAIN_DOMAIN}` на валидный wildcard паттерн `https://*.${MAIN_DOMAIN}`, который разрешит все поддомены dark-maximus.com (включая serv1, serv2 и т.д.).

## Изменения

### Файл: `deploy/nginx/dark-maximus.conf.tpl`

**Строка 290:** Обновить CSP директиву для личного кабинета:

- Заменить `https://serv*.${MAIN_DOMAIN}` на `https://*.${MAIN_DOMAIN}` в директивах `connect-src` и `frame-src`
- Это разрешит все поддомены dark-maximus.com, включая serv1, serv2, serv3 и т.д.

**Текущая строка:**

```
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://api.2ip.ru; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https://api.2ip.ru https://${HELP_DOMAIN} https://serv*.${MAIN_DOMAIN}; frame-src 'self' https://${HELP_DOMAIN} https://serv*.${MAIN_DOMAIN}; frame-ancestors 'self';" always;
```

**Новая строка:**

```
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://api.2ip.ru; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https://api.2ip.ru https://${HELP_DOMAIN} https://*.${MAIN_DOMAIN}; frame-src 'self' https://${HELP_DOMAIN} https://*.${MAIN_DOMAIN}; frame-ancestors 'self';" always;
```

## Тестирование

После применения изменений необходимо:

1. Перезагрузить nginx конфигурацию
2. Проверить, что subscription links загружаются в iframe без ошибок CSP
3. Убедиться, что консоль браузера не показывает предупреждения о невалидных источниках CSP

## Дополнительные замечания

- Wildcard `https://*.${MAIN_DOMAIN}` разрешит все поддомены dark-maximus.com, что является стандартным подходом в CSP
- Это решение гибкое и не требует обновления CSP при добавлении новых серверов (serv3, serv4 и т.д.)
- Безопасность сохраняется, так как разрешаются только поддомены основного домена

### To-dos

- [ ] Заменить невалидный wildcard паттерн 'serv*.${MAIN_DOMAIN}' на валидный '*.${MAIN_DOMAIN}' в CSP директивах connect-src и frame-src в файле deploy/nginx/dark-maximus.conf.tpl
- [ ] Обновить CHANGELOG.md с записью об исправлении CSP для личного кабинета
- [ ] Обновить версию в pyproject.toml (patch bump)