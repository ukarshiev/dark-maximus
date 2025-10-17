#!/usr/bin/env bash
# SSL Setup Script for Dark Maximus
# Usage: curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/ssl-install.sh | sudo bash -s -- domain.com

set -o errexit
set -o pipefail
set -o nounset

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Обработка ошибок
handle_error() {
    echo -e "\n${RED}Ошибка на строке $1. Настройка SSL прервана.${NC}"
    exit 1
}
trap 'handle_error $LINENO' ERR

# Функции для ввода
read_input() {
    if [ -t 0 ]; then
        read -p "$1" "$2" < /dev/tty
    else
        read -p "$1" "$2" || true
    fi
}

# Выбираем docker compose v1/v2
if docker compose version >/dev/null 2>&1; then
    DC=("docker" "compose")
else
    DC=("docker-compose")
fi

echo -e "${GREEN}===============================================${NC}"
echo -e "${GREEN}      🔒 Dark Maximus - Настройка SSL        ${NC}"
echo -e "${GREEN}===============================================${NC}"

# Проверяем права root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Запустите скрипт с правами root: sudo bash <(curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/ssl-install.sh) domain.com${NC}"
    exit 1
fi

# Проверяем, что мы в папке проекта, если нет - переходим в /opt/dark-maximus
if [ ! -f "docker-compose.yml" ]; then
    if [ -f "/opt/dark-maximus/docker-compose.yml" ]; then
        echo -e "${YELLOW}⚠️  Переходим в папку проекта /opt/dark-maximus${NC}"
        cd /opt/dark-maximus
        PROJECT_DIR="/opt/dark-maximus"
    else
        echo -e "${RED}❌ Файл docker-compose.yml не найден!${NC}"
        echo -e "${YELLOW}Убедитесь, что вы находитесь в папке проекта Dark Maximus.${NC}"
        echo -e "${YELLOW}Если проект не установлен, сначала запустите:${NC}"
        echo -e "${CYAN}curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install.sh | sudo bash -s -- domain.com${NC}"
        exit 1
    fi
else
    PROJECT_DIR="$(pwd)"
fi

echo -e "${GREEN}✔ Рабочая директория: ${PROJECT_DIR}${NC}"

# Проверяем, что nginx установлен
if ! command -v nginx >/dev/null 2>&1; then
    echo -e "${RED}❌ Nginx не установлен!${NC}"
    echo -e "${YELLOW}Убедитесь, что основная установка была завершена успешно.${NC}"
    echo -e "${YELLOW}Запустите сначала:${NC}"
    echo -e "${CYAN}curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install.sh | sudo bash -s -- domain.com${NC}"
    exit 1
fi

# Получаем домен из аргументов командной строки или извлекаем из nginx конфигурации
if [ -n "$1" ]; then
    MAIN_DOMAIN="$1"
    echo -e "${GREEN}✔ Домен получен из аргументов: ${MAIN_DOMAIN}${NC}"
else
    # Извлекаем домены из nginx конфигурации (если она существует)
    if [ -f "/etc/nginx/sites-available/dark-maximus" ]; then
        MAIN_DOMAIN=$(grep -o 'server_name [^;]*' "/etc/nginx/sites-available/dark-maximus" | grep -v "default_server" | head -1 | awk '{print $2}')
    fi
    
    if [ -z "$MAIN_DOMAIN" ]; then
        echo -e "${RED}❌ Домен не указан!${NC}"
        echo -e "${YELLOW}Передайте домен как аргумент:${NC}"
        echo -e "${CYAN}curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/ssl-install.sh | sudo bash -s -- example.com${NC}"
        exit 1
    fi
fi

# Генерируем поддомены
PANEL_DOMAIN="panel.${MAIN_DOMAIN}"
DOCS_DOMAIN="docs.${MAIN_DOMAIN}"
HELP_DOMAIN="help.${MAIN_DOMAIN}"

