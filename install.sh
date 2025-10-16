#!/usr/bin/env bash
set -o errexit
set -o pipefail
set -o nounset

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

handle_error() {
    echo -e "\n${RED}Ошибка на строке $1. Установка прервана.${NC}"
    exit 1
}
trap 'handle_error $LINENO' ERR

read_input() {
    read -p "$1" "$2" < /dev/tty
}

read_input_yn() {
    read -p "$1" -n 1 -r REPLY < /dev/tty
    echo
}

REPO_URL="https://github.com/ukarshiev/dark-maximus.git"
PROJECT_DIR="dark-maximus"
NGINX_CONF_FILE="/etc/nginx/sites-available/${PROJECT_DIR}.conf"
NGINX_ENABLED_FILE="/etc/nginx/sites-enabled/${PROJECT_DIR}.conf"

# Выбираем docker compose v1/v2
DC_BIN="$(command -v docker-compose || true)"
if [ -z "${DC_BIN}" ]; then
    DC_BIN="docker compose"
fi

echo -e "${GREEN}--- Запуск скрипта установки/обновления dark-maximus ---${NC}"

if [ -f "$NGINX_CONF_FILE" ]; then
    echo -e "\n${CYAN}Обнаружена существующая конфигурация. Скрипт запущен в режиме обновления.${NC}"

    if [ ! -d "$PROJECT_DIR" ]; then
        echo -e "${RED}Ошибка: Конфигурация Nginx существует, но папка проекта '${PROJECT_DIR}' не найдена!${NC}"
        echo -e "${YELLOW}Удалите файл конфигурации Nginx и запустите установку заново:${NC}"
        echo -e "sudo rm ${NGINX_CONF_FILE}"
        exit 1
    fi

    cd "$PROJECT_DIR"

    echo -e "\n${CYAN}Шаг 1: Обновление кода из репозитория Git...${NC}"
    git pull
    echo -e "${GREEN}✔ Код успешно обновлен.${NC}"

    echo -e "\n${CYAN}Шаг 2: Пересборка и перезапуск Docker-контейнеров...${NC}"
    sudo ${DC_BIN} down --remove-orphans
    sudo ${DC_BIN} up -d --build

    echo -e "\n${CYAN}Шаг 3: Обновление админской документации...${NC}"
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
    echo -e "   - ${GREEN}http://localhost:1488/login${NC}"
    echo -e "\n${YELLOW}2. Пользовательская документация:${NC}"
    echo -e "   - ${GREEN}http://localhost:3001${NC}"
    echo -e "\n${YELLOW}3. Админская документация (Codex.docs):${NC}"
    echo -e "   - ${GREEN}http://localhost:3002${NC}"
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
install_package "docker" "docker.io"
install_package "nginx" "nginx"
# docker compose v2 может идти в пакете docker-ce-plugin-compose, поддерживаем через $DC_BIN
install_package "curl" "curl"
install_package "certbot" "certbot"
install_package "dig" "dnsutils"
install_package "awk" "gawk"

for service in docker nginx; do
    if ! sudo systemctl is-active --quiet "$service"; then
        echo -e "${YELLOW}Сервис $service не запущен. Запускаем и добавляем в автозагрузку...${NC}"
        sudo systemctl start "$service"
        sudo systemctl enable "$service"
    fi
done
echo -e "${GREEN}✔ Все системные зависимости установлены.${NC}"

echo -e "\n${CYAN}Шаг 2: Клонирование репозитория...${NC}"
if [ ! -d "$PROJECT_DIR" ]; then
    git clone "$REPO_URL"
fi
cd "$PROJECT_DIR"
echo -e "${GREEN}✔ Репозиторий готов.${NC}"

echo -e "\n${CYAN}Шаг 3: Настройка домена...${NC}"
read_input "Введите корневой домен (например, dark-maximus.com): " USER_INPUT_DOMAIN
if [ -z "$USER_INPUT_DOMAIN" ]; then
    echo -e "${RED}Ошибка: Домен не может быть пустым. Установка прервана.${NC}"
    exit 1
fi

# Нормализация домена
DOMAIN=$(echo "$USER_INPUT_DOMAIN" | sed -e 's%^https\?://%%' -e 's%/.*$%%' -e 's/^www\.//')

# Требуем именно корень: ровно два лейбла (example.com)
if ! awk -F. 'NF==2 && $1!="" && $2!="" {exit 0} {exit 1}' <<< "$DOMAIN"; then
  echo -e "${RED}Ожидается корневой домен вида example.com (без поддоменов).${NC}"
  exit 1
fi

read_input "Введите ваш email (для регистрации SSL-сертификатов Let's Encrypt): " EMAIL
if [ -z "$EMAIL" ]; then
    echo -e "${RED}Ошибка: Email обязателен для выпуска сертификатов.${NC}"
    exit 1
fi

echo -e "${GREEN}✔ Основной домен: ${DOMAIN}${NC}"

# Поддомены от корня: панель, юзер-доки, админ-доки
MAIN_DOMAIN="panel.$DOMAIN"
DOCS_DOMAIN="docs.$DOMAIN"
HELP_DOMAIN="help.$DOMAIN"

echo -e "${CYAN}Поддомены для документации:${NC}"
echo -e "  - ${YELLOW}${MAIN_DOMAIN}${NC} (панель управления ботом)"
echo -e "  - ${YELLOW}${DOCS_DOMAIN}${NC} (пользовательская документация)"
echo -e "  - ${YELLOW}${HELP_DOMAIN}${NC} (админская документация)"

