#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Общие утилиты для авторизации Flask приложений

Используется в веб-панели, docs-proxy и allure-homepage
"""

import os
import secrets
import logging
from functools import wraps
from flask import session, redirect, url_for, current_app
from flask_session import Session
from datetime import timedelta


def init_flask_auth(app, session_dir='/app/sessions'):
    """
    Инициализирует Flask sessions для авторизации
    
    Args:
        app: Flask приложение
        session_dir: Директория для хранения сессий (по умолчанию /app/sessions)
    """
    # Безопасное получение секретного ключа из переменных окружения
    logger = logging.getLogger(__name__)
    secret_key = os.getenv('FLASK_SECRET_KEY')
    if not secret_key:
        logger.warning("⚠️ FLASK_SECRET_KEY не найден в окружении! Генерируется новый случайный ключ. "
                       "Это приведет к потере всех существующих сессий!")
        secret_key = secrets.token_hex(32)
    else:
        logger.info("✓ FLASK_SECRET_KEY успешно загружен из окружения")
    app.config['SECRET_KEY'] = secret_key
    
    # Настройка постоянного хранения сессий в файловой системе
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_FILE_DIR'] = session_dir
    app.config['SESSION_PERMANENT'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # Сессия на 30 дней
    
    # Срок жизни cookie сессии (в секундах) - должен соответствовать PERMANENT_SESSION_LIFETIME
    # 30 дней = 30 * 24 * 60 * 60 = 2592000 секунд
    app.config['SESSION_COOKIE_MAX_AGE'] = 30 * 24 * 60 * 60  # Cookie на 30 дней
    
    # Безопасность сессий (best practices из Flask документации)
    app.config['SESSION_COOKIE_HTTPONLY'] = True  # Защита от XSS
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Защита от CSRF
    
    # Для production (HTTPS) - устанавливается через переменные окружения
    if os.getenv('FLASK_ENV') == 'production' or os.getenv('SESSION_COOKIE_SECURE', '').lower() == 'true':
        app.config['SESSION_COOKIE_SECURE'] = True
    
    # Создаем директорию для сессий, если её нет
    os.makedirs(session_dir, exist_ok=True)
    os.chmod(session_dir, 0o755)  # Установить права доступа 755
    
    # Инициализация файловой сессии
    Session(app)


def login_required(f):
    """
    Декоратор для защиты маршрутов, требующих авторизации
    
    Использование:
        @app.route('/protected')
        @login_required
        def protected_route():
            return "Защищенная страница"
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function


def verify_and_login(username, password):
    """
    Проверяет учетные данные и устанавливает сессию при успешной авторизации
    
    Args:
        username: Имя пользователя
        password: Пароль
        
    Returns:
        bool: True если авторизация успешна, False в противном случае
    """
    from shop_bot.data_manager.database import verify_admin_credentials
    
    if verify_admin_credentials(username, password):
        session['logged_in'] = True
        session.permanent = True  # Делаем сессию постоянной
        # Явно помечаем сессию как измененную для гарантированного сохранения
        session.modified = True
        
        # Явно сохраняем сессию на диск для предотвращения потери при перезапуске контейнера
        # Flask-Session использует lazy saving, поэтому нужно явно вызвать сохранение
        try:
            # Проверяем, что мы в контексте запроса Flask
            if hasattr(current_app, 'session_interface'):
                session_interface = current_app.session_interface
                if hasattr(session_interface, 'save_session'):
                    # Сохраняем сессию немедленно
                    session_interface.save_session(current_app, session, None)
        except RuntimeError:
            # Если мы не в контексте запроса, session.modified = True достаточно
            # Flask-Session сохранит сессию в конце запроса
            pass
        
        return True
    return False

