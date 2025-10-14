#!/bin/bash

# Скрипт для автоматического развертывания админской документации
# Запускается при первом развертывании сервера

set -e

echo "🚀 Начинаем развертывание админской документации..."

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Проверка существования папки
if [ ! -d "docs/user-docs/admin" ]; then
    echo -e "${YELLOW}Создаем папку для админской документации...${NC}"
    mkdir -p docs/user-docs/admin
fi

# Проверка существования файлов
if [ ! -f "docs/user-docs/admin/installation.md" ]; then
    echo -e "${GREEN}Создаем файл installation.md...${NC}"
    cp docs/installation.md docs/user-docs/admin/installation.md 2>/dev/null || \
    echo "⚠️  Файл docs/installation.md не найден"
fi

if [ ! -f "docs/user-docs/admin/quickstart.md" ]; then
    echo -e "${GREEN}Создаем файл quickstart.md...${NC}"
    cp codex-docs-admin-quickstart.md docs/user-docs/admin/quickstart.md 2>/dev/null || \
    echo "⚠️  Файл codex-docs-admin-quickstart.md не найден, создаем из шаблона"
fi

if [ ! -f "docs/user-docs/admin/guide.md" ]; then
    echo -e "${GREEN}Создаем файл guide.md...${NC}"
    cp docs/admin-panel-guide.md docs/user-docs/admin/guide.md 2>/dev/null || \
    echo "⚠️  Файл docs/admin-panel-guide.md не найден"
fi

if [ ! -f "docs/user-docs/admin/security.md" ]; then
    echo -e "${GREEN}Создаем файл security.md...${NC}"
    cp docs/security-checklist.md docs/user-docs/admin/security.md 2>/dev/null || \
    echo "⚠️  Файл docs/security-checklist.md не найден"
fi

if [ ! -f "docs/user-docs/admin/api.md" ]; then
    echo -e "${GREEN}Создаем файл api.md...${NC}"
    cp docs/api/README.md docs/user-docs/admin/api.md 2>/dev/null || \
    echo "⚠️  Файл docs/api/README.md не найден"
fi

# Проверка _sidebar.md
if ! grep -q "Админская документация" docs/user-docs/_sidebar.md 2>/dev/null; then
    echo -e "${GREEN}Обновляем _sidebar.md...${NC}"
    # Добавляем раздел админской документации в _sidebar.md
    cat >> docs/user-docs/_sidebar.md << 'EOF'

---

* **📖 Админская документация**
  * [⚡ Быстрый старт](admin/quickstart.md)
  * [📖 Полное руководство](admin/guide.md)
  * [🔒 Чек-лист безопасности](admin/security.md)
  * [🔌 API документация](admin/api.md)

EOF
fi

echo -e "${GREEN}✅ Админская документация успешно развернута!${NC}"
echo -e "${YELLOW}📖 Документация доступна по адресу: http://localhost:3001${NC}"
echo ""
echo "Структура документации:"
echo "  📖 Админская документация"
echo "    ├── 🚀 Установка"
echo "    ├── ⚡ Быстрый старт"
echo "    ├── 📖 Полное руководство"
echo "    ├── 🔒 Чек-лист безопасности"
echo "    └── 🔌 API документация"

