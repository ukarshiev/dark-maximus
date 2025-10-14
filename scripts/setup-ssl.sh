#!/bin/bash
# Скрипт настройки SSL для dark-maximus и 3x-ui
# Использование: ./setup-ssl.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Настройка SSL для dark-maximus ===${NC}\n"

# Проверка прав
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Запустите скрипт с sudo${NC}"
    exit 1
fi

# Ввод доменов
read -p "Введите домен для бота (например, bot.example.com): " BOT_DOMAIN
read -p "Введите домен для 3x-ui панели (например, panel.example.com): " PANEL_DOMAIN
read -p "Введите email для Let's Encrypt: " EMAIL

# Проверка DNS
echo -e "\n${YELLOW}Проверка DNS записей...${NC}"
BOT_IP=$(dig +short $BOT_DOMAIN @8.8.8.8 | tail -n1)
PANEL_IP=$(dig +short $PANEL_DOMAIN @8.8.8.8 | tail -n1)
SERVER_IP=$(curl -s ifconfig.me)

if [ "$BOT_IP" != "$SERVER_IP" ]; then
    echo -e "${YELLOW}Предупреждение: $BOT_DOMAIN указывает на $BOT_IP, а ваш сервер имеет IP $SERVER_IP${NC}"
    read -p "Продолжить? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Установка certbot
echo -e "\n${GREEN}Установка Certbot...${NC}"
apt update
apt install -y certbot python3-certbot-nginx

# Временная конфигурация Nginx для получения сертификатов
echo -e "\n${GREEN}Создание временной конфигурации Nginx...${NC}"

# Конфиг для бота
cat > /etc/nginx/sites-available/bot-temp.conf <<EOF
server {
    listen 80;
    server_name $BOT_DOMAIN;
    
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
}
EOF

# Конфиг для панели
cat > /etc/nginx/sites-available/panel-temp.conf <<EOF
server {
    listen 80;
    server_name $PANEL_DOMAIN;
    
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
}
EOF

ln -sf /etc/nginx/sites-available/bot-temp.conf /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/panel-temp.conf /etc/nginx/sites-enabled/

mkdir -p /var/www/certbot
nginx -t && systemctl reload nginx

# Получение сертификатов
echo -e "\n${GREEN}Получение SSL сертификатов...${NC}"
certbot certonly --webroot -w /var/www/certbot \
    -d $BOT_DOMAIN \
    --email $EMAIL \
    --agree-tos \
    --non-interactive

certbot certonly --webroot -w /var/www/certbot \
    -d $PANEL_DOMAIN \
    --email $EMAIL \
    --agree-tos \
    --non-interactive

# Создание production конфигурации
echo -e "\n${GREEN}Создание production конфигурации...${NC}"

# Конфиг для бота
cat > /etc/nginx/sites-available/bot.conf <<EOF
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $BOT_DOMAIN;

    ssl_certificate /etc/letsencrypt/live/$BOT_DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$BOT_DOMAIN/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Заголовки безопасности
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;

    location / {
        proxy_pass http://127.0.0.1:1488;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}

server {
    listen 80;
    listen [::]:80;
    server_name $BOT_DOMAIN;
    return 301 https://\$server_name\$request_uri;
}
EOF

# Конфиг для 3x-ui панели
cat > /etc/nginx/sites-available/panel.conf <<EOF
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $PANEL_DOMAIN;

    ssl_certificate /etc/letsencrypt/live/$PANEL_DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$PANEL_DOMAIN/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Заголовки безопасности
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    location / {
        proxy_pass http://127.0.0.1:2053;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket поддержка
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

server {
    listen 80;
    listen [::]:80;
    server_name $PANEL_DOMAIN;
    return 301 https://\$server_name\$request_uri;
}
EOF

# Применение конфигурации
rm /etc/nginx/sites-enabled/bot-temp.conf
rm /etc/nginx/sites-enabled/panel-temp.conf
ln -sf /etc/nginx/sites-available/bot.conf /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/panel.conf /etc/nginx/sites-enabled/

nginx -t && systemctl reload nginx

# Настройка автообновления
echo -e "\n${GREEN}Настройка автообновления сертификатов...${NC}"
(crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -

# Инструкции для 3x-ui
echo -e "\n${GREEN}=== Настройка завершена! ===${NC}\n"
echo -e "${YELLOW}Следующие шаги:${NC}"
echo -e "1. Зайдите в 3x-ui панель: https://$PANEL_DOMAIN"
echo -e "2. В настройках 3x-ui установите:"
echo -e "   - Listen IP: 127.0.0.1"
echo -e "   - Port: 2053"
echo -e "   - TLS: Отключить (SSL обрабатывает Nginx)"
echo -e "\n3. Для бота панель доступна: https://$BOT_DOMAIN"
echo -e "\n4. Сертификаты будут автоматически обновляться каждый день в 12:00"
echo -e "\n${GREEN}Готово!${NC}"
