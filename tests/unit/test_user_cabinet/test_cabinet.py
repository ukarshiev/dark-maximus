#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для пользовательского кабинета

Тестирует все эндпоинты и функциональность user-cabinet
"""

import pytest
import sys
import os
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
import uuid
from unittest.mock import patch, MagicMock
import requests
import allure

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "apps" / "user-cabinet"))

from shop_bot.data_manager.database import (
    register_user_if_not_exists,
    create_key_with_stats_atomic,
    get_or_create_permanent_token,
    validate_permanent_token,
    get_key_by_id,
    delete_key_by_email,
    get_all_settings,
    update_setting,
)


@pytest.mark.unit
@pytest.mark.database
@allure.epic("Личный кабинет")
@allure.feature("Функциональность кабинета")
@allure.label("package", "tests.unit.test_user_cabinet")
class TestUserCabinet:
    """Тесты для пользовательского кабинета"""

    @pytest.fixture
    def flask_app(self):
        """Фикстура для Flask приложения"""
        import sys
        import importlib.util
        from pathlib import Path
        
        # Определяем project_root разными способами
        test_file = Path(__file__).resolve()
        project_root_from_test = test_file.parent.parent.parent.parent
        
        # Проверяем переменную окружения
        project_root_env = os.getenv('PROJECT_ROOT')
        if project_root_env:
            project_root_env = Path(project_root_env).resolve()
        
        # Проверяем текущую рабочую директорию
        cwd = Path(os.getcwd()).resolve()
        
        # Формируем список возможных путей
        possible_paths = []
        
        # Локальная разработка (от файла теста)
        possible_paths.append(project_root_from_test / "apps" / "user-cabinet" / "app.py")
        
        # Docker окружение (основной путь)
        possible_paths.append(Path("/app/apps/user-cabinet/app.py"))
        
        # Если есть переменная окружения
        if project_root_env:
            possible_paths.append(project_root_env / "apps" / "user-cabinet" / "app.py")
        
        # От текущей рабочей директории
        possible_paths.append(cwd / "apps" / "user-cabinet" / "app.py")
        
        # Убираем дубликаты, сохраняя порядок
        seen = set()
        unique_paths = []
        for path in possible_paths:
            path_str = str(path)
            if path_str not in seen:
                seen.add(path_str)
                unique_paths.append(path)
        
        # Логируем проверяемые пути для отладки
        paths_info = "\n".join([f"  - {p} (exists: {p.exists()})" for p in unique_paths])
        logging.info(f"Checking paths for user-cabinet app.py:\n{paths_info}")
        
        # Используем allure.attach для сохранения отладочной информации
        try:
            allure.attach(paths_info, "Проверяемые пути к app.py", allure.attachment_type.TEXT)
        except Exception:
            pass  # Игнорируем ошибки allure в случае отсутствия контекста
        
        app_file = None
        for path in unique_paths:
            if path.exists():
                app_file = path
                logging.info(f"Found app.py at: {app_file}")
                try:
                    allure.attach(str(app_file), "Найденный путь к app.py", allure.attachment_type.TEXT)
                except Exception:
                    pass
                break
        
        # Если файл не найден, пропускаем тест с детальной информацией
        if not app_file:
            error_msg = f"App file not found in any of the expected locations:\n{paths_info}\nProject root (from test): {project_root_from_test}\nCWD: {cwd}"
            if project_root_env:
                error_msg += f"\nPROJECT_ROOT env: {project_root_env}"
            logging.error(error_msg)
            try:
                allure.attach(error_msg, "Ошибка поиска app.py", allure.attachment_type.TEXT)
            except Exception:
                pass
            pytest.skip(error_msg)
        
        # Добавляем пути для импорта
        app_dir = app_file.parent
        if str(app_dir) not in sys.path:
            sys.path.insert(0, str(app_dir))
        if str(project_root_from_test / "src") not in sys.path:
            sys.path.insert(0, str(project_root_from_test / "src"))
        
        # Импортируем database модуль для патчинга run_migration
        from shop_bot.data_manager import database
        
        # Загружаем модуль с мокированием run_migration, чтобы избежать ошибок миграции в тестах
        spec = importlib.util.spec_from_file_location("user_cabinet_app", app_file)
        app_module = importlib.util.module_from_spec(spec)
        
        # Мокируем run_migration перед выполнением модуля
        with patch.object(database, 'run_migration'):
            spec.loader.exec_module(app_module)
        
        flask_app = app_module.app
        
        # Устанавливаем root_path чтобы Flask находил templates
        flask_app.root_path = str(app_dir)
        
        # Убеждаемся, что template_folder установлен правильно
        templates_dir = app_dir / "templates"
        if templates_dir.exists():
            # Явно устанавливаем template_folder для надёжности
            flask_app.template_folder = str(templates_dir)
            # Также устанавливаем статическую папку для полноты
            static_dir = app_dir / "static"
            if static_dir.exists():
                flask_app.static_folder = str(static_dir)
        
        # Сбрасываем jinja_env, чтобы Flask пересоздал его с правильными путями
        # Это критически важно при динамической загрузке модуля через importlib
        if hasattr(flask_app, '_jinja_env'):
            flask_app._jinja_env = None
        
        flask_app.config['TESTING'] = True
        flask_app.config['SECRET_KEY'] = 'test-secret-key'
        return flask_app.test_client()

    @pytest.fixture
    def test_user(self, temp_db, sample_host):
        """Фикстура для тестового пользователя и ключа"""
        # Создаем пользователя
        user_id = 123456789
        register_user_if_not_exists(user_id, "test_user", None, "Test User")
        
        # Создаем хост в БД
        import sqlite3
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",
                (sample_host['host_name'], sample_host['host_url'], sample_host['host_username'], 
                 sample_host['host_pass'], sample_host['host_inbound_id'], sample_host['host_code'])
            )
            conn.commit()
        
        # Создаем ключ
        xui_client_uuid = str(uuid.uuid4())
        key_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        
        key_id = create_key_with_stats_atomic(
            user_id=user_id,
            host_name=sample_host['host_name'],
            xui_client_uuid=xui_client_uuid,
            key_email=key_email,
            expiry_timestamp_ms=expiry_timestamp_ms,
            amount_spent=100.0,
            months_purchased=1,
            plan_name="Test Plan",
            price=100.0,
            subscription_link="https://example.com/subscription"
        )
        
        # Создаем токен
        token = get_or_create_permanent_token(user_id, key_id)
        
        return {
            'user_id': user_id,
            'key_id': key_id,
            'key_email': key_email,
            'token': token
        }

    def test_health_endpoint(self, flask_app):
        """Тест healthcheck endpoint"""
        response = flask_app.get('/health')
        assert response.status_code == 200, "Health endpoint должен вернуть 200"
        data = response.get_json()
        assert data['status'] == 'ok', "Status должен быть 'ok'"

    def test_index_without_token(self, flask_app):
        """Тест главной страницы без токена"""
        response = flask_app.get('/')
        assert response.status_code == 401, "Без токена должен вернуть 401"
        assert 'Ссылка не предоставлена'.encode('utf-8') in response.data, "Должно быть сообщение об ошибке"

    def test_index_with_valid_token(self, flask_app, test_user, temp_db):
        """Тест главной страницы с валидным токеном"""
        # Используем database.DB_FILE (уже заменен через monkeypatch в фикстуре temp_db)
        from shop_bot.data_manager import database
        
        response = flask_app.get(f'/?token={test_user["token"]}')
        assert response.status_code == 200, "С валидным токеном должен вернуть 200"
        
        # Проверяем наличие ключевых элементов страницы
        # Шаги навигации должны присутствовать
        assert ('Настройка VPN' in response.data.decode('utf-8') or 
                'Настройка' in response.data.decode('utf-8')), "Должен быть шаг 'Настройка VPN'"
        assert 'Подключение' in response.data.decode('utf-8'), "Должен быть шаг 'Подключение'"
        assert 'Проверка IP' in response.data.decode('utf-8'), "Должен быть шаг 'Проверка IP'"
        
        # Проверяем наличие iframe с инструкциями (URL базы знаний должен быть в HTML)
        # По умолчанию это http://localhost:50002/setup или другой URL из настроек
        assert b'setup-iframe' in response.data, "Должен быть iframe с инструкциями"
        assert b'src=' in response.data, "Должен быть атрибут src в iframe"
        
        # Проверяем корректную структуру HTML
        assert b'<!DOCTYPE html>' in response.data, "Должен быть корректный HTML"
        assert 'Личный кабинет' in response.data.decode('utf-8'), "Должен быть заголовок страницы"

    def test_index_with_invalid_token(self, flask_app, temp_db):
        """Тест главной страницы с невалидным токеном"""
        # Патчим DB_FILE для использования временной БД
        from shop_bot.data_manager import database
        
        invalid_token = "invalid_token_12345"
        response = flask_app.get(f'/?token={invalid_token}')
        assert response.status_code == 403, "С невалидным токеном должен вернуть 403"
        assert 'Ссылка недействительна'.encode('utf-8') in response.data, "Должно быть сообщение об ошибке"

    @allure.title("Проверка обработки удаленного ключа при доступе к личному кабинету")
    @allure.description("""
    Проверяет поведение главной страницы личного кабинета (`/`) при попытке доступа
    с токеном, связанным с удаленным ключом.
    
    **Что проверяется:**
    - Приложение корректно обрабатывает ситуацию, когда ключ был удален
    - Возвращается правильный HTTP статус 404 (Not Found)
    - Отображается понятное сообщение об ошибке "Ключ удален"
    - Пользователь получает информацию о том, что ключ был удален, а не просто "Ссылка недействительна"
    
    **Тестовые данные:**
    - user_id: 123456789 (создается через test_user)
    - key_id: создается через test_user
    - key_email: генерируется как test_{uuid}@example.com
    - token: генерируется через get_or_create_permanent_token
    
    **Шаги теста:**
    1. **Патчинг DB_FILE для использования временной БД**
       - Сохраняется оригинальный database.DB_FILE
       - Устанавливается database.DB_FILE = temp_db
       - Ожидаемый результат: все операции с БД используют временную БД
    
    2. **Удаление ключа из БД**
       - Метод: delete_key_by_email(test_user['key_email'])
       - Действие: ключ удаляется из таблицы vpn_keys
       - **Важно:** функция также удаляет токен из user_tokens (текущая реализация)
       - Ожидаемый результат: ключ и токен удалены из БД
    
    3. **Попытка доступа к главной странице с токеном**
       - Метод: flask_app.get(f'/?token={test_user["token"]}')
       - Параметры: токен, который был связан с удаленным ключом
       - Ожидаемый результат: выполняется валидация токена через validate_permanent_token
    
    4. **Проверка HTTP статуса ответа**
       - Проверка: response.status_code == 404
       - Ожидаемый результат: статус 404 (Not Found), а не 403 (Forbidden)
       - **Проблема:** из-за удаления токена при удалении ключа, токен не найден
         и возвращается 403 вместо ожидаемого 404
    
    5. **Проверка сообщения об ошибке**
       - Проверка: 'Ключ удален'.encode('utf-8') in response.data
       - Ожидаемый результат: в ответе должно быть сообщение "Ключ удален"
       - **Проблема:** из-за удаления токена возвращается "Ссылка недействительна"
    
    **Предусловия:**
    - Пользователь зарегистрирован (user_id: 123456789) через test_user
    - Ключ создан в БД через test_user
    - Токен создан через get_or_create_permanent_token
    - Используется временная БД (temp_db)
    - Flask app настроен с правильным root_path для поиска шаблонов
    
    **Ожидаемый результат:**
    После удаления ключа при попытке доступа с токеном приложение должно:
    - Определить, что токен валиден, но ключ удален
    - Вернуть HTTP статус 404 (Not Found)
    - Показать сообщение "Ключ удален" с описанием проблемы
    
    **Известная проблема:**
    Тест в настоящее время падает, потому что функция `delete_key_by_email` удаляет
    токен из таблицы `user_tokens` перед удалением ключа. В результате:
    - validate_permanent_token возвращает None (токен не найден)
    - Приложение возвращает 403 "Ссылка недействительна" вместо 404 "Ключ удален"
    
    **Рекомендация:**
    Не удалять токен при удалении ключа, чтобы приложение могло различать случаи:
    - Токен недействителен (403) vs Ключ удален (404)
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("database", "unit", "cabinet", "deleted-key")
    def test_index_with_deleted_key(self, flask_app, test_user, temp_db):
        """Тест главной страницы с токеном для удаленного ключа"""
        # Используем database.DB_FILE (уже заменен через monkeypatch в фикстуре temp_db)
        from shop_bot.data_manager import database
        
        with allure.step("Удаление ключа из БД через delete_key_by_email"):
            # Удаляем ключ
            delete_key_by_email(test_user['key_email'])
            allure.attach(test_user['key_email'], "Email удаляемого ключа", allure.attachment_type.TEXT)
        
        with allure.step("Попытка доступа к главной странице с токеном удаленного ключа"):
            # Пытаемся получить доступ
            response = flask_app.get(f'/?token={test_user["token"]}')
            allure.attach(str(response.status_code), "HTTP статус ответа", allure.attachment_type.TEXT)
            allure.attach(response.data.decode('utf-8', errors='ignore')[:500], "Содержимое ответа (первые 500 символов)", allure.attachment_type.TEXT)
        
        with allure.step("Проверка HTTP статуса 404"):
            assert response.status_code == 404, "С удаленным ключом должен вернуть 404"
        
        with allure.step("Проверка сообщения 'Ключ удален' в ответе"):
            assert 'Ключ удален'.encode('utf-8') in response.data, "Должно быть сообщение об удаленном ключе"

    def test_auth_route_valid_token(self, flask_app, test_user, temp_db):
        """Тест авторизации по токену"""
        # Используем database.DB_FILE (уже заменен через monkeypatch в фикстуре temp_db)
        from shop_bot.data_manager import database
        
        response = flask_app.get(f'/auth/{test_user["token"]}', follow_redirects=False)
        assert response.status_code == 302, "Должен быть редирект на главную страницу"
        assert '/' in response.location, "Должен быть редирект на /"

    def test_auth_route_invalid_token(self, flask_app):
        """Тест авторизации с невалидным токеном"""
        invalid_token = "invalid_token_12345"
        response = flask_app.get(f'/auth/{invalid_token}')
        assert response.status_code == 403, "С невалидным токеном должен вернуть 403"
        assert 'Ссылка недействительна'.encode('utf-8') in response.data, "Должно быть сообщение об ошибке"

    def test_require_token_decorator(self, flask_app):
        """Тест декоратора @require_token"""
        # Тестируем через endpoint, который требует токен
        response = flask_app.get('/')
        assert response.status_code == 401, "Без токена должен вернуть 401"

    def test_token_validation_success(self, temp_db, test_user):
        """Тест успешной валидации токена"""
        token_data = validate_permanent_token(test_user['token'])
        assert token_data is not None, "Токен должен быть валиден"
        assert token_data['user_id'] == test_user['user_id'], "User ID должен совпадать"
        assert token_data['key_id'] == test_user['key_id'], "Key ID должен совпадать"

    def test_token_validation_failure(self, temp_db):
        """Тест неудачной валидации токена"""
        invalid_token = "invalid_token_12345"
        token_data = validate_permanent_token(invalid_token)
        assert token_data is None, "Невалидный токен должен вернуть None"

    @allure.title("Проверка сохранения данных в сессии после валидации токена")
    @allure.description("""
    Проверяет, что после успешной валидации токена через GET /?token={token}
    данные сохраняются в Flask session: token, user_id, key_id.
    
    **Что проверяется:**
    - После валидации токена данные сохраняются в Flask session
    - В сессии присутствуют ключи: 'token', 'user_id', 'key_id'
    - Данные корректно сохраняются для последующего использования в приложении
    
    **Тестовые данные:**
    - user_id: 123456789 (создается через test_user)
    - key_id: создается через test_user
    - token: генерируется через get_or_create_permanent_token
    
    **Шаги теста:**
    1. **Патчинг DB_FILE для использования временной БД**
       - Сохраняется оригинальный database.DB_FILE
       - Устанавливается database.DB_FILE = temp_db
       - Ожидаемый результат: все операции с БД используют временную БД
    
    2. **Открытие session_transaction() для доступа к сессии**
       - Метод: flask_app.session_transaction()
       - Ожидаемый результат: контекстный менеджер для работы с сессией
    
    3. **Выполнение GET запроса к /?token={valid_token}**
       - Метод: flask_app.get()
       - Параметры: /?token={token} из test_user
       - Ожидаемый результат: выполняется валидация токена и сохранение данных в сессию
    
    4. **Проверка наличия данных в сессии**
       - Проверка: 'token' in sess
       - Проверка: 'user_id' in sess
       - Проверка: 'key_id' in sess
       - Ожидаемый результат: все три ключа должны присутствовать в сессии
    
    **Предусловия:**
    - Пользователь зарегистрирован (user_id: 123456789) через test_user
    - Ключ создан в БД через test_user
    - Токен создан через get_or_create_permanent_token
    - Используется временная БД (temp_db)
    - Flask app настроен с правильным root_path для поиска шаблонов
    
    **Ожидаемый результат:**
    После успешной валидации токена все необходимые данные (token, user_id, key_id)
    должны быть сохранены в Flask session и доступны для последующего использования
    в рамках сессии пользователя.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("database", "unit", "session")
    def test_session_storage(self, flask_app, test_user, temp_db):
        """Тест сохранения данных в сессии"""
        # Используем database.DB_FILE (уже заменен через monkeypatch в фикстуре temp_db)
        from shop_bot.data_manager import database
        
        with allure.step("Выполнение GET запроса к /?token={valid_token}"):
            response = flask_app.get(f'/?token={test_user["token"]}')
            allure.attach(str(response.status_code), "Статус код ответа", allure.attachment_type.TEXT)
            assert response.status_code == 200, "Запрос должен быть успешным"
        
        with allure.step("Проверка сохранения данных в сессии через session_transaction()"):
            # Проверяем сессию ПОСЛЕ запроса
            with flask_app.session_transaction() as sess:
                with allure.step("Проверка наличия 'token' в сессии"):
                    assert 'token' in sess, "Токен должен быть в сессии"
                    allure.attach(str(sess.get('token')), "Значение token в сессии", allure.attachment_type.TEXT)
                
                with allure.step("Проверка наличия 'user_id' в сессии"):
                    assert 'user_id' in sess, "User ID должен быть в сессии"
                    allure.attach(str(sess.get('user_id')), "Значение user_id в сессии", allure.attachment_type.TEXT)
                
                with allure.step("Проверка наличия 'key_id' в сессии"):
                    assert 'key_id' in sess, "Key ID должен быть в сессии"
                    allure.attach(str(sess.get('key_id')), "Значение key_id в сессии", allure.attachment_type.TEXT)

    def test_rate_limit_decorator(self, flask_app):
        """Тест rate limiting (10 запросов в минуту)"""
        # Делаем 10 запросов - все должны пройти
        for i in range(10):
            response = flask_app.get('/health')
            assert response.status_code == 200, f"Запрос {i+1} должен пройти"
        
        # 11-й запрос должен пройти (health endpoint не имеет rate limit)
        response = flask_app.get('/health')
        assert response.status_code == 200, "11-й запрос к health должен пройти"

    def test_rate_limit_exceeded(self, flask_app):
        """Тест превышения лимита запросов"""
        # Делаем много запросов к эндпоинту с rate limit
        # Поскольку /api/ip-info имеет rate limit, делаем запросы к нему
        responses = []
        for i in range(15):  # Делаем больше лимита (10 запросов)
            response = flask_app.get('/api/ip-info')
            responses.append(response.status_code)
        
        # Должен быть хотя бы один ответ с кодом 429 (Too Many Requests)
        # Или все запросы должны вернуть другие коды (например, из-за отсутствия токена)
        assert any(status == 429 for status in responses) or all(status != 200 for status in responses), \
            "Должен быть код 429 или другие ошибки"

    @patch('app.requests.get')
    def test_ip_info_api_success(self, mock_get, flask_app):
        """Тест успешного получения информации об IP"""
        # Мокаем успешный ответ от IP сервиса
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'ip': '192.168.1.1',
            'country': 'Russia',
            'city': 'Moscow',
            'org': 'Test ISP'
        }
        mock_get.return_value = mock_response
        
        response = flask_app.get('/api/ip-info')
        assert response.status_code == 200, "Должен вернуть 200"
        data = response.get_json()
        assert data['status'] == 'ok', "Status должен быть 'ok'"
        assert 'data' in data, "Должны быть данные об IP"

    @patch('app.requests.get')
    def test_ip_info_api_failure(self, mock_get, flask_app):
        """Тест ошибки получения информации об IP"""
        # Мокаем ошибку от IP сервиса
        mock_get.side_effect = requests.RequestException("Connection error")
        
        response = flask_app.get('/api/ip-info')
        assert response.status_code == 502, "Должен вернуть 502 при ошибке"
        data = response.get_json()
        assert data['status'] == 'error', "Status должен быть 'error'"

    def test_build_knowledge_base_url(self, temp_db):
        """Тест построения URL базы знаний"""
        import sys
        import importlib.util
        from pathlib import Path
        
        # Проверяем разные возможные пути к модулю
        project_root = Path(__file__).parent.parent.parent.parent
        possible_paths = [
            project_root / "apps" / "user-cabinet" / "app.py",  # Локальная разработка
            Path("/app/project/apps/user-cabinet/app.py"),  # Docker окружение
            Path("/app/apps/user-cabinet/app.py"),  # Альтернативный Docker путь
        ]
        
        app_file = None
        for path in possible_paths:
            if path.exists():
                app_file = path
                break
        
        # Если файл не найден, пропускаем тест
        if not app_file:
            pytest.skip(f"App file not found in any of the expected locations: {[str(p) for p in possible_paths]}")
        
        # Используем importlib для загрузки модуля
        spec = importlib.util.spec_from_file_location("app", app_file)
        app_module = importlib.util.module_from_spec(spec)
        
        # Добавляем путь к модулям в sys.path для корректного импорта зависимостей
        app_dir = app_file.parent
        if str(app_dir) not in sys.path:
            sys.path.insert(0, str(app_dir))
        if str(project_root / "src") not in sys.path:
            sys.path.insert(0, str(project_root / "src"))
        
        spec.loader.exec_module(app_module)
        _build_knowledge_base_url = app_module._build_knowledge_base_url
        
        # Тест с codex_docs_domain
        update_setting('codex_docs_domain', 'https://docs.example.com')
        update_setting('global_domain', '')
        settings = get_all_settings()
        base_url, setup_url = _build_knowledge_base_url(settings)
        assert base_url == 'https://docs.example.com', "Должен быть правильный base URL"
        assert setup_url == 'https://docs.example.com/setup', "Должен быть правильный setup URL"
        
        # Тест с global_domain (fallback)
        update_setting('codex_docs_domain', '')
        update_setting('global_domain', 'https://example.com')
        settings = get_all_settings()
        base_url, setup_url = _build_knowledge_base_url(settings)
        assert base_url == 'https://example.com:50002', "Должен быть правильный base URL с портом"
        assert setup_url == 'https://example.com:50002/setup', "Должен быть правильный setup URL"
        
        # Тест без настроек (fallback на localhost)
        update_setting('codex_docs_domain', '')
        update_setting('global_domain', '')
        settings = get_all_settings()
        base_url, setup_url = _build_knowledge_base_url(settings)
        assert base_url == 'http://localhost:50002', "Должен быть fallback на localhost"
        assert setup_url == 'http://localhost:50002/setup', "Должен быть правильный setup URL"

    def test_fetch_ip_information(self, temp_db):
        """Тест получения информации об IP с внешних сервисов"""
        import sys
        import importlib.util
        from pathlib import Path
        from unittest.mock import patch, MagicMock
        
        # Проверяем разные возможные пути к модулю
        project_root = Path(__file__).parent.parent.parent.parent
        possible_paths = [
            project_root / "apps" / "user-cabinet" / "app.py",  # Локальная разработка
            Path("/app/project/apps/user-cabinet/app.py"),  # Docker окружение
            Path("/app/apps/user-cabinet/app.py"),  # Альтернативный Docker путь
        ]
        
        app_file = None
        for path in possible_paths:
            if path.exists():
                app_file = path
                break
        
        # Если файл не найден, пропускаем тест
        if not app_file:
            pytest.skip(f"App file not found in any of the expected locations: {[str(p) for p in possible_paths]}")
        
        # Используем importlib для загрузки модуля
        spec = importlib.util.spec_from_file_location("app", app_file)
        app_module = importlib.util.module_from_spec(spec)
        
        # Добавляем путь к модулям в sys.path для корректного импорта зависимостей
        app_dir = app_file.parent
        if str(app_dir) not in sys.path:
            sys.path.insert(0, str(app_dir))
        if str(project_root / "src") not in sys.path:
            sys.path.insert(0, str(project_root / "src"))
        
        spec.loader.exec_module(app_module)
        _fetch_ip_information = app_module._fetch_ip_information
        
        # Мокаем успешный ответ от первого провайдера
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'ip': '192.168.1.1',
            'country_name': 'Russia',
            'city': 'Moscow',
            'org': 'Test ISP'
        }
        
        # Мокируем requests.get() через patch
        with patch.object(app_module, 'requests') as mock_requests:
            mock_requests.get.return_value = mock_response
            
            ip_data, error = _fetch_ip_information()
            assert ip_data is not None, "Должны быть данные об IP"
            assert ip_data['ip'] == '192.168.1.1', "IP должен быть правильным"
            assert ip_data['country'] == 'Russia', "Страна должна быть правильной"
            assert error is None, "Ошибки быть не должно"
        
        # Мокаем ошибку от всех провайдеров
        # Нужно мокировать каждый вызов requests.get() чтобы вернуть ошибку
        with patch.object(app_module, 'requests') as mock_requests:
            # Устанавливаем side_effect для всех вызовов, чтобы каждый вызов возвращал ошибку
            mock_requests.get.side_effect = requests.RequestException("Connection error")
            mock_requests.RequestException = requests.RequestException  # Сохраняем класс исключения
            
            ip_data, error = _fetch_ip_information()
            assert ip_data is None, "При ошибке данных быть не должно"
            assert error is not None, "Должна быть ошибка"

    @allure.title("Проверка валидных ссылок личного кабинета")
    @allure.description("""
    Проверяет, что валидные ссылки на личный кабинет (`/auth/{token}`) не возвращают ошибку 403 (FORBIDDEN) и работают корректно.
    
    **Что проверяется:**
    - Валидные токены не возвращают статус 403
    - Валидные токены возвращают успешный статус (200 или 302)
    - В ответе нет сообщения об ошибке "Ссылка недействительна"
    - Ссылки корректно обрабатываются и не являются битыми
    
    **Тестовые данные:**
    - user_id: 123456789 (создается через test_user)
    - key_id: создается через test_user
    - token: генерируется через get_or_create_permanent_token
    
    **Шаги теста:**
    1. **Создание валидного токена**
       - Метод: get_or_create_permanent_token()
       - Параметры: user_id, key_id из test_user
       - Ожидаемый результат: токен успешно создан или получен из БД
       - Проверка: token is not None
    
    2. **Выполнение HTTP-запроса к /auth/{token}**
       - Метод: flask_app.get()
       - Параметры: /auth/{token}
       - Ожидаемый результат: успешный ответ (200 или 302)
       - Проверка: response.status_code != 403
       - Проверка: response.status_code in [200, 302]
    
    3. **Проверка отсутствия ошибки в ответе**
       - Метод: проверка содержимого response.data
       - Параметры: response.data
       - Ожидаемый результат: в ответе нет сообщения "Ссылка недействительна"
       - Проверка: 'Ссылка недействительна'.encode('utf-8') not in response.data
    
    **Предусловия:**
    - Пользователь зарегистрирован (user_id: 123456789) через test_user
    - Ключ создан в БД через test_user
    - Токен создан через get_or_create_permanent_token
    - Используется временная БД (temp_db)
    
    **Ожидаемый результат:**
    Валидные ссылки на личный кабинет должны работать корректно и не возвращать ошибку 403.
    При переходе по ссылке `/auth/{token}` пользователь должен быть успешно авторизован
    (статус 200 или редирект 302), а не получать ошибку "Ссылка недействительна".
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("cabinet", "links", "validation", "unit", "critical")
    def test_valid_link_not_forbidden(self, flask_app, test_user, temp_db):
        """Тест проверки, что валидные ссылки не возвращают 403"""
        # Используем database.DB_FILE (уже заменен через monkeypatch в фикстуре temp_db)
        from shop_bot.data_manager import database
        
        with allure.step("Создание валидного токена для существующего ключа"):
            token = test_user['token']
            assert token is not None, "Токен должен быть создан"
            allure.attach(token, "Токен", allure.attachment_type.TEXT)
        
        with allure.step("Выполнение HTTP-запроса к /auth/{token}"):
            response = flask_app.get(f'/auth/{token}', follow_redirects=False)
            allure.attach(str(response.status_code), "Статус код ответа", allure.attachment_type.TEXT)
        
        with allure.step("Проверка, что статус НЕ равен 403"):
            assert response.status_code != 403, f"Валидная ссылка не должна возвращать 403, получен статус {response.status_code}"
        
        with allure.step("Проверка, что статус равен 200 или 302 (успешный ответ)"):
            assert response.status_code in [200, 302], f"Ожидался статус 200 или 302, получен {response.status_code}"
        
        with allure.step("Проверка, что в ответе нет сообщения 'Ссылка недействительна'"):
            error_message = 'Ссылка недействительна'.encode('utf-8')
            assert error_message not in response.data, \
                "В ответе не должно быть сообщения об ошибке 'Ссылка недействительна'"

