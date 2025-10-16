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
        echo -e "${GREEN}✔ Docker Compose v1 установлен.${NC}"
    else
        echo -e "${GREEN}✔ Docker Compose v1 уже установлен.${NC}"
    fi
fi

echo -e "${GREEN}--- Запуск скрипта установки dark-maximus (HTTP) ---${NC}"

# Проверяем, существует ли уже конфигурация
if [ -f "docker-compose.yml" ]; then
    echo -e "\n${CYAN}Обнаружена существующая конфигурация. Скрипт запущен в режиме обновления.${NC}"
    
    echo -e "\n${CYAN}Шаг 1: Обновление кода из репозитория Git...${NC}"
    git pull origin main
    echo -e "${GREEN}✔ Код успешно обновлен.${NC}"

    echo -e "\n${CYAN}Шаг 2: Перезапуск сервисов...${NC}"
    sudo "${DC[@]}" down --remove-orphans
    sudo "${DC[@]}" up -d --build
    echo -e "${GREEN}✔ Сервисы перезапущены.${NC}"

    echo -e "\n\n${GREEN}==============================================${NC}"
    echo -e "${GREEN}      🎉 Обновление успешно завершено! 🎉      ${NC}"
    echo -e "${GREEN}==============================================${NC}"
    echo -e "\n${YELLOW}Для настройки SSL запустите: ./setup-ssl.sh${NC}"
    exit 0
fi

echo -e "\n${CYAN}Шаг 1: Установка системных зависимостей...${NC}"

# Обновляем пакеты
echo -e "${YELLOW}Обновляем список пакетов...${NC}"
sudo apt update

# Устанавливаем необходимые пакеты
echo -e "${YELLOW}Устанавливаем необходимые пакеты...${NC}"
sudo apt install -y \
    curl \
    wget \
    git \
    nginx \
    certbot \
    python3-certbot-nginx \
    ufw \
    openssl \
    dnsutils

echo -e "${GREEN}✔ Системные зависимости установлены.${NC}"

echo -e "\n${CYAN}Шаг 2: Установка Docker...${NC}"

# Проверяем, установлен ли Docker
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Docker не найден. Устанавливаем Docker...${NC}"
    
    # Удаляем старые версии
    sudo apt remove -y docker docker-engine docker.io containerd runc || true
    
    # Устанавливаем зависимости
    sudo apt install -y \
        ca-certificates \
        curl \
        gnupg \
        lsb-release
    
    # Добавляем официальный GPG ключ Docker
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    
    # Настраиваем репозиторий
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Обновляем пакеты и устанавливаем Docker
    sudo apt update
    sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Добавляем пользователя в группу docker
    sudo usermod -aG docker $USER
    
    echo -e "${GREEN}✔ Docker установлен.${NC}"
    echo -e "${YELLOW}⚠️  Для применения изменений группы перелогиньтесь или выполните: newgrp docker${NC}"
else
    echo -e "${GREEN}✔ Docker уже установлен.${NC}"
fi

echo -e "\n${CYAN}Шаг 3: Клонирование репозитория...${NC}"

# Проверяем, существует ли папка проекта
if [ -d "$PROJECT_DIR" ]; then
    echo -e "${YELLOW}Папка $PROJECT_DIR уже существует. Обновляем...${NC}"
    cd "$PROJECT_DIR"
    git pull origin main
    echo -e "${GREEN}✔ Репозиторий обновлен.${NC}"
else
    echo -e "${YELLOW}Клонируем репозиторий...${NC}"
    git clone "$REPO_URL" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
    echo -e "${GREEN}✔ Репозиторий клонирован.${NC}"
fi

echo -e "\n${CYAN}Шаг 4: Настройка доменов...${NC}"

# Запрашиваем домены
read_input "Введите основной домен (например, panel.yourdomain.com): " MAIN_DOMAIN
read_input "Введите домен для документации (например, docs.yourdomain.com): " DOCS_DOMAIN
read_input "Введите домен для админской документации (например, help.yourdomain.com): " HELP_DOMAIN

# Проверяем, что домены введены
if [ -z "$MAIN_DOMAIN" ] || [ -z "$DOCS_DOMAIN" ] || [ -z "$HELP_DOMAIN" ]; then
    echo -e "${RED}❌ Все домены должны быть указаны!${NC}"
    exit 1
fi

echo -e "${GREEN}✔ Домены настроены:${NC}"
echo -e "   - Панель: ${MAIN_DOMAIN}"
echo -e "   - Документация: ${DOCS_DOMAIN}"
echo -e "   - Админ-документация: ${HELP_DOMAIN}"

echo -e "\n${CYAN}Шаг 5: Создание самоподписанных SSL сертификатов...${NC}"

# Создаем папку для SSL сертификатов
mkdir -p nginx/ssl

