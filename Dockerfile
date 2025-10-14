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
RUN python3 -m venv .venv
ENV PATH="/app/.venv/bin:$PATH"
COPY . /app/project/
# Копируем собранный CSS из builder-слоя
COPY --from=assets-builder /build/static/css/tw.css /app/project/src/shop_bot/webhook_server/static/css/tw.css
WORKDIR /app/project
RUN pip install --no-cache-dir -e .
# Развертывание админской документации
RUN if [ -f "setup-admin-docs.sh" ]; then \
    chmod +x setup-admin-docs.sh && \
    bash setup-admin-docs.sh; \
    fi
CMD ["python3", "-m", "shop_bot"]