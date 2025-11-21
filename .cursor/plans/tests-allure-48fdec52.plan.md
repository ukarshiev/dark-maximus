<!-- 48fdec52-3150-44c0-976b-55c1fb17b2af 779a19e6-6d16-4b8c-a47d-f9444e06f10b -->
# Замена tests.dark-maximus.com на allure.dark-maximus.com

## Цель

Унифицировать использование домена для Allure отчетов: везде использовать `allure.dark-maximus.com` вместо `tests.dark-maximus.com`.

## Изменения

### 1. Nginx конфигурация

**Файл:** `deploy/nginx/dark-maximus.conf.tpl`

- Удалить дублирующий блок для `${TESTS_DOMAIN}` (строки 299-345)
- Оставить только блок для `${ALLURE_DOMAIN}` (строки 144-190)

### 2. Скрипт установки SSL

**Файл:** `ssl-install.sh`

- Удалить строку `TESTS_DOMAIN="tests.${MAIN_DOMAIN}"` (строка 179)
- Удалить вывод `echo -e "   - Tests: ${TESTS_DOMAIN}"` (строка 188)
- Удалить `$TESTS_DOMAIN` из списка проверки DNS (строка 398)
- Удалить блок получения SSL сертификата для `$TESTS_DOMAIN` (строки 577-579)
- Удалить проверку сертификата для `$TESTS_DOMAIN` (строка 639)
- Удалить `TESTS_DOMAIN` из export и envsubst (строки 656-657)

### 3. Веб-панель настроек

**Файл:** `src/shop_bot/webhook_server/templates/settings.html`

- Изменить placeholder с `https://tests.dark-maximus.com` на `https://allure.dark-maximus.com` (строка 346)

### 4. Документация

Заменить все упоминания `tests.dark-maximus.com` на `allure.dark-maximus.com`:

- **`docs/troubleshooting/allure-502-bad-gateway.md`**
- Заменить в заголовке, описании проблемы, примерах команд и URL

- **`docs/guides/testing/allure-reporting.md`**
- Заменить URL в разделах о доступе к отчетам

- **`docs/reports/KAR-29-AUTOTEST-IMPLEMENTATION-PLAN.md`**
- Заменить упоминания домена в плане реализации

- **`docs/reports/KAR-29-COMPLETION-COMMENT.md`**
- Заменить упоминания домена в отчете о завершении

- **`docs/guides/admin/message-templates-testing.md`**
- Заменить URL в примерах доступа к отчетам

### 5. Старые nginx конфигурации (если существуют)

**Файлы:** `nginx/nginx.conf`, `nginx/nginx-ssl.conf`

- Проверить наличие упоминаний `tests.dark-maximus.com` и заменить на `allure.dark-maximus.com`

## Примечания

- CHANGELOG.md не изменяется (исторические записи сохраняются)
- После изменений потребуется перезапуск nginx на боевом сервере
- На боевом сервере нужно будет обновить DNS запись (если она существует) или создать новую для `allure.dark-maximus.com`

### To-dos

- [ ] Удалить дублирующий блок nginx для TESTS_DOMAIN из deploy/nginx/dark-maximus.conf.tpl
- [ ] Удалить TESTS_DOMAIN из ssl-install.sh (определение, вывод, проверки DNS, SSL сертификаты, envsubst)
- [ ] Изменить placeholder в settings.html с tests.dark-maximus.com на allure.dark-maximus.com
- [ ] Заменить tests.dark-maximus.com на allure.dark-maximus.com в docs/troubleshooting/allure-502-bad-gateway.md
- [ ] Заменить tests.dark-maximus.com на allure.dark-maximus.com в docs/guides/testing/allure-reporting.md
- [ ] Заменить tests.dark-maximus.com на allure.dark-maximus.com в docs/reports/KAR-29-*.md
- [ ] Заменить tests.dark-maximus.com на allure.dark-maximus.com в docs/guides/admin/message-templates-testing.md
- [ ] Проверить и обновить nginx/nginx.conf и nginx/nginx-ssl.conf при наличии упоминаний tests.dark-maximus.com