#!/usr/bin/env bash

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

# Функция проверки занятости порта
check_port() {
    local port=$1
    local service_name=$2
    
    if netstat -tuln 2>/dev/null | grep -q ":$port " || ss -tuln 2>/dev/null | grep -q ":$port "; then
        local process=$(lsof -ti:$port 2>/dev/null | head -1)
        if [ -n "$process" ]; then
            local process_name=$(ps -p $process -o comm= 2>/dev/null || echo "unknown")
            echo -e "${RED}❌ Порт $port занят процессом $process_name (PID: $process)${NC}"
            echo -e "${YELLOW}   Этот порт нужен для $service_name${NC}"
            return 1
        fi
    fi
    echo -e "${GREEN}✅ Порт $port свободен${NC}"
    return 0
}

# Функция открытия порта в firewall
open_firewall_port() {
    local port=$1
    local protocol=${2:-tcp}
    
    # UFW (Ubuntu/Debian)
    if command -v ufw &> /dev/null && sudo ufw status | grep -q 'Status: active'; then
        echo -e "${YELLOW}Открываем порт $port в UFW...${NC}"
        sudo ufw allow $port/$protocol
        echo -e "${GREEN}✔ Порт $port/$protocol открыт в UFW${NC}"
    fi
    
    # iptables (если UFW не используется)
    if command -v iptables &> /dev/null; then
        echo -e "${YELLOW}Открываем порт $port в iptables...${NC}"
        sudo iptables -A INPUT -p $protocol --dport $port -j ACCEPT 2>/dev/null || true
        echo -e "${GREEN}✔ Порт $port/$protocol открыт в iptables${NC}"
    fi
    
    # firewalld (CentOS/RHEL)
    if command -v firewall-cmd &> /dev/null && sudo firewall-cmd --state &> /dev/null; then
        echo -e "${YELLOW}Открываем порт $port в firewalld...${NC}"
        sudo firewall-cmd --permanent --add-port=$port/$protocol
        sudo firewall-cmd --reload
        echo -e "${GREEN}✔ Порт $port/$protocol открыт в firewalld${NC}"
    fi
}

REPO_URL="https://github.com/ukarshiev/dark-maximus.git"
PROJECT_DIR="dark-maximus"
NGINX_CONF_FILE="/etc/nginx/sites-available/${PROJECT_DIR}.conf"

echo -e "${GREEN}--- Запуск скрипта установки/обновления dark-maximus ---${NC}"

if [ -f "$NGINX_CONF_FILE" ]; then
    echo -e "\n${CYAN}Обнаружена существующая конфигурация. Скрипт запущен в режиме обновления.${NC}"

    if [ ! -d "$PROJECT_DIR" ]; then
        echo -e "${RED}Ошибка: Конфигурация Nginx существует, но папка проекта '${PROJECT_DIR}' не найдена!${NC}"
        echo -e "${YELLOW}Возможно, вы переместили или удалили папку. Для исправления удалите файл конфигурации Nginx и запустите установку заново:${NC}"
        echo -e "sudo rm ${NGINX_CONF_FILE}"
        exit 1
    fi

    cd $PROJECT_DIR

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

# Обновление системы (опционально)
echo -e "\n${YELLOW}Обновление системы может занять 10-30 минут. Продолжить? (y/n): ${NC}"
read_input_yn
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${CYAN}Обновление системы...${NC}"
    sudo apt update
    sudo apt upgrade -y
    sudo apt dist-upgrade -y
    sudo apt autoremove -y
    sudo apt autoclean
    echo -e "${GREEN}✔ Система обновлена.${NC}"
    
    echo -e "${YELLOW}⚠️  Возможно, потребуется перезагрузка. Перезагрузить сейчас? (y/n): ${NC}"
    read_input_yn
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Перезагружаем систему...${NC}"
        sudo reboot
    fi
else
    echo -e "${YELLOW}⚠️  Пропускаем обновление системы.${NC}"
fi

# Проверка портов и настройка firewall
echo -e "\n${CYAN}Шаг 0: Проверка портов и настройка firewall...${NC}"

# Проверяем все необходимые порты
echo -e "${YELLOW}Проверяем занятость портов...${NC}"
PORT_CONFLICTS=0

