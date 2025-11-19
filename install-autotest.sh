#!/usr/bin/env bash
# Autotest Setup Script for Dark Maximus
# Usage: curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install-autotest.sh | sudo bash

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
    echo -e "\n${RED}Ошибка на строке $1. Установка автотестов прервана.${NC}"
    exit 1
}
trap 'handle_error $LINENO' ERR

# Выбираем docker compose v1/v2
set_dc_command() {
    if docker compose version >/dev/null 2>&1; then
        DC=("docker" "compose")
        DC_SERVICE_CMD="$(command -v docker) compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        DC=("docker-compose")
        DC_SERVICE_CMD="$(command -v docker-compose)"
    else
        echo -e "${RED}❌ Docker Compose не найден!${NC}"
        echo -e "${YELLOW}Убедитесь, что Docker и Docker Compose установлены.${NC}"
        exit 1
    fi
}

set_dc_command

echo -e "${GREEN}===============================================${NC}"
echo -e "${GREEN}   📊 Dark Maximus - Установка автотестов    ${NC}"
echo -e "${GREEN}===============================================${NC}"

# Проверяем права root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Запустите скрипт с правами root: sudo bash <(curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install-autotest.sh)${NC}"
    exit 1
fi

# Проверяем, что мы в папке проекта, если нет - переходим в /opt/dark-maximus
if [ ! -f "docker-compose.yml" ]; then
    if [ -f "/opt/dark-maximus/docker-compose.yml" ]; then
        echo -e "${YELLOW}⚠️  Переходим в папку проекта /opt/dark-maximus${NC}"
        cd /opt/dark-maximus
        PROJECT_DIR="/opt/dark-maximus"
    else
        echo -e "${RED}❌ Файл docker-compose.yml не найден!${NC}"
        echo -e "${YELLOW}Убедитесь, что вы находитесь в папке проекта Dark Maximus.${NC}"
        echo -e "${YELLOW}Если проект не установлен, сначала запустите:${NC}"
        echo -e "${CYAN}curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install.sh | sudo bash -s -- domain.com${NC}"
        exit 1
    fi
else
    PROJECT_DIR="$(pwd)"
fi

echo -e "${GREEN}✔ Рабочая директория: ${PROJECT_DIR}${NC}"

# Проверяем наличие Docker
if ! command -v docker >/dev/null 2>&1; then
    echo -e "${RED}❌ Docker не установлен!${NC}"
    echo -e "${YELLOW}Установите Docker перед запуском этого скрипта.${NC}"
    exit 1
fi

# Проверяем наличие Dockerfile.tests
if [ ! -f "Dockerfile.tests" ]; then
    echo -e "${RED}❌ Файл Dockerfile.tests не найден!${NC}"
    echo -e "${YELLOW}Убедитесь, что проект полностью склонирован из репозитория.${NC}"
    exit 1
fi

# Константы портов
readonly PORT_ALLURE_SERVICE=50004
readonly PORT_ALLURE_HOMEPAGE=50005

# Функция проверки наличия сервиса
service_exists() {
    local service_name="$1"
    grep -q "^  ${service_name}:" docker-compose.yml 2>/dev/null
}

# Функция создания директорий с проверкой
create_directories() {
    local dirs=("$@")
    
    for dir in "${dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            chmod 755 "$dir"
            echo -e "${GREEN}✔ Создана директория: $dir${NC}"
        else
            echo -e "${YELLOW}⚠️  Директория уже существует: $dir${NC}"
        fi
    done
}

