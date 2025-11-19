#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Личный кабинет пользователя Dark Maximus
Веб-сервис для пошаговой настройки VPN
"""

import os
import sys
import logging
import requests
from pathlib import Path
from functools import wraps
from flask import Flask, render_template, request, session, redirect, url_for, jsonify, abort
from datetime import datetime, timezone
from collections import defaultdict
import time

# Определяем путь к проекту в зависимости от окружения
if os.path.exists("/app/project"):
    # Docker окружение
    PROJECT_ROOT = Path("/app/project")
else:
    # Локальная разработка
    PROJECT_ROOT = Path(__file__).parent.parent.parent

# Добавляем путь к проекту для импорта модулей
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Импортируем функции работы с БД
from shop_bot.data_manager.database import (
    get_key_by_id,
    get_user_keys,
    run_migration,
    validate_permanent_token,
    get_all_settings
)

# Импортируем StructuredLogger для логирования
try:
    from shop_bot.utils.logger import get_logger
    app_logger = get_logger("user_cabinet")
except ImportError:
    # Fallback если logger недоступен
    app_logger = None

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')


def _build_knowledge_base_url(settings: dict) -> tuple[str, str]:
    """Определяем базовый URL базы знаний и ссылку на инструкции."""
    codex_docs_domain = (settings.get('codex_docs_domain') or '').strip()
    global_domain = (settings.get('global_domain') or '').strip()

    if codex_docs_domain:
        base_url = codex_docs_domain.rstrip('/')
        if not base_url.startswith(('http://', 'https://')):
            base_url = f'https://{base_url}'
    elif global_domain:
        temp_url = global_domain.rstrip('/')
        if not temp_url.startswith(('http://', 'https://')):
            temp_url = f'https://{temp_url}'
        base_url = f'{temp_url}:50002'
    else:
        base_url = 'http://localhost:50002'

    setup_url = f"{base_url.rstrip('/')}/setup"
    return base_url, setup_url


def _fetch_ip_information() -> tuple[dict | None, str | None]:
    """Получение сведений об IP-адресе с внешних сервисов."""
    providers = [
        ("https://ipapi.co/json/", "ipapi"),
        ("https://ipwho.is/", "ipwhois"),
    ]

    for url, provider in providers:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                logger.warning("IP provider %s returned status %s", provider, response.status_code)
                continue

            data = response.json()
            if provider == "ipapi" and data.get("error"):
                logger.warning("IP provider ipapi responded with error: %s", data.get("reason", "unknown"))
                continue

            if provider == "ipwhois" and data.get("success") is False:
                logger.warning("IP provider ipwhois responded with error: %s", data.get("message", "unknown"))
                continue

            if provider == "ipapi":
                formatted = {
                    "ip": data.get("ip"),
                    "country": data.get("country_name") or data.get("country"),
                    "city": data.get("city"),
                    "provider": data.get("org") or data.get("org_name") or data.get("asn"),
                }
            else:
                connection = data.get("connection") or {}
                formatted = {
                    "ip": data.get("ip"),
                    "country": data.get("country") or data.get("country_name"),
                    "city": data.get("city"),
                    "provider": connection.get("isp") or connection.get("org"),
                }

            if any(formatted.values()):
                return formatted, None
        except requests.RequestException as exc:
            logger.warning("IP provider %s request failed: %s", provider, exc)
        except ValueError as exc:
            logger.warning("Failed to parse IP provider %s response: %s", provider, exc)

    return None, "Сервис IP-определения временно недоступен."

# Запускаем миграцию БД при старте приложения
try:
    logger.info("Running database migration...")
    run_migration()
    logger.info("Database migration completed")
except Exception as e:
    logger.error(f"Failed to run database migration: {e}", exc_info=True)

# Rate limiting: храним время последнего запроса по IP
rate_limit_store = defaultdict(list)
RATE_LIMIT_REQUESTS = 10  # Максимум запросов
RATE_LIMIT_WINDOW = 60  # Окно в секундах (1 минута)


def rate_limit(f):
    """Декоратор для rate limiting по IP"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        # Очищаем старые записи
        current_time = time.time()
        rate_limit_store[client_ip] = [
            req_time for req_time in rate_limit_store[client_ip]
            if current_time - req_time < RATE_LIMIT_WINDOW
        ]
        
        # Проверяем лимит
        if len(rate_limit_store[client_ip]) >= RATE_LIMIT_REQUESTS:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            abort(429)
        
        # Добавляем текущий запрос
        rate_limit_store[client_ip].append(current_time)
        
        return f(*args, **kwargs)
    return decorated_function


@app.route('/health')
def health():
    """Healthcheck endpoint для Docker"""
    return jsonify({"status": "ok"}), 200


@app.route('/api/ip-info')
@rate_limit
def ip_info():
    """Возвращает данные об IP-адресе клиента."""
    ip_data, error_message = _fetch_ip_information()
    if ip_data:
        return jsonify({"status": "ok", "data": ip_data})

    return jsonify({
        "status": "error",
        "message": error_message or "Не удалось получить информацию об IP-адресе."
    }), 502


