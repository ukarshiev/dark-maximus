#!/usr/bin/env bash
set -o errexit
set -o pipefail
set -o nounset

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

# Обработка ошибок
handle_error() {
    echo -e "\n${RED}Ошибка на строке $1. Установка SSL прервана.${NC}"
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

read_input_yn() {
    if [ -t 0 ]; then
        read -p "$1" -n 1 -r REPLY < /dev/tty
    else
        read -p "$1" -n 1 -r REPLY || true
    fi
    echo
}

# Определение docker compose команды
if docker compose version >/dev/null 2>&1; then 
    DC=("docker" "compose")
    echo -e "${GREEN}✔ Docker Compose v2 (плагин) работает.${NC}"
else 
    DC=("docker-compose")
    echo -e "${GREEN}✔ Docker Compose v1 работает.${NC}"
fi

# Функция ожидания освобождения порта
wait_for_port_free() {
    local port="$1"
    echo -e "${YELLOW}Ждем освобождения порта $port...${NC}"
    for i in {1..20}; do 
        ss -ltn "( sport = :$port )" | grep -q ":$port" || break
        sleep 1
    done
    echo -e "${GREEN}✔ Порт $port свободен.${NC}"
}

# Функция создания nginx конфигурации с SSL
create_nginx_config_with_ssl() {
    local main_domain="$1"
    local docs_domain="$2"
    local help_domain="$3"
    
    echo -e "${YELLOW}Создаем nginx конфигурацию с SSL...${NC}"
    
    cat > nginx/nginx.conf << EOF
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    
    # Логирование
    log_format main '\$remote_addr - \$remote_user [\$time_local] "\$request" '
                    '\$status \$body_bytes_sent "\$http_referer" '
                    '"\$http_user_agent" "\$http_x_forwarded_for"';
    
    access_log /var/log/nginx/access.log main;
    error_log /var/log/nginx/error.log;
    
    # Основные настройки
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    
    # Gzip сжатие
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
    
    # Upstream для docs сервиса
    upstream docs_backend {
        server docs:80;
    }
    
    # Upstream для codex-docs сервиса  
    upstream codex_docs_backend {
        server codex-docs:3000;
    }
    
    # Upstream для bot сервиса
    upstream bot_backend {
        server bot:1488;
    }
    
    # Конфигурация для ${main_domain}
    server {
        listen 80;
        server_name ${main_domain};
        
        # Редирект с HTTP на HTTPS
        return 301 https://\$server_name\$request_uri;
    }
    
    server {
        listen 443 ssl http2;
        server_name ${main_domain};
        
        # SSL сертификаты Let's Encrypt
        ssl_certificate /etc/letsencrypt/live/${main_domain}/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/${main_domain}/privkey.pem;
        
        # SSL настройки
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
        ssl_prefer_server_ciphers off;
        
        # Проксирование на bot сервис
        location / {
            proxy_pass http://bot_backend;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            
            # Таймауты
            proxy_connect_timeout 30s;
            proxy_send_timeout 30s;
            proxy_read_timeout 30s;
        }
    }
    
    # Конфигурация для ${docs_domain}
    server {
        listen 80;
        server_name ${docs_domain};
        
        # Редирект с HTTP на HTTPS
        return 301 https://\$server_name\$request_uri;
    }
    
    server {
        listen 443 ssl http2;
        server_name ${docs_domain};
        
        # SSL сертификаты Let's Encrypt
        ssl_certificate /etc/letsencrypt/live/${docs_domain}/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/${docs_domain}/privkey.pem;
        
        # SSL настройки
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
        ssl_prefer_server_ciphers off;
        
        # Проксирование на docs сервис
        location / {
            proxy_pass http://docs_backend;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            
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
    
    # Конфигурация для ${help_domain}
    server {
        listen 80;
        server_name ${help_domain};
        
        # Редирект с HTTP на HTTPS
        return 301 https://\$server_name\$request_uri;
    }
    
    server {
        listen 443 ssl http2;
        server_name ${help_domain};
        
        # SSL сертификаты Let's Encrypt
        ssl_certificate /etc/letsencrypt/live/${help_domain}/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/${help_domain}/privkey.pem;
        
        # SSL настройки
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
        ssl_prefer_server_ciphers off;
        
        # Проксирование на codex-docs сервис
        location / {
            proxy_pass http://codex_docs_backend;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            
            # Таймауты
            proxy_connect_timeout 30s;
            proxy_send_timeout 30s;
            proxy_read_timeout 30s;
        }
        
        # Health check
        location /health {
            proxy_pass http://codex_docs_backend/;
            access_log off;
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
        
        # SSL сертификаты (заглушки)
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        
        return 444;
    }
}
EOF
    
    echo -e "${GREEN}✔ nginx конфигурация с SSL создана.${NC}"
}

# Функция создания docker-compose.yml с SSL
create_docker_compose_with_ssl() {
    echo -e "${YELLOW}Создаем docker-compose.yml с SSL...${NC}"
    
    cat > docker-compose.yml << 'EOF'
name: dark-maximus
services:
  bot:
    build: .
    restart: unless-stopped
    container_name: dark-maximus-bot
    ports:
      - '1488:1488'
    environment:
      - PYTHONIOENCODING=utf-8
      - LANG=C.UTF-8
      - LC_ALL=C.UTF-8
    volumes:
      - .:/app/project
      - /app/.venv
      - sessions_data:/app/sessions

  docs:
    build:
      context: .
      dockerfile: Dockerfile.docs
    restart: unless-stopped
    container_name: dark-maximus-docs
    ports:
      - '3001:80'
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:80/health"]
      interval: 30s
      timeout: 3s
      start_period: 5s
      retries: 3

  codex-docs:
    build:
      context: .
      dockerfile: Dockerfile.codex-docs
    restart: unless-stopped
    container_name: dark-maximus-codex-docs
    ports:
      - '3002:3000'
    volumes:
      - codex_uploads:/usr/src/app/uploads
      - codex_db:/usr/src/app/db
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:3000/"]
      interval: 30s
      timeout: 3s
      start_period: 10s
      retries: 3

  nginx-proxy:
    image: nginx:alpine
    restart: unless-stopped
    container_name: dark-maximus-nginx-proxy
    user: root
    ports:
      - '80:80'
      - '443:443'
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - /etc/letsencrypt/live:/etc/letsencrypt/live:ro
    depends_on:
      - bot
      - docs
      - codex-docs
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost/health"]
      interval: 30s
      timeout: 3s
      start_period: 5s
      retries: 3

volumes:
  sessions_data:
  codex_uploads:
  codex_db:
EOF
    
    echo -e "${GREEN}✔ docker-compose.yml с SSL создан.${NC}"
}

echo -e "${GREEN}--- Настройка SSL для dark-maximus ---${NC}"

# Проверяем, что мы в правильной директории
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}Ошибка: docker-compose.yml не найден. Запустите скрипт из директории проекта.${NC}"
    exit 1
fi

# Извлекаем домены из nginx.conf
if [ -f "nginx/nginx.conf" ]; then
    MAIN_DOMAIN=$(grep -o 'server_name [^;]*' "nginx/nginx.conf" | grep "panel\." | head -1 | awk '{print $2}')
    DOCS_DOMAIN=$(grep -o 'server_name [^;]*' "nginx/nginx.conf" | grep "docs\." | head -1 | awk '{print $2}')
    HELP_DOMAIN=$(grep -o 'server_name [^;]*' "nginx/nginx.conf" | grep "help\." | head -1 | awk '{print $2}')
    
    if [ -n "$MAIN_DOMAIN" ] && [ -n "$DOCS_DOMAIN" ] && [ -n "$HELP_DOMAIN" ]; then
        echo -e "${GREEN}✔ Домены извлечены из существующей конфигурации:${NC}"
        echo -e "   - Панель: ${MAIN_DOMAIN}"
        echo -e "   - Документация: ${DOCS_DOMAIN}"
        echo -e "   - Админ-документация: ${HELP_DOMAIN}"
    else
        echo -e "${RED}❌ Не удалось извлечь домены из конфигурации.${NC}"
        exit 1
    fi
else
    echo -e "${RED}❌ nginx/nginx.conf не найден.${NC}"
    exit 1
fi

# Проверяем DNS записи
echo -e "\n${CYAN}Шаг 1: Проверка DNS записей...${NC}"
SERVER_IP="$(curl -s4 https://api.ipify.org || hostname -I | awk '{print $1}')"
echo -e "${YELLOW}IP вашего сервера (IPv4): $SERVER_IP${NC}"

domain_ok() {
    local domain="$1"
    local ips; ips=$(dig +short A "$domain" @8.8.8.8 | sort -u)
    echo -e "  - ${domain} → ${ips:-<нет A>}"
    [ -n "$ips" ] && grep -Fxq "$SERVER_IP" <<<"$ips"
}

DNS_OK=true
for check_domain in "$MAIN_DOMAIN" "$DOCS_DOMAIN" "$HELP_DOMAIN"; do
    if ! domain_ok "$check_domain"; then
        echo -e "${RED}❌ ОШИБКА: DNS для ${check_domain} не указывает на IP этого сервера!${NC}"
        DNS_OK=false
    fi
done

if [ "$DNS_OK" = false ]; then
    echo -e "${RED}❌ КРИТИЧЕСКАЯ ОШИБКА: DNS записи настроены неправильно!${NC}"
    echo -e "${YELLOW}Настройте A-записи для всех поддоменов на IP: ${SERVER_IP}${NC}"
    exit 1
fi

echo -e "${GREEN}✔ Все DNS записи корректны.${NC}"

# Получаем email для Let's Encrypt
EMAIL=""
read_input "Введите ваш email (для регистрации SSL-сертификатов Let's Encrypt): " EMAIL
if [ -z "$EMAIL" ]; then
    echo -e "${YELLOW}⚠️  Email не введен, используем значение по умолчанию: admin@${MAIN_DOMAIN#*.}${NC}"
    EMAIL="admin@${MAIN_DOMAIN#*.}"
fi

# Останавливаем nginx-proxy для освобождения порта 80
echo -e "\n${CYAN}Шаг 2: Остановка nginx-proxy для выпуска сертификатов...${NC}"
sudo "${DC[@]}" stop nginx-proxy
wait_for_port_free 80

# Выпускаем Let's Encrypt сертификаты
echo -e "\n${CYAN}Шаг 3: Выпуск Let's Encrypt сертификатов...${NC}"

echo -e "${YELLOW}Выпускаем Let's Encrypt сертификат для ${MAIN_DOMAIN}...${NC}"
sudo certbot certonly --standalone \
    --preferred-challenges http \
    -d "$MAIN_DOMAIN" \
    --email "$EMAIL" --agree-tos --non-interactive

echo -e "${YELLOW}Выпускаем Let's Encrypt сертификат для ${DOCS_DOMAIN}...${NC}"
sudo certbot certonly --standalone \
    --preferred-challenges http \
    -d "$DOCS_DOMAIN" \
    --email "$EMAIL" --agree-tos --non-interactive

echo -e "${YELLOW}Выпускаем Let's Encrypt сертификат для ${HELP_DOMAIN}...${NC}"
sudo certbot certonly --standalone \
    --preferred-challenges http \
    -d "$HELP_DOMAIN" \
    --email "$EMAIL" --agree-tos --non-interactive

echo -e "${GREEN}✔ Let's Encrypt сертификаты выпущены.${NC}"

# Создаем nginx конфигурацию с SSL
echo -e "\n${CYAN}Шаг 4: Создание nginx конфигурации с SSL...${NC}"
create_nginx_config_with_ssl "$MAIN_DOMAIN" "$DOCS_DOMAIN" "$HELP_DOMAIN"

# Создаем docker-compose.yml с SSL
echo -e "\n${CYAN}Шаг 5: Обновление Docker конфигурации...${NC}"
create_docker_compose_with_ssl

# Перезапускаем контейнеры
echo -e "\n${CYAN}Шаг 6: Перезапуск контейнеров с SSL...${NC}"
sudo "${DC[@]}" up -d --build

# Проверяем, что nginx-прокси запустился
echo -e "${YELLOW}Проверяем статус nginx-прокси...${NC}"
sleep 5
if sudo "${DC[@]}" ps | grep -q "nginx-proxy.*Up"; then
    echo -e "${GREEN}✔ nginx-прокси запущен и работает.${NC}"
else
    echo -e "${RED}❌ Ошибка запуска nginx-прокси!${NC}"
    echo -e "${YELLOW}Логи nginx-прокси:${NC}"
    sudo "${DC[@]}" logs nginx-proxy
    exit 1
fi

# Настраиваем автообновление сертификатов
echo -e "\n${CYAN}Шаг 7: Настройка автообновления сертификатов...${NC}"
PROJECT_ABS_DIR="$(pwd -P)"

# Создаем обертку для docker compose
echo '#!/usr/bin/env bash' | sudo tee /usr/local/bin/dc >/dev/null
echo 'exec '"${DC[*]}"' "$@"' | sudo tee -a /usr/local/bin/dc >/dev/null
sudo chmod +x /usr/local/bin/dc

# Создаем динамический post-hook для cron
POST_HOOK='
name=$(docker ps --filter "name=nginx-proxy" --format "{{.Names}}" | head -1);
if [ -n "$name" ]; then docker exec "$name" sh -c "nginx -t && nginx -s reload" || docker restart "$name"; fi
'

# Создаем скрипт для автообновления Let's Encrypt сертификатов
sudo bash -c "cat > /etc/cron.d/certbot-renew" << EOF
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
# Автообновление Let's Encrypt сертификатов каждый день в 2:30 утра
30 2 * * * root /usr/bin/certbot renew --quiet \\
  --pre-hook "/usr/local/bin/dc -f ${PROJECT_ABS_DIR}/docker-compose.yml stop nginx-proxy" \\
  --post-hook 'eval '"$(printf %q "$POST_HOOK")"
EOF

# Устанавливаем правильные права и перезагружаем cron
sudo chmod 644 /etc/cron.d/certbot-renew
sudo systemctl reload cron || sudo service cron reload

echo -e "${GREEN}✔ Автообновление сертификатов настроено.${NC}"

echo -e "\n\n${GREEN}=====================================================${NC}"
echo -e "${GREEN}      🎉 SSL настройка успешно завершена! 🎉      ${NC}"
echo -e "${GREEN}=====================================================${NC}"
echo -e "\n${CYAN}📱 Доступные сервисы с SSL:${NC}"
echo -e "  - ${YELLOW}Панель управления:${NC} ${GREEN}https://${MAIN_DOMAIN}${NC}"
echo -e "  - ${YELLOW}Пользовательская документация:${NC} ${GREEN}https://${DOCS_DOMAIN}${NC}"
echo -e "  - ${YELLOW}Админская документация:${NC} ${GREEN}https://${HELP_DOMAIN}${NC}"
echo -e "\n${GREEN}✅ Используются доверенные Let's Encrypt SSL сертификаты${NC}"
echo -e "✅ Автообновление сертификатов настроено"
echo -e "✅ Мягкий reload nginx при обновлении сертификатов"

# ДИАГНОСТИЧЕСКАЯ ИНФОРМАЦИЯ
echo -e "\n${CYAN}🔍 ДИАГНОСТИЧЕСКАЯ ИНФОРМАЦИЯ:${NC}"

echo -e "\n${YELLOW}📋 Созданные Let's Encrypt сертификаты:${NC}"
for domain in "$MAIN_DOMAIN" "$DOCS_DOMAIN" "$HELP_DOMAIN"; do
    if [ -f "/etc/letsencrypt/live/${domain}/fullchain.pem" ]; then
        echo -e "   ✅ ${domain}: /etc/letsencrypt/live/${domain}/"
        # Показываем информацию о сертификате
        echo -e "      $(openssl x509 -in /etc/letsencrypt/live/${domain}/fullchain.pem -text -noout | grep -E "Subject:|Not After|Issuer:" | head -3)"
    else
        echo -e "   ❌ ${domain}: Let's Encrypt сертификат НЕ НАЙДЕН!"
    fi
done

echo -e "\n${YELLOW}🐳 Статус Docker контейнеров:${NC}"
docker compose ps

echo -e "\n${YELLOW}🔧 Проверка SSL соединений:${NC}"
for domain in "$MAIN_DOMAIN" "$DOCS_DOMAIN" "$HELP_DOMAIN"; do
    echo -n "   ${domain}: "
    if timeout 5 openssl s_client -connect "${domain}:443" -servername "${domain}" </dev/null 2>/dev/null | grep -q "Verify return code: 0"; then
        echo -e "${GREEN}✅ SSL работает корректно${NC}"
    else
        echo -e "${RED}❌ Проблемы с SSL${NC}"
    fi
done

echo -e "\n${CYAN}🔐 Данные для первого входа в админ-панель:${NC}"
echo -e "   • Логин:   ${GREEN}admin${NC}"
echo -e "   • Пароль:  ${GREEN}admin${NC}"
echo -e "\n${CYAN}🔗 Вебхуки:${NC}"
echo -e "   • YooKassa:  ${GREEN}https://${MAIN_DOMAIN}/yookassa-webhook${NC}"
echo -e "   • CryptoBot: ${GREEN}https://${MAIN_DOMAIN}/cryptobot-webhook${NC}"
echo -e "\n"
