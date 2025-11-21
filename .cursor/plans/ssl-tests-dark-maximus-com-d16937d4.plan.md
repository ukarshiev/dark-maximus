<!-- d16937d4-e2b3-471f-bfbb-e8cbd9f597df 4ac2a451-a515-48ed-998d-5c47cd4088e6 -->
# Исправление проверки DNS и обработки certbot renewal

## Проблемы (подтвержденные факты)

1. **Отсутствие проверки DNS для ALLURE_DOMAIN (100% факт):**

   - В строке 398 проверяется только TESTS_DOMAIN, но не ALLURE_DOMAIN
   - Это приводит к тому, что DNS для allure.dark-maximus.com не проверяется

2. **На сервере выполняется старая версия скрипта (подтверждено анализом вывода):**

   - В выводе терминала нет сообщений из функции `get_certificate()` (нет цветовых кодов, нет сообщений "✔ Сертификат для ... уже существует")
   - В выводе нет попытки получить сертификат для tests.dark-maximus.com
   - В выводе нет проверки DNS для allure.dark-maximus.com и tests.dark-maximus.com
   - Это означает, что на сервере выполняется старая версия скрипта без функции `get_certificate()`

3. **Проблема с "Certificate not yet due for renewal":**

   - Certbot возвращает код 0, когда сертификат уже существует
   - Но если сертификат отсутствует для нового домена (tests.dark-maximus.com), certbot может вернуть код 0 с сообщением "Certificate not yet due for renewal", но сертификат не будет создан
   - Нужно использовать флаг `--force-renewal` или `--keep-until-expiring` для принудительного получения

## Решение

### 1. Добавить ALLURE_DOMAIN в проверку DNS

**Файл:** `ssl-install.sh`

Изменить строку 398:

```bash
for check_domain in "$MAIN_DOMAIN" "$PANEL_DOMAIN" "$DOCS_DOMAIN" "$HELP_DOMAIN" "$APP_DOMAIN" "$TESTS_DOMAIN"; do
```

На:

```bash
for check_domain in "$MAIN_DOMAIN" "$PANEL_DOMAIN" "$DOCS_DOMAIN" "$HELP_DOMAIN" "$APP_DOMAIN" "$ALLURE_DOMAIN" "$TESTS_DOMAIN"; do
```

### 2. Улучшить обработку "Certificate not yet due for renewal"

**Файл:** `ssl-install.sh`

В функции `get_certificate()`:

- Если certbot возвращает код 0, но выводит "Certificate not yet due for renewal", это означает, что сертификат уже существует
- Но нужно проверить, что файлы действительно существуют
- Если файлы не существуют, но certbot говорит "not yet due for renewal", это ошибка - нужно принудительно получить сертификат

### 3. Добавить принудительное получение для отсутствующих сертификатов

**Файл:** `ssl-install.sh`

Если сертификат не существует, но certbot говорит "not yet due for renewal", использовать `--force-renewal` или проверить, что файлы действительно существуют после вызова certbot.

## Файлы для изменения

1. `ssl-install.sh` - добавление ALLURE_DOMAIN в проверку DNS и улучшение обработки certbot

## Ожидаемый результат

- Проверка DNS выполняется для всех 7 доменов, включая ALLURE_DOMAIN
- Сертификаты получаются для всех доменов, включая tests.dark-maximus.com
- Правильная обработка случая "Certificate not yet due for renewal"