echo -e "${GREEN}✔ Домены настроены:${NC}"
echo -e "   - Панель: ${MAIN_DOMAIN}"
echo -e "   - Панель (поддомен): ${PANEL_DOMAIN}"
echo -e "   - Документация: ${DOCS_DOMAIN}"
echo -e "   - Админ-документация: ${HELP_DOMAIN}"

# Устанавливаем email для Let's Encrypt
EMAIL="admin@${MAIN_DOMAIN}"
echo -e "${YELLOW}Используем email по умолчанию: ${EMAIL}${NC}"

echo -e "\n${CYAN}Шаг 0: Проверка и создание HTTP nginx конфигурации...${NC}"

# Проверяем, есть ли HTTP конфигурация с upstream серверами
if ! grep -q "upstream bot_backend" /etc/nginx/sites-available/dark-maximus 2>/dev/null; then
    echo -e "${YELLOW}Создание HTTP nginx конфигурации с upstream серверами...${NC}"
    
    # Создаем HTTP конфигурацию nginx с upstream серверами
    cat > /etc/nginx/sites-available/dark-maximus << 'EOF'
# Upstream серверы для Docker контейнеров (localhost)
upstream bot_backend {
    server 127.0.0.1:1488;
    keepalive 32;
}

upstream docs_backend {
    server 127.0.0.1:3001;
    keepalive 32;
}

upstream codex_docs_backend {
    server 127.0.0.1:3002;
    keepalive 32;
}

# Основной сервер (панель)
server {
    listen 80;
    server_name ${MAIN_DOMAIN};
    
    # Ограничение размера загружаемых файлов
    client_max_body_size 20m;
    
    # Проксирование на bot сервис
    location / {
        proxy_pass http://bot_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # Таймауты
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        
        # Буферизация
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }
    
    # Health check
    location /health {
        proxy_pass http://bot_backend/health;
        access_log off;
    }
}

# Сервер panel поддомена
server {
    listen 80;
    server_name ${PANEL_DOMAIN};
    
    # Ограничение размера загружаемых файлов
    client_max_body_size 20m;
    
    # Проксирование на bot сервис
    location / {
        proxy_pass http://bot_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # Таймауты
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        
        # Буферизация
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }
    
    # Health check
    location /health {
        proxy_pass http://bot_backend/health;
        access_log off;
    }
}

