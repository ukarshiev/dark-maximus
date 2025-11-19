# ============================================
# Makefile для Dark Maximus
# Автоматизация команд разработки
# ============================================

.PHONY: help install dev build test clean docker-build docker-up docker-down docker-logs docker-restart

# Цвета для вывода
GREEN  := $(shell tput -Txterm setaf 2)
YELLOW := $(shell tput -Txterm setaf 3)
RESET  := $(shell tput -Txterm sgr0)

help: ## Показать справку по командам
	@echo "$(GREEN)Доступные команды:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(RESET) %s\n", $$1, $$2}'

# ============================================
# Установка зависимостей
# ============================================

install: ## Установить все зависимости (Python + Node.js)
	@echo "$(GREEN)Установка Python зависимостей...$(RESET)"
	pip install -e .
	@echo "$(GREEN)Установка Node.js зависимостей...$(RESET)"
	npm install
	@echo "$(GREEN)✓ Зависимости установлены$(RESET)"

install-python: ## Установить только Python зависимости
	@echo "$(GREEN)Установка Python зависимостей...$(RESET)"
	pip install -e .
	@echo "$(GREEN)✓ Python зависимости установлены$(RESET)"

install-node: ## Установить только Node.js зависимости
	@echo "$(GREEN)Установка Node.js зависимостей...$(RESET)"
	npm install
	@echo "$(GREEN)✓ Node.js зависимости установлены$(RESET)"

# ============================================
# Разработка
# ============================================

dev: ## Запустить в режиме разработки (watch CSS)
	@echo "$(GREEN)Запуск watch-режима для CSS...$(RESET)"
	npm run dev:css

build: ## Собрать CSS (production)
	@echo "$(GREEN)Сборка CSS...$(RESET)"
	npm run build:css
	@echo "$(GREEN)✓ CSS собран$(RESET)"

# ============================================
# Тестирование
# ============================================

test: ## Запустить тесты
	@echo "$(GREEN)Запуск тестов...$(RESET)"
	pytest tests/ -v

# ============================================
# Очистка
# ============================================

clean: ## Очистить временные файлы
	@echo "$(GREEN)Очистка временных файлов...$(RESET)"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name "*.log" -delete 2>/dev/null || true
	rm -rf temp/ 2>/dev/null || true
	rm -rf .pytest_cache/ 2>/dev/null || true
	rm -rf .coverage htmlcov/ 2>/dev/null || true
	@echo "$(GREEN)✓ Временные файлы удалены$(RESET)"

clean-all: clean ## Очистить всё включая node_modules и venv
	@echo "$(GREEN)Полная очистка...$(RESET)"
	rm -rf node_modules/ 2>/dev/null || true
	rm -rf venv/ 2>/dev/null || true
	rm -rf .venv/ 2>/dev/null || true
	@echo "$(GREEN)✓ Полная очистка завершена$(RESET)"

# ============================================
# Docker
# ============================================

docker-build: ## Собрать Docker образ
	@echo "$(GREEN)Сборка Docker образа...$(RESET)"
	docker compose build bot
	@echo "$(GREEN)✓ Docker образ собран$(RESET)"

docker-up: ## Запустить Docker контейнеры
	@echo "$(GREEN)Запуск Docker контейнеров...$(RESET)"
	docker compose up -d
	@echo "$(GREEN)✓ Docker контейнеры запущены$(RESET)"

docker-down: ## Остановить Docker контейнеры
	@echo "$(YELLOW)Остановка Docker контейнеров...$(RESET)"
	docker compose down
	@echo "$(GREEN)✓ Docker контейнеры остановлены$(RESET)"

docker-restart: ## Перезапустить Docker контейнеры
	@echo "$(YELLOW)Перезапуск Docker контейнеров...$(RESET)"
	docker compose restart bot
	@echo "$(GREEN)✓ Docker контейнеры перезапущены$(RESET)"

docker-logs: ## Показать логи Docker контейнера
	docker compose logs -f bot

docker-rebuild: ## Пересобрать и перезапустить контейнер
	@echo "$(GREEN)Пересборка и перезапуск контейнера...$(RESET)"
	docker compose down
	docker compose build bot
	docker compose up -d
	@echo "$(GREEN)✓ Контейнер пересобран и перезапущен$(RESET)"

# ============================================
# База данных
# ============================================

db-backup: ## Создать резервную копию базы данных
	@echo "$(GREEN)Создание резервной копии базы данных...$(RESET)"
	mkdir -p backups
	cp users.db backups/users_$(shell date +%Y%m%d_%H%M%S).db
	@echo "$(GREEN)✓ Резервная копия создана$(RESET)"

# ============================================
# Проверка
# ============================================

check: ## Проверить код (linting)
	@echo "$(GREEN)Проверка кода...$(RESET)"
	@echo "$(GREEN)=== Python linting (pylint) ===$(RESET)"
	PYTHONIOENCODING=utf-8 pylint src/shop_bot/ --disable=C0111,C0103 --fail-under=7.0 || true
	@echo "$(GREEN)=== Python formatting (black) ===$(RESET)"
	black --check src/shop_bot/ || true
	@echo "$(GREEN)=== Jinja2 templates (djlint) ===$(RESET)"
	djlint --check src/shop_bot/webhook_server/templates/ apps/user-cabinet/templates/ || true
	@echo "$(GREEN)=== JavaScript (eslint) ===$(RESET)"
	npx eslint apps/user-cabinet/static/js/ src/shop_bot/webhook_server/static/js/ apps/web-interface/server.js || true
	@echo "$(GREEN)=== HTML (htmlhint) ===$(RESET)"
	npx htmlhint apps/web-interface/src/*.html || true
	@echo "$(GREEN)=== CSS (stylelint) ===$(RESET)"
	npx stylelint "src/shop_bot/webhook_server/static/css/*.css" "apps/user-cabinet/static/css/*.css" --ignore-path .stylelintignore || true
	@echo "$(GREEN)✓ Проверка завершена$(RESET)"

format: ## Отформатировать код
	@echo "$(GREEN)Форматирование кода...$(RESET)"
	black src/shop_bot/
	@echo "$(GREEN)✓ Код отформатирован$(RESET)"

# ============================================
# Информация
# ============================================

info: ## Показать информацию о проекте
	@echo "$(GREEN)Информация о проекте:$(RESET)"
	@echo "  Python версия: $$(python --version 2>/dev/null || echo 'не установлен')"
	@echo "  Node версия: $$(node --version 2>/dev/null || echo 'не установлен')"
	@echo "  Docker версия: $$(docker --version 2>/dev/null || echo 'не установлен')"
	@echo "  Docker Compose версия: $$(docker compose version 2>/dev/null || echo 'не установлен')"

