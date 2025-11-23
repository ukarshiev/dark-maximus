# Настройка nginx для сервера 3x-ui

## Автоматизированная установка

Для автоматизированной установки nginx и SSL-сертификатов используйте два скрипта:

### Порядок выполнения

1. **Установите и настройте 3x-ui вручную** (если еще не установлен)
2. **Запустите скрипт установки nginx** (HTTP конфигурация)
3. **Запустите скрипт установки SSL** (HTTPS конфигурация)

### Скрипт 1: Установка nginx (`install-nginx.sh`)

Устанавливает nginx с временной HTTP конфигурацией.

```bash
# С доменом (порты по умолчанию: 8443 и 2096)
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/deploy/nginx/install-nginx.sh | sudo bash -s -- serv4.dark-maximus.com

# С кастомными портами
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/deploy/nginx/install-nginx.sh | sudo bash -s -- serv4.dark-maximus.com 8443 2096
```

**Что делает скрипт:**
- Проверяет доступность портов 3x-ui
- Устанавливает nginx и зависимости
- Создает HTTP конфигурацию (без SSL)
- Настраивает правила UFW (но не включает его)
- Выводит инструкции для следующего шага

### Скрипт 2: Установка SSL (`install-ssl-certbot.sh`)

Получает SSL-сертификаты через Let's Encrypt и настраивает HTTPS.

```bash
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/deploy/nginx/install-ssl-certbot.sh | sudo bash -s -- serv4.dark-maximus.com
```

**Что делает скрипт:**
- Проверяет DNS (критично для certbot)
- Получает SSL-сертификаты через certbot standalone
- Копирует сертификаты в `/root/cert/${DOMAIN}/`
- Обновляет конфигурацию nginx на HTTPS
- Настраивает автоматическое обновление сертификатов
- Выполняет встроенную проверку установки

**Важно:** 
- DNS должен быть настроен до запуска скрипта
- Certbot автоматически освободит порт 80 (остановит nginx, получит сертификат, запустит nginx)

### Скрипт 3: Проверка установки (`verify-3xui-setup.sh`)

Отдельный скрипт для ручной проверки установки.

```bash
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/deploy/nginx/verify-3xui-setup.sh | bash -s -- serv4.dark-maximus.com

# Или локально:
./deploy/nginx/verify-3xui-setup.sh serv4.dark-maximus.com
```

**Что проверяет скрипт:**
- Статус сервисов (nginx, 3x-ui)
- Доступность портов локально
- Конфигурацию nginx
- SSL-сертификаты (наличие, валидность, срок действия)
- Доступность через HTTPS
- Редирект HTTP → HTTPS
- Логи nginx на наличие ошибок

### Настройка UFW

Скрипты настраивают правила UFW, но не включают его автоматически. После проверки установки включите UFW вручную:

```bash
ufw enable
```

## Проблема: 404 на /configpanel

Если после выполнения скрипта вы получаете 404 на `https://serv4.dark-maximus.com/configpanel`, выполните следующие шаги диагностики:

## Шаг 1: Проверка портов 3x-ui

Используйте скрипт проверки:

```bash
./deploy/nginx/verify-3xui-setup.sh serv4.dark-maximus.com
```

Или вручную проверьте порты:

```bash
# Проверка открытых портов
netstat -tlnp | grep -E '8443|2096|2053'
# или
ss -tlnp | grep -E '8443|2096|2053'

# Проверка локальной доступности
curl -k http://127.0.0.1:8443/configpanel
curl -k http://127.0.0.1:2096/subs/
```

## Шаг 2: Определение правильных портов

3x-ui обычно использует:
- **Порт 8443** - для панели управления (configpanel)
- **Порт 2096** - для подписок (subs)

Но на вашем сервере может быть другая конфигурация. Проверьте конфигурационный файл 3x-ui или настройки в веб-интерфейсе.

## Шаг 3: Использование правильного скрипта