# Сервер документации
server {
    listen 80;
    server_name ${DOCS_DOMAIN};
    
    # Ограничение размера загружаемых файлов
    client_max_body_size 20m;
    
    # Проксирование на docs сервис
    location / {
        proxy_pass http://docs_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # Таймауты
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
    
    # Health check
    location /health {
        proxy_pass http://docs_backend/health;
        access_log off;
    }
}

# Сервер админской документации
server {
    listen 80;
    server_name ${HELP_DOMAIN};
    
    # Ограничение размера загружаемых файлов
    client_max_body_size 20m;
    
    # Проксирование на codex-docs сервис
    location / {
        proxy_pass http://codex_docs_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # WebSocket поддержка с оптимизацией
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 60m;
        proxy_buffering off;
        
        # Таймауты
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
    }
    
    # Health check
    location /health {
        proxy_pass http://codex_docs_backend/;
        access_log off;
    }
}

# Блокировка неопознанных доменов
server {
    listen 80 default_server;
    server_name _;
    return 444;
}
EOF
    
    echo -e "${GREEN}✔ HTTP nginx конфигурация создана${NC}"
else
    echo -e "${GREEN}✔ HTTP nginx конфигурация уже существует${NC}"
fi

# Проверяем, что контейнеры запущены
echo -e "${YELLOW}Проверка запущенных контейнеров...${NC}"
if ! nc -z 127.0.0.1 1488 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Контейнеры не запущены. Запускаем...${NC}"
    cd "$PROJECT_DIR"
    ${DC[@]} up -d
    
    # Ждем запуска контейнеров
    echo -e "${YELLOW}Ожидание запуска контейнеров...${NC}"
    timeout 120 bash -c 'until nc -z 127.0.0.1 1488; do sleep 2; done' || {
        echo -e "${RED}❌ Bot сервис не запустился в течение 2 минут${NC}"
        ${DC[@]} logs bot
        exit 1
    }
    
    timeout 60 bash -c 'until nc -z 127.0.0.1 3001; do sleep 2; done' || {
        echo -e "${RED}❌ Docs сервис не запустился в течение 1 минуты${NC}"
        ${DC[@]} logs docs
        exit 1
    }
    
    timeout 60 bash -c 'until nc -z 127.0.0.1 3002; do sleep 2; done' || {
        echo -e "${RED}❌ Codex-docs сервис не запустился в течение 1 минуты${NC}"
        ${DC[@]} logs codex-docs
        exit 1
    }
    
    echo -e "${GREEN}✔ Контейнеры запущены${NC}"
else
    echo -e "${GREEN}✔ Контейнеры уже запущены${NC}"
fi

echo -e "\n${CYAN}Шаг 1: Проверка DNS записей...${NC}"

# Получаем IP сервера
SERVER_IP="$(curl -s4 https://api.ipify.org || hostname -I | awk '{print $1}')"
echo -e "${YELLOW}IP вашего сервера (IPv4): $SERVER_IP${NC}"

# Функция проверки DNS
check_dns() {
    local domain="$1"
    local ips
    ips=$(dig +short A "$domain" @8.8.8.8 | sort -u)
    echo -e "  - ${domain} → ${ips:-<нет A>}"
    [ -n "$ips" ] && grep -Fxq "$SERVER_IP" <<<"$ips"
}

DNS_OK=true
for check_domain in "$MAIN_DOMAIN" "$PANEL_DOMAIN" "$DOCS_DOMAIN" "$HELP_DOMAIN"; do
    if ! check_dns "$check_domain"; then
        echo -e "${RED}❌ ОШИБКА: DNS для ${check_domain} не указывает на IP этого сервера!${NC}"
        DNS_OK=false
    fi
done

if [ "$DNS_OK" = false ]; then
    echo -e "${RED}❌ КРИТИЧЕСКАЯ ОШИБКА: DNS записи настроены неправильно!${NC}"
    echo -e "${YELLOW}Настройте A-записи для всех поддоменов на IP: ${SERVER_IP}${NC}"
    echo -e "${YELLOW}После настройки DNS запустите скрипт снова.${NC}"
    exit 1
fi

echo -e "${GREEN}✔ Все DNS записи корректны.${NC}"

echo -e "\n${CYAN}Шаг 2: Установка Certbot...${NC}"

# Настройка неинтерактивного режима для APT
export DEBIAN_FRONTEND=noninteractive

# Устанавливаем Certbot
apt -yq update
apt -yq install certbot python3-certbot-nginx

echo -e "${GREEN}✔ Certbot установлен${NC}"

echo -e "\n${CYAN}Шаг 3: Создание SSL-конфигурации...${NC}"

# Создаем директории для SSL
mkdir -p /etc/letsencrypt/live
mkdir -p /etc/letsencrypt/archive

# Создаем современную конфигурацию SSL для nginx
cat > /etc/nginx/snippets/ssl-params.conf << 'EOF'
# Современная конфигурация SSL с лучшими практиками безопасности
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;

# SSL сессии для производительности
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;
ssl_session_tickets off;

# OCSP stapling для безопасности
ssl_stapling on;
ssl_stapling_verify on;
resolver 8.8.8.8 8.8.4.4 valid=300s;
resolver_timeout 5s;

# Современные заголовки безопасности
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
add_header X-Frame-Options DENY always;
add_header X-Content-Type-Options nosniff always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' wss: https:; frame-ancestors 'none';" always;

# Дополнительные заголовки безопасности
add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), interest-cohort=()" always;
add_header X-Permitted-Cross-Domain-Policies "none" always;
add_header X-Download-Options "noopen" always;
add_header X-DNS-Prefetch-Control "off" always;
EOF

echo -e "${GREEN}✔ SSL-конфигурация создана${NC}"

echo -e "\n${CYAN}Шаг 4: Остановка nginx для получения сертификатов...${NC}"

# Останавливаем nginx
systemctl stop nginx

