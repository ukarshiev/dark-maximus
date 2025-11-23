<!-- e4c7a2ae-40f1-4df8-b8fa-f7f6c990e79e d0964396-0f7f-4b3d-8479-91f352dd303a -->
# План: Автоматизированная установка nginx и SSL для 3x-ui сервера

## Структура решения (2 скрипта)

### Скрипт 1: `deploy/nginx/install-nginx.sh`

**Параметры:**

- `$1` - DOMAIN (обязательный): например, `serv4.dark-maximus.com`
- `$2` - CONFIG_PANEL_PORT (опционально, по умолчанию `8443`)
- `$3` - SUBS_PORT (опционально, по умолчанию `2096`)

**Важно:** Этот скрипт запускается ПОСЛЕ установки и настройки 3x-ui вручную.

**Дополнительные проверки:**

- Проверка доступности портов 3x-ui (curl на 127.0.0.1:${CONFIG_PANEL_PORT} и 127.0.0.1:${SUBS_PORT}) - предупреждение, если недоступны, но продолжение
- Проверка существующей конфигурации nginx для домена - предупреждение, если существует, но продолжение с перезаписью

**Этапы выполнения:**

1. **Проверка и подготовка:**

   - Проверка прав root
   - Проверка наличия домена в аргументах
   - Подготовка сервера (apt update/upgrade/dist-upgrade/autoremove/autoclean)
   - Установка зависимостей: `curl`, `wget`, `nginx`

2. **Проверка DNS:**

   - Проверка, что домен указывает на IP текущего сервера
   - Вывод предупреждения, если DNS не настроен (но не остановка)

3. **Установка и настройка nginx (HTTP временно):**

   - Установка nginx
   - Создание временной HTTP конфигурации (без SSL) на основе `setup-3xui-server.sh`
   - Конфигурация включает:
     - Upstream для configpanel (127.0.0.1:${CONFIG_PANEL_PORT})
     - Upstream для subs (127.0.0.1:${SUBS_PORT})
     - Server block на порту 80 с proxy_pass к бэкендам
     - Location блоки для /configpanel, /configpanel/, /subs/, /assets/
     - Статические файлы (css, js, images)
   - Проверка синтаксиса: `nginx -t`
   - Перезагрузка nginx: `systemctl reload nginx`

4. **Настройка UFW (но не включение):**

   - Если UFW установлен, настройка правил:
     - `ufw allow 443/tcp` (но не активация)
     - `ufw deny ${CONFIG_PANEL_PORT}/tcp` (но не активация)
     - `ufw deny ${SUBS_PORT}/tcp` (но не активация)
   - Вывод сообщения, что UFW настроен, но не включен

5. **Вывод информации:**

   - Инструкция по запуску второго скрипта для получения SSL-сертификатов
   - URL для проверки HTTP версии

### Скрипт 2: `deploy/nginx/install-ssl-certbot.sh`

**Параметры:**

- `$1` - DOMAIN (обязательный): например, `serv4.dark-maximus.com`

**Этапы выполнения:**

1. **Проверка и подготовка:**

   - Проверка прав root
   - Проверка наличия домена в аргументах
   - Проверка, что nginx установлен и работает
   - Установка certbot: `apt install -y certbot`

2. **Проверка DNS:**

   - Проверка, что домен указывает на IP текущего сервера
   - Остановка скрипта с ошибкой, если DNS не настроен (критично для certbot)

3. **Получение SSL-сертификатов через certbot standalone:**

   - Certbot автоматически остановит nginx, получит сертификат и запустит nginx обратно
   - Команда:
     ```bash
     certbot certonly --standalone -d ${DOMAIN} --non-interactive --agree-tos --register-unsafely-without-email
     ```

   - Certbot сохранит сертификаты в `/etc/letsencrypt/live/${DOMAIN}/`

4. **Копирование сертификатов в /root/cert/{domain}/:**

   - Создание директории: `mkdir -p /root/cert/${DOMAIN}`
   - Копирование сертификатов:
     ```bash
     cp /etc/letsencrypt/live/${DOMAIN}/fullchain.pem /root/cert/${DOMAIN}/
     cp /etc/letsencrypt/live/${DOMAIN}/privkey.pem /root/cert/${DOMAIN}/
     ```

   - Установка прав доступа:
     ```bash
     chmod 644 /root/cert/${DOMAIN}/fullchain.pem
     chmod 600 /root/cert/${DOMAIN}/privkey.pem
     ```


5. **Обновление конфигурации nginx на HTTPS:**

   - Обновление существующей конфигурации (замена HTTP на HTTPS)
   - Добавление SSL-директив:
     - `listen 443 ssl http2;`
     - `ssl_certificate /root/cert/${DOMAIN}/fullchain.pem;`
     - `ssl_certificate_key /root/cert/${DOMAIN}/privkey.pem;`
     - Все proxy заголовки из `setup-3xui-server.sh`
   - Добавление редиректа HTTP → HTTPS:
     ```nginx
     server {
       listen 80;
       server_name ${DOMAIN};
       return 301 https://$host$request_uri;
     }
     ```

   - Проверка синтаксиса: `nginx -t`
   - Перезагрузка nginx: `systemctl reload nginx`