# Функция проверки наличия файлов
check_required_files() {
    local missing_files=()
    
    # Проверяем необходимые файлы
    [ ! -f "Dockerfile.tests" ] && missing_files+=("Dockerfile.tests")
    [ ! -f "apps/allure-homepage/Dockerfile" ] && missing_files+=("apps/allure-homepage/Dockerfile")
    
    if [ ${#missing_files[@]} -gt 0 ]; then
        echo -e "${RED}❌ Отсутствуют необходимые файлы:${NC}"
        for file in "${missing_files[@]}"; do
            echo -e "${RED}   - $file${NC}"
        done
        exit 1
    fi
}

# Функция безопасного добавления сервисов в docker-compose.yml
add_services_to_compose() {
    local backup_file="docker-compose.yml.backup.$(date +%Y%m%d-%H%M%S)"
    echo -e "${YELLOW}Создаем резервную копию: $backup_file${NC}"
    cp docker-compose.yml "$backup_file"
    
    # Проверяем, какие сервисы нужно добавить
    local services_to_add=()
    ! service_exists "autotest" && services_to_add+=("autotest")
    ! service_exists "allure-service" && services_to_add+=("allure-service")
    ! service_exists "allure-homepage" && services_to_add+=("allure-homepage")
    
    if [ ${#services_to_add[@]} -eq 0 ]; then
        echo -e "${GREEN}✔ Все сервисы автотестов уже существуют в docker-compose.yml${NC}"
        rm -f "$backup_file"
        return 0
    fi
    
    echo -e "${YELLOW}Добавляем сервисы: ${services_to_add[*]}${NC}"
    
    # Используем Python для безопасного добавления сервисов
    python3 << 'PYTHON_SCRIPT'
import yaml
import sys

try:
    with open('docker-compose.yml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    if not config or 'services' not in config:
        print("❌ Ошибка: некорректная структура docker-compose.yml", file=sys.stderr)
        sys.exit(1)
    
    services = config.get('services', {})
    services_added = []
    
    # Добавляем autotest если его нет
    if 'autotest' not in services:
        services['autotest'] = {
            'build': {
                'context': '.',
                'dockerfile': 'Dockerfile.tests'
            },
            'container_name': 'dark-maximus-autotest',
            'volumes': [
                './tests:/app/tests',
                './src:/app/src',
                './apps:/app/apps',
                './allure-results:/app/allure-results',
                './allure-report:/app/allure-report',
                './.env:/app/.env:ro'
            ],
            'networks': ['dark-maximus-network']
        }
        services_added.append('autotest')
    
    # Добавляем allure-service если его нет (должен быть перед allure-homepage)
    if 'allure-service' not in services:
        services['allure-service'] = {
            'image': 'frankescobar/allure-docker-service:latest',
            'container_name': 'dark-maximus-allure',
            'expose': ['5050'],
            'ports': ['127.0.0.1:50004:5050'],
            'volumes': [
                './allure-results:/app/allure-docker-api/static/projects/default/results',
                './allure-report:/app/allure-report',
                './allure-reports:/app/allure-docker-api/static/projects',
                './allure-categories.json:/app/allure-categories.json'
            ],
            'environment': [
                'CHECK_RESULTS_EVERY_SECONDS=3',
                'KEEP_HISTORY=1',
                'KEEP_HISTORY_LATEST=100',
                'ALLURE_PUBLIC_URL=http://localhost:50005',
                'URL_PREFIX=/allure-docker-service'
            ],
            'networks': ['dark-maximus-network']
        }
        services_added.append('allure-service')
    
    # Добавляем allure-homepage если его нет (после allure-service)
    if 'allure-homepage' not in services:
        services['allure-homepage'] = {
            'build': {
                'context': './apps/allure-homepage',
                'dockerfile': 'Dockerfile'
            },
            'container_name': 'dark-maximus-allure-homepage',
            'restart': 'unless-stopped',
            'ports': ['127.0.0.1:50005:50005'],
            'volumes': [
                './sessions-allure:/app/sessions',
                './users.db:/app/users.db',
                './src:/app/src'
            ],
            'environment': [
                'ALLURE_SERVICE_URL=http://allure-service:5050',
                'PORT=50005',
                'FLASK_SECRET_KEY=${FLASK_SECRET_KEY}'
            ],
            'healthcheck': {
                'test': ['CMD-SHELL', 'nc -z localhost 50005 || exit 1'],
                'interval': '30s',
                'timeout': '10s',
                'retries': 3,
                'start_period': '10s'
            },
            'networks': ['dark-maximus-network'],
            'depends_on': ['allure-service']
        }
        services_added.append('allure-homepage')
    
    config['services'] = services
    
    with open('docker-compose.yml', 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    if services_added:
        print(f'✓ Добавлены сервисы: {", ".join(services_added)}')
    else:
        print('✓ Все сервисы уже существуют')
        
except Exception as e:
    print(f'❌ Ошибка при добавлении сервисов: {e}', file=sys.stderr)
    sys.exit(1)
PYTHON_SCRIPT
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Ошибка при добавлении сервисов, восстанавливаем из резервной копии${NC}"
        cp "$backup_file" docker-compose.yml
        exit 1
    fi
    
    # Проверяем валидность YAML после модификации
    if ! ${DC[@]} config > /dev/null 2>&1; then
        echo -e "${RED}❌ Ошибка валидации docker-compose.yml после добавления сервисов${NC}"
        echo -e "${YELLOW}Восстанавливаем из резервной копии...${NC}"
        cp "$backup_file" docker-compose.yml
        exit 1
    fi
    
    echo -e "${GREEN}✔ Сервисы успешно добавлены в docker-compose.yml${NC}"
}

echo -e "\n${CYAN}Шаг 1: Проверка необходимых файлов...${NC}"

# Проверяем наличие необходимых файлов
check_required_files

echo -e "${GREEN}✔ Все необходимые файлы найдены${NC}"

echo -e "\n${CYAN}Шаг 2: Создание директорий для результатов Allure...${NC}"

# Создаем директории для результатов Allure
create_directories \
    "${PROJECT_DIR}/allure-results" \
    "${PROJECT_DIR}/allure-report" \
    "${PROJECT_DIR}/allure-reports" \
    "${PROJECT_DIR}/sessions-allure"

# Создаем allure-categories.json если его нет
if [ ! -f "${PROJECT_DIR}/allure-categories.json" ]; then
    echo -e "${YELLOW}Создаем шаблон allure-categories.json...${NC}"
    cat > "${PROJECT_DIR}/allure-categories.json" << 'EOF'
{
  "categories": []
}
EOF
    chmod 644 "${PROJECT_DIR}/allure-categories.json"
    echo -e "${GREEN}✔ Создан шаблон allure-categories.json${NC}"
else
    echo -e "${GREEN}✔ Файл allure-categories.json уже существует${NC}"
fi

echo -e "${GREEN}✔ Директории и файлы готовы${NC}"

echo -e "\n${CYAN}Шаг 3: Добавление сервисов автотестов в docker-compose.yml...${NC}"

# Добавляем сервисы в docker-compose.yml
add_services_to_compose

echo -e "\n${CYAN}Шаг 4: Сборка образов для автотестов...${NC}"

# Определяем, какие сервисы нужно собрать
SERVICES_TO_BUILD=()
if service_exists "autotest"; then
    SERVICES_TO_BUILD+=("autotest")
fi
if service_exists "allure-homepage"; then
    SERVICES_TO_BUILD+=("allure-homepage")
fi

# Собираем образы
if [ ${#SERVICES_TO_BUILD[@]} -gt 0 ]; then
    echo -e "${YELLOW}Сборка образов: ${SERVICES_TO_BUILD[*]}...${NC}"
    for service in "${SERVICES_TO_BUILD[@]}"; do
        echo -e "${YELLOW}Сборка $service...${NC}"
        ${DC[@]} build "$service" || {
            echo -e "${RED}❌ Ошибка при сборке образа $service${NC}"
            exit 1
        }
    done
    echo -e "${GREEN}✔ Образы успешно собраны${NC}"
else
    echo -e "${GREEN}✔ Образы уже собраны${NC}"
fi

echo -e "\n${CYAN}Шаг 5: Запуск сервисов автотестов...${NC}"

# Запускаем все три сервиса: autotest, allure-service, allure-homepage
echo -e "${YELLOW}Запуск сервисов autotest, allure-service, allure-homepage...${NC}"
${DC[@]} up -d autotest allure-service allure-homepage || {
    echo -e "${RED}❌ Ошибка при запуске сервисов${NC}"
    ${DC[@]} logs autotest allure-service allure-homepage
    exit 1
}

echo -e "${GREEN}✔ Сервисы запущены${NC}"

echo -e "\n${CYAN}Шаг 6: Ожидание готовности Allure Homepage...${NC}"

# Ожидаем готовности Allure Homepage (на порту 50005)
echo -e "${YELLOW}Проверка доступности Allure Homepage на localhost:${PORT_ALLURE_HOMEPAGE}...${NC}"
timeout 60 bash -c "until nc -z 127.0.0.1 ${PORT_ALLURE_HOMEPAGE}; do sleep 2; done" || {
    echo -e "${YELLOW}⚠️  Allure Homepage не запустился в течение 1 минуты${NC}"
    echo -e "${YELLOW}   Проверьте логи: ${DC[@]} logs allure-homepage${NC}"
    ${DC[@]} logs allure-homepage
    exit 1
}

echo -e "${GREEN}✔ Allure Homepage доступен${NC}"

# Проверяем статус контейнеров
echo -e "\n${CYAN}Статус контейнеров:${NC}"
${DC[@]} ps autotest allure-service allure-homepage

echo -e "\n${GREEN}===============================================${NC}"
echo -e "${GREEN}   🎉 Установка автотестов завершена! 🎉      ${NC}"
echo -e "${GREEN}===============================================${NC}"

echo -e "\n${BLUE}📊 Доступные сервисы:${NC}"
echo -e "1. Allure Homepage (локально):"
echo -e "   - Веб-интерфейс отчетов: ${GREEN}http://localhost:${PORT_ALLURE_HOMEPAGE}/allure-docker-service/projects/default/reports/latest/index.html${NC}"
echo -e "   - API документация (Swagger UI): ${GREEN}http://localhost:${PORT_ALLURE_HOMEPAGE}${NC}"
echo -e "   - API проектов: ${GREEN}http://localhost:${PORT_ALLURE_HOMEPAGE}/allure-docker-service/projects${NC}"

echo -e "\n2. Контейнер автотестов:"
echo -e "   - Контейнер: ${GREEN}dark-maximus-autotest${NC}"
echo -e "   - Для запуска тестов: ${YELLOW}docker compose exec autotest pytest${NC}"

echo -e "\n${BLUE}🔧 Полезные команды:${NC}"
echo -e "- Запустить тесты: ${YELLOW}cd ${PROJECT_DIR} && ${DC[@]} exec autotest pytest${NC}"
echo -e "- Запустить только unit-тесты: ${YELLOW}cd ${PROJECT_DIR} && ${DC[@]} exec autotest pytest tests/unit/ -m unit${NC}"
echo -e "- Запустить только интеграционные тесты: ${YELLOW}cd ${PROJECT_DIR} && ${DC[@]} exec autotest pytest tests/integration/ -m integration${NC}"
echo -e "- Остановить сервисы: ${YELLOW}cd ${PROJECT_DIR} && ${DC[@]} stop autotest allure-service${NC}"
echo -e "- Запустить сервисы: ${YELLOW}cd ${PROJECT_DIR} && ${DC[@]} start autotest allure-service${NC}"
echo -e "- Просмотреть логи: ${YELLOW}cd ${PROJECT_DIR} && ${DC[@]} logs -f autotest allure-service${NC}"

echo -e "\n${BLUE}📋 Следующие шаги:${NC}"
echo -e "1. Откройте веб-интерфейс Allure отчетов в браузере:"
echo -e "   ${GREEN}http://localhost:${PORT_ALLURE_HOMEPAGE}/allure-docker-service/projects/default/reports/latest/index.html${NC}"
echo -e "   Или API документацию (Swagger UI): ${GREEN}http://localhost:${PORT_ALLURE_HOMEPAGE}${NC}"
echo -e "2. Запустите тесты для генерации отчетов:"
echo -e "   ${YELLOW}cd ${PROJECT_DIR} && ${DC[@]} exec autotest pytest${NC}"
echo -e "3. Для внешнего доступа через HTTPS настройте SSL:"
echo -e "   ${YELLOW}curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/ssl-install.sh | sudo bash -s -- domain.com${NC}"
echo -e "   После этого будет доступно: ${GREEN}https://tests.domain.com/allure-docker-service/projects/default/reports/latest/index.html${NC}"

echo -e "\n${BLUE}📁 Директории:${NC}"
echo -e "- Результаты тестов: ${YELLOW}${PROJECT_DIR}/allure-results/${NC}"
echo -e "- Сгенерированные отчеты: ${YELLOW}${PROJECT_DIR}/allure-report/${NC}"
echo -e "- Отчеты Allure Service: ${YELLOW}${PROJECT_DIR}/allure-reports/${NC}"
echo -e "- Сессии Allure: ${YELLOW}${PROJECT_DIR}/sessions-allure/${NC}"

echo -e "\n${GREEN}Автотесты готовы к работе!${NC}"