check_port 80 "HTTP (для SSL-сертификатов)" || PORT_CONFLICTS=1
check_port 443 "HTTPS (основной порт)" || PORT_CONFLICTS=1
check_port 1488 "Telegram Bot" || PORT_CONFLICTS=1
check_port 3001 "Пользовательская документация" || PORT_CONFLICTS=1
check_port 3002 "Админская документация" || PORT_CONFLICTS=1

if [ $PORT_CONFLICTS -eq 1 ]; then
    echo -e "\n${RED}⚠️  Обнаружены конфликты портов!${NC}"
    echo -e "${YELLOW}Для решения проблем:${NC}"
    echo -e "1. Остановите конфликтующие сервисы"
    echo -e "2. Или измените порты в конфигурации"
    echo -e "3. Или перезапустите скрипт после решения конфликтов"
    
    read_input_yn "Продолжить установку несмотря на конфликты? (y/n): "
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Установка прервана. Решите конфликты портов и запустите скрипт снова.${NC}"
        exit 1
    fi
fi

# Настраиваем firewall
echo -e "\n${YELLOW}Настраиваем firewall...${NC}"
open_firewall_port 80 tcp
open_firewall_port 443 tcp
open_firewall_port 1488 tcp
open_firewall_port 3001 tcp
open_firewall_port 3002 tcp

echo -e "${GREEN}✔ Проверка портов и настройка firewall завершены.${NC}"

