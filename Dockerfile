FROM node:20-alpine AS assets-builder
WORKDIR /build
COPY package*.json ./
RUN npm install --no-audit --no-fund
COPY tailwind.config.js postcss.config.js ./
COPY src/shop_bot/webhook_server/templates ./templates
COPY src/shop_bot/webhook_server/static ./static
RUN npx tailwindcss -i ./static/css/tailwind.input.css -o ./static/css/tw.css --minify

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Устанавливаем зависимости: netcat для healthcheck, docker CLI и docker compose
RUN apt-get update \
    && apt-get install -y netcat-openbsd docker-cli docker-compose \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv .venv
ENV PATH="/app/.venv/bin:$PATH"
COPY . /app/project/
# Копируем собранный CSS из builder-слоя
COPY --from=assets-builder /build/static/css/tw.css /app/project/src/shop_bot/webhook_server/static/css/tw.css
WORKDIR /app/project
RUN pip install --no-cache-dir -e .
# Развертывание админской документации
RUN echo "🚀 Начинаем развертывание админской документации..." && \
    # Создаем папку для админской документации
    mkdir -p docs/user-docs/admin && \
    # Копируем файлы админской документации
    if [ -f "docs/installation.md" ]; then \
        cp docs/installation.md docs/user-docs/admin/installation.md; \
        echo "✅ Создан installation.md"; \
    fi && \
    if [ -f "docs/admin-panel-guide.md" ]; then \
        cp docs/admin-panel-guide.md docs/user-docs/admin/guide.md; \
        echo "✅ Создан guide.md"; \
    fi && \
    if [ -f "docs/security-checklist.md" ]; then \
        cp docs/security-checklist.md docs/user-docs/admin/security.md; \
        echo "✅ Создан security.md"; \
    fi && \
    if [ -f "docs/api/README.md" ]; then \
        cp docs/api/README.md docs/user-docs/admin/api.md; \
        echo "✅ Создан api.md"; \
    fi && \
    # Создаем quickstart.md если его нет
    if [ ! -f "docs/user-docs/admin/quickstart.md" ]; then \
        echo "# ⚡ Быстрый старт" > docs/user-docs/admin/quickstart.md && \
        echo "" >> docs/user-docs/admin/quickstart.md && \
        echo "## 🚀 Первые шаги" >> docs/user-docs/admin/quickstart.md && \
        echo "" >> docs/user-docs/admin/quickstart.md && \
        echo "1. Зайдите в админ-панель" >> docs/user-docs/admin/quickstart.md && \
        echo "2. Настройте Telegram бота" >> docs/user-docs/admin/quickstart.md && \
        echo "3. Добавьте серверы 3x-ui" >> docs/user-docs/admin/quickstart.md && \
        echo "4. Создайте тарифы" >> docs/user-docs/admin/quickstart.md && \
        echo "" >> docs/user-docs/admin/quickstart.md && \
        echo "## 📋 Основные настройки" >> docs/user-docs/admin/quickstart.md && \
        echo "" >> docs/user-docs/admin/quickstart.md && \
        echo "- **Telegram Bot Token**: Получите у @BotFather" >> docs/user-docs/admin/quickstart.md && \
        echo "- **Admin Telegram ID**: Ваш ID в Telegram" >> docs/user-docs/admin/quickstart.md && \
        echo "- **3x-ui серверы**: Добавьте через панель" >> docs/user-docs/admin/quickstart.md && \
        echo "" >> docs/user-docs/admin/quickstart.md && \
        echo "## 🔧 Полезные ссылки" >> docs/user-docs/admin/quickstart.md && \
        echo "" >> docs/user-docs/admin/quickstart.md && \
        echo "- [Полное руководство](guide.md)" >> docs/user-docs/admin/quickstart.md && \
        echo "- [Чек-лист безопасности](security.md)" >> docs/user-docs/admin/quickstart.md && \
        echo "- [API документация](api.md)" >> docs/user-docs/admin/quickstart.md && \
        echo "✅ Создан quickstart.md"; \
    fi && \
    # Обновляем _sidebar.md если нужно
    if [ -f "docs/user-docs/_sidebar.md" ] && ! grep -q "Админская документация" docs/user-docs/_sidebar.md; then \
        echo "" >> docs/user-docs/_sidebar.md && \
        echo "---" >> docs/user-docs/_sidebar.md && \
        echo "" >> docs/user-docs/_sidebar.md && \
        echo "* **📖 Админская документация**" >> docs/user-docs/_sidebar.md && \
        echo "  * [⚡ Быстрый старт](admin/quickstart.md)" >> docs/user-docs/_sidebar.md && \
        echo "  * [📖 Полное руководство](admin/guide.md)" >> docs/user-docs/_sidebar.md && \
        echo "  * [🔒 Чек-лист безопасности](admin/security.md)" >> docs/user-docs/_sidebar.md && \
        echo "  * [🔌 API документация](admin/api.md)" >> docs/user-docs/_sidebar.md && \
        echo "✅ Обновлен _sidebar.md"; \
    fi && \
    echo "✅ Админская документация успешно развернута!"
CMD ["python3", "-m", "shop_bot"]