read_input_yn "Использовать эти поддомены? (y/n): "
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    read_input "Введите поддомен для пользовательской документации (docs.example.com): " DOCS_DOMAIN
    read_input "Введите поддомен для админской документации (help.example.com): " HELP_DOMAIN
    read_input "Введите поддомен для панели управления (panel.example.com): " MAIN_DOMAIN
fi

echo -e "${GREEN}✔ Домены для работы:${NC}"
echo -e "  - Панель: ${MAIN_DOMAIN}"
echo -e "  - Документация: ${DOCS_DOMAIN}"
echo -e "  - Админ-документация: ${HELP_DOMAIN}"

SERVER_IP="$(curl -s4 ifconfig.me || hostname -I | awk '{print $1}')"
echo -e "${YELLOW}IP вашего сервера (IPv4): $SERVER_IP${NC}"

echo -e "${YELLOW}Проверяем DNS-записи (A-записи)...${NC}"
for check_domain in $MAIN_DOMAIN $DOCS_DOMAIN $HELP_DOMAIN; do
    DOMAIN_IP=$(dig +short A "$check_domain" @8.8.8.8 | tail -n1)
    echo -e "  - ${check_domain} → ${DOMAIN_IP}"
    if [ -z "${DOMAIN_IP}" ] || [ "$SERVER_IP" != "$DOMAIN_IP" ]; then
        echo -e "${RED}⚠️  ВНИМАНИЕ: DNS для ${check_domain} не указывает на IP этого сервера!${NC}"
    fi
done

read_input_yn "Продолжить установку? (y/n): "
if [[ ! $REPLY =~ ^[Yy]$ ]]; then echo "Установка прервана."; exit 1; fi

# Открываем порты при активном UFW (локаль-независимая проверка)
if command -v ufw &>/dev/null && sudo ufw status | head -1 | grep -qi active; then
    echo -e "${YELLOW}Обнаружен активный UFW. Открываем порты 80/443/1488/8443...${NC}"
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    sudo ufw allow 1488/tcp
    sudo ufw allow 8443/tcp
fi

echo -e "${YELLOW}Выпускаем SSL-сертификаты (standalone, порт 80)...${NC}"
# Останавливаем Nginx, чтобы standalone занял 80 порт
sudo systemctl stop nginx
sudo certbot certonly --standalone \
    --preferred-challenges http \
    -d "$MAIN_DOMAIN" -d "$DOCS_DOMAIN" -d "$HELP_DOMAIN" \
    --email "$EMAIL" --agree-tos --non-interactive
sudo systemctl start nginx
echo -e "${GREEN}✔ Сертификаты выпущены.${NC}"

echo -e "\n${CYAN}Шаг 4: Настройка Nginx...${NC}"
echo -e "Создаем конфигурацию Nginx для всех сервисов..."
sudo rm -rf /etc/nginx/sites-enabled/default || true
sudo bash -c "cat > $NGINX_CONF_FILE" <<EOF
# Панель управления
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${MAIN_DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${MAIN_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${MAIN_DOMAIN}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://127.0.0.1:1488;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}

# Пользовательская документация
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${DOCS_DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${DOCS_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOCS_DOMAIN}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}

# Админская документация (Codex.docs)
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${HELP_DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${HELP_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${HELP_DOMAIN}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://127.0.0.1:3002;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # WebSocket поддержка для Codex.docs
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

# HTTP -> HTTPS редирект для всех трёх доменов
server {
    listen 80;
    listen [::]:80;
    server_name ${MAIN_DOMAIN} ${DOCS_DOMAIN} ${HELP_DOMAIN};
    return 301 https://\$host\$request_uri;
}
EOF

if [ ! -f "$NGINX_ENABLED_FILE" ]; then
    sudo ln -s "$NGINX_CONF_FILE" "$NGINX_ENABLED_FILE"
fi

echo -e "${YELLOW}Проверяем и перезагружаем Nginx...${NC}"
sudo nginx -t && sudo systemctl reload nginx
echo -e "${GREEN}✔ Конфигурация Nginx применена.${NC}"

echo -e "\n${CYAN}Шаг 5: Сборка и запуск Docker-контейнеров...${NC}"
if [ -n "$(sudo ${DC_BIN} ps -q || true)" ]; then
    sudo ${DC_BIN} down || true
fi
sudo ${DC_BIN} up -d --build
echo -e "${GREEN}✔ Контейнеры запущены.${NC}"

echo -e "\n${CYAN}Шаг 6: Развертывание админской документации...${NC}"
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
echo -e "  - ${YELLOW}Панель управления:${NC} ${GREEN}https://${MAIN_DOMAIN}/login${NC}"
echo -e "  - ${YELLOW}Пользовательская документация:${NC} ${GREEN}https://${DOCS_DOMAIN}${NC}"
echo -e "  - ${YELLOW}Админская документация:${NC} ${GREEN}https://${HELP_DOMAIN}${NC}"
echo -e "\n${CYAN}🔐 Данные для первого входа в админ-панель:${NC}"
echo -e "   • Логин:   ${GREEN}admin${NC}"
echo -e "   • Пароль:  ${GREEN}admin${NC}"
echo -e "\n${CYAN}🔗 Вебхуки:${NC}"
echo -e "   • YooKassa:  ${GREEN}https://${MAIN_DOMAIN}/yookassa-webhook${NC}"
echo -e "   • CryptoBot: ${GREEN}https://${MAIN_DOMAIN}/cryptobot-webhook${NC}"
echo -e "\n"
