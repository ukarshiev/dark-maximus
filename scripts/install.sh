#!/usr/bin/env bash
set -o errexit
set -o pipefail

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
    sudo docker-compose down --remove-orphans && sudo docker-compose up -d --build
    
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
install_package "docker-compose" "docker-compose"
install_package "nginx" "nginx"
install_package "curl" "curl"
install_package "certbot" "certbot python3-certbot-nginx"
install_package "dig" "dnsutils"

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

echo -e "\n${CYAN}Шаг 3: Настройка домена и получение SSL-сертификатов...${NC}"

read_input "Введите ваш основной домен (например, panel.dark-maximus.com): " USER_INPUT_DOMAIN

if [ -z "$USER_INPUT_DOMAIN" ]; then
    echo -e "${RED}Ошибка: Домен не может быть пустым. Установка прервана.${NC}"
    exit 1
fi

# Нормализация домена
DOMAIN=$(echo "$USER_INPUT_DOMAIN" \
    | sed -e 's%^https\?://%%' -e 's%/.*$%%' -e 's/^www\.//')

read_input "Введите ваш email (для регистрации SSL-сертификатов Let's Encrypt): " EMAIL
if [ -z "$EMAIL" ]; then
    echo -e "${RED}Ошибка: Email обязателен для выпуска сертификатов.${NC}"
    exit 1
fi

echo -e "${GREEN}✔ Основной домен: ${DOMAIN}${NC}"

# Формируем поддомены: берём базовый домен = последние два лейбла
BASE_DOMAIN=$(awk -F. '{if(NF>=2)print $(NF-1)"."$NF; else print $0}' <<< "$DOMAIN")
MAIN_DOMAIN="$DOMAIN"
DOCS_DOMAIN="docs.$BASE_DOMAIN"
HELP_DOMAIN="help.$BASE_DOMAIN"

echo -e "${CYAN}Поддомены для документации:${NC}"
echo -e "  - ${YELLOW}${MAIN_DOMAIN}${NC} (основной бот)"
echo -e "  - ${YELLOW}${DOCS_DOMAIN}${NC} (пользовательская документация)"
echo -e "  - ${YELLOW}${HELP_DOMAIN}${NC} (админская документация)"

read_input_yn "Использовать эти поддомены? (y/n): "
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    read_input "Введите поддомен для пользовательской документации (docs.your-domain.com): " DOCS_DOMAIN
    read_input "Введите поддомен для админской документации (help.your-domain.com): " HELP_DOMAIN
fi

echo -e "${GREEN}✔ Домены для работы:${NC}"
echo -e "  - Основной: ${MAIN_DOMAIN}"
echo -e "  - Документация: ${DOCS_DOMAIN}"
echo -e "  - Админ-документация: ${HELP_DOMAIN}"

SERVER_IP=$(curl -s ifconfig.me || hostname -I | awk '{print $1}')
echo -e "${YELLOW}IP вашего сервера: $SERVER_IP${NC}"

echo -e "${YELLOW}Проверяем DNS-записи...${NC}"
for check_domain in $MAIN_DOMAIN $DOCS_DOMAIN $HELP_DOMAIN; do
    DOMAIN_IP=$(dig +short "$check_domain" @8.8.8.8 | tail -n1)
    echo -e "  - ${check_domain} → ${DOMAIN_IP}"
    if [ "$SERVER_IP" != "$DOMAIN_IP" ]; then
        echo -e "${RED}⚠️  ВНИМАНИЕ: DNS-запись для ${check_domain} не указывает на IP-адрес этого сервера!${NC}"
    fi
done

read_input_yn "Продолжить установку? (y/n): "
if [[ ! $REPLY =~ ^[Yy]$ ]]; then echo "Установка прервана."; exit 1; fi

if command -v ufw &> /dev/null && sudo ufw status | grep -q 'Status: active'; then
    echo -e "${YELLOW}Обнаружен активный файрвол (ufw). Открываем порты...${NC}"
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    sudo ufw allow 1488/tcp
    sudo ufw allow 8443/tcp
fi

echo -e "${YELLOW}Получаем SSL-сертификаты для всех доменов...${NC}"
sudo certbot certonly --nginx -d "$MAIN_DOMAIN" -d "$DOCS_DOMAIN" -d "$HELP_DOMAIN" --email "$EMAIL" --agree-tos --non-interactive
echo -e "${GREEN}✔ SSL-сертификаты успешно получены для всех доменов.${NC}"

echo -e "\n${CYAN}Шаг 4: Настройка Nginx...${NC}"
read_input "Какой порт вы будете использовать для вебхуков YooKassa? (443 или 8443, рекомендуется 443): " YOOKASSA_PORT_INPUT
YOOKASSA_PORT=${YOOKASSA_PORT_INPUT:-443}

NGINX_ENABLED_FILE="/etc/nginx/sites-enabled/${PROJECT_DIR}.conf"

echo -e "Создаем конфигурацию Nginx для всех сервисов..."
sudo rm -rf /etc/nginx/sites-enabled/default
sudo bash -c "cat > $NGINX_CONF_FILE" <<EOF
# Основной бот
server {
    listen ${YOOKASSA_PORT} ssl http2;
    listen [::]:${YOOKASSA_PORT} ssl http2;
    server_name ${MAIN_DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${MAIN_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${MAIN_DOMAIN}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Прокси на основной бот
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
    listen ${YOOKASSA_PORT} ssl http2;
    listen [::]:${YOOKASSA_PORT} ssl http2;
    server_name ${DOCS_DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${DOCS_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOCS_DOMAIN}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Прокси на пользовательскую документацию
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
    listen ${YOOKASSA_PORT} ssl http2;
    listen [::]:${YOOKASSA_PORT} ssl http2;
    server_name ${HELP_DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${HELP_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${HELP_DOMAIN}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Прокси на админскую документацию
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
EOF

if [ ! -f "$NGINX_ENABLED_FILE" ]; then
    sudo ln -s "$NGINX_CONF_FILE" "$NGINX_ENABLED_FILE"
fi

echo -e "${GREEN}✔ Конфигурация Nginx создана для всех сервисов.${NC}"
echo -e "${YELLOW}Проверяем и перезагружаем Nginx...${NC}"
sudo nginx -t && sudo systemctl reload nginx
