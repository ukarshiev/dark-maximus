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
    echo -e "\n${GREEN}📖 Админская документация доступна по адресу:${NC}"
    echo -e "  - ${YELLOW}http://localhost:3001/admin/installation${NC}"
    echo -e "  - ${YELLOW}http://localhost:3001/admin/quickstart${NC}"
    echo -e "  - ${YELLOW}http://localhost:3001/admin/guide${NC}"
    echo -e "  - ${YELLOW}http://localhost:3001/admin/security${NC}"
    echo -e "  - ${YELLOW}http://localhost:3001/admin/api${NC}"
    echo -e "\n"

    exit 0
fi

echo -e "\n${YELLOW}Существующая конфигурация не найдена. Запускается первоначальная установка...${NC}"

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

read_input "Введите ваш домен (например, my-vpn-shop.com): " USER_INPUT_DOMAIN

if [ -z "$USER_INPUT_DOMAIN" ]; then
    echo -e "${RED}Ошибка: Домен не может быть пустым. Установка прервана.${NC}"
    exit 1
fi

DOMAIN=$(echo "$USER_INPUT_DOMAIN" | sed -e 's%^https\?://%%' -e 's%/.*$%%')

read_input "Введите ваш email (для регистрации SSL-сертификатов Let's Encrypt): " EMAIL

echo -e "${GREEN}✔ Домен для работы: ${DOMAIN}${NC}"
SERVER_IP=$(curl -s ifconfig.me || hostname -I | awk '{print $1}')
DOMAIN_IP=$(dig +short $DOMAIN @8.8.8.8 | tail -n1)
echo -e "${YELLOW}IP вашего сервера: $SERVER_IP${NC}"
echo -e "${YELLOW}IP, на который указывает домен '$DOMAIN': $DOMAIN_IP${NC}"

if [ "$SERVER_IP" != "$DOMAIN_IP" ]; then
    echo -e "${RED}ВНИМАНИЕ: DNS-запись для домена $DOMAIN не указывает на IP-адрес этого сервера!${NC}"
    read_input_yn "Продолжить установку? (y/n): "
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then echo "Установка прервана."; exit 1; fi
fi

if command -v ufw &> /dev/null && sudo ufw status | grep -q 'Status: active'; then
    echo -e "${YELLOW}Обнаружен активный файрвол (ufw). Открываем порты...${NC}"
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    sudo ufw allow 1488/tcp
    sudo ufw allow 8443/tcp
fi

if [ -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    echo -e "${GREEN}✔ SSL-сертификаты для домена $DOMAIN уже существуют.${NC}"
else
    echo -e "${YELLOW}Получаем SSL-сертификаты для $DOMAIN...${NC}"
    sudo certbot --nginx -d $DOMAIN --email $EMAIL --agree-tos --non-interactive --redirect
    echo -e "${GREEN}✔ SSL-сертификаты успешно получены.${NC}"
fi

echo -e "\n${CYAN}Шаг 4: Настройка Nginx...${NC}"
read_input "Какой порт вы будете использовать для вебхуков YooKassa? (443 или 8443, рекомендуется 443): " YOOKASSA_PORT_INPUT
YOOKASSA_PORT=${YOOKASSA_PORT_INPUT:-443}

NGINX_ENABLED_FILE="/etc/nginx/sites-enabled/${PROJECT_DIR}.conf"

echo -e "Создаем конфигурацию Nginx..."
sudo rm -rf /etc/nginx/sites-enabled/default
sudo bash -c "cat > $NGINX_CONF_FILE" <<EOF
server {
    listen ${YOOKASSA_PORT} ssl http2;
    listen [::]:${YOOKASSA_PORT} ssl http2;
    server_name ${DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
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
EOF

if [ ! -f "$NGINX_ENABLED_FILE" ]; then
    sudo ln -s $NGINX_CONF_FILE $NGINX_ENABLED_FILE
fi

echo -e "${GREEN}✔ Конфигурация Nginx создана.${NC}"
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
echo -e "\nВеб-панель доступна по адресу:"
echo -e "  - ${YELLOW}https://${DOMAIN}:${YOOKASSA_PORT}/login${NC}"
echo -e "\nДанные для первого входа:"
echo -e "  - Логин:   ${CYAN}admin${NC}"
echo -e "  - Пароль:  ${CYAN}admin${NC}"
echo -e "\n${RED}ПЕРВЫЕ ШАГИ:${NC}"
echo -e "1. Войдите в панель и ${RED}сразу же смените логин и пароль${NC}."
echo -e "2. На странице 'Настройки' введите ваш Telegram токен, username бота и ваш Telegram ID."
echo -e "3. Нажмите 'Сохранить' и затем 'Запустить Бота'."
echo -e "\n${CYAN}Не забудьте указать URL для вебхуков в YooKassa:${NC}"
echo -e "  - ${YELLOW}https://${DOMAIN}:${YOOKASSA_PORT}/yookassa-webhook${NC}"
echo -e "\n${GREEN}📖 Админская документация доступна по адресу:${NC}"
echo -e "  - ${YELLOW}https://${DOMAIN}:${YOOKASSA_PORT}/admin/installation${NC}"
echo -e "  - ${YELLOW}https://${DOMAIN}:${YOOKASSA_PORT}/admin/quickstart${NC}"
echo -e "  - ${YELLOW}https://${DOMAIN}:${YOOKASSA_PORT}/admin/guide${NC}"
echo -e "  - ${YELLOW}https://${DOMAIN}:${YOOKASSA_PORT}/admin/security${NC}"
echo -e "  - ${YELLOW}https://${DOMAIN}:${YOOKASSA_PORT}/admin/api${NC}"
echo -e "\n"
