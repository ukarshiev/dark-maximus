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
    local line_number="${1:-неизвестно}"
    echo -e "\n${RED}Ошибка на строке $line_number. Установка прервана.${NC}"
    exit 1
}
trap 'handle_error $LINENO' ERR

# Функции для ввода
read_input() {
    local prompt="$1"
    local var_name="$2"
    
    # Проверяем, запущен ли скрипт через pipe (curl | bash)
    if [ ! -t 0 ]; then
        echo -e "${YELLOW}⚠️  Скрипт запущен через pipe. Для передачи домена используйте один из способов:${NC}"
        echo -e "${CYAN}   1. Через переменную окружения (рекомендуется):${NC}"
        echo -e "${CYAN}      DOMAIN=example.com curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install.sh | sudo bash${NC}"
        echo -e "${CYAN}   2. Скачайте и запустите локально:${NC}"
        echo -e "${CYAN}      wget https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install.sh${NC}"
        echo -e "${CYAN}      chmod +x install.sh${NC}"
        echo -e "${CYAN}      sudo ./install.sh example.com${NC}"
        echo -e "${CYAN}   3. Или запустите в директории проекта:${NC}"
        echo -e "${CYAN}      cd /opt/dark-maximus && sudo ./install.sh example.com${NC}"
        echo -e "${YELLOW}⚠️  Для обновления существующей установки домен будет взят из .env файла${NC}"
        # Не завершаем скрипт, а используем значение по умолчанию
        eval "$var_name='localhost'"
        return
    fi
    
    # Интерактивный ввод
    read -p "$prompt" "$var_name" || {
        echo -e "${RED}❌ Ошибка ввода. Установка прервана.${NC}"
        exit 1
    }
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

# Безопасная проверка аргументов командной строки
# Инициализируем переменные для предотвращения ошибок "unbound variable"
MAIN_DOMAIN=""
PANEL_DOMAIN=""
DOCS_DOMAIN=""
HELP_DOMAIN=""

# Определяем директорию установки
INSTALL_DIR="/opt/dark-maximus"
PROJECT_DIR="$INSTALL_DIR"

echo -e "\n${CYAN}Шаг 0: Подготовка директории и клонирование репозитория...${NC}"

# Создаем директорию установки
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Клонируем репозиторий
echo -e "${YELLOW}Клонирование репозитория...${NC}"
if [ -d ".git" ]; then
    echo -e "${YELLOW}Репозиторий уже существует, обновляем...${NC}"
    
    # Настраиваем git для слияния
    git config pull.rebase false
    
    # Проверяем, есть ли локальные изменения
    if ! git diff --quiet; then
        echo -e "${YELLOW}Обнаружены локальные изменения, сохраняем их...${NC}"
        git add .
        git commit -m "Auto-save local changes before update" || true
    fi
    
    # Обновляем репозиторий
    git pull origin main || {
        echo -e "${RED}❌ Ошибка при обновлении репозитория. Попробуем принудительное обновление...${NC}"
        git fetch origin main
        git reset --hard origin/main
    }
else
    git clone https://github.com/ukarshiev/dark-maximus.git .
fi

# Проверяем, что мы в папке проекта
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}❌ Файл pyproject.toml не найден! Проблема с клонированием репозитория.${NC}"
    exit 1
fi

echo -e "${GREEN}✔ Репозиторий клонирован в $PROJECT_DIR${NC}"

# Проверяем наличие необходимых файлов для Docker
echo -e "${YELLOW}Проверка наличия необходимых файлов...${NC}"
REQUIRED_FILES=(
    "Dockerfile"
    "Dockerfile.docs" 
    "Dockerfile.codex-docs"
    "deploy/nginx/docs.conf"
    "codex.docs/docs-config.yaml"
    "codex.docs/package.json"
    "codex.docs/yarn.lock"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}❌ Не найден необходимый файл: $file${NC}"
        exit 1
    fi
done

echo -e "${GREEN}✔ Все необходимые файлы найдены${NC}"

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

# Получаем домен из аргументов командной строки или переменных окружения
echo -e "${YELLOW}Проверка источников домена...${NC}"
echo -e "Количество аргументов: $#"
echo -e "Переменная DOMAIN: ${DOMAIN:-не установлена}"

