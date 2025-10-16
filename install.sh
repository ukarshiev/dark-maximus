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
    echo -e "\n${RED}Ошибка на строке $1. Установка прервана.${NC}"
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

# Константы
REPO_URL="https://github.com/ukarshiev/dark-maximus.git"
PROJECT_DIR="dark-maximus"

# Определение docker compose команды
if docker compose version >/dev/null 2>&1; then 
    DC=("docker" "compose")
    echo -e "${GREEN}✔ Docker Compose v2 (плагин) работает.${NC}"
else 
    DC=("docker-compose")
    if ! command -v docker-compose &> /dev/null || ! docker-compose --version &> /dev/null; then
        echo -e "${YELLOW}Docker Compose не найден. Устанавливаем Docker Compose v1...${NC}"
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
        DC=("docker-compose")
    fi
    echo -e "${GREEN}✔ Docker Compose v1 работает.${NC}"
fi

# Функция создания SSL конфигурации
create_ssl_config() {
    echo -e "${YELLOW}Создаем SSL-конфигурацию...${NC}"
    
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
}

# Функция проверки DNS
check_dns_records() {
    local main_domain="$1"
    local docs_domain="$2"
    local help_domain="$3"
    
    echo -e "${YELLOW}Проверяем DNS-записи (A-записи)...${NC}"
    
    SERVER_IP="$(curl -s4 https://api.ipify.org || hostname -I | awk '{print $1}')"
    echo -e "${YELLOW}IP вашего сервера (IPv4): $SERVER_IP${NC}"
    
    domain_ok() {
        local domain="$1"
        local ips; ips=$(dig +short A "$domain" @8.8.8.8 | sort -u)
        echo -e "  - ${domain} → ${ips:-<нет A>}"
        [ -n "$ips" ] && grep -Fxq "$SERVER_IP" <<<"$ips"
    }
    
    DNS_OK=true
    for check_domain in "$main_domain" "$docs_domain" "$help_domain"; do
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
}

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
    
    echo -e "${GREEN}✔ nginx конфигурация создана.${NC}"
}

# Функция создания nginx конфигурации без SSL (для отладки)
create_nginx_config_without_ssl() {
    local main_domain="$1"
    local docs_domain="$2"
    local help_domain="$3"
    
    echo -e "${YELLOW}Создаем nginx конфигурацию без SSL (для отладки)...${NC}"
    
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
}
EOF
    
    echo -e "${GREEN}✔ nginx конфигурация без SSL создана.${NC}"
}

# Функция создания docker-compose.yml с правильными volume
create_docker_compose() {
    local use_ssl="$1"
    
    echo -e "${YELLOW}Создаем docker-compose.yml...${NC}"
    
    if [ "$use_ssl" = "true" ]; then
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
    else
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
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
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
    fi
    
    echo -e "${GREEN}✔ docker-compose.yml создан.${NC}"
}

# Функция создания самоподписанных сертификатов
create_self_signed_certs() {
    echo -e "${YELLOW}Создаем самоподписанные SSL сертификаты...${NC}"
    
    mkdir -p nginx/ssl
    
    if [ ! -f "nginx/ssl/cert.pem" ] || [ ! -f "nginx/ssl/key.pem" ]; then
        openssl genrsa -out nginx/ssl/key.pem 2048
        openssl req -new -x509 -key nginx/ssl/key.pem -out nginx/ssl/cert.pem -days 365 \
            -subj "/C=RU/ST=Moscow/L=Moscow/O=DarkMaximus/OU=IT/CN=dark-maximus.com"
        echo -e "${GREEN}✔ Самоподписанные сертификаты созданы.${NC}"
    else
        echo -e "${GREEN}✔ Самоподписанные сертификаты уже существуют.${NC}"
    fi
}

echo -e "${GREEN}--- Запуск скрипта установки/обновления dark-maximus ---${NC}"

