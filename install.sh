#!/usr/bin/env bash
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

# Выбираем docker compose v1/v2
if docker compose version >/dev/null 2>&1; then
    DC=("docker" "compose")
else
    DC=("docker-compose")
fi

echo -e "${GREEN}===============================================${NC}"
echo -e "${GREEN}      🚀 Dark Maximus - Установка системы     ${NC}"
echo -e "${GREEN}===============================================${NC}"

# Проверяем права root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Запустите скрипт с правами root: sudo ./install.sh${NC}"
    exit 1
fi

# Проверяем, что мы в папке проекта
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}❌ Файл pyproject.toml не найден! Убедитесь, что вы находитесь в папке проекта.${NC}"
    exit 1
fi

# Настройка неинтерактивного режима для APT
export DEBIAN_FRONTEND=noninteractive

echo -e "\n${CYAN}Шаг 1: Обновление системы и установка зависимостей...${NC}"

# Обновляем систему
apt -yq update
apt -yq upgrade

# Устанавливаем необходимые пакеты
apt -yq install \
    curl \
    wget \
    git \
    nginx \
    ufw \
    openssl \
    dnsutils \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    unzip \
    jq \
    bc \
    netcat-openbsd

echo -e "${GREEN}✔ Системные зависимости установлены${NC}"

echo -e "\n${CYAN}Шаг 2: Установка Docker и Docker Compose...${NC}"

# Удаляем старые версии Docker
apt -yq remove docker docker-engine docker.io containerd runc 2>/dev/null || true

# Устанавливаем Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm get-docker.sh

# Определяем пользователя для добавления в группу docker
TARGET_USER="${SUDO_USER:-${USER:-root}}"
if [ "$TARGET_USER" != "root" ]; then
    id -nG "$TARGET_USER" | grep -qw docker || usermod -aG docker "$TARGET_USER" || true
    echo -e "${YELLOW}⚠️  Пользователь $TARGET_USER добавлен в группу docker.${NC}"
    echo -e "${YELLOW}   Выйдите и войдите в сессию для применения изменений.${NC}"
fi

# Устанавливаем Docker Compose (только если не установлен)
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | jq -r '.tag_name')
    curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
fi

echo -e "${GREEN}✔ Docker и Docker Compose установлены${NC}"

echo -e "\n${CYAN}Шаг 3: Настройка доменов...${NC}"

# Запрашиваем основной домен
read_input "Введите основной домен (например: example.com): " MAIN_DOMAIN
if [ -z "$MAIN_DOMAIN" ]; then
    echo -e "${RED}❌ Домен не может быть пустым!${NC}"
    exit 1
fi

# Генерируем поддомены
PANEL_DOMAIN="panel.${MAIN_DOMAIN}"
DOCS_DOMAIN="docs.${MAIN_DOMAIN}"
HELP_DOMAIN="help.${MAIN_DOMAIN}"

echo -e "${GREEN}✔ Домены настроены:${NC}"
echo -e "   - Панель: ${PANEL_DOMAIN}"
echo -e "   - Документация: ${DOCS_DOMAIN}"
echo -e "   - Админ-документация: ${HELP_DOMAIN}"

echo -e "\n${CYAN}Шаг 4: Генерация секретов...${NC}"

# Генерируем секреты
FLASK_SECRET_KEY=$(openssl rand -hex 32)
ADMIN_PASSWORD=$(openssl rand -base64 18)

# Создаем .env файл
cat > .env << EOF
# Dark Maximus Environment Variables
# Автоматически сгенерировано при установке

# Flask Secret Key
FLASK_SECRET_KEY=${FLASK_SECRET_KEY}

# Admin Password
ADMIN_PASSWORD=${ADMIN_PASSWORD}

# SSH Port
SSH_PORT=22
EOF

# Сохраняем пароль админа в отдельный файл
echo "$ADMIN_PASSWORD" > .admin_pass
chmod 600 .admin_pass

echo -e "${GREEN}✔ Секреты сгенерированы и сохранены в .env${NC}"
echo -e "${YELLOW}⚠️  Пароль админа сохранен в .admin_pass (только для чтения root)${NC}"

echo -e "\n${CYAN}Шаг 5: Создание docker-compose.yml...${NC}"

# Создаем docker-compose.yml с localhost-only портами
cat > docker-compose.yml << EOF
version: '3.8'