echo -e "\n${CYAN}Шаг 5: Получение SSL-сертификатов...${NC}"

# Получаем сертификаты для всех доменов
echo -e "${YELLOW}Получение сертификата для ${MAIN_DOMAIN}...${NC}"
certbot certonly --standalone \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --non-interactive \
    -d "$MAIN_DOMAIN"

echo -e "${YELLOW}Получение сертификата для ${PANEL_DOMAIN}...${NC}"
certbot certonly --standalone \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --non-interactive \
    -d "$PANEL_DOMAIN"

echo -e "${YELLOW}Получение сертификата для ${DOCS_DOMAIN}...${NC}"
certbot certonly --standalone \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --non-interactive \
    -d "$DOCS_DOMAIN"

echo -e "${YELLOW}Получение сертификата для ${HELP_DOMAIN}...${NC}"
certbot certonly --standalone \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --non-interactive \
    -d "$HELP_DOMAIN"

echo -e "${GREEN}✔ Все SSL-сертификаты получены${NC}"

echo -e "\n${CYAN}Шаг 6: Создание HTTPS конфигурации nginx...${NC}"

# Создаем HTTPS конфигурацию nginx с улучшенными настройками безопасности
cat > /etc/nginx/sites-available/dark-maximus-ssl << 'EOF'
# Upstream серверы для Docker контейнеров (localhost)
upstream bot_backend {
    server 127.0.0.1:1488;
    keepalive 32;
}

upstream docs_backend {
    server 127.0.0.1:3001;
    keepalive 32;
}

upstream codex_docs_backend {
    server 127.0.0.1:3002;
    keepalive 32;
}

# HTTP редирект на HTTPS для основного домена
server {
    listen 80;
    server_name ${MAIN_DOMAIN};
    return 301 https://$server_name$request_uri;
}