# Проверяем, существует ли уже конфигурация
if [ -f "docker-compose.yml" ]; then
    echo -e "\n${CYAN}Обнаружена существующая конфигурация. Скрипт запущен в режиме обновления.${NC}"

    if [ ! -d "$PROJECT_DIR" ]; then
        echo -e "${RED}Ошибка: Конфигурация существует, но папка проекта '${PROJECT_DIR}' не найдена!${NC}"
        exit 1
    fi

    cd "$PROJECT_DIR"

    echo -e "\n${CYAN}Шаг 1: Проверка docker-compose...${NC}"
    echo -e "${GREEN}✔ Docker Compose уже проверен в начале скрипта.${NC}"
    
    echo -e "\n${CYAN}Шаг 2: Обновление кода из репозитория Git...${NC}"
    git pull
    echo -e "${GREEN}✔ Код успешно обновлен.${NC}"

    echo -e "\n${CYAN}Шаг 2.5: Проверка SSL-конфигурации...${NC}"
    create_ssl_config

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
            echo -e "${YELLOW}⚠️  Не удалось извлечь домены из конфигурации. Используем значения по умолчанию.${NC}"
            MAIN_DOMAIN="panel.dark-maximus.com"
            DOCS_DOMAIN="docs.dark-maximus.com"
            HELP_DOMAIN="help.dark-maximus.com"
        fi
    else
        MAIN_DOMAIN="panel.dark-maximus.com"
        DOCS_DOMAIN="docs.dark-maximus.com"
        HELP_DOMAIN="help.dark-maximus.com"
    fi

    echo -e "${GREEN}✔ SSL-конфигурация проверена.${NC}"

    # Создаем самоподписанные сертификаты для отладки
    create_self_signed_certs

    # Создаем nginx конфигурацию без SSL для начала
    echo -e "\n${CYAN}Шаг 2.6: Создание nginx конфигурации...${NC}"
    create_nginx_config_without_ssl "$MAIN_DOMAIN" "$DOCS_DOMAIN" "$HELP_DOMAIN"

    # Создаем docker-compose.yml без SSL
    create_docker_compose "false"

    echo -e "\n${CYAN}Шаг 3: Перезапуск nginx-proxy контейнера...${NC}"
    sudo "${DC[@]}" restart nginx-proxy
    echo -e "${GREEN}✔ nginx-proxy перезапущен.${NC}"

    echo -e "\n${CYAN}Шаг 4: Пересборка и перезапуск Docker-контейнеров...${NC}"
    sudo "${DC[@]}" down --remove-orphans
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

    echo -e "\n${CYAN}Шаг 5: Обновление админской документации...${NC}"
    if [ -f "setup-admin-docs.sh" ]; then
        chmod +x setup-admin-docs.sh
        bash setup-admin-docs.sh
        echo -e "${GREEN}✔ Админская документация обновлена.${NC}"
    else
        echo -e "${YELLOW}⚠️  Скрипт setup-admin-docs.sh не найден, пропускаем...${NC}"
    fi

    echo -e "\n\n${GREEN}==============================================${NC}"
    echo -e "${GREEN}      🎉 Обновление успешно завершено! 🎉      ${NC}"
    echo -e "${GREEN}==============================================${NC}"
    echo -e "\nБот был обновлен до последней версии и перезапущен."
    echo -e "\n${CYAN}📱 Доступные сервисы:${NC}"
    echo -e "\n${YELLOW}1. Основной бот и админ-панель:${NC}"
    echo -e "   - ${GREEN}http://${MAIN_DOMAIN}/login${NC}"
    echo -e "\n${YELLOW}2. Пользовательская документация:${NC}"
    echo -e "   - ${GREEN}http://${DOCS_DOMAIN}${NC}"
    echo -e "\n${YELLOW}3. Админская документация (Codex.docs):${NC}"
    echo -e "   - ${GREEN}http://${HELP_DOMAIN}${NC}"
    echo -e "\n"
    exit 0
fi

echo -e "\n${YELLOW}Существующая конфигурация не найдена. Запускается первоначальная установка...${NC}"

echo -e "\n${CYAN}Шаг 1: Установка системных зависимостей...${NC}"
install_package() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${YELLOW}Утилита '$1' не найдена. Устанавливаем...${NC}"
        sudo apt-get update
        sudo apt-get install -y $2
    else
        echo -e "${GREEN}✔ $1 уже установлен.${NC}"
    fi
}

install_package "git" "git"
install_package "curl" "curl"
install_package "nginx" "nginx"
install_package "certbot" "certbot"
install_package "dig" "dnsutils"
install_package "awk" "gawk"

