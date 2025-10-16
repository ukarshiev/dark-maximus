#!/usr/bin/env bash
set -o errexit
set -o pipefail
set -o nounset

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
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

echo -e "${GREEN}--- Настройка SSL для dark-maximus ---${NC}"

# Проверяем, что мы в папке проекта
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ Файл docker-compose.yml не найден! Убедитесь, что вы находитесь в папке проекта.${NC}"
    exit 1
fi

# Извлекаем домены из nginx.conf
MAIN_DOMAIN=$(grep -o 'server_name [^;]*' "nginx/nginx.conf" | grep -v "default_server" | head -1 | awk '{print $2}')
DOCS_DOMAIN=$(grep -o 'server_name [^;]*' "nginx/nginx.conf" | grep -v "default_server" | sed -n '2p' | awk '{print $2}')
HELP_DOMAIN=$(grep -o 'server_name [^;]*' "nginx/nginx.conf" | grep -v "default_server" | sed -n '3p' | awk '{print $2}')

if [ -z "$MAIN_DOMAIN" ] || [ -z "$DOCS_DOMAIN" ] || [ -z "$HELP_DOMAIN" ]; then
    echo -e "${RED}❌ Не удалось извлечь домены из nginx.conf!${NC}"
    echo -e "${YELLOW}Убедитесь, что install.sh был запущен успешно.${NC}"
    exit 1
fi

echo -e "${GREEN}✔ Домены извлечены из конфигурации:${NC}"
echo -e "   - Панель: ${MAIN_DOMAIN}"
echo -e "   - Документация: ${DOCS_DOMAIN}"
echo -e "   - Админ-документация: ${HELP_DOMAIN}"

# Запрашиваем email для Let's Encrypt
read_input "Введите ваш email (для регистрации SSL-сертификатов Let's Encrypt): " EMAIL
if [ -z "$EMAIL" ]; then
    EMAIL="admin@${MAIN_DOMAIN}"
    echo -e "${YELLOW}Используем email по умолчанию: ${EMAIL}${NC}"
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
for check_domain in "$MAIN_DOMAIN" "$DOCS_DOMAIN" "$HELP_DOMAIN"; do
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

echo -e "\n${CYAN}Шаг 2: Создание SSL-конфигурации...${NC}"

# Создаем SSL-конфигурацию
sudo mkdir -p /etc/letsencrypt

if [ ! -f "/etc/letsencrypt/options-ssl-nginx.conf" ]; then
    sudo bash -c "cat > /etc/letsencrypt/options-ssl-nginx.conf" << 'EOF'
# This file contains important security parameters. If you modify this file
# manually, Certbot will be unable to automatically provide future security
# updates. Instead, Certbot will print a message to the log when it encounters
# a configuration that would be updated.

ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-SHA256:ECDHE-RSA-AES256-SHA384;
ssl_prefer_server_ciphers off;
EOF
    echo -e "${GREEN}✔ options-ssl-nginx.conf создан.${NC}"
else
    echo -e "${GREEN}✔ options-ssl-nginx.conf уже существует.${NC}"
fi

if [ ! -f "/etc/letsencrypt/ssl-dhparams.pem" ]; then
    echo -e "${YELLOW}Генерируем DH параметры (это может занять несколько минут)...${NC}"
    sudo openssl dhparam -out /etc/letsencrypt/ssl-dhparams.pem 2048
    echo -e "${GREEN}✔ ssl-dhparams.pem создан.${NC}"
else
    echo -e "${GREEN}✔ ssl-dhparams.pem уже существует.${NC}"
fi

echo -e "\n${CYAN}Шаг 3: Остановка nginx-proxy для выпуска сертификатов...${NC}"

# Останавливаем nginx-proxy
sudo "${DC[@]}" stop nginx-proxy

# Ждем освобождения порта 80
echo -e "${YELLOW}Ждем освобождения порта 80...${NC}"
for i in {1..20}; do
    ss -ltn "( sport = :80 )" | grep -q ":80" || break
    sleep 1