services:
  bot:
    build: .
    container_name: dark-maximus-bot
    restart: unless-stopped
    ports:
      - '127.0.0.1:1488:1488'
    volumes:
      - ./users.db:/app/project/users.db
      - ./logs:/app/project/logs
      - ./backups:/app/project/backups
    environment:
      - FLASK_SECRET_KEY=\${FLASK_SECRET_KEY}
    healthcheck:
      test: ["CMD-SHELL", "nc -z localhost 1488 || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - dark-maximus-network

  docs:
    build:
      context: .
      dockerfile: Dockerfile.docs
    container_name: dark-maximus-docs
    restart: unless-stopped
    ports:
      - '127.0.0.1:3001:80'
    healthcheck:
      test: ["CMD-SHELL", "nc -z localhost 80 || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    networks:
      - dark-maximus-network

  codex-docs:
    build:
      context: .
      dockerfile: Dockerfile.codex-docs
    container_name: dark-maximus-codex-docs
    restart: unless-stopped
    ports:
      - '127.0.0.1:3002:3000'
    volumes:
      - ./codex.docs/uploads:/usr/src/app/uploads
      - ./codex.docs/db:/usr/src/app/db
    environment:
      - NODE_ENV=production
    healthcheck:
      test: ["CMD-SHELL", "nc -z localhost 3000 || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    networks:
      - dark-maximus-network

networks:
  dark-maximus-network:
    driver: bridge
    name: dark-maximus-network
EOF

echo -e "${GREEN}✔ docker-compose.yml создан с localhost-only портами${NC}"

echo -e "\n${CYAN}Шаг 6: Создание nginx конфигурации (HTTP)...${NC}"

# Создаем директорию для nginx конфигурации
mkdir -p /etc/nginx/sites-available
mkdir -p /etc/nginx/sites-enabled

# Создаем HTTP конфигурацию nginx с улучшенными настройками
cat > /etc/nginx/sites-available/dark-maximus << EOF
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
    server_name ${PANEL_DOMAIN};
    
    # Ограничение размера загружаемых файлов
    client_max_body_size 20m;
    
    # Проксирование на bot сервис
    location / {
        proxy_pass http://bot_backend;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_set_header X-Forwarded-Port \$server_port;
        
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
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_set_header X-Forwarded-Port \$server_port;
        
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
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_set_header X-Forwarded-Port \$server_port;
        
        # WebSocket поддержка с оптимизацией
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
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

# Активируем конфигурацию
ln -sf /etc/nginx/sites-available/dark-maximus /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Проверяем конфигурацию nginx
nginx -t

echo -e "${GREEN}✔ nginx конфигурация создана и проверена${NC}"

echo -e "\n${CYAN}Шаг 7: Настройка UFW (файрвол)...${NC}"

# Определяем SSH порт
SSH_PORT="${SSH_PORT:-22}"

# Настраиваем UFW безопасно
ufw --force reset
ufw default deny incoming
ufw default allow outgoing

# Разрешаем SSH (важно сделать это первым!)
ufw allow ${SSH_PORT}/tcp comment "SSH"

# Разрешаем HTTP и HTTPS
ufw allow 80/tcp comment "HTTP"
ufw allow 443/tcp comment "HTTPS"

# НЕ открываем отладочные порты наружу!
echo -e "${YELLOW}⚠️  Отладочные порты 1488/3001/3002 НЕ открыты наружу (безопасность)${NC}"

# Включаем UFW
ufw --force enable

echo -e "${GREEN}✔ UFW настроен безопасно${NC}"

echo -e "\n${CYAN}Шаг 8: Запуск Docker контейнеров...${NC}"

# Собираем и запускаем контейнеры
${DC[@]} down --remove-orphans 2>/dev/null || true
${DC[@]} build --no-cache
${DC[@]} up -d

# Ждем запуска контейнеров с улучшенной проверкой
echo -e "${YELLOW}Ожидание запуска контейнеров...${NC}"

# Ожидаем готовности bot сервиса
echo -e "${YELLOW}Проверка готовности bot сервиса...${NC}"
timeout 120 bash -c 'until nc -z 127.0.0.1 1488; do sleep 2; done' || {
    echo -e "${RED}❌ Bot сервис не запустился в течение 2 минут${NC}"
    ${DC[@]} logs bot
    exit 1
}

# Ожидаем готовности docs сервиса
echo -e "${YELLOW}Проверка готовности docs сервиса...${NC}"
timeout 60 bash -c 'until nc -z 127.0.0.1 3001; do sleep 2; done' || {
    echo -e "${RED}❌ Docs сервис не запустился в течение 1 минуты${NC}"
    ${DC[@]} logs docs
    exit 1
}

# Ожидаем готовности codex-docs сервиса
echo -e "${YELLOW}Проверка готовности codex-docs сервиса...${NC}"
timeout 60 bash -c 'until nc -z 127.0.0.1 3002; do sleep 2; done' || {
    echo -e "${RED}❌ Codex-docs сервис не запустился в течение 1 минуты${NC}"
    ${DC[@]} logs codex-docs
    exit 1
}

# Проверяем статус контейнеров
echo -e "\n${CYAN}Статус контейнеров:${NC}"
${DC[@]} ps

echo -e "\n${CYAN}Шаг 9: Запуск nginx...${NC}"

# Перезапускаем nginx
systemctl enable nginx
systemctl restart nginx

# Проверяем статус nginx
systemctl status nginx --no-pager -l

echo -e "\n${CYAN}Шаг 10: Финальная проверка доступности...${NC}"

# Ждем полного запуска
sleep 5

# Проверяем доступность сервисов
echo -e "${YELLOW}Проверка доступности сервисов...${NC}"

# Проверяем bot сервис
if nc -z 127.0.0.1 1488; then
    echo -e "${GREEN}✅ Bot сервис доступен${NC}"
else
    echo -e "${RED}❌ Bot сервис недоступен${NC}"
fi

# Проверяем docs сервис
if nc -z 127.0.0.1 3001; then
    echo -e "${GREEN}✅ Docs сервис доступен${NC}"
else
    echo -e "${RED}❌ Docs сервис недоступен${NC}"
fi

# Проверяем codex-docs сервис
if nc -z 127.0.0.1 3002; then
    echo -e "${GREEN}✅ Codex-docs сервис доступен${NC}"
else
    echo -e "${RED}❌ Codex-docs сервис недоступен${NC}"
fi

echo -e "\n${GREEN}===============================================${NC}"
echo -e "${GREEN}      🎉 Установка успешно завершена! 🎉      ${NC}"
echo -e "${GREEN}===============================================${NC}"

echo -e "\n${BLUE}📱 Доступные сервисы (HTTP):${NC}"
echo -e "1. Основной бот и админ-панель:"
echo -e "   - ${GREEN}http://${PANEL_DOMAIN}/login${NC}"
echo -e "   - Логин: ${YELLOW}admin${NC}"
echo -e "   - Пароль: ${YELLOW}${ADMIN_PASSWORD}${NC}"

echo -e "\n2. Пользовательская документация:"
echo -e "   - ${GREEN}http://${DOCS_DOMAIN}${NC}"

echo -e "\n3. Админская документация (Codex.docs):"
echo -e "   - ${GREEN}http://${HELP_DOMAIN}${NC}"

echo -e "\n4. Прямые порты (только localhost):"
echo -e "   - Бот: ${GREEN}http://localhost:1488${NC}"
echo -e "   - Документация: ${GREEN}http://localhost:3001${NC}"
echo -e "   - Админ-документация: ${GREEN}http://localhost:3002${NC}"

echo -e "\n${BLUE}🔧 Следующие шаги:${NC}"
echo -e "1. Настройте DNS A-записи для всех доменов на IP этого сервера"
echo -e "2. Для настройки SSL запустите: ${YELLOW}./setup-ssl.sh${NC}"
echo -e "3. Проверьте статус контейнеров: ${YELLOW}${DC[@]} ps${NC}"
echo -e "4. Просмотрите логи: ${YELLOW}${DC[@]} logs -f${NC}"

echo -e "\n${BLUE}📋 Полезные команды:${NC}"
echo -e "- Остановить все сервисы: ${YELLOW}${DC[@]} down${NC}"
echo -e "- Запустить все сервисы: ${YELLOW}${DC[@]} up -d${NC}"
echo -e "- Перезапустить nginx: ${YELLOW}systemctl restart nginx${NC}"
echo -e "- Проверить nginx: ${YELLOW}nginx -t${NC}"

echo -e "\n${BLUE}🔒 Безопасность:${NC}"
echo -e "- Пароль админа сохранен в: ${YELLOW}.admin_pass${NC}"
echo -e "- Секреты в: ${YELLOW}.env${NC}"
echo -e "- Отладочные порты доступны только с localhost"
echo -e "- UFW настроен безопасно (только 22, 80, 443)"

echo -e "\n${GREEN}Установка завершена! Система готова к работе.${NC}"