# Устанавливаем Docker CE
echo -e "${YELLOW}Устанавливаем Docker CE...${NC}"
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Проверяем успешность установки Docker
if docker --version &> /dev/null; then
    echo -e "${GREEN}✔ Docker CE установлен и работает.${NC}"
    docker --version
else
    echo -e "${RED}❌ Ошибка установки Docker CE!${NC}"
    exit 1
fi

# Запускаем Docker
if ! sudo systemctl is-active --quiet docker; then
    echo -e "${YELLOW}Сервис docker не запущен. Запускаем и добавляем в автозагрузку...${NC}"
    sudo systemctl start docker
    sudo systemctl enable docker
fi

# Останавливаем системный nginx
if sudo systemctl is-active --quiet nginx; then
    echo -e "${YELLOW}Останавливаем системный nginx (будет использоваться Docker nginx-прокси)...${NC}"
    sudo systemctl stop nginx
    sudo systemctl disable nginx
fi
echo -e "${GREEN}✔ Все системные зависимости установлены.${NC}"

echo -e "\n${CYAN}Шаг 2: Клонирование репозитория...${NC}"
if [ ! -d "$PROJECT_DIR" ]; then
    git clone "$REPO_URL"
fi
cd "$PROJECT_DIR"
echo -e "${GREEN}✔ Репозиторий готов.${NC}"

echo -e "\n${CYAN}Шаг 3: Настройка домена...${NC}"
USER_INPUT_DOMAIN=""
read_input "Введите корневой домен (например, dark-maximus.com): " USER_INPUT_DOMAIN
if [ -z "$USER_INPUT_DOMAIN" ]; then
    echo -e "${YELLOW}⚠️  Домен не введен, используем значение по умолчанию: dark-maximus.com${NC}"
    USER_INPUT_DOMAIN="dark-maximus.com"
fi

# Нормализация домена
DOMAIN=$(echo "$USER_INPUT_DOMAIN" | sed -e 's%^https\?://%%' -e 's%/.*$%%' -e 's/^www\.//')

# Требуем именно корень: ровно два лейбла (example.com)
if ! awk -F. 'NF==2 && $1!="" && $2!="" {exit 0} {exit 1}' <<< "$DOMAIN"; then
  echo -e "${RED}Ожидается корневой домен вида example.com (без поддоменов).${NC}"
  exit 1
fi

EMAIL=""
read_input "Введите ваш email (для регистрации SSL-сертификатов Let's Encrypt): " EMAIL
if [ -z "$EMAIL" ]; then
    echo -e "${YELLOW}⚠️  Email не введен, используем значение по умолчанию: admin@${DOMAIN}${NC}"
    EMAIL="admin@${DOMAIN}"
fi

echo -e "${GREEN}✔ Основной домен: ${DOMAIN}${NC}"

# Поддомены от корня
MAIN_DOMAIN="panel.$DOMAIN"
DOCS_DOMAIN="docs.$DOMAIN"
HELP_DOMAIN="help.$DOMAIN"

echo -e "${CYAN}Поддомены для документации:${NC}"
echo -e "  - ${YELLOW}${MAIN_DOMAIN}${NC} (панель управления ботом)"
echo -e "  - ${YELLOW}${DOCS_DOMAIN}${NC} (пользовательская документация)"
echo -e "  - ${YELLOW}${HELP_DOMAIN}${NC} (админская документация)"

read_input_yn "Использовать эти поддомены? (y/n): "
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}⚠️  Используем поддомены по умолчанию.${NC}"
fi

echo -e "${GREEN}✔ Домены для работы:${NC}"
echo -e "  - Панель: ${MAIN_DOMAIN}"
echo -e "  - Документация: ${DOCS_DOMAIN}"
echo -e "  - Админ-документация: ${HELP_DOMAIN}"

# Проверяем DNS записи
check_dns_records "$MAIN_DOMAIN" "$DOCS_DOMAIN" "$HELP_DOMAIN"

read_input_yn "Продолжить установку? (y/n): "
if [[ ! $REPLY =~ ^[Yy]$ ]]; then 
    echo -e "${YELLOW}⚠️  Продолжаем установку автоматически.${NC}"
fi

# Открываем порты при активном UFW
if command -v ufw &>/dev/null && sudo ufw status | head -1 | grep -qi active; then
    echo -e "${YELLOW}Обнаружен активный UFW. Открываем порты 80/443/1488/8443...${NC}"
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    sudo ufw allow 1488/tcp
    sudo ufw allow 8443/tcp
