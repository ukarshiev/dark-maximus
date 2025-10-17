#!/usr/bin/env bash
# SSL Setup Script for Dark Maximus
# Downloads and runs setup-ssl.sh from GitHub

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

echo -e "${GREEN}===============================================${NC}"
echo -e "${GREEN}      🔒 Dark Maximus - SSL Setup            ${NC}"
echo -e "${GREEN}===============================================${NC}"

# Проверяем права root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Запустите скрипт с правами root: sudo bash <(curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/ssl-install.sh)${NC}"
    exit 1
fi

# Проверяем, что мы в папке проекта, если нет - переходим в /opt/dark-maximus
if [ ! -f "docker-compose.yml" ]; then
    if [ -f "/opt/dark-maximus/docker-compose.yml" ]; then
        echo -e "${YELLOW}⚠️  Переходим в папку проекта /opt/dark-maximus${NC}"
        cd /opt/dark-maximus
    else
        echo -e "${RED}❌ Файл docker-compose.yml не найден!${NC}"
        echo -e "${YELLOW}Убедитесь, что вы находитесь в папке проекта Dark Maximus.${NC}"
        echo -e "${YELLOW}Если проект не установлен, сначала запустите:${NC}"
        echo -e "${CYAN}curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install.sh | sudo bash${NC}"
        exit 1
    fi
fi

# Проверяем, что nginx конфигурация существует
if [ ! -f "/etc/nginx/sites-available/dark-maximus" ]; then
    echo -e "${RED}❌ Nginx конфигурация не найдена!${NC}"
    echo -e "${YELLOW}Убедитесь, что основная установка была завершена успешно.${NC}"
    echo -e "${YELLOW}Запустите сначала:${NC}"
    echo -e "${CYAN}curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install.sh | sudo bash${NC}"
    exit 1
fi

echo -e "${GREEN}✔ Проверки пройдены. Загружаем SSL скрипт...${NC}"

# Скачиваем и запускаем setup-ssl.sh
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/setup-ssl.sh -o setup-ssl.sh
chmod +x setup-ssl.sh

echo -e "${GREEN}✔ SSL скрипт загружен. Запускаем настройку SSL...${NC}"
echo -e "${YELLOW}⚠️  Убедитесь, что DNS A-записи для всех доменов настроены!${NC}"

# Запускаем setup-ssl.sh с передачей всех аргументов или переменной окружения
if [ -n "$DOMAIN" ]; then
    ./setup-ssl.sh "$DOMAIN"
else
    ./setup-ssl.sh "$@"
fi

# Удаляем временный файл
rm -f setup-ssl.sh

echo -e "\n${GREEN}🎉 SSL настройка завершена!${NC}"