Используйте автоматизированные скрипты установки:

### Если configpanel и subs на разных портах (8443 и 2096):

```bash
# Установка nginx
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/deploy/nginx/install-nginx.sh | sudo bash -s -- serv4.dark-maximus.com 8443 2096

# Установка SSL
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/deploy/nginx/install-ssl-certbot.sh | sudo bash -s -- serv4.dark-maximus.com
```

### Если оба сервиса на одном порту (например, 8443):

```bash
# Установка nginx
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/deploy/nginx/install-nginx.sh | sudo bash -s -- serv4.dark-maximus.com 8443 8443

# Установка SSL
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/deploy/nginx/install-ssl-certbot.sh | sudo bash -s -- serv4.dark-maximus.com
```

## Шаг 4: Проверка логов nginx

Если проблема сохраняется, проверьте логи:

```bash
# Ошибки nginx
tail -f /var/log/nginx/error.log

# Доступы
tail -f /var/log/nginx/access.log
```

Ищите ошибки типа:
- `connect() failed (111: Connection refused)` - неправильный порт
- `upstream prematurely closed connection` - проблема с бэкендом
- `404 Not Found` - неправильный путь

## Шаг 5: Проверка конфигурации nginx

Проверьте синтаксис конфигурации:

```bash
nginx -t
```

Проверьте активную конфигурацию:

```bash
cat /etc/nginx/sites-available/subs.conf
```

## Шаг 6: Ручная проверка подключения

Проверьте, доступен ли 3x-ui локально:

```bash
# Проверка configpanel
curl -vk http://127.0.0.1:8443/configpanel

# Проверка subs
curl -vk http://127.0.0.1:2096/subs/
```

Если локально не работает, проблема в конфигурации 3x-ui, а не в nginx.

## Шаг 7: Альтернативные решения

### Если 3x-ui работает на HTTP локально, но требует HTTPS:

В конфигурации nginx измените `proxy_pass` с `http://` на `https://`:

```nginx
upstream configpanel_backend { 
  server 127.0.0.1:8443; 
}

location /configpanel {
  proxy_pass https://configpanel_backend;  # Используйте https вместо http
  # ...
}
```

### Если путь /configpanel нужно убрать:

Используйте rewrite:

```nginx
location /configpanel {
  rewrite ^/configpanel/(.*) /$1 break;
  proxy_pass http://configpanel_backend;
}
```

### Если 3x-ui работает на другом пути:

Например, если панель доступна по `/panel` вместо `/configpanel`, измените location:

```nginx
location /configpanel {
  proxy_pass http://configpanel_backend/panel;  # Добавьте нужный путь
}
```

## Частые проблемы и решения

### Проблема: "502 Bad Gateway"

**Причина:** nginx не может подключиться к бэкенду

**Решение:**
1. Проверьте, что 3x-ui запущен: `systemctl status x-ui` или `ps aux | grep x-ui`
2. Проверьте порт в upstream: должен совпадать с портом 3x-ui
3. Проверьте firewall: `ufw status`

### Проблема: "404 Not Found"

**Причина:** Неправильный путь в proxy_pass

**Решение:**
1. Проверьте, на каком пути работает 3x-ui локально
2. Попробуйте оба варианта: с trailing slash и без
3. Проверьте конфигурацию nginx в `/etc/nginx/sites-available/subs.conf`

### Проблема: "SSL certificate problem"

**Причина:** 3x-ui использует самоподписанный сертификат

**Решение:**
В конфигурации nginx добавьте для локальных подключений:

```nginx
proxy_ssl_verify off;
proxy_ssl_server_name off;
```

## Контакты и поддержка

Если проблема не решена:
1. Соберите информацию: логи nginx, результат `verify-3xui-setup.sh`, конфигурацию nginx
2. Проверьте документацию 3x-ui: https://github.com/MHSanaei/3x-ui/wiki
3. Создайте issue с подробным описанием проблемы