done
echo -e "${GREEN}✔ Порт 80 свободен.${NC}"

echo -e "\n${CYAN}Шаг 4: Выпуск Let's Encrypt сертификатов...${NC}"

# Выпускаем сертификаты для каждого домена
for domain in "$MAIN_DOMAIN" "$DOCS_DOMAIN" "$HELP_DOMAIN"; do
    echo -e "${YELLOW}Выпускаем Let's Encrypt сертификат для ${domain}...${NC}"
    sudo certbot certonly --standalone \
        --preferred-challenges http \
        -d "$domain" \
        --email "$EMAIL" --agree-tos --non-interactive
done

echo -e "${GREEN}✔ Let's Encrypt сертификаты выпущены.${NC}"

echo -e "\n${CYAN}Шаг 5: Создание nginx конфигурации с SSL...${NC}"

# Создаем nginx конфигурацию с SSL
cat > nginx/nginx.conf << EOF
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format main '\$remote_addr - \$remote_user [\$time_local] "\$request" '
                    '\$status \$body_bytes_sent "\$http_referer" '
                    '"\$http_user_agent" "\$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;
    error_log /var/log/nginx/error.log;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;

    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml;

    upstream docs_backend {
        server docs:80;
    }

    upstream codex_docs_backend {
        server codex-docs:3000;
    }

    upstream bot_backend {
        server bot:1488;
    }

    # Конфигурация для $DOCS_DOMAIN
    server {
        listen 80;
        server_name $DOCS_DOMAIN;
        return 301 https://\$server_name\$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name $DOCS_DOMAIN;

        ssl_certificate /etc/letsencrypt/live/$DOCS_DOMAIN/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/$DOCS_DOMAIN/privkey.pem;
        ssl_trusted_certificate /etc/letsencrypt/live/$DOCS_DOMAIN/chain.pem;

        include /etc/letsencrypt/options-ssl-nginx.conf;
        ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

        location / {
            proxy_pass http://docs_backend;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;

            proxy_connect_timeout 30s;
            proxy_send_timeout 30s;
            proxy_read_timeout 30s;
        }

        location /health {
            proxy_pass http://docs_backend/health;
            access_log off;
        }
    }

    # Конфигурация для $HELP_DOMAIN
    server {
        listen 80;
        server_name $HELP_DOMAIN;
        return 301 https://\$server_name\$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name $HELP_DOMAIN;

        ssl_certificate /etc/letsencrypt/live/$HELP_DOMAIN/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/$HELP_DOMAIN/privkey.pem;
        ssl_trusted_certificate /etc/letsencrypt/live/$HELP_DOMAIN/chain.pem;

        include /etc/letsencrypt/options-ssl-nginx.conf;
        ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

        location / {
            proxy_pass http://codex_docs_backend;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;

            proxy_connect_timeout 30s;
            proxy_send_timeout 30s;
            proxy_read_timeout 30s;
        }

        location /health {
            proxy_pass http://codex_docs_backend/;
            access_log off;
        }
    }

    # Конфигурация для $MAIN_DOMAIN
    server {
        listen 80;
        server_name $MAIN_DOMAIN;
        return 301 https://\$server_name\$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name $MAIN_DOMAIN;

        ssl_certificate /etc/letsencrypt/live/$MAIN_DOMAIN/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/$MAIN_DOMAIN/privkey.pem;
        ssl_trusted_certificate /etc/letsencrypt/live/$MAIN_DOMAIN/chain.pem;

        include /etc/letsencrypt/options-ssl-nginx.conf;
        ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

        location / {
            proxy_pass http://bot_backend;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;

            proxy_connect_timeout 30s;
            proxy_send_timeout 30s;
            proxy_read_timeout 30s;
        }
    }

    # Конфигурация по умолчанию для неопознанных доменов
    server {
        listen 80 default_server;
        server_name _;
        return 444;
    }

    server {
        listen 443 ssl default_server;
        server_name _;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;

        return 444;
    }
}
EOF