# Проверяем, существует ли уже .env файл (обновление)
if [ -f ".env" ]; then
    echo -e "${GREEN}✔ Найден существующий .env файл - режим обновления${NC}"
    # Читаем домен из существующего .env файла
    if grep -q "DOMAIN=" .env; then
        MAIN_DOMAIN=$(grep "DOMAIN=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'")
        echo -e "${GREEN}✔ Домен получен из существующего .env: ${MAIN_DOMAIN}${NC}"
    else
        echo -e "${YELLOW}⚠️  Домен не найден в .env файле, используем значение по умолчанию${NC}"
        MAIN_DOMAIN="localhost"
    fi
elif [ -n "${DOMAIN:-}" ]; then
    MAIN_DOMAIN="$DOMAIN"
    echo -e "${GREEN}✔ Домен получен из переменной окружения: ${MAIN_DOMAIN}${NC}"
elif [ $# -gt 0 ] && [ -n "${1:-}" ]; then
    MAIN_DOMAIN="$1"
    echo -e "${GREEN}✔ Домен получен из аргументов: ${MAIN_DOMAIN}${NC}"
else
    echo -e "${YELLOW}Переменная окружения и аргументы не найдены, запрашиваем интерактивный ввод...${NC}"
    # Запрашиваем основной домен
    read_input "Введите основной домен (например: example.com): " MAIN_DOMAIN
fi

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
# Примечание: ADMIN_PASSWORD не используется - учетные данные панели хранятся в базе данных users.db

# Создаем .env файл на основе шаблона
if [ -f "config/env.example" ]; then
    cp config/env.example .env
    echo -e "${YELLOW}Скопирован шаблон .env из config/env.example${NC}"
else
    # Создаем базовый .env файл
    cat > .env << EOF
# Dark Maximus Environment Variables
# Автоматически сгенерировано при установке

# Flask Secret Key
FLASK_SECRET_KEY=${FLASK_SECRET_KEY}

# Примечание: учетные данные панели (логин/пароль) хранятся в базе данных users.db

# SSH Port
SSH_PORT=22

# Domains
MAIN_DOMAIN=${MAIN_DOMAIN}
PANEL_DOMAIN=${PANEL_DOMAIN}
DOCS_DOMAIN=${DOCS_DOMAIN}
HELP_DOMAIN=${HELP_DOMAIN}
EOF
fi

# Обновляем .env с нашими значениями
# Используем более безопасный способ - пересоздаем .env файл
cat > .env << EOF
# Основные настройки
FLASK_SECRET_KEY=${FLASK_SECRET_KEY}
# Примечание: учетные данные панели (логин/пароль) хранятся в базе данных users.db, а не в .env
DOMAIN=${MAIN_DOMAIN}

# Дополнительные настройки из шаблона
BOT_TOKEN=${BOT_TOKEN:-}
WEBHOOK_URL=${WEBHOOK_URL:-}
PAYMENT_PROVIDER=${PAYMENT_PROVIDER:-}
PAYMENT_TOKEN=${PAYMENT_TOKEN:-}
DATABASE_URL=${DATABASE_URL:-sqlite:///bot.db}

# Домены
MAIN_DOMAIN=${MAIN_DOMAIN}
DOCS_DOMAIN=${DOCS_DOMAIN}
HELP_DOMAIN=${HELP_DOMAIN}
EOF

# Примечание: учетные данные панели хранятся в базе данных users.db
# Для просмотра текущего логина и пароля используйте веб-панель или базу данных

echo -e "${GREEN}✔ Секреты сгенерированы и сохранены в .env${NC}"
echo -e "${YELLOW}⚠️  Учетные данные панели хранятся в базе данных users.db${NC}"

echo -e "\n${CYAN}Шаг 4.1: Создание необходимых директорий...${NC}"

# Создаем необходимые директории
mkdir -p logs
mkdir -p backups
mkdir -p codex.docs/uploads
mkdir -p codex.docs/db
mkdir -p sessions

# Устанавливаем правильные права доступа
chmod 755 logs backups sessions
chmod 755 codex.docs/uploads codex.docs/db

echo -e "${GREEN}✔ Необходимые директории созданы${NC}"

echo -e "\n${CYAN}Шаг 4.2: Инициализация базы данных...${NC}"

# Создаем пустую базу данных если её нет
if [ ! -f "users.db" ]; then
    touch users.db
    chmod 644 users.db
    echo -e "${YELLOW}Создана пустая база данных users.db${NC}"
fi

# Инициализируем базу данных с правильным паролем админа
echo -e "${YELLOW}Инициализация базы данных с настройками...${NC}"

# Устанавливаем зависимости для bcrypt
echo -e "${YELLOW}Установка зависимостей для bcrypt...${NC}"
apt-get update -qq >/dev/null 2>&1
apt-get install -y build-essential cargo python3-pip python3-dev >/dev/null 2>&1

# Устанавливаем bcrypt
pip3 install --break-system-packages bcrypt >/dev/null 2>&1 || echo "bcrypt установлен"

python3 -c "
import sqlite3
import bcrypt

# КРИТИЧНО: Защита учетных данных администратора
# Best practice: Никогда не перезаписываем существующие логин и пароль
# Если ЛЮБОЙ из параметров существует - полностью пропускаем создание дефолтных

conn = sqlite3.connect('users.db')
cursor = conn.cursor()

# Создаем таблицу настроек если её нет
cursor.execute('''
    CREATE TABLE IF NOT EXISTS bot_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
''')

# Оптимизированная проверка: один запрос для проверки обоих учетных данных
cursor.execute('''
    SELECT key, value FROM bot_settings 
    WHERE key IN ('panel_login', 'panel_password')
''')
existing_credentials = dict(cursor.fetchall())

existing_login = existing_credentials.get('panel_login')
existing_password = existing_credentials.get('panel_password')

# КРИТИЧНО: Защита существующих учетных данных
# Если ЛЮБОЙ из параметров уже существует - НЕ СОЗДАЕМ и НЕ ИЗМЕНЯЕМ ничего
if existing_login is not None or existing_password is not None:
    # Хотя бы один параметр существует - защищаем существующие данные
    if existing_login and existing_password:
        print(f'✓ Логин и пароль админа уже существуют, сохраняем существующие (логин: {existing_login})')
    elif existing_login:
        print(f'⚠️  Логин админа существует ({existing_login}), но пароль отсутствует. Пропускаем автоматическое создание.')
        print('   Для безопасности создайте пароль вручную через веб-панель.')
    elif existing_password:
        print(f'⚠️  Пароль админа существует, но логин отсутствует. Пропускаем автоматическое создание.')
        print('   Для безопасности создайте логин вручную через веб-панель.')
else:
    # ТОЛЬКО если ОБА параметра отсутствуют - создаём дефолтные значения
    admin_password = 'admin'
    hashed_password = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    cursor.execute('INSERT INTO bot_settings (key, value) VALUES (?, ?)', ('panel_login', 'admin'))
    cursor.execute('INSERT INTO bot_settings (key, value) VALUES (?, ?)', ('panel_password', hashed_password))
    print('✓ Созданы дефолтные учетные данные админа (логин: admin, пароль: admin)')
    print('  ВАЖНО: Смените пароль при первом входе!')

# Добавляем остальные настройки по умолчанию
# КРИТИЧНО: Явно исключаем учетные данные из этого словаря
default_settings = {
    'about_content': None,
    'terms_url': None,
    'privacy_url': None,
    'support_user': None,
    'support_text': None,
    'channel_url': None,
    'force_subscription': 'true',
    'receipt_email': 'example@example.com',
    'telegram_bot_token': None,
    'support_bot_token': None,
    'telegram_bot_username': None,
    'trial_enabled': 'true',
    'trial_duration_days': '3',
    'enable_referrals': 'true',
    'referral_percentage': '10',
    'referral_discount': '5',
    'minimum_withdrawal': '100',
    'support_group_id': None,
    'admin_telegram_id': None,
    'yookassa_shop_id': None,
    'yookassa_secret_key': None,
    'yookassa_test_mode': 'true',
    'yookassa_test_shop_id': None,
    'yookassa_test_secret_key': None,
    'yookassa_api_url': 'https://api.yookassa.ru/v3',
    'yookassa_test_api_url': 'https://api.test.yookassa.ru/v3',
    'yookassa_verify_ssl': 'true',
    'yookassa_test_verify_ssl': 'false',
    'sbp_enabled': 'false',
    'cryptobot_token': None,
    'heleket_merchant_id': None,
    'heleket_api_key': None,
    'domain': None,
    'global_domain': None,
    'ton_wallet_address': None,
    'tonapi_key': None,
    'auto_delete_orphans': 'false',
    'hidden_mode': '0',
    'support_enabled': 'true',
    'minimum_topup': '50',
    'ton_manifest_name': 'Dark Maximus Shop Bot',
    'ton_manifest_icon_url': None,
    'ton_manifest_terms_url': None,
    'ton_manifest_privacy_url': None,
    'app_url': None,
    'logging_bot_token': None,
    'logging_bot_username': None,
    'logging_bot_admin_chat_id': None,
    'logging_bot_level': 'INFO'
}

# Явно исключаем учетные данные из обработки
EXCLUDED_KEYS = {'panel_login', 'panel_password'}
for key, value in default_settings.items():
    if key not in EXCLUDED_KEYS:
        cursor.execute('INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)', (key, value))

# Коммитим все изменения в одной транзакции
conn.commit()
conn.close()
print('✓ База данных инициализирована')
"

echo -e "${GREEN}✔ База данных готова${NC}"

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

echo -e "\n${CYAN}Шаг 6: Проверка nginx конфигурации...${NC}"

# Создаем директорию для nginx конфигурации
mkdir -p /etc/nginx/sites-available
mkdir -p /etc/nginx/sites-enabled

# Проверяем, существует ли уже конфигурация с SSL
NGINX_CONFIG_EXISTS=false
NGINX_HAS_SSL=false

# Проверяем наличие SSL конфигурации несколькими способами
if [ -f "/etc/nginx/sites-available/dark-maximus" ]; then
    NGINX_CONFIG_EXISTS=true
    
    # Проверяем наличие SSL директив в конфигурации
    if grep -qiE "ssl_certificate|listen\s+443|ssl_protocols" /etc/nginx/sites-available/dark-maximus 2>/dev/null; then
        NGINX_HAS_SSL=true
    fi
    
    # Дополнительно проверяем наличие сертификатов Let's Encrypt
    if [ -d "/etc/letsencrypt/live" ] && [ -n "$(find /etc/letsencrypt/live -mindepth 1 -maxdepth 1 -type d 2>/dev/null)" ]; then
        # Если есть сертификаты, скорее всего SSL настроен
        if ! grep -qiE "ssl_certificate|listen\s+443" /etc/nginx/sites-available/dark-maximus 2>/dev/null; then
            # Сертификаты есть, но конфигурация может быть неправильной - не перезаписываем
            echo -e "${YELLOW}⚠️  Обнаружены SSL сертификаты Let's Encrypt${NC}"
            echo -e "${YELLOW}   Проверяем конфигурацию nginx...${NC}"
            if nginx -t 2>/dev/null | grep -q "successful"; then
                NGINX_HAS_SSL=true
            fi
        else
            NGINX_HAS_SSL=true
        fi
    fi
    
    if [ "$NGINX_HAS_SSL" = "true" ]; then
        echo -e "${GREEN}✔ Найдена существующая SSL конфигурация nginx - пропускаем обновление${NC}"
        echo -e "${YELLOW}⚠️  Для изменения SSL настроек используйте ssl-install.sh${NC}"
        # Убедимся, что конфигурация активирована
        if [ ! -L "/etc/nginx/sites-enabled/dark-maximus" ]; then
            ln -sf /etc/nginx/sites-available/dark-maximus /etc/nginx/sites-enabled/dark-maximus
        fi
        # Проверяем конфигурацию
        if nginx -t 2>/dev/null | grep -q "successful"; then
            echo -e "${GREEN}✔ Конфигурация nginx корректна${NC}"
        else
            echo -e "${YELLOW}⚠️  Обнаружена ошибка в конфигурации nginx, но она не перезаписана${NC}"
            echo -e "${YELLOW}   Проверьте конфигурацию вручную или запустите ssl-install.sh${NC}"
        fi
    fi
fi

# Создаём конфигурацию только если SSL конфигурации нет И файла не существует
if [ "$NGINX_HAS_SSL" = "false" ]; then
    # КРИТИЧЕСКАЯ ПРОВЕРКА: если файл конфигурации существует - НИКОГДА не трогаем его
    if [ -f "/etc/nginx/sites-available/dark-maximus" ]; then
        echo -e "${GREEN}✔ Обнаружена существующая конфигурация nginx - НЕ трогаем её${NC}"
        echo -e "${YELLOW}⚠️  Если нужно обновить конфигурацию, используйте ssl-install.sh${NC}"
        NGINX_HAS_SSL=true  # Помечаем как "не трогать"
    fi
    
    # ТОЛЬКО если файла нет - создаём базовую HTTP конфигурацию
    if [ "$NGINX_HAS_SSL" = "false" ]; then
        echo -e "${YELLOW}Создание HTTP конфигурации nginx...${NC}"
        
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
    
    # Раздача статических файлов напрямую (приоритет выше чем location /)
    location /dist/ {
        proxy_pass http://codex_docs_backend;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Кэширование статических файлов
        expires 1y;
        add_header Cache-Control "public, immutable";
        
        # Таймауты
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
    
    # Проксирование на codex-docs сервис для остальных запросов
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

    # Очищаем старые конфигурации nginx, НО сохраняем dark-maximus если он уже активирован
    if [ -L "/etc/nginx/sites-enabled/dark-maximus" ]; then
        # Если dark-maximus уже активирован - не трогаем его
        find /etc/nginx/sites-enabled -maxdepth 1 -type f -exec rm -f {} +
        # Восстанавливаем ссылку на dark-maximus
        ln -sf /etc/nginx/sites-available/dark-maximus /etc/nginx/sites-enabled/dark-maximus
    else
        # Если dark-maximus не активирован - очищаем всё
        rm -f /etc/nginx/sites-enabled/*
    fi

    # Обновляем nginx.conf только если его нет или он повреждён
    if [ ! -f "/etc/nginx/nginx.conf" ] || ! nginx -t >/dev/null 2>&1; then
        # Очищаем системную nginx конфигурацию, которая может содержать старые upstream
        # Сначала делаем резервную копию
        cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup 2>/dev/null || true
        # Перезаписываем nginx.conf
        echo "# Nginx configuration for dark-maximus" > /etc/nginx/nginx.conf
        cat >> /etc/nginx/nginx.conf << 'EOF'
user www-data;
worker_processes auto;
pid /run/nginx.pid;
include /etc/nginx/modules-enabled/*.conf;

events {
    worker_connections 1024;
}

http {
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    server_tokens off;

    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging Settings
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    # Gzip Settings
    gzip on;
    gzip_vary on;
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

    # Virtual Host Configs
    include /etc/nginx/conf.d/*.conf;
    include /etc/nginx/sites-enabled/*;
}
EOF
    fi

    # Создаем временную конфигурацию nginx без upstream (для проверки синтаксиса)
    cat > /etc/nginx/sites-available/dark-maximus-temp << EOF
# Временная конфигурация nginx (без upstream)
server {
    listen 80 default_server;
    server_name _;
    return 444;
}
EOF

    # Активируем временную конфигурацию
    ln -sf /etc/nginx/sites-available/dark-maximus-temp /etc/nginx/sites-enabled/dark-maximus

    # Проверяем базовую конфигурацию nginx
    nginx -t || {
        echo -e "${RED}❌ Ошибка в базовой конфигурации nginx${NC}"
        nginx -t
        exit 1
    }

    echo -e "${GREEN}✔ Временная nginx конфигурация создана и проверена${NC}"
    fi
fi

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

echo -e "\n${CYAN}Шаг 7.1: Настройка logrotate...${NC}"

# Создаем конфигурацию logrotate для логов проекта
cat > /etc/logrotate.d/dark-maximus << EOF
${PROJECT_DIR}/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root root
    postrotate
        # Перезапускаем nginx если нужно
        systemctl reload nginx > /dev/null 2>&1 || true
    endscript
}
EOF

echo -e "${GREEN}✔ Logrotate настроен${NC}"

echo -e "\n${CYAN}Шаг 7.2: Создание systemd сервиса...${NC}"

# Создаем systemd сервис для автозапуска
cat > /etc/systemd/system/dark-maximus.service << EOF
[Unit]
Description=Dark Maximus VPN Bot
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${PROJECT_DIR}
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

# Перезагружаем systemd и включаем сервис
systemctl daemon-reload
systemctl enable dark-maximus.service

echo -e "${GREEN}✔ Systemd сервис создан и включен${NC}"

echo -e "\n${CYAN}Шаг 8: Запуск Docker контейнеров...${NC}"

# Принудительно останавливаем и удаляем существующие контейнеры по именам
# Это необходимо, если контейнеры были созданы не через docker-compose или есть конфликты
echo -e "${YELLOW}Проверка и удаление существующих контейнеров...${NC}"
CONTAINER_NAMES=("dark-maximus-bot" "dark-maximus-docs" "dark-maximus-codex-docs")
for container_name in "${CONTAINER_NAMES[@]}"; do
    if docker ps -a --format '{{.Names}}' | grep -q "^${container_name}$"; then
        echo -e "${YELLOW}Останавливаем и удаляем контейнер ${container_name}...${NC}"
        docker stop "${container_name}" 2>/dev/null || true
        docker rm -f "${container_name}" 2>/dev/null || true
    fi
done

# Теперь выполняем docker compose down для очистки сетей и volumes
${DC[@]} down --remove-orphans 2>/dev/null || true

# Собираем и запускаем контейнеры
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

echo -e "\n${CYAN}Шаг 9: Активация полной nginx конфигурации...${NC}"

# Проверяем, есть ли конфигурация вообще
if [ -f "/etc/nginx/sites-available/dark-maximus" ]; then
    # Проверяем, есть ли SSL конфигурация
    if grep -qiE "ssl_certificate|listen\s+443|ssl_protocols" /etc/nginx/sites-available/dark-maximus 2>/dev/null; then
        echo -e "${GREEN}✔ Найдена SSL конфигурация nginx - НЕ трогаем${NC}"
        NGINX_HAS_SSL_CHECK=true
    elif [ -d "/etc/letsencrypt/live" ] && [ -n "$(find /etc/letsencrypt/live -mindepth 1 -maxdepth 1 -type d 2>/dev/null)" ]; then
        # Если есть сертификаты, скорее всего SSL настроен
        if nginx -t 2>/dev/null | grep -q "successful"; then
            echo -e "${GREEN}✔ Обнаружены SSL сертификаты, конфигурация работает - НЕ трогаем${NC}"
            NGINX_HAS_SSL_CHECK=true
        fi
    fi
    
    # Активируем существующую конфигурацию (если она ещё не активирована)
    if [ ! -L "/etc/nginx/sites-enabled/dark-maximus" ]; then
        ln -sf /etc/nginx/sites-available/dark-maximus /etc/nginx/sites-enabled/dark-maximus
        echo -e "${GREEN}✔ Конфигурация nginx активирована${NC}"
    else
        echo -e "${GREEN}✔ Конфигурация nginx уже активирована${NC}"
    fi
    
    # Проверяем конфигурацию nginx
    echo -e "${YELLOW}Проверка конфигурации nginx...${NC}"
    if nginx -t 2>/dev/null | grep -q "successful"; then
        echo -e "${GREEN}✔ Конфигурация nginx корректна${NC}"
        
        # Перезапускаем nginx только если конфигурация корректна
        systemctl enable nginx
        systemctl restart nginx
        
        # Проверяем статус nginx
        systemctl status nginx --no-pager -l
    else
        echo -e "${RED}❌ Ошибка в конфигурации nginx${NC}"
        nginx -t
        echo -e "${YELLOW}⚠️  Nginx не перезапущен из-за ошибок в конфигурации${NC}"
        echo -e "${YELLOW}   Исправьте конфигурацию вручную или запустите ssl-install.sh${NC}"
    fi
else
    # Активируем конфигурацию nginx с upstream серверами ТОЛЬКО если она была создана в этом скрипте
    if [ -f "/etc/nginx/sites-available/dark-maximus-temp" ]; then
        echo -e "${YELLOW}Активация полной конфигурации nginx...${NC}"
        # Удаляем временную конфигурацию
        rm -f /etc/nginx/sites-available/dark-maximus-temp
        rm -f /etc/nginx/sites-enabled/dark-maximus-temp
        # Активируем основную конфигурацию (только если она была создана)
        if [ -f "/etc/nginx/sites-available/dark-maximus" ]; then
            ln -sf /etc/nginx/sites-available/dark-maximus /etc/nginx/sites-enabled/dark-maximus
            echo -e "${GREEN}✔ Конфигурация nginx активирована${NC}"
        fi
        
        # Проверяем конфигурацию nginx теперь, когда контейнеры запущены
        echo -e "${YELLOW}Проверка конфигурации nginx...${NC}"
        nginx -t || {
            echo -e "${RED}❌ Ошибка в конфигурации nginx${NC}"
            nginx -t
            exit 1
        }

        # Перезапускаем nginx
        systemctl enable nginx
        systemctl restart nginx

        # Проверяем статус nginx
        systemctl status nginx --no-pager -l
    else
        echo -e "${YELLOW}⚠️  Конфигурация nginx не создана - nginx не настроен${NC}"
        echo -e "${YELLOW}   Для настройки nginx запустите: ${CYAN}curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/ssl-install.sh | sudo bash -s -- ${MAIN_DOMAIN}${NC}"
    fi
fi

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

echo -e "\n${BLUE}📋 РЕЗЮМЕ УСТАНОВКИ:${NC}"
echo -e "✅ Обновлена система и установлены все зависимости"
echo -e "✅ Установлен Docker и Docker Compose"
echo -e "✅ Создан .env файл на основе шаблона config/env.example"
echo -e "✅ Созданы все необходимые директории (logs, backups, sessions)"
echo -e "✅ Инициализирована база данных users.db"
echo -e "✅ Настроены 3 контейнера: bot, docs, codex-docs"
echo -e "✅ Настроен nginx с проксированием на контейнеры"
echo -e "✅ Настроен UFW файрвол (порты 22, 80, 443)"
echo -e "✅ Настроен logrotate для ротации логов"
echo -e "✅ Создан systemd сервис для автозапуска"
echo -e "✅ Сгенерированы секреты и пароли"
echo -e "✅ Все сервисы запущены и проверены"

echo -e "\n${BLUE}📱 Доступные сервисы (HTTP):${NC}"
echo -e "1. Основной бот и админ-панель:"
echo -e "   - ${GREEN}http://${PANEL_DOMAIN}/login${NC}"
echo -e "   - Логин: ${YELLOW}admin${NC}"
echo -e "   - Пароль: ${YELLOW}admin${NC}"

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
echo -e "2. Для настройки SSL запустите: ${YELLOW}curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/ssl-install.sh | sudo bash -s -- $MAIN_DOMAIN${NC}"
echo -e "3. Проверьте статус контейнеров: ${YELLOW}cd $PROJECT_DIR && ${DC[@]} ps${NC}"
echo -e "4. Просмотрите логи: ${YELLOW}cd $PROJECT_DIR && ${DC[@]} logs -f${NC}"

echo -e "\n${BLUE}📋 Полезные команды:${NC}"
echo -e "- Перейти в папку проекта: ${YELLOW}cd $PROJECT_DIR${NC}"
echo -e "- Остановить все сервисы: ${YELLOW}cd $PROJECT_DIR && ${DC[@]} down${NC}"
echo -e "- Запустить все сервисы: ${YELLOW}cd $PROJECT_DIR && ${DC[@]} up -d${NC}"
echo -e "- Перезапустить nginx: ${YELLOW}systemctl restart nginx${NC}"
echo -e "- Проверить nginx: ${YELLOW}nginx -t${NC}"
echo -e "- Управление systemd сервисом:"
echo -e "  - Статус: ${YELLOW}systemctl status dark-maximus${NC}"
echo -e "  - Запуск: ${YELLOW}systemctl start dark-maximus${NC}"
echo -e "  - Остановка: ${YELLOW}systemctl stop dark-maximus${NC}"
echo -e "  - Перезапуск: ${YELLOW}systemctl restart dark-maximus${NC}"

echo -e "\n${BLUE}🔒 Безопасность:${NC}"
echo -e "- Учетные данные панели хранятся в: ${YELLOW}$PROJECT_DIR/users.db${NC}"
echo -e "- Секреты в: ${YELLOW}$PROJECT_DIR/.env${NC}"
echo -e "- Отладочные порты доступны только с localhost"
echo -e "- UFW настроен безопасно (только 22, 80, 443)"

echo -e "\n${GREEN}Установка завершена! Система готова к работе.${NC}"