# HTTPS сервер для основного домена (панель)
server {
    listen 443 ssl http2;
    server_name ${MAIN_DOMAIN};
    
    # SSL сертификаты
    ssl_certificate /etc/letsencrypt/live/${MAIN_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${MAIN_DOMAIN}/privkey.pem;
    include /etc/nginx/snippets/ssl-params.conf;
    
    # Ограничение размера загружаемых файлов
    client_max_body_size 20m;
    
    # Проксирование на bot сервис
    location / {
        proxy_pass http://bot_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # Таймауты
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        
        # Буферизация
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }
    
    # Health check
    location /health {
        proxy_pass http://bot_backend/health;
        access_log off;
    }
}

# HTTP редирект на HTTPS для panel поддомена
server {
    listen 80;
    server_name ${PANEL_DOMAIN};
    return 301 https://$server_name$request_uri;
}

# HTTPS сервер для panel поддомена
server {
    listen 443 ssl http2;
    server_name ${PANEL_DOMAIN};
    
    # SSL сертификаты
    ssl_certificate /etc/letsencrypt/live/${PANEL_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${PANEL_DOMAIN}/privkey.pem;
    include /etc/nginx/snippets/ssl-params.conf;
    
    # Ограничение размера загружаемых файлов
    client_max_body_size 20m;
    
    # Проксирование на bot сервис
    location / {
        proxy_pass http://bot_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # Таймауты
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        
        # Буферизация
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }
    
    # Health check
    location /health {
        proxy_pass http://bot_backend/health;
        access_log off;
    }
}

# HTTP редирект на HTTPS для документации
server {
    listen 80;
    server_name ${DOCS_DOMAIN};
    return 301 https://$server_name$request_uri;
}

# HTTPS сервер для документации
server {
    listen 443 ssl http2;
    server_name ${DOCS_DOMAIN};
    
    # SSL сертификаты
    ssl_certificate /etc/letsencrypt/live/${DOCS_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOCS_DOMAIN}/privkey.pem;
    include /etc/nginx/snippets/ssl-params.conf;
    
    # Ограничение размера загружаемых файлов
    client_max_body_size 20m;
    
    # Проксирование на docs сервис
    location / {
        proxy_pass http://docs_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # Таймауты
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
    
    # Health check
    location /health {
        proxy_pass http://docs_backend/health;
        access_log off;
    }
}

# HTTP редирект на HTTPS для админской документации
server {
    listen 80;
    server_name ${HELP_DOMAIN};
    return 301 https://$server_name$request_uri;
}

# HTTPS сервер для админской документации
server {
    listen 443 ssl http2;
    server_name ${HELP_DOMAIN};
    
    # SSL сертификаты
    ssl_certificate /etc/letsencrypt/live/${HELP_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${HELP_DOMAIN}/privkey.pem;
    include /etc/nginx/snippets/ssl-params.conf;
    
    # Ограничение размера загружаемых файлов
    client_max_body_size 20m;
    
    # Проксирование на codex-docs сервис
    location / {
        proxy_pass http://codex_docs_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # WebSocket поддержка с оптимизацией
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 60m;
        proxy_buffering off;
        
        # Таймауты
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
    }
    
    # Health check
    location /health {
        proxy_pass http://codex_docs_backend/;
        access_log off;
    }
}

# Блокировка неопознанных доменов
server {
    listen 80 default_server;
    server_name _;
    return 444;
}

server {
    listen 443 ssl default_server;
    server_name _;
    
    # Заглушка SSL сертификат
    ssl_certificate /etc/letsencrypt/live/${MAIN_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${MAIN_DOMAIN}/privkey.pem;
    include /etc/nginx/snippets/ssl-params.conf;
    
    return 444;
}
EOF

# Активируем HTTPS конфигурацию
ln -sf /etc/nginx/sites-available/dark-maximus-ssl /etc/nginx/sites-enabled/dark-maximus

# Проверяем конфигурацию nginx
nginx -t

echo -e "${GREEN}✔ HTTPS конфигурация nginx создана и проверена${NC}"

echo -e "\n${CYAN}Шаг 7: Запуск nginx с SSL...${NC}"

# Запускаем nginx
systemctl start nginx
systemctl enable nginx

# Проверяем статус nginx
systemctl status nginx --no-pager -l

echo -e "\n${CYAN}Шаг 8: Настройка автообновления сертификатов...${NC}"

# Создаем скрипт для обновления сертификатов
cat > /usr/local/bin/renew-ssl.sh << 'EOF'
#!/bin/bash
# Скрипт обновления SSL сертификатов

echo "Проверка обновления SSL сертификатов..."
certbot renew --quiet --post-hook "systemctl reload nginx"

if [ $? -eq 0 ]; then
    echo "SSL сертификаты обновлены успешно"
else
    echo "Ошибка при обновлении SSL сертификатов"
    exit 1
fi
EOF

chmod +x /usr/local/bin/renew-ssl.sh

# Настраиваем cron для автообновления каждые 2 месяца
TEMP_CRON=$(mktemp)
# Создаем новый crontab или добавляем к существующему
(crontab -l 2>/dev/null || echo "") > "$TEMP_CRON"
echo "0 3 1 */2 * /usr/local/bin/renew-ssl.sh >> /var/log/ssl-renewal.log 2>&1" >> "$TEMP_CRON"
crontab "$TEMP_CRON" 2>/dev/null || {
    echo "0 3 1 */2 * /usr/local/bin/renew-ssl.sh >> /var/log/ssl-renewal.log 2>&1" | crontab -
}
rm "$TEMP_CRON"

echo -e "${GREEN}✔ Автообновление сертификатов настроено (каждые 2 месяца)${NC}"

echo -e "\n${CYAN}Шаг 9: Проверка SSL сертификатов...${NC}"

# Проверяем сертификаты
echo -e "${YELLOW}Проверка сертификатов...${NC}"
certbot certificates

echo -e "\n${CYAN}Шаг 10: Финальная проверка доступности...${NC}"

# Ждем полного запуска
sleep 5

# Проверяем доступность HTTPS сервисов
echo -e "${YELLOW}Проверка HTTPS доступности...${NC}"

# Проверяем основной домен
if curl -f -s -k https://${MAIN_DOMAIN}/health >/dev/null 2>&1; then
    echo -e "${GREEN}✅ HTTPS панель доступна: https://${MAIN_DOMAIN}${NC}"
else
    echo -e "${RED}❌ HTTPS панель недоступна${NC}"
fi

# Проверяем panel поддомен
if curl -f -s -k https://${PANEL_DOMAIN}/health >/dev/null 2>&1; then
    echo -e "${GREEN}✅ HTTPS панель (поддомен) доступна: https://${PANEL_DOMAIN}${NC}"
else
    echo -e "${RED}❌ HTTPS панель (поддомен) недоступна${NC}"
fi

# Проверяем документацию
if curl -f -s -k https://${DOCS_DOMAIN}/health >/dev/null 2>&1; then
    echo -e "${GREEN}✅ HTTPS документация доступна: https://${DOCS_DOMAIN}${NC}"
else
    echo -e "${RED}❌ HTTPS документация недоступна${NC}"
fi

# Проверяем админскую документацию
if curl -f -s -k https://${HELP_DOMAIN}/ >/dev/null 2>&1; then
    echo -e "${GREEN}✅ HTTPS админ-документация доступна: https://${HELP_DOMAIN}${NC}"
else
    echo -e "${RED}❌ HTTPS админ-документация недоступна${NC}"
fi

echo -e "\n${GREEN}===============================================${NC}"
echo -e "${GREEN}      🎉 Настройка SSL успешно завершена! 🎉  ${NC}"
echo -e "${GREEN}===============================================${NC}"

echo -e "\n${BLUE}📱 Доступные сервисы (HTTPS):${NC}"
echo -e "1. Основной бот и админ-панель:"
echo -e "   - ${GREEN}https://${MAIN_DOMAIN}/login${NC}"

# Читаем пароль админа из файла
if [ -f ".admin_pass" ]; then
    ADMIN_PASSWORD=$(cat .admin_pass)
    echo -e "   - Логин: ${YELLOW}admin${NC}"
    echo -e "   - Пароль: ${YELLOW}${ADMIN_PASSWORD}${NC}"
else
    echo -e "   - Логин: ${YELLOW}admin${NC}"
    echo -e "   - Пароль: ${YELLOW}admin${NC} (по умолчанию)"
fi

echo -e "\n2. Панель (поддомен):"
echo -e "   - ${GREEN}https://${PANEL_DOMAIN}/login${NC}"

echo -e "\n3. Пользовательская документация:"
echo -e "   - ${GREEN}https://${DOCS_DOMAIN}${NC}"

echo -e "\n4. Админская документация (Codex.docs):"
echo -e "   - ${GREEN}https://${HELP_DOMAIN}${NC}"

echo -e "\n${BLUE}🔧 Полезные команды:${NC}"
echo -e "- Проверить сертификаты: ${YELLOW}certbot certificates${NC}"
echo -e "- Тест обновления: ${YELLOW}certbot renew --dry-run${NC}"
echo -e "- Принудительное обновление: ${YELLOW}certbot renew --force-renewal${NC}"
echo -e "- Проверить nginx: ${YELLOW}nginx -t${NC}"
echo -e "- Перезапустить nginx: ${YELLOW}systemctl restart nginx${NC}"

echo -e "\n${BLUE}📋 Мониторинг:${NC}"
echo -e "- Логи обновления SSL: ${YELLOW}/var/log/ssl-renewal.log${NC}"
echo -e "- Логи nginx: ${YELLOW}/var/log/nginx/error.log${NC}"
echo -e "- Статус сервисов: ${YELLOW}${DC[@]} ps${NC}"

echo -e "\n${BLUE}🔒 Безопасность:${NC}"
echo -e "- Современные SSL настройки с TLS 1.2/1.3"
echo -e "- Заголовки безопасности (HSTS, CSP, X-Frame-Options)"
echo -e "- Отладочные порты доступны только с localhost"
echo -e "- Автообновление сертификатов каждые 2 месяца"

echo -e "\n${GREEN}SSL настройка завершена! Все сервисы работают по HTTPS.${NC}"