echo -e "${GREEN}✔ nginx конфигурация с SSL создана.${NC}"

echo -e "\n${CYAN}Шаг 6: Обновление docker-compose.yml для SSL...${NC}"

# Обновляем docker-compose.yml для монтирования Let's Encrypt сертификатов
sed -i 's|- ./nginx/ssl:/etc/nginx/ssl:ro|- ./nginx/ssl:/etc/nginx/ssl:ro\n      - /etc/letsencrypt/live:/etc/letsencrypt/live:ro|g' docker-compose.yml

echo -e "${GREEN}✔ docker-compose.yml обновлен для SSL.${NC}"

echo -e "\n${CYAN}Шаг 7: Перезапуск контейнеров с SSL...${NC}"

# Перезапускаем контейнеры
sudo "${DC[@]}" up -d

# Проверяем статус nginx-proxy
echo -e "${YELLOW}Проверяем статус nginx-proxy...${NC}"
sleep 5

if sudo "${DC[@]}" ps | grep -q "nginx-proxy.*Up"; then
    echo -e "${GREEN}✔ nginx-proxy запущен и работает с SSL.${NC}"
else
    echo -e "${RED}❌ Ошибка запуска nginx-proxy!${NC}"
    echo -e "${YELLOW}Логи nginx-proxy:${NC}"
    sudo "${DC[@]}" logs nginx-proxy
    exit 1
fi

echo -e "\n${CYAN}Шаг 8: Настройка автообновления сертификатов...${NC}"

# Создаем скрипт для автообновления
PROJECT_ABS_DIR="$(pwd -P)"
echo '#!/usr/bin/env bash' | sudo tee /usr/local/bin/dc >/dev/null
echo 'exec '"${DC[*]}"' "$@"' | sudo tee -a /usr/local/bin/dc >/dev/null
sudo chmod +x /usr/local/bin/dc

# Создаем cron задачу для автообновления
POST_HOOK='
name=$(docker ps --filter "name=nginx-proxy" --format "{{.Names}}" | head -1);
if [ -n "$name" ]; then docker exec "$name" sh -c "nginx -t && nginx -s reload" || docker restart "$name"; fi
'

sudo bash -c "cat > /etc/cron.d/certbot-renew" << EOF
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
30 2 * * * root /usr/bin/certbot renew --quiet \\
  --pre-hook "/usr/local/bin/dc -f ${PROJECT_ABS_DIR}/docker-compose.yml stop nginx-proxy" \\
  --post-hook 'eval '"$(printf %q "$POST_HOOK")"
EOF

sudo chmod 644 /etc/cron.d/certbot-renew
sudo systemctl reload cron || sudo service cron reload

echo -e "${GREEN}✔ Автообновление сертификатов настроено.${NC}"

echo -e "\n\n${GREEN}==============================================${NC}"
echo -e "${GREEN}      🎉 Настройка SSL успешно завершена! 🎉      ${NC}"
echo -e "${GREEN}==============================================${NC}"

echo -e "\n${CYAN}📱 Доступные сервисы (HTTPS):${NC}"

echo -e "\n${YELLOW}1. Основной бот и админ-панель:${NC}"
echo -e "   - ${GREEN}https://${MAIN_DOMAIN}/login${NC}"

echo -e "\n${YELLOW}2. Пользовательская документация:${NC}"
echo -e "   - ${GREEN}https://${DOCS_DOMAIN}${NC}"

echo -e "\n${YELLOW}3. Админская документация (Codex.docs):${NC}"
echo -e "   - ${GREEN}https://${HELP_DOMAIN}${NC}"

echo -e "\n${GREEN}✅ Используются доверенные Let's Encrypt SSL сертификаты${NC}"
echo -e "✅ Автообновление сертификатов настроено"
echo -e "✅ Мягкий reload nginx при обновлении сертификатов"

echo -e "\n"