6. **Настройка автоматического обновления сертификатов:**

   - Создание systemd service для deploy-hook:
     ```bash
     /etc/systemd/system/certbot-renew-${DOMAIN}.service
     ```

   - Создание systemd timer:
     ```bash
     /etc/systemd/system/certbot-renew-${DOMAIN}.timer
     ```

   - Создание скрипта deploy-hook:
     ```bash
     /etc/letsencrypt/renewal-hooks/deploy/copy-to-root-cert-${DOMAIN}.sh
     ```

   - Скрипт deploy-hook выполняет:
     - Копирование обновленных сертификатов в `/root/cert/${DOMAIN}/`
     - Перезагрузку nginx: `systemctl reload nginx`
   - Активация timer: `systemctl enable --now certbot-renew-${DOMAIN}.timer`

7. **Вывод информации:**

   - URL для доступа к configpanel и subs через HTTPS
   - Информация о настройке автообновления сертификатов

### Скрипт 3: `deploy/nginx/verify-3xui-setup.sh`

**Параметры:**

- `$1` - DOMAIN (обязательный)

**Проверяет:**

1. **Статус сервисов:**

   - Статус nginx (systemctl is-active nginx)
   - Статус 3x-ui (systemctl is-active x-ui, если доступен)

2. **Доступность портов локально:**

   - Проверка порта configpanel (8443 по умолчанию) через curl на 127.0.0.1
   - Проверка порта subs (2096 по умолчанию) через curl на 127.0.0.1

3. **Конфигурация nginx:**

   - Проверка синтаксиса: `nginx -t`
   - Наличие конфигурации для домена в `/etc/nginx/sites-available/`
   - Наличие символической ссылки в `/etc/nginx/sites-enabled/`

4. **SSL-сертификаты:**

   - Наличие файлов в `/root/cert/${DOMAIN}/fullchain.pem` и `privkey.pem`
   - Валидность сертификатов через `openssl x509 -in /root/cert/${DOMAIN}/fullchain.pem -noout -dates`
   - Проверка срока действия (не истек ли)

5. **Доступность через HTTPS:**

   - Configpanel: `curl -kI https://${DOMAIN}/configpanel` (ожидается 200, 301 или 302)
   - Subs: `curl -kI https://${DOMAIN}/subs/` (ожидается 200, 301 или 302)

6. **Редирект HTTP → HTTPS:**

   - Проверка: `curl -I http://${DOMAIN}/configpanel` (ожидается 301 редирект)

7. **Логи nginx:**

   - Проверка последних ошибок в `/var/log/nginx/error.log` (последние 10 строк)
   - Вывод предупреждения, если есть ошибки

8. **Вывод подробного отчета:**

   - Таблица с результатами всех проверок (✓ или ✗)
   - Рекомендации по исправлению проблем
   - Итоговый статус (успешно/есть проблемы)

### Обновление документации: `deploy/nginx/README-3xui-setup.md`

**Добавить разделы:**

- Инструкция по использованию двух скриптов установки
- Порядок выполнения: сначала install-nginx-3xui.sh, затем install-ssl-certbot.sh
- Примеры использования
- Troubleshooting
- Информация о настройке UFW (настроен, но не включен)

## Использование

**Важно:** Домен передается как обязательный аргумент через `$1` в обоих скриптах установки.

```bash
# Шаг 1: Установка nginx с HTTP конфигурацией
# Домен передается через аргумент командной строки
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/deploy/nginx/install-nginx-3xui.sh | sudo bash -s -- serv4.dark-maximus.com

# С кастомными портами (домен обязателен, порты опциональны):
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/deploy/nginx/install-nginx-3xui.sh | sudo bash -s -- serv4.dark-maximus.com 8443 2096

# Шаг 2: Получение SSL-сертификатов и настройка HTTPS
# Домен передается через аргумент командной строки
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/deploy/nginx/install-ssl-certbot.sh | sudo bash -s -- serv4.dark-maximus.com

# Шаг 3: Проверка системы
# Домен передается через аргумент командной строки
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/deploy/nginx/verify-3xui-setup.sh | bash -s -- serv4.dark-maximus.com
# Или локально:
./deploy/nginx/verify-3xui-setup.sh serv4.dark-maximus.com
```

**Обработка аргументов в скриптах:**

- Скрипт 1 (`install-nginx-3xui.sh`):
  ```bash
  DOMAIN="${1:?Ошибка: укажите домен как первый аргумент}"
  CONFIG_PANEL_PORT="${2:-8443}"
  SUBS_PORT="${3:-2096}"
  ```

- Скрипт 2 (`install-ssl-certbot.sh`):
  ```bash
  DOMAIN="${1:?Ошибка: укажите домен как первый аргумент}"
  ```

- Скрипт 3 (`verify-3xui-setup.sh`):
  ```bash
  DOMAIN="${1:?Ошибка: укажите домен как первый аргумент}"
  ```


## Технические детали

1. **Certbot standalone метод:**

   - Автоматически останавливает nginx перед получением сертификата
   - Получает сертификат через порт 80
   - Автоматически запускает nginx обратно после получения

2. **Автообновление сертификатов:**

   - Systemd timer запускается дважды в день (как рекомендует certbot)
   - Deploy-hook копирует обновленные сертификаты в `/root/cert/${DOMAIN}/`
   - Deploy-hook перезагружает nginx для применения новых сертификатов

3. **Безопасность:**

   - Проверка прав root в обоих скриптах
   - Проверка DNS перед certbot (критично)
   - Использование `set -euo pipefail` для безопасности скриптов
   - Логирование всех действий

4. **UFW:**

   - Правила настраиваются, но UFW не включается автоматически
   - Пользователь может включить UFW вручную после проверки: `ufw enable`

5. **Обработка ошибок:**

   - Проверка каждого этапа
   - Вывод понятных сообщений об ошибках
   - Остановка скрипта при критических ошибках (DNS для certbot)