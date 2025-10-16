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

# Проверяем и настраиваем Docker Compose
check_docker_compose() {
    # Проверяем Docker Compose v2 (плагин) - приоритетный
    if docker compose version &> /dev/null; then
        DC_BIN="docker compose"
        echo -e "${GREEN}✔ Docker Compose v2 (плагин) работает.${NC}"
        return
    fi
    
    # Проверяем Docker Compose v1 (отдельная утилита)
    if command -v docker-compose &> /dev/null && docker-compose --version &> /dev/null; then
        DC_BIN="docker-compose"
        echo -e "${GREEN}✔ Docker Compose v1 работает.${NC}"
        return
    fi
    
    # Если ничего не работает, устанавливаем Docker Compose v1 как fallback
    echo -e "${YELLOW}Docker Compose не найден. Устанавливаем Docker Compose v1...${NC}"
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    DC_BIN="docker-compose"
    echo -e "${GREEN}✔ Docker Compose v1 установлен.${NC}"
}

check_docker_compose

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

    echo -e "\n${CYAN}Шаг 1: Проверка docker-compose...${NC}"
    check_docker_compose
    
    echo -e "\n${CYAN}Шаг 2: Обновление кода из репозитория Git...${NC}"
    git pull
    echo -e "${GREEN}✔ Код успешно обновлен.${NC}"

    echo -e "\n${CYAN}Шаг 2.5: Проверка SSL-конфигурации...${NC}"
    # Проверяем и создаем SSL-файлы если их нет
    if [ ! -f "/etc/letsencrypt/options-ssl-nginx.conf" ]; then
        echo -e "${YELLOW}Создаем отсутствующий файл SSL-конфигурации...${NC}"
        sudo bash -c "cat > /etc/letsencrypt/options-ssl-nginx.conf" << 'EOF'
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-SHA256:ECDHE-RSA-AES256-SHA384;
ssl_prefer_server_ciphers off;
EOF
    fi

    if [ ! -f "/etc/letsencrypt/ssl-dhparams.pem" ]; then
        echo -e "${YELLOW}Создаем отсутствующие DH параметры...${NC}"
        sudo openssl dhparam -out /etc/letsencrypt/ssl-dhparams.pem 2048
    fi

    # Извлекаем домены из nginx конфигурации
    if [ -f "$NGINX_CONF_FILE" ]; then
        EXTRACTED_DOMAIN=$(grep -o 'server_name [^;]*' "$NGINX_CONF_FILE" | head -1 | awk '{print $2}' | sed 's/panel\.//')
        if [ -n "$EXTRACTED_DOMAIN" ]; then
            MAIN_DOMAIN="panel.$EXTRACTED_DOMAIN"
            DOCS_DOMAIN="docs.$EXTRACTED_DOMAIN" 
            HELP_DOMAIN="help.$EXTRACTED_DOMAIN"
        fi
    fi

    # Если не удалось извлечь домены, используем localhost
    if [ -z "$MAIN_DOMAIN" ]; then
        MAIN_DOMAIN="localhost:1488"
        DOCS_DOMAIN="localhost:3001"
        HELP_DOMAIN="localhost:3002"
        PROTOCOL="http"
    else
        PROTOCOL="https"
    fi

    echo -e "${GREEN}✔ SSL-конфигурация проверена.${NC}"

    echo -e "\n${CYAN}Шаг 3: Перезапуск Nginx с SSL-конфигурацией...${NC}"
    sudo nginx -t && sudo systemctl reload nginx
    echo -e "${GREEN}✔ Nginx перезапущен с SSL-конфигурацией.${NC}"

    echo -e "\n${CYAN}Шаг 4: Пересборка и перезапуск Docker-контейнеров...${NC}"
    sudo ${DC_BIN} down --remove-orphans
    sudo ${DC_BIN} up -d --build

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
    echo -e "   - ${GREEN}${PROTOCOL}://${MAIN_DOMAIN}/login${NC}"
    echo -e "\n${YELLOW}2. Пользовательская документация:${NC}"
    echo -e "   - ${GREEN}${PROTOCOL}://${DOCS_DOMAIN}${NC}"
    echo -e "\n${YELLOW}3. Админская документация (Codex.docs):${NC}"
    echo -e "   - ${GREEN}${PROTOCOL}://${HELP_DOMAIN}${NC}"
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

# Устанавливаем Docker CE (официальная версия)
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

# Запускаем только Docker (nginx будет в контейнере)
if ! sudo systemctl is-active --quiet docker; then
    echo -e "${YELLOW}Сервис docker не запущен. Запускаем и добавляем в автозагрузку...${NC}"
    sudo systemctl start docker
    sudo systemctl enable docker
fi

# Останавливаем системный nginx, если он запущен (конфликт с Docker nginx-прокси)
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

echo -e "\n${CYAN}Шаг 4: Создание SSL-конфигурации...${NC}"
echo -e "Создаем необходимые файлы SSL-конфигурации..."