def require_token(f):
    """Декоратор для проверки токена доступа"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = kwargs.get('token') or request.args.get('token') or session.get('token')
        
        if not token:
            logger.warning("Token validation failed: token not provided")
            return render_template('error.html', 
                                 error_title="Ссылка не предоставлена",
                                 error_message="Для доступа к личному кабинету необходима ссылка доступа."), 401
        
        # Логируем попытку валидации (первые 10 символов для безопасности)
        token_preview = token[:10] + "..." if len(token) > 10 else token
        logger.info(f"Validating token: {token_preview}")
        
        try:
            # Валидируем токен
            token_data = validate_permanent_token(token)
            
            if not token_data:
                logger.warning(f"Token validation failed: token {token_preview} not found")
                return render_template('error.html',
                                     error_title="Ссылка недействительна",
                                     error_message="Ссылка устарела или указана с ошибкой. Скопируйте ссылку заново из Telegram-бота и попробуйте ещё раз."), 403
            
            # Проверяем, не был ли ключ удален
            if token_data.get('key_deleted'):
                logger.warning(f"Token validated but key_id={token_data.get('key_id')} was deleted")
                return render_template('error.html',
                                     error_title="Ключ удален",
                                     error_message="Ссылка действительна, но ключ был удален. Обратитесь в поддержку или создайте новый ключ."), 404
            
            # Логируем успешную валидацию
            logger.info(f"Token validated successfully: user_id={token_data.get('user_id')}, key_id={token_data.get('key_id')}")
            
            # Сохраняем данные в сессию
            session['token'] = token
            session['user_id'] = token_data['user_id']
            session['key_id'] = token_data['key_id']
            session['subscription_link'] = token_data.get('subscription_link')
            
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Exception during token validation for token {token_preview}: {e}", exc_info=True)
            return render_template('error.html',
                                 error_title="Ошибка при проверке ссылки",
                                 error_message="Произошла ошибка при проверке ссылки доступа. Попробуйте позже."), 500
        
    return decorated_function


@app.route('/auth/<token>')
@rate_limit
@require_token
def auth(token):
    """Маршрут авторизации по токену"""
    # После успешной валидации токена перенаправляем на главную страницу
    return redirect(url_for('index'))


@app.route('/')
@rate_limit
def index():
    """Главная страница личного кабинета"""
    # Проверяем наличие токена в query параметрах или сессии
    token = request.args.get('token') or session.get('token')
    
    if token:
        token_preview = token[:10] + "..." if len(token) > 10 else token
        logger.info(f"Index page: token found in request: {token_preview}")
        
        try:
            # Валидируем токен
            token_data = validate_permanent_token(token)
            
            if token_data:
                logger.info(f"Index page: token validated - user_id={token_data.get('user_id')}, key_id={token_data.get('key_id')}")
                
                # Проверяем, не был ли ключ удален
                if token_data.get('key_deleted'):
                    logger.warning(f"Index page: token valid but key_id={token_data.get('key_id')} was deleted")
                    return render_template('error.html',
                                         error_title="Ключ удален",
                                         error_message="Ссылка действительна, но ключ был удален. Обратитесь в поддержку или создайте новый ключ."), 404
                
                # Сохраняем данные в сессию
                session['token'] = token
                session['user_id'] = token_data['user_id']
                session['key_id'] = token_data['key_id']
                session['subscription_link'] = token_data.get('subscription_link')
                
                # Получаем информацию о ключе
                key_id = token_data['key_id']
                logger.info(f"Index page: fetching key data for key_id={key_id}")
                key_data = get_key_by_id(key_id)
                
                if key_data:
                    logger.info(f"Index page: key data retrieved successfully for key_id={key_id}")
                    settings = get_all_settings()
                    knowledge_base_url, knowledge_base_setup_url = _build_knowledge_base_url(settings)
                    return render_template('index.html', 
                                         key_data=key_data,
                                         subscription_link=token_data.get('subscription_link'),
                                         knowledge_base_url=knowledge_base_url,
                                         knowledge_base_setup_url=knowledge_base_setup_url)
                else:
                    logger.warning(f"Index page: key not found for key_id={key_id} (token was valid but key missing)")
                    return render_template('error.html',
                                         error_title="Ключ не найден",
                                         error_message="Ссылка действительна, но информация о ключе недоступна. Обратитесь в поддержку."), 404
            else:
                logger.warning(f"Index page: token validation failed for token {token_preview}")
                return render_template('error.html',
                                     error_title="Ссылка недействительна",
                                     error_message="Ссылка устарела или указана с ошибкой. Скопируйте ссылку заново из Telegram-бота и попробуйте ещё раз."), 403
        except Exception as e:
            logger.error(f"Index page: exception during token validation or key retrieval: {e}", exc_info=True)
            return render_template('error.html',
                                 error_title="Ошибка при загрузке данных",
                                 error_message="Произошла ошибка при загрузке данных личного кабинета. Попробуйте позже."), 500
    else:
        # Если токена нет - показываем сообщение о необходимости ссылки
        logger.info("Index page: no token provided in request")
        return render_template('error.html',
                             error_title="Ссылка не предоставлена",
                             error_message="Для доступа к личному кабинету необходима ссылка доступа. Используйте ссылку из Telegram."), 401


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=50003, debug=False)

