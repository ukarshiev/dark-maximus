#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask-прокси для пользовательской документации (docs)
Добавляет авторизацию перед проксированием запросов к docs контейнеру
"""

import os
import sys
import logging
import requests
from flask import Flask, render_template, request, Response, session, flash, url_for, redirect
from pathlib import Path
from werkzeug.middleware.proxy_fix import ProxyFix

# Добавляем путь к src для импорта модулей
# В контейнере src маппится в /app/src, в локальной разработке - в корень проекта
app_dir = Path(__file__).parent  # /app/ в контейнере
container_src_path = app_dir / "src"  # /app/src в контейнере
local_src_path = app_dir.parent.parent / "src"  # для локальной разработки

# Проверяем, какой путь существует
if container_src_path.exists():
    src_path = container_src_path
elif local_src_path.exists():
    src_path = local_src_path
else:
    # Fallback: используем /app/src (для контейнера)
    src_path = Path("/app/src")

if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Импортируем утилиты авторизации
from shop_bot.webhook_server.auth_utils import init_flask_auth, login_required, verify_and_login

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates')

# Инициализация авторизации
init_flask_auth(app, session_dir='/app/sessions')

# ProxyFix для правильной работы за reverse proxy
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1,
    x_port=1,
    x_prefix=1
)

# URL docs контейнера (внутренний порт)
DOCS_BACKEND_URL = os.getenv('DOCS_BACKEND_URL', 'http://docs:80')


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """Страница входа в систему"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if verify_and_login(username, password):
            # Редирект на главную страницу после успешного входа
            next_url = request.args.get('next', '/')
            return redirect(next_url)
        else:
            flash('Неверный логин или пароль', 'danger')
    
    return render_template('login.html')


@app.route('/logout', methods=['POST'])
@login_required
def logout_page():
    """Выход из системы"""
    session.pop('logged_in', None)
    flash('Вы успешно вышли.', 'success')
    return redirect(url_for('login_page'))


@app.route('/health')
def health():
    """Health check endpoint (без авторизации)"""
    try:
        # Проверяем доступность docs контейнера
        response = requests.get(f"{DOCS_BACKEND_URL}/health", timeout=5)
        return {'status': 'ok', 'service': 'docs-proxy', 'backend': response.status_code == 200}, 200
    except Exception as e:
        logger.warning(f"Health check failed: {e}")
        return {'status': 'degraded', 'service': 'docs-proxy', 'backend': 'unavailable'}, 200


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
@login_required
def proxy(path):
    """Проксирование всех запросов к docs контейнеру после авторизации"""
    # Формируем полный URL для запроса к docs контейнеру
    if path:
        target_url = f"{DOCS_BACKEND_URL}/{path}"
    else:
        target_url = DOCS_BACKEND_URL
    
    # Добавляем query параметры, если есть
    if request.query_string:
        target_url += f"?{request.query_string.decode('utf-8')}"
    
    try:
        # Получаем заголовки запроса
        headers = dict(request.headers)
        # Удаляем заголовки, которые не должны передаваться
        headers.pop('Host', None)
        headers.pop('Connection', None)
        headers.pop('Content-Length', None)
        
        # Определяем метод запроса
        method = request.method
        
        # Получаем тело запроса
        data = request.get_data() if request.data else None
        
        # Выполняем запрос к docs контейнеру
        response = requests.request(
            method=method,
            url=target_url,
            headers=headers,
            data=data,
            stream=True,
            timeout=60,
            allow_redirects=False  # Обрабатываем редиректы вручную
        )
        
        # Формируем заголовки ответа
        response_headers = dict(response.headers)
        # Удаляем заголовки, которые могут вызвать проблемы
        response_headers.pop('Content-Encoding', None)
        response_headers.pop('Transfer-Encoding', None)
        response_headers.pop('Content-Length', None)
        response_headers.pop('Connection', None)
        
        # Обрабатываем редиректы
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get('Location', '')
            if location.startswith(DOCS_BACKEND_URL):
                # Заменяем внутренний URL на публичный
                location = location.replace(DOCS_BACKEND_URL, '')
            response_headers['Location'] = location
        
        # Возвращаем ответ
        return Response(
            response.content,
            status=response.status_code,
            headers=response_headers,
            mimetype=response.headers.get('Content-Type', 'text/html')
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при проксировании запроса к docs: {e}")
        return Response(
            f"Ошибка подключения к сервису документации: {str(e)}",
            status=502,
            mimetype='text/plain'
        )
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        return Response(
            "Внутренняя ошибка сервера",
            status=500,
            mimetype='text/plain'
        )


if __name__ == '__main__':
    port = int(os.getenv('PORT', 50001))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)

