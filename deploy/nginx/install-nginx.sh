#!/usr/bin/env bash

set -euo pipefail

# Параметры
DOMAIN="${1:?Ошибка: укажите домен как первый аргумент}"
CONFIG_PANEL_PORT="${2:-8443}"
SUBS_PORT="${3:-2096}"

CONF_AVAIL="/etc/nginx/sites-available/subs.conf"
CONF_ENAB="/etc/nginx/sites-enabled/subs.conf"

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    echo "Ошибка: скрипт должен запускаться от root"
    exit 1
fi

echo "=========================================="
echo "Установка nginx для 3x-ui"
echo "Домен: ${DOMAIN}"
echo "Порт configpanel: ${CONFIG_PANEL_PORT}"
echo "Порт subs: ${SUBS_PORT}"
echo "=========================================="
echo ""

# 1. Проверка и подготовка
echo "[1/5] Подготовка сервера..."

# Проверка доступности портов 3x-ui
echo "Проверка доступности портов 3x-ui..."
if ! curl -k -s -o /dev/null -w "%{http_code}" --connect-timeout 2 http://127.0.0.1:${CONFIG_PANEL_PORT}/configpanel 2>/dev/null | grep -q "200\|301\|302"; then
    echo "⚠ Предупреждение: порт ${CONFIG_PANEL_PORT} (configpanel) недоступен локально"
    echo "   Убедитесь, что 3x-ui запущен и слушает на этом порту"
else
    echo "✓ Порт ${CONFIG_PANEL_PORT} (configpanel) доступен"
fi

if ! curl -k -s -o /dev/null -w "%{http_code}" --connect-timeout 2 http://127.0.0.1:${SUBS_PORT}/subs/ 2>/dev/null | grep -q "200\|301\|302"; then
    echo "⚠ Предупреждение: порт ${SUBS_PORT} (subs) недоступен локально"
    echo "   Убедитесь, что 3x-ui запущен и слушает на этом порту"
else
    echo "✓ Порт ${SUBS_PORT} (subs) доступен"
fi

# Проверка существующей конфигурации
if [ -f "$CONF_AVAIL" ]; then
    echo "⚠ Предупреждение: конфигурация nginx для домена уже существует"
    echo "   Существующая конфигурация будет перезаписана"
fi

# Подготовка сервера
apt update
apt upgrade -y
apt dist-upgrade -y
apt autoremove -y
apt autoclean

# Установка зависимостей
apt install -y curl wget nginx

echo "✓ Подготовка завершена"
echo ""

# 2. Проверка DNS
echo "[2/5] Проверка DNS..."

SERVER_IP=$(curl -s ifconfig.me || curl -s ipinfo.io/ip || echo "")
DOMAIN_IP=$(dig +short ${DOMAIN} | tail -n1 || echo "")

if [ -z "$SERVER_IP" ] || [ -z "$DOMAIN_IP" ]; then
    echo "⚠ Предупреждение: не удалось проверить DNS"
    echo "   Убедитесь, что домен ${DOMAIN} указывает на IP этого сервера"
else
    if [ "$SERVER_IP" = "$DOMAIN_IP" ]; then
        echo "✓ DNS настроен правильно: ${DOMAIN} → ${DOMAIN_IP}"
    else
        echo "⚠ Предупреждение: DNS может быть настроен неправильно"
        echo "   IP сервера: ${SERVER_IP}"
        echo "   IP домена: ${DOMAIN_IP}"
        echo "   Убедитесь, что домен указывает на правильный IP"
    fi
fi

echo ""

# 3. Установка и настройка nginx (HTTP временно)
echo "[3/5] Установка и настройка nginx (HTTP)..."

install -d /etc/nginx/sites-available

# Создание HTTP конфигурации (без SSL)
cat > "$CONF_AVAIL" <<NGINX
upstream subs_backend { 
  server 127.0.0.1:${SUBS_PORT}; 
}

upstream configpanel_backend { 
  server 127.0.0.1:${CONFIG_PANEL_PORT}; 
}

server {
  listen 80;
  server_name ${DOMAIN};

  proxy_http_version 1.1;
  proxy_set_header Host                \$host;
  proxy_set_header X-Forwarded-Host    \$host;
  proxy_set_header X-Forwarded-Server  \$host;
  proxy_set_header X-Real-IP           \$remote_addr;
  proxy_set_header X-Forwarded-For     \$proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto  http;
  proxy_set_header X-Forwarded-Port    80;

  proxy_ssl_server_name on;
  proxy_ssl_name \$host;

  # Подписки - используем порт для subs
  location = /subs { 
    return 301 /subs/; 
  }

  location /subs/ {
    proxy_pass http://subs_backend/;
    proxy_redirect ~^https?://[^/]+:${SUBS_PORT}(/.*)\$ http://\$host\$1;
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
NGINX

# Создание символической ссылки
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

echo "✓ Nginx настроен и запущен"
echo ""

# 4. Настройка UFW (но не включение)
echo "[4/5] Настройка UFW..."

if command -v ufw >/dev/null 2>&1; then
    ufw allow 443/tcp || true
    ufw deny ${CONFIG_PANEL_PORT}/tcp || true
    ufw deny ${SUBS_PORT}/tcp || true
    echo "✓ Правила UFW настроены (но UFW не включен)"
    echo "   Для включения UFW выполните: ufw enable"
else
    echo "⚠ UFW не установлен, пропускаем настройку"
fi

echo ""

# 5. Вывод информации
echo "[5/5] Завершение установки..."
echo ""
echo "=========================================="
echo "✓ Установка nginx завершена успешно!"
echo "=========================================="
echo ""
echo "Следующие шаги:"
echo ""
echo "1. Проверьте HTTP версию:"
echo "   curl -I http://${DOMAIN}/configpanel"
echo "   curl -I http://${DOMAIN}/subs/"
echo ""
echo "2. Запустите скрипт для получения SSL-сертификатов:"
echo "   curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/deploy/nginx/install-ssl-certbot.sh | sudo bash -s -- ${DOMAIN}"
echo ""
echo "Или локально:"
echo "   ./deploy/nginx/install-ssl-certbot.sh ${DOMAIN}"
echo ""