# Генерируем самоподписанные сертификаты
if [ ! -f "nginx/ssl/cert.pem" ] || [ ! -f "nginx/ssl/key.pem" ]; then
    echo -e "${YELLOW}Генерируем самоподписанные SSL сертификаты...${NC}"
    openssl req -x509 -newkey rsa:2048 -keyout nginx/ssl/key.pem -out nginx/ssl/cert.pem -days 365 -nodes \
        -subj "/C=RU/ST=Moscow/L=Moscow/O=DarkMaximus/OU=IT/CN=dark-maximus.com"
    echo -e "${GREEN}✔ Самоподписанные сертификаты созданы.${NC}"
else
    echo -e "${GREEN}✔ Самоподписанные сертификаты уже существуют.${NC}"
fi

echo -e "\n${CYAN}Шаг 6: Создание nginx конфигурации (HTTP)...${NC}"

# Создаем nginx конфигурацию для HTTP
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
}
EOF

echo -e "${GREEN}✔ nginx конфигурация создана.${NC}"

echo -e "\n${CYAN}Шаг 7: Создание docker-compose.yml...${NC}"

# Создаем docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  bot:
    build:
      context: .
      dockerfile: Dockerfile
    restart: unless-stopped
    container_name: dark-maximus-bot
    ports:
      - '1488:1488'
    volumes:
      - ./data:/app/project/data
      - ./logs:/app/project/logs
      - ./backups:/app/project/backups
    environment:
      - PYTHONPATH=/app/project
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:1488/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  docs:
    build:
      context: .
      dockerfile: Dockerfile.docs
    restart: unless-stopped
    container_name: dark-maximus-docs
    ports:
      - '3001:80'
    volumes:
      - ./docs/user-docs:/usr/share/nginx/html/docs:ro
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost/health"]
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
      - ./docs/admin-docs:/usr/src/app/docs:ro
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:3000/"]
      interval: 30s
      timeout: 3s
      start_period: 5s
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
  data:
  logs:
  backups:
EOF

echo -e "${GREEN}✔ docker-compose.yml создан.${NC}"

echo -e "\n${CYAN}Шаг 8: Настройка файрвола...${NC}"

# Настраиваем UFW
if command -v ufw &> /dev/null; then
    echo -e "${YELLOW}Настраиваем UFW...${NC}"
    sudo ufw --force enable
    sudo ufw allow ssh
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    sudo ufw allow 1488/tcp
    echo -e "${GREEN}✔ UFW настроен.${NC}"
else
    echo -e "${YELLOW}UFW не найден, пропускаем настройку файрвола.${NC}"
fi

echo -e "\n${CYAN}Шаг 9: Запуск Docker-контейнеров...${NC}"

# Запускаем контейнеры
sudo "${DC[@]}" up -d --build

# Проверяем статус контейнеров
echo -e "${YELLOW}Проверяем статус контейнеров...${NC}"
sleep 10

if sudo "${DC[@]}" ps | grep -q "nginx-proxy.*Up"; then
    echo -e "${GREEN}✔ nginx-proxy запущен и работает.${NC}"
else
    echo -e "${RED}❌ Ошибка запуска nginx-proxy!${NC}"
    echo -e "${YELLOW}Логи nginx-proxy:${NC}"
    sudo "${DC[@]}" logs nginx-proxy
    exit 1
fi

echo -e "\n${CYAN}Шаг 10: Развертывание админской документации...${NC}"

# Запускаем скрипт развертывания админской документации
if [ -f "setup-admin-docs.sh" ]; then
    chmod +x setup-admin-docs.sh
    bash setup-admin-docs.sh
    echo -e "${GREEN}✔ Админская документация развернута.${NC}"
fi

echo -e "\n\n${GREEN}==============================================${NC}"
echo -e "${GREEN}      🎉 Установка успешно завершена! 🎉      ${NC}"
echo -e "${GREEN}==============================================${NC}"

echo -e "\n${CYAN}📱 Доступные сервисы (HTTP):${NC}"

echo -e "\n${YELLOW}1. Основной бот и админ-панель:${NC}"
echo -e "   - ${GREEN}http://${MAIN_DOMAIN}/login${NC}"

echo -e "\n${YELLOW}2. Пользовательская документация:${NC}"
echo -e "   - ${GREEN}http://${DOCS_DOMAIN}${NC}"

echo -e "\n${YELLOW}3. Админская документация (Codex.docs):${NC}"
echo -e "   - ${GREEN}http://${HELP_DOMAIN}${NC}"

echo -e "\n${YELLOW}4. Прямые порты (для отладки):${NC}"
echo -e "   - Бот: ${GREEN}http://localhost:1488${NC}"
echo -e "   - Документация: ${GREEN}http://localhost:3001${NC}"
echo -e "   - Админ-документация: ${GREEN}http://localhost:3002${NC}"

echo -e "\n${CYAN}🔧 Следующие шаги:${NC}"
echo -e "1. Настройте DNS A-записи для всех доменов на IP этого сервера"
echo -e "2. Для настройки SSL запустите: ${YELLOW}./setup-ssl.sh${NC}"
echo -e "3. Проверьте статус контейнеров: ${YELLOW}docker compose ps${NC}"

echo -e "\n"
