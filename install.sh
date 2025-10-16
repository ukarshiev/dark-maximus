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

# Выбираем docker compose v1/v2 как массив
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

# Функция для создания SSL конфигурации
create_ssl_config() {
    echo -e "${YELLOW}Создаем SSL-конфигурацию...${NC}"
    
    # Создаем директорию для SSL-конфигурации
    sudo mkdir -p /etc/letsencrypt

    # Создаем файл options-ssl-nginx.conf
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

    # Создаем файл ssl-dhparams.pem
    if [ ! -f "/etc/letsencrypt/ssl-dhparams.pem" ]; then
        echo -e "${YELLOW}Генерируем DH параметры (это может занять несколько минут)...${NC}"
        sudo openssl dhparam -out /etc/letsencrypt/ssl-dhparams.pem 2048
        echo -e "${GREEN}✔ ssl-dhparams.pem создан.${NC}"
    else
        echo -e "${GREEN}✔ ssl-dhparams.pem уже существует.${NC}"
    fi
}

# Функция для проверки DNS
check_dns_records() {
    local main_domain="$1"
    local docs_domain="$2"
    local help_domain="$3"
    
    echo -e "${YELLOW}Проверяем DNS-записи (A-записи)...${NC}"
    
    SERVER_IP="$(curl -s4 https://api.ipify.org || hostname -I | awk '{print $1}')"
    echo -e "${YELLOW}IP вашего сервера (IPv4): $SERVER_IP${NC}"
    
    # Функция проверки домена
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

# Функция для надежной замены в файлах
ensure_replace() {
    local pat="$1" rep="$2" file="$3"
    local before; before=$(grep -Eoc "$pat" "$file" || true)
    sed -i -E "s|$pat|$rep|g" "$file"
    local after; after=$(grep -Eoc "$pat" "$file" || true)
    [ "$before" -gt 0 ] || { echo -e "${RED}Не найден шаблон: $pat в $file${NC}"; exit 1; }
    echo -e "${GREEN}✔ Заменено $before совпадений: $pat${NC}"
}

# Функция для обновления nginx конфигурации
update_nginx_config() {
    local main_domain="$1"
    local docs_domain="$2"
    local help_domain="$3"
    
    echo -e "${YELLOW}Обновляем конфигурацию nginx-прокси...${NC}"
    
    # Заменяем домены только если это новая установка (есть шаблоны)
    if grep -q "panel\.dark-maximus\.com" nginx/nginx.conf; then
        ensure_replace 'panel\.dark-maximus\.com' "$main_domain" nginx/nginx.conf
        ensure_replace 'docs\.dark-maximus\.com' "$docs_domain" nginx/nginx.conf
        ensure_replace 'help\.dark-maximus\.com' "$help_domain" nginx/nginx.conf
        echo -e "${GREEN}✔ Домены заменены в nginx.conf.${NC}"
    else
        echo -e "${YELLOW}⚠️  Домены уже настроены, пропускаем замену доменов.${NC}"
    fi
    
    # Настраиваем пути к Let's Encrypt сертификатам (отдельные для каждого домена)
    echo -e "${YELLOW}Настраиваем пути к Let's Encrypt сертификатам...${NC}"
    
    # Настраиваем для panel домена
    sed -i "/server_name.*${main_domain}/,/}/ s|ssl_certificate .*|ssl_certificate /etc/letsencrypt/live/${main_domain}.crt;|g" nginx/nginx.conf
    sed -i "/server_name.*${main_domain}/,/}/ s|ssl_certificate_key .*|ssl_certificate_key /etc/letsencrypt/live/${main_domain}.key;|g" nginx/nginx.conf
    
    # Настраиваем для docs домена
    sed -i "/server_name.*${docs_domain}/,/}/ s|ssl_certificate .*|ssl_certificate /etc/letsencrypt/live/${docs_domain}.crt;|g" nginx/nginx.conf
    sed -i "/server_name.*${docs_domain}/,/}/ s|ssl_certificate_key .*|ssl_certificate_key /etc/letsencrypt/live/${docs_domain}.key;|g" nginx/nginx.conf
    
    # Настраиваем для help домена
    sed -i "/server_name.*${help_domain}/,/}/ s|ssl_certificate .*|ssl_certificate /etc/letsencrypt/live/${help_domain}.crt;|g" nginx/nginx.conf
    sed -i "/server_name.*${help_domain}/,/}/ s|ssl_certificate_key .*|ssl_certificate_key /etc/letsencrypt/live/${help_domain}.key;|g" nginx/nginx.conf
    
    # Проверяем, что замена прошла успешно
    if grep -q "/etc/letsencrypt/live/" nginx/nginx.conf; then
        echo -e "${GREEN}✔ Пути к Let's Encrypt сертификатам обновлены.${NC}"
    else
        echo -e "${RED}❌ Ошибка: не удалось заменить пути к сертификатам!${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✔ Конфигурация nginx-прокси обновлена.${NC}"
}

# Функция для ожидания освобождения порта
wait_for_port_free() {
    local port="$1"
    echo -e "${YELLOW}Ждем освобождения порта $port...${NC}"
    for i in {1..20}; do 
        ss -ltn "( sport = :$port )" | grep -q ":$port" || break
        sleep 1
    done
    echo -e "${GREEN}✔ Порт $port свободен.${NC}"
}

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
    create_ssl_config

    # Извлекаем домены из nginx конфигурации
    if [ -f "$NGINX_CONF_FILE" ]; then
        EXTRACTED_DOMAIN=$(grep -o 'server_name [^;]*' "$NGINX_CONF_FILE" | head -1 | awk '{print $2}' | sed 's/panel\.//')
        if [ -n "$EXTRACTED_DOMAIN" ]; then
            MAIN_DOMAIN="panel.$EXTRACTED_DOMAIN"
            DOCS_DOMAIN="docs.$EXTRACTED_DOMAIN" 
            HELP_DOMAIN="help.$EXTRACTED_DOMAIN"
        fi
    fi

    # Исправление для nounset - используем параметр по умолчанию
    if [ -z "${MAIN_DOMAIN:-}" ]; then
        MAIN_DOMAIN="localhost:1488"
        DOCS_DOMAIN="localhost:3001"
        HELP_DOMAIN="localhost:3002"
        PROTOCOL="http"
    else
        PROTOCOL="https"
    fi

    echo -e "${GREEN}✔ SSL-конфигурация проверена.${NC}"

    # В режиме обновления тоже обновляем nginx.conf если домен сменился
    echo -e "\n${CYAN}Шаг 2.6: Обновление nginx конфигурации...${NC}"
    update_nginx_config "$MAIN_DOMAIN" "$DOCS_DOMAIN" "$HELP_DOMAIN"

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

# Проверяем DNS записи
check_dns_records "$MAIN_DOMAIN" "$DOCS_DOMAIN" "$HELP_DOMAIN"

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

echo -e "${YELLOW}Выпускаем Let's Encrypt SSL сертификаты (standalone, порт 80)...${NC}"
# Останавливаем все сервисы, которые могут занимать порт 80
sudo systemctl stop nginx 2>/dev/null || true
sudo "${DC[@]}" stop nginx-proxy 2>/dev/null || true

# Ждем освобождения порта 80 до 20 секунд
wait_for_port_free 80

# Выпускаем отдельный Let's Encrypt сертификат для каждого домена
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

echo -e "\n${CYAN}Шаг 4: Создание SSL-конфигурации...${NC}"
create_ssl_config

echo -e "\n${CYAN}Шаг 5: Настройка Docker nginx-прокси...${NC}"
echo -e "Настраиваем nginx-прокси контейнер для использования Let's Encrypt сертификатов..."

# Обновляем nginx конфигурацию
update_nginx_config "$MAIN_DOMAIN" "$DOCS_DOMAIN" "$HELP_DOMAIN"

echo -e "${GREEN}✔ Docker nginx-прокси настроен для использования Let's Encrypt сертификатов.${NC}"

# Создаем папку ssl-certs и копируем сертификаты
echo -e "\n${CYAN}Шаг 6: Подготовка SSL сертификатов для Docker...${NC}"
mkdir -p ssl-certs/live

# Копируем сертификаты из Let's Encrypt в локальную папку
if [ -f "/etc/letsencrypt/live/${MAIN_DOMAIN}/fullchain.pem" ]; then
    cp "/etc/letsencrypt/live/${MAIN_DOMAIN}/fullchain.pem" "ssl-certs/live/${MAIN_DOMAIN}.crt"
    cp "/etc/letsencrypt/live/${MAIN_DOMAIN}/privkey.pem" "ssl-certs/live/${MAIN_DOMAIN}.key"
    echo -e "${GREEN}✔ Сертификаты для ${MAIN_DOMAIN} скопированы.${NC}"
fi

if [ -f "/etc/letsencrypt/live/${DOCS_DOMAIN}/fullchain.pem" ]; then
    cp "/etc/letsencrypt/live/${DOCS_DOMAIN}/fullchain.pem" "ssl-certs/live/${DOCS_DOMAIN}.crt"
    cp "/etc/letsencrypt/live/${DOCS_DOMAIN}/privkey.pem" "ssl-certs/live/${DOCS_DOMAIN}.key"
    echo -e "${GREEN}✔ Сертификаты для ${DOCS_DOMAIN} скопированы.${NC}"
fi

if [ -f "/etc/letsencrypt/live/${HELP_DOMAIN}/fullchain.pem" ]; then
    cp "/etc/letsencrypt/live/${HELP_DOMAIN}/fullchain.pem" "ssl-certs/live/${HELP_DOMAIN}.crt"
    cp "/etc/letsencrypt/live/${HELP_DOMAIN}/privkey.pem" "ssl-certs/live/${HELP_DOMAIN}.key"
    echo -e "${GREEN}✔ Сертификаты для ${HELP_DOMAIN} скопированы.${NC}"
fi

echo -e "\n${CYAN}Шаг 7: Сборка и запуск Docker-контейнеров...${NC}"
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

echo -e "\n${CYAN}Шаг 8: Настройка автообновления сертификатов...${NC}"
# Сохраняем абсолютный путь к проекту
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
echo -e "  - ${YELLOW}Панель управления:${NC} ${GREEN}https://${MAIN_DOMAIN}${NC}"
echo -e "  - ${YELLOW}Пользовательская документация:${NC} ${GREEN}https://${DOCS_DOMAIN}${NC}"
echo -e "  - ${YELLOW}Админская документация:${NC} ${GREEN}https://${HELP_DOMAIN}${NC}"
echo -e "\n${GREEN}✅ Используются доверенные Let's Encrypt SSL сертификаты${NC}"
echo -e "✅ Автообновление сертификатов настроено"
echo -e "✅ Мягкий reload nginx при обновлении сертификатов"
echo -e "✅ Динамическое определение имени контейнера nginx-proxy"
echo -e "✅ Надежное ожидание освобождения порта 80"

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

echo -e "\n${YELLOW}📄 Конфигурация nginx (ssl_certificate):${NC}"
grep -A1 "ssl_certificate " nginx/nginx.conf | grep -E "(ssl_certificate|server_name)" | while read line; do
    if [[ $line =~ server_name ]]; then
        echo -e "   ${line}"
    elif [[ $line =~ ssl_certificate ]]; then
        echo -e "      ${line}"
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
echo -e "\n${YELLOW}💡 На будущее: рассмотрите переход на webroot-метод для обновления сертификатов без даунтайма${NC}"
echo -e "\n"