echo -e "\n${CYAN}Шаг 1: Установка системных зависимостей...${NC}"
install_package() {
    if ! command -v $1 &> /dev/null; then
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

for service in docker nginx; do
    if ! sudo systemctl is-active --quiet $service; then
        echo -e "${YELLOW}Сервис $service не запущен. Запускаем и добавляем в автозагрузку...${NC}"
        sudo systemctl start $service
        sudo systemctl enable $service
    fi
done
echo -e "${GREEN}✔ Все системные зависимости установлены.${NC}"

echo -e "\n${CYAN}Шаг 2: Клонирование репозитория...${NC}"
if [ ! -d "$PROJECT_DIR" ]; then
    git clone $REPO_URL
fi
cd $PROJECT_DIR
echo -e "${GREEN}✔ Репозиторий готов.${NC}"

echo -e "\n${CYAN}Шаг 3: Настройка домена и получение SSL-сертификатов...${NC}"

read_input "Введите ваш основной домен (например, myvpn.com): " USER_INPUT_DOMAIN

if [ -z "$USER_INPUT_DOMAIN" ]; then
    echo -e "${RED}Ошибка: Домен не может быть пустым. Установка прервана.${NC}"
    exit 1
fi

DOMAIN=$(echo "$USER_INPUT_DOMAIN" | sed -e 's%^https\?://%%' -e 's%/.*$%%')

# Валидация домена
if [[ "$DOMAIN" != "localhost" && "$DOMAIN" != *"."* ]]; then
    echo -e "${RED}Ошибка: Домен должен содержать точку (например, example.com) или быть localhost${NC}"
    exit 1
fi

read_input "Введите ваш реальный email (для регистрации SSL-сертификатов на него придет письмо от Let's Encrypt): " EMAIL

echo -e "${GREEN}✔ Основной домен: ${DOMAIN}${NC}"

# Формируем поддомены (исправленная логика)
# Берем корневой домен (последние 2 лейбла) для поддоменов
BASE_DOMAIN=$(echo "$DOMAIN" | awk -F. '{ if (NF>=2) print $(NF-1)"."$NF; else print $0 }')

MAIN_DOMAIN="$DOMAIN"
DOCS_DOMAIN="docs.$BASE_DOMAIN"
HELP_DOMAIN="help.$BASE_DOMAIN"

echo -e "${CYAN}Поддомены для документации:${NC}"
echo -e "  - ${YELLOW}${MAIN_DOMAIN}${NC} (основной бот)"
echo -e "  - ${YELLOW}${DOCS_DOMAIN}${NC} (пользовательская документация)"
echo -e "  - ${YELLOW}${HELP_DOMAIN}${NC} (админская документация)"

read_input_yn "Использовать эти поддомены? (y/n): "
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    read_input "Укажите поддомен для панели: " MAIN_DOMAIN
    read_input "Укажите поддомен для пользовательской документации: " DOCS_DOMAIN
    read_input "Укажите поддомен для админской документации: " HELP_DOMAIN
fi

echo -e "${GREEN}✔ Домены для работы:${NC}"
echo -e "  - Основной: ${MAIN_DOMAIN}"
echo -e "  - Документация: ${DOCS_DOMAIN}"
echo -e "  - Админ-документация: ${HELP_DOMAIN}"

SERVER_IP=$(curl -s ifconfig.me || hostname -I | awk '{print $1}')
echo -e "${YELLOW}IP вашего сервера: $SERVER_IP${NC}"

echo -e "${YELLOW}Проверяем DNS-записи...${NC}"

# Проверяем наличие dig, если нет - устанавливаем
if ! command -v dig &> /dev/null; then
    echo -e "${YELLOW}Устанавливаем dnsutils для проверки DNS...${NC}"
    sudo apt update && sudo apt install -y dnsutils
fi

for check_domain in $MAIN_DOMAIN $DOCS_DOMAIN $HELP_DOMAIN; do
    DOMAIN_IP=$(dig +short $check_domain @8.8.8.8 2>/dev/null | tail -n1)
    if [ -n "$DOMAIN_IP" ]; then
        echo -e "  - ${check_domain} → ${DOMAIN_IP}"
        if [ "$SERVER_IP" != "$DOMAIN_IP" ]; then
            echo -e "${RED}⚠️  ВНИМАНИЕ: DNS-запись для ${check_domain} не указывает на IP-адрес этого сервера!${NC}"
        else
            echo -e "${GREEN}✔ DNS-запись для ${check_domain} настроена корректно${NC}"
        fi
    else
        echo -e "  - ${check_domain} → ${RED}Не удалось получить IP-адрес${NC}"
        echo -e "${RED}⚠️  ВНИМАНИЕ: Не удалось проверить DNS-запись для ${check_domain}!${NC}"
    fi
done

read_input_yn "Продолжить установку? (y/n): "
if [[ ! $REPLY =~ ^[Yy]$ ]]; then echo "Установка прервана."; exit 1; fi

# Убираем вопрос про порт YooKassa - используем 443 по умолчанию
YOOKASSA_PORT=443

echo -e "${YELLOW}Получаем SSL-сертификаты для всех доменов...${NC}"

# Создаем временную конфигурацию Nginx для получения сертификатов
echo -e "${YELLOW}Создаем временную конфигурацию Nginx...${NC}"
sudo mkdir -p /var/www/certbot

# Создаем временный конфиг для каждого домена
for domain in $MAIN_DOMAIN $DOCS_DOMAIN $HELP_DOMAIN; do
    sudo tee /etc/nginx/sites-available/${domain}-temp.conf > /dev/null <<EOF
server {
    listen 80;
    server_name ${domain};
    
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    location / {
        return 200 'OK';
        add_header Content-Type text/plain;
    }
}
EOF
    sudo ln -sf /etc/nginx/sites-available/${domain}-temp.conf /etc/nginx/sites-enabled/
done

# Перезагружаем Nginx
sudo nginx -t && sudo systemctl reload nginx

# Получаем один сертификат для всех поддоменов
sudo certbot certonly --webroot -w /var/www/certbot \
    -d $MAIN_DOMAIN -d $DOCS_DOMAIN -d $HELP_DOMAIN \
    --email $EMAIL --agree-tos --non-interactive

# Определяем базовое имя сертификата (первый домен)
CERT_NAME=$MAIN_DOMAIN

# Удаляем временные конфиги
for domain in $MAIN_DOMAIN $DOCS_DOMAIN $HELP_DOMAIN; do
    sudo rm -f /etc/nginx/sites-enabled/${domain}-temp.conf
    sudo rm -f /etc/nginx/sites-available/${domain}-temp.conf
done

echo -e "${GREEN}✔ SSL-сертификаты успешно получены для всех доменов.${NC}"

echo -e "\n${CYAN}Шаг 4: Настройка Nginx...${NC}"

NGINX_ENABLED_FILE="/etc/nginx/sites-enabled/${PROJECT_DIR}.conf"

echo -e "Создаем конфигурацию Nginx для всех сервисов..."
sudo rm -rf /etc/nginx/sites-enabled/default
sudo bash -c "cat > $NGINX_CONF_FILE" <<EOF
# Основной бот
server {
    listen ${YOOKASSA_PORT} ssl http2;
    listen [::]:${YOOKASSA_PORT} ssl http2;
    server_name ${MAIN_DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${CERT_NAME}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${CERT_NAME}/privkey.pem;
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

    ssl_certificate /etc/letsencrypt/live/${CERT_NAME}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${CERT_NAME}/privkey.pem;
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

    ssl_certificate /etc/letsencrypt/live/${CERT_NAME}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${CERT_NAME}/privkey.pem;
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

# HTTP редиректы на HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name ${MAIN_DOMAIN} ${DOCS_DOMAIN} ${HELP_DOMAIN};
    return 301 https://\$server_name\$request_uri;
}
EOF

if [ ! -f "$NGINX_ENABLED_FILE" ]; then
    sudo ln -s $NGINX_CONF_FILE $NGINX_ENABLED_FILE
fi

echo -e "${GREEN}✔ Конфигурация Nginx создана для всех сервисов.${NC}"
echo -e "${YELLOW}Проверяем и перезагружаем Nginx...${NC}"
sudo nginx -t && sudo systemctl reload nginx

echo -e "\n${CYAN}Шаг 5: Сборка и запуск Docker-контейнера...${NC}"
if [ "$(sudo docker-compose ps -q)" ]; then
    sudo docker-compose down
fi
sudo docker-compose up -d --build

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
echo -e "\n${YELLOW}1. Основной бот и админ-панель:${NC}"
echo -e "   - ${GREEN}https://${MAIN_DOMAIN}:${YOOKASSA_PORT}/login${NC}"
echo -e "\n${YELLOW}2. Пользовательская документация:${NC}"
echo -e "   - ${GREEN}https://${DOCS_DOMAIN}:${YOOKASSA_PORT}${NC}"
echo -e "\n${YELLOW}3. Админская документация (Codex.docs):${NC}"
echo -e "   - ${GREEN}https://${HELP_DOMAIN}:${YOOKASSA_PORT}${NC}"
echo -e "\n${CYAN}🔐 Данные для первого входа в админ-панель:${NC}"
echo -e "   - Логин:   ${GREEN}admin${NC}"
echo -e "   - Пароль:  ${GREEN}admin${NC}"
echo -e "\n${RED}⚠️  ВАЖНО - ПЕРВЫЕ ШАГИ:${NC}"
echo -e "1. Войдите в админ-панель и ${RED}немедленно смените логин и пароль${NC}."
echo -e "2. На странице 'Настройки' введите:"
echo -e "   • Токен Telegram бота"
echo -e "   • Username бота (без @)"
echo -e "   • Ваш Telegram ID"
echo -e "3. Нажмите 'Сохранить все настройки' и затем 'Запустить Бота'."
echo -e "\n${CYAN}🔗 Настройка платежных систем:${NC}"
echo -e "\n${YELLOW}YooKassa webhook URL:${NC}"
echo -e "   ${GREEN}https://${MAIN_DOMAIN}:${YOOKASSA_PORT}/yookassa-webhook${NC}"
echo -e "\n${YELLOW}CryptoBot webhook URL:${NC}"
echo -e "   ${GREEN}https://${MAIN_DOMAIN}:${YOOKASSA_PORT}/cryptobot-webhook${NC}"
echo -e "\n${GREEN}📖 Админская документация (в админ-панели):${NC}"
echo -e "   - ${YELLOW}https://${HELP_DOMAIN}:${YOOKASSA_PORT}/installation${NC}"
echo -e "   - ${YELLOW}https://${HELP_DOMAIN}:${YOOKASSA_PORT}/quickstart${NC}"
echo -e "   - ${YELLOW}https://${HELP_DOMAIN}:${YOOKASSA_PORT}/guide${NC}"
echo -e "   - ${YELLOW}https://${HELP_DOMAIN}:${YOOKASSA_PORT}/security${NC}"
echo -e "   - ${YELLOW}https://${HELP_DOMAIN}:${YOOKASSA_PORT}/api${NC}"
echo -e "\n"