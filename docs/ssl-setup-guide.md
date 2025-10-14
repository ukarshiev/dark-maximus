# Руководство по настройке SSL для 3x-ui

> Обновлено: 29.12.2024

## ⚠️ Важно: Проблемы встроенного SSL в 3x-ui

**НЕ используйте встроенный механизм SSL в 3x-ui!**

### Почему встроенный SSL ненадежен:

1. **Нестабильность** - сертификаты часто "слетают" через некоторое время
2. **Сложность отладки** - трудно понять причину проблем
3. **Конфликты с обновлением** - certbot может конфликтовать с внутренним механизмом 3x-ui
4. **Ограниченная функциональность** - нет гибкости в настройке
5. **Проблемы с автообновлением** - сертификаты не обновляются автоматически

## ✅ Рекомендуемое решение: Nginx + Let's Encrypt

### Архитектура

```
┌─────────┐     HTTPS     ┌───────────┐    HTTP     ┌────────────┐
│ Интернет│ ──────────────→│   Nginx   │────────────→│   3x-ui    │
│         │   (SSL/TLS)    │ (порт 443)│ (localhost) │ (порт 2053)│
└─────────┘                └───────────┘             └────────────┘
                                 ↓
                           Let's Encrypt
                           SSL Certificates
```

### Преимущества этого подхода:

✅ **Надежность** - стабильная работа SSL без сбоев  
✅ **Автообновление** - сертификаты обновляются автоматически  
✅ **Безопасность** - проверенное решение с лучшими практиками  
✅ **Гибкость** - легко настроить несколько доменов  
✅ **Производительность** - оптимизированная обработка SSL  

## 🚀 Быстрая установка

### Вариант 1: Автоматический скрипт (рекомендуется)

```bash
# Скачайте скрипт
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/setup-ssl.sh -o setup-ssl.sh

# Сделайте его исполняемым
chmod +x setup-ssl.sh

# Запустите с правами root
sudo ./setup-ssl.sh
```

**Скрипт автоматически:**
- Проверит DNS записи
- Установит Certbot
- Получит SSL сертификаты для всех доменов
- Настроит Nginx как reverse proxy
- Настроит автообновление сертификатов
- Создаст конфигурации для production

### Вариант 2: Ручная настройка

#### Шаг 1: Установка Certbot

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y certbot python3-certbot-nginx

# CentOS/RHEL
sudo yum install -y certbot python3-certbot-nginx
```

#### Шаг 2: Получение сертификатов

```bash
# Для домена бота
sudo certbot certonly --nginx \
  -d bot.example.com \
  --email your-email@example.com \
  --agree-tos \
  --non-interactive

# Для домена панели 3x-ui
sudo certbot certonly --nginx \
  -d panel.example.com \
  --email your-email@example.com \
  --agree-tos \
  --non-interactive
```

#### Шаг 3: Настройка Nginx

**Для бота (bot.example.com):**

```nginx
# /etc/nginx/sites-available/bot.conf

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name bot.example.com;

    # SSL сертификаты
    ssl_certificate /etc/letsencrypt/live/bot.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bot.example.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Заголовки безопасности
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    location / {
        proxy_pass http://127.0.0.1:1488;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Редирект с HTTP на HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name bot.example.com;
    return 301 https://$server_name$request_uri;
}
```

**Для панели 3x-ui (panel.example.com):**

```nginx
# /etc/nginx/sites-available/panel.conf

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name panel.example.com;

    # SSL сертификаты
    ssl_certificate /etc/letsencrypt/live/panel.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/panel.example.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Заголовки безопасности
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    location / {
        proxy_pass http://127.0.0.1:2053;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket поддержка
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

# Редирект с HTTP на HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name panel.example.com;
    return 301 https://$server_name$request_uri;
}
```

#### Шаг 4: Активация конфигурации

```bash
# Создайте символические ссылки
sudo ln -sf /etc/nginx/sites-available/bot.conf /etc/nginx/sites-enabled/
sudo ln -sf /etc/nginx/sites-available/panel.conf /etc/nginx/sites-enabled/

# Проверьте конфигурацию
sudo nginx -t

# Перезагрузите Nginx
sudo systemctl reload nginx
```

#### Шаг 5: Автообновление сертификатов

```bash
# Добавьте задачу в cron
sudo crontab -e

# Добавьте эту строку (обновление каждый день в 12:00)
0 12 * * * /usr/bin/certbot renew --quiet --post-hook "systemctl reload nginx"
```

## ⚙️ Настройка 3x-ui

После настройки SSL в Nginx, **обязательно настройте 3x-ui для работы без SSL:**

1. Зайдите в панель 3x-ui: `https://panel.example.com`

2. Перейдите в **Настройки панели** (Settings)

3. Установите следующие параметры:
   - **Listen IP**: `127.0.0.1` ⚠️
   - **Port**: `2053` (или любой другой локальный порт)
   - **Enable TLS/SSL**: `❌ ОТКЛЮЧИТЬ` ⚠️

