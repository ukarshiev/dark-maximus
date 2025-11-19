#!/usr/bin/env bash
# Скрипт для валидации скриптов установки
# Использование: ./scripts/validate-scripts.sh

set -o errexit
set -o pipefail
set -o nounset

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Переходим в корень проекта
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${GREEN}===============================================${NC}"
echo -e "${GREEN}   Валидация скриптов установки               ${NC}"
echo -e "${GREEN}===============================================${NC}"

ERRORS=0

# Проверка ShellCheck
echo -e "\n${YELLOW}Проверка ShellCheck...${NC}"
if command -v shellcheck >/dev/null 2>&1; then
    echo -e "${GREEN}✔ ShellCheck установлен${NC}"
    
    SCRIPTS=("install.sh" "install-autotest.sh" "ssl-install.sh")
    
    for script in "${SCRIPTS[@]}"; do
        if [ -f "$script" ]; then
            echo -e "${YELLOW}Проверка $script...${NC}"
            if shellcheck "$script"; then
                echo -e "${GREEN}✔ $script прошел проверку ShellCheck${NC}"
            else
                echo -e "${RED}❌ $script не прошел проверку ShellCheck${NC}"
                ((ERRORS++))
            fi
        else
            echo -e "${YELLOW}⚠️  $script не найден, пропускаем${NC}"
        fi
    done
else
    echo -e "${YELLOW}⚠️  ShellCheck не установлен, пропускаем проверку${NC}"
    echo -e "${YELLOW}   Установите: sudo apt-get install -y shellcheck${NC}"
fi

# Проверка yamllint для docker-compose.yml
echo -e "\n${YELLOW}Проверка yamllint...${NC}"
if command -v yamllint >/dev/null 2>&1; then
    echo -e "${GREEN}✔ yamllint установлен${NC}"
    
    if [ -f "docker-compose.yml" ]; then
        echo -e "${YELLOW}Проверка docker-compose.yml...${NC}"
        if yamllint docker-compose.yml; then
            echo -e "${GREEN}✔ docker-compose.yml прошел проверку yamllint${NC}"
        else
            echo -e "${RED}❌ docker-compose.yml не прошел проверку yamllint${NC}"
            ((ERRORS++))
        fi
    else
        echo -e "${YELLOW}⚠️  docker-compose.yml не найден${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  yamllint не установлен, пропускаем проверку${NC}"
    echo -e "${YELLOW}   Установите: pip install yamllint${NC}"
fi

# Проверка docker compose config
echo -e "\n${YELLOW}Проверка docker compose config...${NC}"
if command -v docker >/dev/null 2>&1; then
    if docker compose version >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1; then
        if [ -f "docker-compose.yml" ]; then
            echo -e "${YELLOW}Валидация docker-compose.yml через docker compose config...${NC}"
            if docker compose config >/dev/null 2>&1 || docker-compose config >/dev/null 2>&1; then
                echo -e "${GREEN}✔ docker-compose.yml валиден${NC}"
            else
                echo -e "${RED}❌ docker-compose.yml невалиден${NC}"
                ((ERRORS++))
            fi
        else
            echo -e "${YELLOW}⚠️  docker-compose.yml не найден${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Docker Compose не найден${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Docker не найден${NC}"
fi

# Итоги
echo -e "\n${GREEN}===============================================${NC}"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}   ✅ Все проверки пройдены успешно!          ${NC}"
    echo -e "${GREEN}===============================================${NC}"
    exit 0
else
    echo -e "${RED}   ❌ Найдено ошибок: $ERRORS                  ${NC}"
    echo -e "${GREEN}===============================================${NC}"
    exit 1
fi

