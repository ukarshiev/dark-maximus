#!/usr/bin/env bash

set -euo pipefail

# Параметры
DOMAIN="${1:?Ошибка: укажите домен как первый аргумент}"

# Значения по умолчанию для портов (соответствуют скрипту install-nginx.sh)
CONFIG_PANEL_PORT="${2:-8443}"
SUBS_PORT="${3:-2096}"

CONF_AVAIL="/etc/nginx/sites-available/subs.conf"
CONF_ENAB="/etc/nginx/sites-enabled/subs.conf"
CERT_DIR="/root/cert/${DOMAIN}"
LETSENCRYPT_CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    echo "Ошибка: скрипт должен запускаться от root"
    exit 1
fi

echo "=========================================="
echo "Установка SSL-сертификатов для 3x-ui"
echo "Домен: ${DOMAIN}"
echo "=========================================="
echo ""

# 1. Проверка и подготовка
echo "[1/7] Проверка и подготовка..."

# Проверка, что nginx установлен и работает
if ! command -v nginx >/dev/null 2>&1; then
    echo "✗ Ошибка: nginx не установлен"
    echo "   Сначала запустите скрипт install-nginx.sh"
    exit 1
fi

if ! systemctl is-active --quiet nginx; then
    echo "✗ Ошибка: nginx не запущен"
    echo "   Запустите nginx: systemctl start nginx"
    exit 1
fi

echo "✓ Nginx установлен и работает"

# Установка certbot
if ! command -v certbot >/dev/null 2>&1; then
    echo "Установка certbot..."
    apt update
    apt install -y certbot
    echo "✓ Certbot установлен"
else
    echo "✓ Certbot уже установлен"
fi

echo ""

# 2. Проверка DNS (критично)
echo "[2/7] Проверка DNS (критично для certbot)..."

SERVER_IP=$(curl -s ifconfig.me || curl -s ipinfo.io/ip || echo "")
DOMAIN_IP=$(dig +short ${DOMAIN} | tail -n1 || echo "")

if [ -z "$SERVER_IP" ] || [ -z "$DOMAIN_IP" ]; then
    echo "✗ Ошибка: не удалось проверить DNS"
    echo "   Убедитесь, что домен ${DOMAIN} указывает на IP этого сервера"
    exit 1
fi

if [ "$SERVER_IP" != "$DOMAIN_IP" ]; then
    echo "✗ Ошибка: DNS настроен неправильно"
    echo "   IP сервера: ${SERVER_IP}"
    echo "   IP домена: ${DOMAIN_IP}"
    echo "   Домен должен указывать на IP сервера для получения сертификата"
    exit 1
fi

echo "✓ DNS настроен правильно: ${DOMAIN} → ${DOMAIN_IP}"
echo ""

# 3. Получение SSL-сертификатов через certbot standalone
echo "[3/7] Получение SSL-сертификатов через certbot standalone..."

# Certbot автоматически остановит nginx, получит сертификат и запустит nginx обратно
if certbot certonly --standalone -d ${DOMAIN} --non-interactive --agree-tos --register-unsafely-without-email; then
    echo "✓ SSL-сертификат успешно получен"
else
    echo "✗ Ошибка: не удалось получить SSL-сертификат"
    exit 1
fi

echo ""

# 4. Копирование сертификатов в /root/cert/{domain}/
echo "[4/7] Копирование сертификатов в /root/cert/${DOMAIN}/..."

# Создание директории
mkdir -p "$CERT_DIR"

# Копирование сертификатов
if [ -f "${LETSENCRYPT_CERT_DIR}/fullchain.pem" ] && [ -f "${LETSENCRYPT_CERT_DIR}/privkey.pem" ]; then
    cp "${LETSENCRYPT_CERT_DIR}/fullchain.pem" "$CERT_DIR/"
    cp "${LETSENCRYPT_CERT_DIR}/privkey.pem" "$CERT_DIR/"
    
    # Установка прав доступа
    chmod 644 "${CERT_DIR}/fullchain.pem"
    chmod 600 "${CERT_DIR}/privkey.pem"
    
    echo "✓ Сертификаты скопированы в ${CERT_DIR}/"
else
    echo "✗ Ошибка: сертификаты не найдены в ${LETSENCRYPT_CERT_DIR}/"
    exit 1
fi

echo ""

# 5. Обновление конфигурации nginx на HTTPS
echo "[5/7] Обновление конфигурации nginx на HTTPS..."

# Проверка существования конфигурации
if [ ! -f "$CONF_AVAIL" ]; then
    echo "✗ Ошибка: конфигурация nginx не найдена"
    echo "   Сначала запустите скрипт install-nginx.sh"
    exit 1
fi

# Обновление конфигурации: замена HTTP на HTTPS
cat > "$CONF_AVAIL" <<NGINX
upstream subs_backend { 
  server 127.0.0.1:${SUBS_PORT}; 
}

upstream configpanel_backend { 
  server 127.0.0.1:${CONFIG_PANEL_PORT}; 
}