4. Нажмите **Save** и перезапустите 3x-ui

### ⚠️ Критически важно:

```diff
- ❌ НЕ включайте SSL в 3x-ui
- ❌ НЕ используйте 0.0.0.0 в Listen IP
+ ✅ Используйте 127.0.0.1 (только localhost)
+ ✅ Отключите TLS/SSL в настройках 3x-ui
+ ✅ SSL обрабатывает Nginx
```

## 🔍 Проверка работы

### Проверка сертификатов

```bash
# Список установленных сертификатов
sudo certbot certificates

# Тест автообновления (dry run)
sudo certbot renew --dry-run

# Проверка срока действия
echo | openssl s_client -servername bot.example.com -connect bot.example.com:443 2>/dev/null | openssl x509 -noout -dates
```

### Проверка Nginx

```bash
# Тест конфигурации
sudo nginx -t

# Статус Nginx
sudo systemctl status nginx

# Просмотр логов
sudo tail -f /var/log/nginx/error.log
```

### Проверка доступности

```bash
# Проверка бота
curl -I https://bot.example.com

# Проверка панели 3x-ui
curl -I https://panel.example.com

# Проверка редиректа с HTTP на HTTPS
curl -I http://bot.example.com
```

## 🔧 Устранение неполадок

### Проблема: Сертификат не применяется

**Решение:**
```bash
# Проверьте пути к сертификатам
sudo ls -la /etc/letsencrypt/live/

# Проверьте конфигурацию Nginx
sudo nginx -t

# Перезапустите Nginx
sudo systemctl restart nginx
```

### Проблема: Ошибка "connection refused" при доступе к панели

**Решение:**
```bash
# Проверьте, что 3x-ui запущен на localhost
sudo netstat -tlnp | grep 2053

# Проверьте настройки 3x-ui (должно быть 127.0.0.1:2053)
```

### Проблема: Сертификат не обновляется автоматически

**Решение:**
```bash
# Проверьте задачи cron
sudo crontab -l

# Принудительное обновление
sudo certbot renew --force-renewal

# Проверьте логи
sudo tail -f /var/log/letsencrypt/letsencrypt.log
```

### Проблема: "Too Many Failed Authorizations"

**Решение:**
```bash
# Let's Encrypt имеет лимиты на количество попыток
# Подождите 1 час перед следующей попыткой

# Используйте staging сервер для тестов
sudo certbot certonly --staging \
  -d bot.example.com \
  --nginx
```

## 📊 Мониторинг SSL

### Проверка срока действия сертификата

Создайте скрипт для мониторинга:

```bash
# /usr/local/bin/check-ssl.sh
#!/bin/bash

DOMAIN="bot.example.com"
DAYS_BEFORE_EXPIRY=$(echo | openssl s_client -servername $DOMAIN -connect $DOMAIN:443 2>/dev/null | openssl x509 -noout -checkend 604800)

if [ $? -eq 0 ]; then
    echo "✅ SSL сертификат для $DOMAIN действителен"
else
    echo "⚠️ SSL сертификат для $DOMAIN истекает менее чем через 7 дней!"
fi
```

### Добавление в мониторинг

```bash
# Сделайте скрипт исполняемым
chmod +x /usr/local/bin/check-ssl.sh

# Добавьте в cron (проверка каждый день)
0 9 * * * /usr/local/bin/check-ssl.sh
```

## 🔐 Безопасность

### Рекомендуемые настройки SSL для Nginx

```nginx
# Современные SSL протоколы
ssl_protocols TLSv1.2 TLSv1.3;

# Сильные шифры
ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';

# Предпочитать серверные шифры
ssl_prefer_server_ciphers on;

# HSTS (HTTP Strict Transport Security)
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

# Защита от clickjacking
add_header X-Frame-Options "SAMEORIGIN" always;

# Защита от MIME-sniffing
add_header X-Content-Type-Options "nosniff" always;

# XSS Protection
add_header X-XSS-Protection "1; mode=block" always;

# OCSP Stapling
ssl_stapling on;
ssl_stapling_verify on;
```

## 📚 Дополнительные ресурсы

- [Let's Encrypt документация](https://letsencrypt.org/docs/)
- [Certbot документация](https://certbot.eff.org/docs/)
- [Nginx SSL конфигурация](https://nginx.org/en/docs/http/configuring_https_servers.html)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)

## 🆘 Поддержка

Если у вас возникли проблемы:

1. Проверьте логи: `/var/log/nginx/error.log` и `/var/log/letsencrypt/letsencrypt.log`
2. Создайте Issue в репозитории: [GitHub Issues](https://github.com/ukarshiev/dark-maximus/issues)
3. Обратитесь в Telegram: [@ukarshiev](https://t.me/ukarshiev)

---

*Помните: надежный SSL - основа безопасности вашего VPN-сервиса!*