# Создаем директорию для SSL-конфигурации
sudo mkdir -p /etc/letsencrypt

# Создаем файл options-ssl-nginx.conf
sudo bash -c "cat > /etc/letsencrypt/options-ssl-nginx.conf" << 'EOF'
# This file contains important security parameters. If you modify this file
# manually, Certbot will be unable to automatically provide future security
# updates. Instead, Certbot will print a message to the log when it encounters
# a configuration that would be updated.

ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-SHA256:ECDHE-RSA-AES256-SHA384;
ssl_prefer_server_ciphers off;
EOF

# Создаем файл ssl-dhparams.pem
echo -e "${YELLOW}Генерируем DH параметры (это может занять несколько минут)...${NC}"
sudo openssl dhparam -out /etc/letsencrypt/ssl-dhparams.pem 2048

echo -e "${GREEN}✔ SSL-конфигурация создана.${NC}"

echo -e "\n${CYAN}Шаг 5: Настройка Docker nginx-прокси...${NC}"
echo -e "Настраиваем nginx-прокси контейнер для маршрутизации поддоменов..."

# Создаем SSL сертификаты для nginx-прокси
echo -e "${YELLOW}Создаем SSL сертификаты для nginx-прокси...${NC}"
mkdir -p nginx/ssl
if [ ! -f "nginx/ssl/cert.pem" ] || [ ! -f "nginx/ssl/key.pem" ]; then
    echo -e "${YELLOW}Генерируем самоподписанные SSL сертификаты...${NC}"
    docker run --rm -v "$(pwd)/nginx/ssl:/ssl" alpine sh -c "apk add --no-cache openssl && cd /ssl && openssl genrsa -out key.pem 2048 && openssl req -new -x509 -key key.pem -out cert.pem -days 365 -subj '/C=RU/ST=Moscow/L=Moscow/O=DarkMaximus/OU=IT/CN=${DOMAIN}'"
    echo -e "${GREEN}✔ SSL сертификаты созданы.${NC}"
else
    echo -e "${GREEN}✔ SSL сертификаты уже существуют.${NC}"
fi

# Обновляем nginx.conf с правильными доменами
echo -e "${YELLOW}Обновляем конфигурацию nginx-прокси...${NC}"
sed -i "s/panel\.dark-maximus\.com/${MAIN_DOMAIN}/g" nginx/nginx.conf
sed -i "s/docs\.dark-maximus\.com/${DOCS_DOMAIN}/g" nginx/nginx.conf
sed -i "s/help\.dark-maximus\.com/${HELP_DOMAIN}/g" nginx/nginx.conf

echo -e "${GREEN}✔ Docker nginx-прокси настроен.${NC}"

echo -e "\n${CYAN}Шаг 6: Сборка и запуск Docker-контейнеров...${NC}"
if [ -n "$(sudo ${DC_BIN} ps -q || true)" ]; then
    sudo ${DC_BIN} down || true
fi
sudo ${DC_BIN} up -d --build
echo -e "${GREEN}✔ Контейнеры запущены.${NC}"

# Проверяем, что nginx-прокси запустился
echo -e "${YELLOW}Проверяем статус nginx-прокси...${NC}"
sleep 5
if sudo ${DC_BIN} ps | grep -q "nginx-proxy.*Up"; then
    echo -e "${GREEN}✔ nginx-прокси запущен и работает.${NC}"
else
    echo -e "${RED}❌ Ошибка запуска nginx-прокси!${NC}"
    echo -e "${YELLOW}Логи nginx-прокси:${NC}"
    sudo ${DC_BIN} logs nginx-proxy
    exit 1
fi

echo -e "\n${CYAN}Шаг 7: Развертывание админской документации...${NC}"
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
echo -e "  - ${YELLOW}Панель управления:${NC} ${GREEN}https://${MAIN_DOMAIN}${NC}"
echo -e "  - ${YELLOW}Пользовательская документация:${NC} ${GREEN}https://${DOCS_DOMAIN}${NC}"
echo -e "  - ${YELLOW}Админская документация:${NC} ${GREEN}https://${HELP_DOMAIN}${NC}"
echo -e "\n${YELLOW}⚠️  Примечание: Используются самоподписанные SSL сертификаты для тестирования.${NC}"
echo -e "   Для продакшена настройте Let's Encrypt сертификаты.${NC}"
echo -e "\n${CYAN}🔐 Данные для первого входа в админ-панель:${NC}"
echo -e "   • Логин:   ${GREEN}admin${NC}"
echo -e "   • Пароль:  ${GREEN}admin${NC}"
echo -e "\n${CYAN}🔗 Вебхуки:${NC}"
echo -e "   • YooKassa:  ${GREEN}https://${MAIN_DOMAIN}/yookassa-webhook${NC}"
echo -e "   • CryptoBot: ${GREEN}https://${MAIN_DOMAIN}/cryptobot-webhook${NC}"
echo -e "\n"