server {
  listen 443 ssl http2;
  server_name ${DOMAIN};

  ssl_certificate     /root/cert/${DOMAIN}/fullchain.pem;
  ssl_certificate_key /root/cert/${DOMAIN}/privkey.pem;

  proxy_http_version 1.1;
  proxy_set_header Host                \$host;
  proxy_set_header X-Forwarded-Host    \$host;
  proxy_set_header X-Forwarded-Server  \$host;
  proxy_set_header X-Real-IP           \$remote_addr;
  proxy_set_header X-Forwarded-For     \$proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto  https;
  proxy_set_header X-Forwarded-Port    443;

  proxy_ssl_server_name on;
  proxy_ssl_name \$host;

  # Подписки - используем порт для subs
  location = /subs { 
    return 301 /subs/; 
  }

  location /subs/ {
    proxy_pass http://subs_backend/;
    proxy_redirect ~^https?://[^/]+:${SUBS_PORT}(/.*)\$ https://\$host\$1;
  }

  # Панель управления 3x-ui - используем порт для configpanel
  # Важно: без trailing slash в proxy_pass, чтобы сохранить путь /configpanel
  location /configpanel {
    proxy_pass http://configpanel_backend;
    proxy_redirect off;
    
    # Дополнительные заголовки для WebSocket (если нужно)
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection "upgrade";
  }

  location /configpanel/ {
    proxy_pass http://configpanel_backend/;
    proxy_redirect off;
    
    # Дополнительные заголовки для WebSocket (если нужно)
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection "upgrade";
  }

  # Статические файлы для configpanel
  location ^~ /assets/ { 
    proxy_pass http://configpanel_backend; 
  }

  location ~* \.(css|js|map|png|jpe?g|gif|svg|ico|woff2?|ttf|eot)$ {
    proxy_pass http://configpanel_backend;
  }

  # 404 от бэка → 200 для страницы подписки
  location ~ ^/subs/[A-Za-z0-9]+\$ {
    proxy_intercept_errors on;
    proxy_pass http://subs_backend;
    error_page 404 =200 @subs200;
  }

  location @subs200 {
    proxy_pass http://subs_backend;
  }
}

server { 
  listen 80; 
  server_name ${DOMAIN}; 
  return 301 https://\$host\$request_uri; 
}
NGINX

# Создание символической ссылки (если еще не создана)
ln -sf "$CONF_AVAIL" "$CONF_ENAB"

# Проверка синтаксиса
if nginx -t; then
    echo "✓ Синтаксис конфигурации nginx корректен"
else
    echo "✗ Ошибка в конфигурации nginx"
    exit 1
fi

# Перезагрузка nginx
systemctl reload nginx

echo "✓ Nginx обновлен на HTTPS"
echo ""

# 6. Настройка автоматического обновления сертификатов
echo "[6/7] Настройка автоматического обновления сертификатов..."

# Создание директории для deploy-hooks
mkdir -p /etc/letsencrypt/renewal-hooks/deploy

# Создание скрипта deploy-hook
DEPLOY_HOOK="/etc/letsencrypt/renewal-hooks/deploy/copy-to-root-cert-${DOMAIN}.sh"
cat > "$DEPLOY_HOOK" <<'DEPLOY_SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${RENEWED_DOMAINS%% *}"
CERT_DIR="/root/cert/${DOMAIN}"

if [ -n "$DOMAIN" ] && [ -d "/etc/letsencrypt/live/${DOMAIN}" ]; then
    mkdir -p "$CERT_DIR"
    cp "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" "$CERT_DIR/"
    cp "/etc/letsencrypt/live/${DOMAIN}/privkey.pem" "$CERT_DIR/"
    chmod 644 "${CERT_DIR}/fullchain.pem"
    chmod 600 "${CERT_DIR}/privkey.pem"
    systemctl reload nginx
    echo "Сертификаты для ${DOMAIN} обновлены и скопированы в ${CERT_DIR}/"
fi
DEPLOY_SCRIPT

chmod +x "$DEPLOY_HOOK"

echo "✓ Deploy-hook создан: ${DEPLOY_HOOK}"
echo "   Сертификаты будут автоматически обновляться через встроенный certbot.timer"
echo ""

# 7. Встроенная проверка
echo "[7/7] Проверка установки..."

# Проверка статуса nginx
if systemctl is-active --quiet nginx; then
    echo "✓ Nginx работает"
else
    echo "✗ Nginx не работает"
fi

# Проверка статуса 3x-ui (если доступен)
if systemctl list-unit-files | grep -q "x-ui.service"; then
    if systemctl is-active --quiet x-ui 2>/dev/null; then
        echo "✓ 3x-ui работает"
    else
        echo "⚠ 3x-ui не работает (но это может быть нормально)"
    fi
fi

