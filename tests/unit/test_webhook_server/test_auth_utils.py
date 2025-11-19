#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для auth_utils модуля

Тестирует инициализацию Flask авторизации, загрузку FLASK_SECRET_KEY и установку прав доступа
"""

import pytest
import allure
import sys
import os
import tempfile
import stat
from pathlib import Path
from unittest.mock import patch, MagicMock
from flask import Flask

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.unit
@pytest.mark.database
@allure.epic("Веб-панель")
@allure.feature("Авторизация")
@allure.label("package", "src.shop_bot.webhook_server")
class TestAuthUtils:
    """Тесты для auth_utils модуля"""

    @allure.story("Инициализация авторизации: загрузка FLASK_SECRET_KEY")
    @allure.title("Успешная загрузка FLASK_SECRET_KEY из окружения")
    @allure.description("""
    Проверяет успешную загрузку FLASK_SECRET_KEY из переменных окружения при инициализации авторизации.
    
    **Что проверяется:**
    - Загрузка FLASK_SECRET_KEY из переменных окружения
    - Установка SECRET_KEY в конфигурацию Flask приложения
    - Логирование успешной загрузки ключа
    - Отсутствие генерации случайного ключа (fallback)
    
    **Тестовые данные:**
    - FLASK_SECRET_KEY: 'test-secret-key-12345'
    
    **Ожидаемый результат:**
    FLASK_SECRET_KEY успешно загружен из окружения, SECRET_KEY установлен в конфигурацию приложения,
    в логах есть сообщение об успешной загрузке, случайный ключ не генерируется.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("auth", "secret_key", "environment", "webhook_server", "unit", "critical")
    def test_init_flask_auth_with_secret_key(self, temp_db):
        """Тест успешной загрузки FLASK_SECRET_KEY из окружения"""
        from shop_bot.webhook_server.auth_utils import init_flask_auth
        import logging
        
        test_secret_key = 'test-secret-key-12345'
        test_session_dir = tempfile.mkdtemp()
        
        with allure.step("Подготовка тестового окружения"):
            app = Flask(__name__)
            allure.attach(test_secret_key, "FLASK_SECRET_KEY", allure.attachment_type.TEXT)
            allure.attach(test_session_dir, "Директория сессий", allure.attachment_type.TEXT)
        
        with allure.step("Инициализация авторизации с FLASK_SECRET_KEY в окружении"):
            with patch.dict(os.environ, {'FLASK_SECRET_KEY': test_secret_key}):
                # Настраиваем логирование для перехвата сообщений
                log_capture = []
                handler = logging.Handler()
                handler.emit = lambda record: log_capture.append(record.getMessage())
                logger = logging.getLogger('shop_bot.webhook_server.auth_utils')
                logger.addHandler(handler)
                logger.setLevel(logging.INFO)
                
                init_flask_auth(app, session_dir=test_session_dir)
                
                allure.attach('\n'.join(log_capture), "Логи", allure.attachment_type.TEXT)
        
        with allure.step("Проверка установки SECRET_KEY"):
            assert app.config['SECRET_KEY'] == test_secret_key, \
                f"SECRET_KEY должен быть равен '{test_secret_key}', получен '{app.config['SECRET_KEY']}'"
            allure.attach(app.config['SECRET_KEY'], "Установленный SECRET_KEY", allure.attachment_type.TEXT)
        
        with allure.step("Проверка логирования успешной загрузки"):
            log_messages = '\n'.join(log_capture)
            assert 'FLASK_SECRET_KEY успешно загружен из окружения' in log_messages, \
                "В логах должно быть сообщение об успешной загрузке FLASK_SECRET_KEY"
            assert 'Генерируется новый случайный ключ' not in log_messages, \
                "В логах НЕ должно быть предупреждения о генерации нового ключа"
            allure.attach(log_messages, "Сообщения в логах", allure.attachment_type.TEXT)
        
        # Очистка
        logger.removeHandler(handler)
        import shutil
        shutil.rmtree(test_session_dir)

    @allure.story("Инициализация авторизации: отсутствие FLASK_SECRET_KEY")
    @allure.title("Предупреждение при отсутствии FLASK_SECRET_KEY в окружении")
    @allure.description("""
    Проверяет генерацию предупреждения при отсутствии FLASK_SECRET_KEY в переменных окружения.
    
    **Что проверяется:**
    - Отсутствие FLASK_SECRET_KEY в переменных окружения
    - Генерация случайного ключа (fallback)
    - Логирование предупреждения о потере сессий
    - Установка сгенерированного SECRET_KEY в конфигурацию приложения
    
    **Тестовые данные:**
    - FLASK_SECRET_KEY: отсутствует в окружении
    
    **Ожидаемый результат:**
    Генерируется случайный ключ, в логах есть предупреждение о потере сессий, SECRET_KEY установлен в конфигурацию.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("auth", "secret_key", "warning", "webhook_server", "unit", "critical")
    def test_init_flask_auth_without_secret_key(self, temp_db):
        """Тест предупреждения при отсутствии FLASK_SECRET_KEY"""
        from shop_bot.webhook_server.auth_utils import init_flask_auth
        import logging
        
        test_session_dir = tempfile.mkdtemp()
        
        with allure.step("Подготовка тестового окружения"):
            app = Flask(__name__)
            allure.attach("FLASK_SECRET_KEY отсутствует", "Состояние окружения", allure.attachment_type.TEXT)
        
        with allure.step("Инициализация авторизации без FLASK_SECRET_KEY в окружении"):
            # Удаляем FLASK_SECRET_KEY из окружения, если он есть
            env_backup = os.environ.pop('FLASK_SECRET_KEY', None)
            
            try:
                # Настраиваем логирование для перехвата сообщений
                log_capture = []
                handler = logging.Handler()
                handler.emit = lambda record: log_capture.append(record.getMessage())
                logger = logging.getLogger('shop_bot.webhook_server.auth_utils')
                logger.addHandler(handler)
                logger.setLevel(logging.WARNING)
                
                init_flask_auth(app, session_dir=test_session_dir)
                
                allure.attach('\n'.join(log_capture), "Логи", allure.attachment_type.TEXT)
            finally:
                # Восстанавливаем окружение
                if env_backup:
                    os.environ['FLASK_SECRET_KEY'] = env_backup
        
        with allure.step("Проверка генерации случайного ключа"):
            assert app.config['SECRET_KEY'] is not None, "SECRET_KEY должен быть установлен"
            assert len(app.config['SECRET_KEY']) == 64, \
                f"Сгенерированный ключ должен быть длиной 64 символа (hex), получен {len(app.config['SECRET_KEY'])}"
            allure.attach(app.config['SECRET_KEY'], "Сгенерированный SECRET_KEY", allure.attachment_type.TEXT)
        
        with allure.step("Проверка логирования предупреждения"):
            log_messages = '\n'.join(log_capture)
            assert 'FLASK_SECRET_KEY не найден в окружении' in log_messages, \
                "В логах должно быть предупреждение об отсутствии FLASK_SECRET_KEY"
            assert 'Генерируется новый случайный ключ' in log_messages, \
                "В логах должно быть сообщение о генерации нового ключа"
            assert 'приведет к потере всех существующих сессий' in log_messages, \
                "В логах должно быть предупреждение о потере сессий"
            allure.attach(log_messages, "Сообщения в логах", allure.attachment_type.TEXT)
        
        # Очистка
        logger.removeHandler(handler)
        import shutil
        shutil.rmtree(test_session_dir)

    @allure.story("Инициализация авторизации: установка прав доступа")
    @allure.title("Установка прав доступа 755 для директории сессий")
    @allure.description("""
    Проверяет установку прав доступа 755 для директории сессий при инициализации авторизации.
    
    **Что проверяется:**
    - Создание директории сессий, если её нет
    - Установка прав доступа 755 (rwxr-xr-x) для директории сессий
    - Корректная работа с существующей директорией
    
    **Тестовые данные:**
    - Директория сессий: временная директория
    
    **Ожидаемый результат:**
    Директория сессий создана с правами доступа 755, права установлены корректно.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "permissions", "session_dir", "webhook_server", "unit")
    def test_init_flask_auth_session_dir_permissions(self, temp_db):
        """Тест установки прав доступа для директории сессий"""
        from shop_bot.webhook_server.auth_utils import init_flask_auth
        import tempfile
        import shutil
        
        test_session_dir = tempfile.mkdtemp()
        # Удаляем директорию, чтобы проверить создание
        shutil.rmtree(test_session_dir)
        
        with allure.step("Подготовка тестового окружения"):
            app = Flask(__name__)
            allure.attach(test_session_dir, "Директория сессий", allure.attachment_type.TEXT)
        
        with allure.step("Инициализация авторизации с созданием директории"):
            with patch.dict(os.environ, {'FLASK_SECRET_KEY': 'test-secret-key'}):
                init_flask_auth(app, session_dir=test_session_dir)
        
        with allure.step("Проверка существования директории"):
            assert os.path.exists(test_session_dir), \
                f"Директория сессий должна существовать: {test_session_dir}"
            assert os.path.isdir(test_session_dir), \
                f"Путь должен быть директорией: {test_session_dir}"
            allure.attach(str(os.path.exists(test_session_dir)), "Директория существует", allure.attachment_type.TEXT)
        
        with allure.step("Проверка прав доступа к директории"):
            # Получаем права доступа к директории
            dir_stat = os.stat(test_session_dir)
            dir_permissions = stat.filemode(dir_stat.st_mode)
            # Проверяем, что права включают rwxr-xr-x (755)
            # В Windows права могут отличаться, поэтому проверяем только на Unix-подобных системах
            if os.name != 'nt':  # Не Windows
                expected_permissions = 'drwxr-xr-x'
                assert dir_permissions == expected_permissions, \
                    f"Права доступа должны быть {expected_permissions}, получены {dir_permissions}"
                allure.attach(dir_permissions, "Права доступа", allure.attachment_type.TEXT)
            else:
                # На Windows просто проверяем, что директория существует и доступна
                assert os.access(test_session_dir, os.R_OK | os.W_OK | os.X_OK), \
                    "Директория должна быть доступна для чтения, записи и выполнения"
                allure.attach("Windows: права доступа проверены", "Права доступа", allure.attachment_type.TEXT)
        
        # Очистка
        shutil.rmtree(test_session_dir)

    @allure.story("Инициализация авторизации: конфигурация сессий")
    @allure.title("Корректная настройка конфигурации Flask-Session")
    @allure.description("""
    Проверяет корректную настройку конфигурации Flask-Session при инициализации авторизации.
    
    **Что проверяется:**
    - Установка SESSION_TYPE = 'filesystem'
    - Установка SESSION_FILE_DIR
    - Установка SESSION_PERMANENT = True
    - Установка PERMANENT_SESSION_LIFETIME = 30 дней
    - Установка SESSION_COOKIE_MAX_AGE = 2592000 секунд (30 дней)
    - Установка SESSION_COOKIE_HTTPONLY = True
    - Установка SESSION_COOKIE_SAMESITE = 'Lax'
    
    **Ожидаемый результат:**
    Все настройки Flask-Session установлены корректно согласно конфигурации.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "session_config", "webhook_server", "unit")
    def test_init_flask_auth_session_config(self, temp_db):
        """Тест настройки конфигурации Flask-Session"""
        from shop_bot.webhook_server.auth_utils import init_flask_auth
        from datetime import timedelta
        import tempfile
        
        test_session_dir = tempfile.mkdtemp()
        
        with allure.step("Подготовка тестового окружения"):
            app = Flask(__name__)
        
        with allure.step("Инициализация авторизации"):
            with patch.dict(os.environ, {'FLASK_SECRET_KEY': 'test-secret-key'}):
                init_flask_auth(app, session_dir=test_session_dir)
        
        with allure.step("Проверка конфигурации сессий"):
            assert app.config['SESSION_TYPE'] == 'filesystem', \
                f"SESSION_TYPE должен быть 'filesystem', получен '{app.config['SESSION_TYPE']}'"
            assert app.config['SESSION_FILE_DIR'] == test_session_dir, \
                f"SESSION_FILE_DIR должен быть '{test_session_dir}', получен '{app.config['SESSION_FILE_DIR']}'"
            assert app.config['SESSION_PERMANENT'] is True, \
                f"SESSION_PERMANENT должен быть True, получен {app.config['SESSION_PERMANENT']}"
            assert app.config['PERMANENT_SESSION_LIFETIME'] == timedelta(days=30), \
                f"PERMANENT_SESSION_LIFETIME должен быть 30 дней, получен {app.config['PERMANENT_SESSION_LIFETIME']}"
            assert app.config['SESSION_COOKIE_MAX_AGE'] == 30 * 24 * 60 * 60, \
                f"SESSION_COOKIE_MAX_AGE должен быть 2592000 секунд (30 дней), получен {app.config['SESSION_COOKIE_MAX_AGE']}"
            assert app.config['SESSION_COOKIE_HTTPONLY'] is True, \
                f"SESSION_COOKIE_HTTPONLY должен быть True, получен {app.config['SESSION_COOKIE_HTTPONLY']}"
            assert app.config['SESSION_COOKIE_SAMESITE'] == 'Lax', \
                f"SESSION_COOKIE_SAMESITE должен быть 'Lax', получен '{app.config['SESSION_COOKIE_SAMESITE']}'"
            
            config_data = {
                'SESSION_TYPE': app.config['SESSION_TYPE'],
                'SESSION_FILE_DIR': app.config['SESSION_FILE_DIR'],
                'SESSION_PERMANENT': app.config['SESSION_PERMANENT'],
                'PERMANENT_SESSION_LIFETIME': str(app.config['PERMANENT_SESSION_LIFETIME']),
                'SESSION_COOKIE_MAX_AGE': app.config['SESSION_COOKIE_MAX_AGE'],
                'SESSION_COOKIE_HTTPONLY': app.config['SESSION_COOKIE_HTTPONLY'],
                'SESSION_COOKIE_SAMESITE': app.config['SESSION_COOKIE_SAMESITE']
            }
            import json
            allure.attach(
                json.dumps(config_data, indent=2, ensure_ascii=False),
                "Конфигурация сессий",
                allure.attachment_type.JSON
            )
        
        # Очистка
        import shutil
        shutil.rmtree(test_session_dir)
    
    @allure.story("Изоляция сессий: уникальные имена cookie")
    @allure.title("Проверка уникальности имен cookie для разных сервисов")
    @allure.description("""
    Проверяет, что функция init_flask_auth() поддерживает установку уникальных имен cookie
    для разных сервисов, что предотвращает конфликт сессий при использовании одинакового FLASK_SECRET_KEY.
    
    **Что проверяется:**
    - Параметр cookie_name устанавливает уникальное имя cookie
    - Дефолтное значение cookie_name = 'panel_session'
    - Разные сервисы могут использовать разные имена cookie
    - Имена cookie не конфликтуют между сервисами
    
    **Тестовые данные:**
    - cookie_name='panel_session' (дефолт)
    - cookie_name='docs_session'
    - cookie_name='allure_session'
    - cookie_name='cabinet_session'
    
    **Критичность:**
    Конфликт cookie между сервисами приводит к потере сессии при переходах между сервисами.
    Это критичная проблема безопасности и UX.
    
    **Ожидаемый результат:**
    Каждый сервис использует уникальное имя cookie, сессии изолированы и не конфликтуют.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("auth", "session_isolation", "cookie_name", "webhook_server", "unit", "critical")
    def test_cookie_name_isolation(self, temp_db):
        """Тест изоляции сессий через уникальные имена cookie"""
        from shop_bot.webhook_server.auth_utils import init_flask_auth
        import tempfile
        import shutil
        
        test_session_dir = tempfile.mkdtemp()
        
        # Ожидаемые имена cookie для каждого сервиса
        expected_cookie_names = {
            'panel_session': 'panel_session',  # Дефолт для веб-панели
            'docs_session': 'docs_session',
            'allure_session': 'allure_session',
            'cabinet_session': 'cabinet_session',
        }
        
        with allure.step("Подготовка тестового окружения"):
            apps = {}
            for cookie_name in expected_cookie_names.keys():
                apps[cookie_name] = Flask(__name__)
        
        with allure.step("Инициализация авторизации с разными именами cookie"):
            with patch.dict(os.environ, {'FLASK_SECRET_KEY': 'test-secret-key'}):
                for cookie_name, app in apps.items():
                    init_flask_auth(app, session_dir=test_session_dir, cookie_name=cookie_name)
        
        with allure.step("Проверка уникальности имен cookie"):
            actual_cookie_names = {}
            for cookie_name, app in apps.items():
                actual_cookie_names[cookie_name] = app.config.get('SESSION_COOKIE_NAME')
                assert app.config.get('SESSION_COOKIE_NAME') == expected_cookie_names[cookie_name], \
                    f"Ожидалось SESSION_COOKIE_NAME='{expected_cookie_names[cookie_name]}', " \
                    f"получено '{app.config.get('SESSION_COOKIE_NAME')}' для cookie_name='{cookie_name}'"
            
            # Проверяем, что все имена уникальны
            unique_names = set(actual_cookie_names.values())
            assert len(unique_names) == len(expected_cookie_names), \
                f"Имена cookie должны быть уникальными. " \
                f"Ожидалось {len(expected_cookie_names)} уникальных имен, получено {len(unique_names)}. " \
                f"Имена: {actual_cookie_names}"
            
            import json
            allure.attach(
                json.dumps(actual_cookie_names, indent=2, ensure_ascii=False),
                "Имена cookie для каждого сервиса",
                allure.attachment_type.JSON
            )
        
        with allure.step("Проверка дефолтного значения cookie_name"):
            app_default = Flask(__name__)
            with patch.dict(os.environ, {'FLASK_SECRET_KEY': 'test-secret-key'}):
                init_flask_auth(app_default, session_dir=test_session_dir)
            
            assert app_default.config.get('SESSION_COOKIE_NAME') == 'panel_session', \
                f"Дефолтное значение cookie_name должно быть 'panel_session', " \
                f"получено '{app_default.config.get('SESSION_COOKIE_NAME')}'"
            
            allure.attach(
                app_default.config.get('SESSION_COOKIE_NAME'),
                "Дефолтное имя cookie",
                allure.attachment_type.TEXT
            )
        
        # Очистка
        shutil.rmtree(test_session_dir)