fi

# Создаем самоподписанные сертификаты для начала
echo -e "\n${CYAN}Шаг 4: Создание самоподписанных SSL сертификатов...${NC}"
create_self_signed_certs

# Создаем SSL конфигурацию
echo -e "\n${CYAN}Шаг 5: Создание SSL-конфигурации...${NC}"
create_ssl_config

# Создаем nginx конфигурацию без SSL для начала
echo -e "\n${CYAN}Шаг 6: Создание nginx конфигурации...${NC}"
create_nginx_config_without_ssl "$MAIN_DOMAIN" "$DOCS_DOMAIN" "$HELP_DOMAIN"

# Создаем docker-compose.yml без SSL
echo -e "\n${CYAN}Шаг 7: Создание Docker конфигурации...${NC}"
create_docker_compose "false"

echo -e "\n${CYAN}Шаг 8: Сборка и запуск Docker-контейнеров...${NC}"
if [ -n "$(sudo "${DC[@]}" ps -q || true)" ]; then
    sudo "${DC[@]}" down || true
fi
sudo "${DC[@]}" up -d --build
echo -e "${GREEN}✔ Контейнеры запущены.${NC}"

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

echo -e "\n${CYAN}Шаг 9: Развертывание админской документации...${NC}"
if [ -f "setup-admin-docs.sh" ]; then
    chmod +x setup-admin-docs.sh
    bash setup-admin-docs.sh
    echo -e "${GREEN}✔ Админская документация развернута.${NC}"
else
    echo -e "${YELLOW}⚠️  Скрипт setup-admin-docs.sh не найден, пропускаем...${NC}"
fi

echo -e "\n\n${GREEN}=====================================================${NC}"
echo -e "${GREEN}      🎉 Установка и запуск успешно завершены! 🎉      ${NC}"
echo -e "${GREEN}=====================================================${NC}"
echo -e "\n${CYAN}📱 Доступные сервисы:${NC}"
echo -e "  - ${YELLOW}Панель управления:${NC} ${GREEN}http://${MAIN_DOMAIN}${NC}"
echo -e "  - ${YELLOW}Пользовательская документация:${NC} ${GREEN}http://${DOCS_DOMAIN}${NC}"
echo -e "  - ${YELLOW}Админская документация:${NC} ${GREEN}http://${HELP_DOMAIN}${NC}"
echo -e "\n${GREEN}✅ Используются самоподписанные SSL сертификаты${NC}"
echo -e "✅ Все сервисы работают по HTTP"
echo -e "✅ nginx-прокси настроен и работает"

# ДИАГНОСТИЧЕСКАЯ ИНФОРМАЦИЯ
echo -e "\n${CYAN}🔍 ДИАГНОСТИЧЕСКАЯ ИНФОРМАЦИЯ:${NC}"

echo -e "\n${YELLOW}🐳 Статус Docker контейнеров:${NC}"
docker compose ps

echo -e "\n${YELLOW}🔧 Проверка HTTP соединений:${NC}"
for domain in "$MAIN_DOMAIN" "$DOCS_DOMAIN" "$HELP_DOMAIN"; do
    echo -n "   ${domain}: "
    if timeout 5 curl -s -o /dev/null -w "%{http_code}" "http://${domain}" | grep -q "200\|302"; then
        echo -e "${GREEN}✅ HTTP работает корректно${NC}"
    else
        echo -e "${RED}❌ Проблемы с HTTP${NC}"
    fi
done

echo -e "\n${CYAN}🔐 Данные для первого входа в админ-панель:${NC}"
echo -e "   • Логин:   ${GREEN}admin${NC}"
echo -e "   • Пароль:  ${GREEN}admin${NC}"
echo -e "\n${CYAN}🔗 Вебхуки:${NC}"
echo -e "   • YooKassa:  ${GREEN}http://${MAIN_DOMAIN}/yookassa-webhook${NC}"
echo -e "   • CryptoBot: ${GREEN}http://${MAIN_DOMAIN}/cryptobot-webhook${NC}"
echo -e "\n${YELLOW}💡 Для настройки Let's Encrypt SSL сертификатов запустите скрипт снова после настройки DNS${NC}"
echo -e "\n"