# Проверка доступности портов локально
if curl -k -s -o /dev/null -w "%{http_code}" --connect-timeout 2 http://127.0.0.1:${CONFIG_PANEL_PORT}/configpanel 2>/dev/null | grep -q "200\|301\|302"; then
    echo "✓ Порт ${CONFIG_PANEL_PORT} (configpanel) доступен локально"
else
    echo "⚠ Порт ${CONFIG_PANEL_PORT} (configpanel) недоступен локально"
fi

if curl -k -s -o /dev/null -w "%{http_code}" --connect-timeout 2 http://127.0.0.1:${SUBS_PORT}/subs/ 2>/dev/null | grep -q "200\|301\|302"; then
    echo "✓ Порт ${SUBS_PORT} (subs) доступен локально"
else
    echo "⚠ Порт ${SUBS_PORT} (subs) недоступен локально"
fi

# Проверка конфигурации nginx
if nginx -t >/dev/null 2>&1; then
    echo "✓ Синтаксис конфигурации nginx корректен"
else
    echo "✗ Ошибка в конфигурации nginx"
fi

# Проверка наличия конфигурации
if [ -f "$CONF_AVAIL" ] && [ -L "$CONF_ENAB" ]; then
    echo "✓ Конфигурация nginx найдена"
else
    echo "✗ Конфигурация nginx не найдена"
fi

# Проверка SSL-сертификатов
if [ -f "${CERT_DIR}/fullchain.pem" ] && [ -f "${CERT_DIR}/privkey.pem" ]; then
    echo "✓ SSL-сертификаты найдены в ${CERT_DIR}/"
    
    # Проверка валидности сертификата
    if openssl x509 -in "${CERT_DIR}/fullchain.pem" -noout -dates >/dev/null 2>&1; then
        NOT_AFTER=$(openssl x509 -in "${CERT_DIR}/fullchain.pem" -noout -enddate | cut -d= -f2)
        echo "  Сертификат действителен до: ${NOT_AFTER}"
    fi
else
    echo "✗ SSL-сертификаты не найдены"
fi

# Проверка доступности через HTTPS
echo ""
echo "Проверка доступности через HTTPS..."

CONFIGPANEL_STATUS=$(curl -k -s -o /dev/null -w "%{http_code}" --connect-timeout 5 https://${DOMAIN}/configpanel 2>/dev/null || echo "000")
if [ "$CONFIGPANEL_STATUS" = "200" ] || [ "$CONFIGPANEL_STATUS" = "301" ] || [ "$CONFIGPANEL_STATUS" = "302" ]; then
    echo "✓ Configpanel доступен через HTTPS (HTTP ${CONFIGPANEL_STATUS})"
else
    echo "⚠ Configpanel недоступен через HTTPS (HTTP ${CONFIGPANEL_STATUS})"
fi

SUBS_STATUS=$(curl -k -s -o /dev/null -w "%{http_code}" --connect-timeout 5 https://${DOMAIN}/subs/ 2>/dev/null || echo "000")
if [ "$SUBS_STATUS" = "200" ] || [ "$SUBS_STATUS" = "301" ] || [ "$SUBS_STATUS" = "302" ]; then
    echo "✓ Subs доступен через HTTPS (HTTP ${SUBS_STATUS})"
else
    echo "⚠ Subs недоступен через HTTPS (HTTP ${SUBS_STATUS})"
fi

# Проверка редиректа HTTP → HTTPS
HTTP_REDIRECT=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 http://${DOMAIN}/configpanel 2>/dev/null || echo "000")
if [ "$HTTP_REDIRECT" = "301" ]; then
    echo "✓ Редирект HTTP → HTTPS работает (HTTP 301)"
else
    echo "⚠ Редирект HTTP → HTTPS не работает (HTTP ${HTTP_REDIRECT})"
fi

# Проверка логов nginx
if [ -f /var/log/nginx/error.log ]; then
    ERROR_COUNT=$(tail -n 10 /var/log/nginx/error.log | grep -i error | wc -l)
    if [ "$ERROR_COUNT" -gt 0 ]; then
        echo "⚠ Обнаружены ошибки в логах nginx (последние 10 строк)"
        echo "   Проверьте: tail -n 10 /var/log/nginx/error.log"
    else
        echo "✓ Ошибок в логах nginx не обнаружено"
    fi
fi

echo ""

# Вывод информации
echo "=========================================="
echo "✓ Установка SSL-сертификатов завершена!"
echo "=========================================="
echo ""
echo "Доступ к сервисам:"
echo "  - Configpanel: https://${DOMAIN}/configpanel"
echo "  - Subs: https://${DOMAIN}/subs/"
echo ""
echo "Автоматическое обновление сертификатов:"
echo "  - Deploy-hook настроен: ${DEPLOY_HOOK}"
echo "  - Certbot будет автоматически обновлять сертификаты через встроенный timer"
echo "  - Сертификаты будут автоматически копироваться в ${CERT_DIR}/"
echo ""
echo "Для ручной проверки запустите:"
echo "  ./deploy/nginx/verify-3xui-setup.sh ${DOMAIN}"
echo ""

