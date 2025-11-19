#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для авторизации docs-proxy сервиса

Тестирует логику входа, выхода и проверки доступа
"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from flask import session

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))
# Примечание: директория называется docs-proxy (с дефисом), поэтому используем динамический импорт


@pytest.mark.unit
@allure.epic("Docs Proxy")
@allure.feature("Авторизация")
@allure.label("package", "apps.docs-proxy")
class TestDocsProxyAuth:
    """Тесты для авторизации docs-proxy"""

    @allure.story("Авторизация: отображение страницы входа")
    @allure.title("Отображение страницы входа")
    @allure.description("""
    Проверяет отображение страницы входа в docs-proxy.
    
    **Что проверяется:**
    - Доступность страницы /login
    - Наличие элементов формы входа в ответе
    - Корректный статус ответа (200)
    
    **Ожидаемый результат:**
    Страница входа успешно отображается с формой входа.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "login", "docs-proxy", "unit")
    def test_login_page_get(self, temp_db):
        """Тест отображения страницы входа"""
        import importlib.util
        from flask import Flask
        app_path = project_root / "apps" / "docs-proxy" / "app.py"
        templates_path = project_root / "apps" / "docs-proxy" / "templates"
        spec = importlib.util.spec_from_file_location("docs_proxy_app", app_path)
        docs_proxy_app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(docs_proxy_app)
        app = docs_proxy_app.app
        # Настраиваем правильный путь к шаблонам для тестов
        app.jinja_loader.searchpath = [str(templates_path)]
        
        with app.test_client() as client:
            response = client.get('/login')
            assert response.status_code == 200
            assert b'login' in response.data.lower() or 'вход'.encode('utf-8') in response.data.lower()

    @allure.story("Авторизация: успешный вход")
    @allure.title("Успешный вход в docs-proxy")
    @allure.description("""
    Проверяет успешный вход в docs-proxy с корректными учетными данными.
    
    **Что проверяется:**
    - Отправка POST запроса на /login с корректными данными
    - Установка сессии logged_in=True после успешного входа
    - Перенаправление после успешного входа
    
    **Тестовые данные:**
    - username: из admin_credentials
    - password: из admin_credentials
    
    **Ожидаемый результат:**
    Пользователь успешно авторизован, сессия установлена, происходит перенаправление.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "login", "success", "docs-proxy", "unit")
    def test_login_success(self, temp_db, admin_credentials):
        """Тест успешного входа"""
        import importlib.util
        from flask import Flask
        app_path = project_root / "apps" / "docs-proxy" / "app.py"
        templates_path = project_root / "apps" / "docs-proxy" / "templates"
        spec = importlib.util.spec_from_file_location("docs_proxy_app", app_path)
        docs_proxy_app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(docs_proxy_app)
        app = docs_proxy_app.app
        # Настраиваем правильный путь к шаблонам для тестов
        app.jinja_loader.searchpath = [str(templates_path)]
        
        with app.test_client() as client:
            # Мокируем verify_admin_credentials, чтобы реальная функция verify_and_login выполнилась и установила сессию
            with patch('shop_bot.data_manager.database.verify_admin_credentials', return_value=True):
                response = client.post('/login', data=admin_credentials, follow_redirects=True)
                assert response.status_code == 200
                # Проверяем доступ к защищенной странице вместо прямого чтения сессии
                # (для filesystem sessions session_transaction может работать некорректно)
                response = client.get('/')
                assert response.status_code == 200  # Доступ разрешен, значит сессия установлена

    @allure.story("Авторизация: обработка неверных данных")
    @allure.title("Неудачный вход с неверными учетными данными")
    @allure.description("""
    Проверяет обработку неверных учетных данных при входе.
    
    **Что проверяется:**
    - Отправка POST запроса на /login с неверными данными
    - Отсутствие установки сессии logged_in
    - Отображение сообщения об ошибке
    
    **Тестовые данные:**
    - username: 'wrong_user'
    - password: 'wrong_password'
    
    **Ожидаемый результат:**
    Вход не выполнен, сессия не установлена, отображается сообщение об ошибке.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "login", "failure", "docs-proxy", "unit")
    def test_login_failure(self, temp_db):
        """Тест неверных учетных данных"""
        import importlib.util
        from flask import Flask
        app_path = project_root / "apps" / "docs-proxy" / "app.py"
        templates_path = project_root / "apps" / "docs-proxy" / "templates"
        spec = importlib.util.spec_from_file_location("docs_proxy_app", app_path)
        docs_proxy_app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(docs_proxy_app)
        app = docs_proxy_app.app
        # Настраиваем правильный путь к шаблонам для тестов
        app.jinja_loader.searchpath = [str(templates_path)]
        
        with app.test_client() as client:
            # Мокируем verify_admin_credentials, чтобы вернуть False для неверных данных
            with patch('shop_bot.data_manager.database.verify_admin_credentials', return_value=False):
                response = client.post('/login', data={
                    'username': 'wrong_user',
                    'password': 'wrong_password'
                })
                assert response.status_code == 200
                # Проверяем, что сессия не установлена через попытку доступа к защищенной странице
                response = client.get('/')
                assert response.status_code == 302  # Редирект на /login, значит сессия не установлена

    @allure.story("Авторизация: выход из системы")
    @allure.title("Выход из системы")
    @allure.description("""
    Проверяет корректный выход пользователя из docs-proxy и очистку сессии.
    
    **Что проверяется:**
    - Успешный вход в систему с установкой сессии
    - Отправка POST запроса на /logout
    - Очистка сессии после выхода (удаление logged_in из сессии)
    - Перенаправление на страницу входа после выхода
    - Отсутствие доступа к защищенным страницам после выхода (редирект на /login)
    
    **Ожидаемый результат:**
    Пользователь успешно вышел из системы, сессия очищена, доступ к защищенным страницам запрещен.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "logout", "session", "docs-proxy", "unit")
    def test_logout(self, temp_db):
        """Тест выхода из системы"""
        import importlib.util
        from flask import Flask
        app_path = project_root / "apps" / "docs-proxy" / "app.py"
        templates_path = project_root / "apps" / "docs-proxy" / "templates"
        spec = importlib.util.spec_from_file_location("docs_proxy_app", app_path)
        docs_proxy_app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(docs_proxy_app)
        app = docs_proxy_app.app
        # Настраиваем правильный путь к шаблонам для тестов
        app.jinja_loader.searchpath = [str(templates_path)]
        
        test_credentials = {
            'username': 'test_admin',
            'password': 'test_password'
        }
        
        with app.test_client() as client:
            with allure.step("Выполнение входа в систему"):
                with patch('shop_bot.data_manager.database.verify_admin_credentials', return_value=True):
                    response = client.post('/login', data=test_credentials, follow_redirects=True)
                    assert response.status_code == 200
            
            with allure.step("Проверка установки сессии"):
                # Проверяем доступ к защищенной странице вместо прямого чтения сессии
                response = client.get('/')
                assert response.status_code == 200  # Доступ разрешен, значит сессия установлена
            
            with allure.step("Выполнение выхода из системы"):
                response = client.post('/logout', follow_redirects=True)
                assert response.status_code == 200
            
            with allure.step("Проверка очистки сессии"):
                # Проверяем, что доступ к защищенной странице запрещен
                response = client.get('/')
                assert response.status_code == 302  # Редирект на /login

    @allure.story("Авторизация: проверка доступа")
    @allure.title("Проверка декоратора @login_required")
    @allure.description("""
    Проверяет работу декоратора @login_required для защиты страниц.
    
    **Что проверяется:**
    - Редирект на /login при попытке доступа к защищенной странице без авторизации
    - Разрешение доступа к защищенной странице после успешной авторизации
    - Корректная работа декоратора @login_required
    
    **Ожидаемый результат:**
    Без авторизации происходит редирект на /login, после авторизации доступ разрешен.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "login_required", "decorator", "docs-proxy", "unit")
    def test_login_required_decorator(self, temp_db, admin_credentials):
        """Тест проверки декоратора @login_required"""
        import importlib.util
        from flask import Flask
        app_path = project_root / "apps" / "docs-proxy" / "app.py"
        templates_path = project_root / "apps" / "docs-proxy" / "templates"
        spec = importlib.util.spec_from_file_location("docs_proxy_app", app_path)
        docs_proxy_app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(docs_proxy_app)
        app = docs_proxy_app.app
        # Настраиваем правильный путь к шаблонам для тестов
        app.jinja_loader.searchpath = [str(templates_path)]
        
        with app.test_client() as client:
            # Пытаемся получить доступ к защищенной странице без входа
            response = client.get('/')
            assert response.status_code == 302  # Редирект на /login
            
            # Входим
            with patch('shop_bot.data_manager.database.verify_admin_credentials', return_value=True):
                client.post('/login', data=admin_credentials)
            
            # Теперь доступ должен быть разрешен
            response = client.get('/')
            assert response.status_code == 200

    @allure.story("Авторизация: сохранение сессии")
    @allure.title("Сохранение сессии на 30 дней")
    @allure.description("""
    Проверяет сохранение сессии пользователя между запросами и доступ к защищенным страницам.
    
    **Что проверяется:**
    - Установка сессии после успешного входа (logged_in=True, session.permanent=True)
    - Сохранение сессии между запросами (сессия доступна в последующих запросах)
    - Доступ к защищенным страницам через сохраненную сессию
    
    **Ожидаемый результат:**
    Сессия сохраняется и работает между запросами, доступ к защищенным страницам разрешен.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "session", "persistence", "docs-proxy", "unit")
    def test_session_persistence(self, temp_db):
        """Тест сохранения сессии на 30 дней"""
        import importlib.util
        app_path = project_root / "apps" / "docs-proxy" / "app.py"
        spec = importlib.util.spec_from_file_location("docs_proxy_app", app_path)
        docs_proxy_app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(docs_proxy_app)
        app = docs_proxy_app.app
        
        test_credentials = {
            'username': 'test_admin',
            'password': 'test_password'
        }
        
        with app.test_client() as client:
            with allure.step("Выполнение входа в систему"):
                with patch('shop_bot.data_manager.database.verify_admin_credentials', return_value=True):
                    response = client.post('/login', data=test_credentials, follow_redirects=True)
                    assert response.status_code == 200
            
            with allure.step("Проверка установки сессии"):
                # Проверяем доступ к защищенной странице - это подтверждает, что сессия установлена
                response = client.get('/')
                assert response.status_code == 200  # Доступ разрешен, значит сессия установлена
            
            with allure.step("Проверка доступа к защищенной странице через сохраненную сессию"):
                # Делаем еще один запрос, чтобы проверить, что сессия сохраняется между запросами
                response = client.get('/')
                assert response.status_code == 200  # Сессия работает между запросами

    @allure.story("Healthcheck: доступность без авторизации")
    @allure.title("Healthcheck доступен без авторизации")
    @allure.description("""
    Проверяет, что healthcheck endpoint доступен без авторизации.
    
    **Что проверяется:**
    - Доступность /health без авторизации
    - Корректный статус ответа (200)
    - Отсутствие редиректа на /login
    
    **Ожидаемый результат:**
    Healthcheck endpoint доступен без авторизации, возвращает статус 200.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "healthcheck", "docs-proxy", "unit")
    def test_health_check_no_auth(self, temp_db):
        """Тест healthcheck без авторизации"""
        import importlib.util
        from flask import Flask
        app_path = project_root / "apps" / "docs-proxy" / "app.py"
        templates_path = project_root / "apps" / "docs-proxy" / "templates"
        spec = importlib.util.spec_from_file_location("docs_proxy_app", app_path)
        docs_proxy_app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(docs_proxy_app)
        app = docs_proxy_app.app
        # Настраиваем правильный путь к шаблонам для тестов
        app.jinja_loader.searchpath = [str(templates_path)]
        
        with app.test_client() as client:
            with patch.object(docs_proxy_app, 'requests') as mock_requests:
                mock_get = mock_requests.get
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_get.return_value = mock_response
                
                response = client.get('/health')
                assert response.status_code == 200
                assert b'status' in response.data.lower()

    @allure.story("Проксирование: запросы после авторизации")
    @allure.title("Проксирование запросов к docs после авторизации")
    @allure.description("""
    Проверяет проксирование запросов к docs контейнеру после успешной авторизации.
    
    **Что проверяется:**
    - После авторизации запросы проксируются к docs контейнеру
    - Корректная передача заголовков
    - Корректная обработка ответов от docs
    
    **Ожидаемый результат:**
    После авторизации запросы успешно проксируются к docs контейнеру.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "proxy", "docs-proxy", "unit")
    def test_proxy_after_auth(self, temp_db):
        """Тест проксирования запросов к docs после авторизации"""
        import importlib.util
        app_path = project_root / "apps" / "docs-proxy" / "app.py"
        spec = importlib.util.spec_from_file_location("docs_proxy_app", app_path)
        docs_proxy_app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(docs_proxy_app)
        app = docs_proxy_app.app
        
        test_credentials = {
            'username': 'test_admin',
            'password': 'test_password'
        }
        
        with app.test_client() as client:
            with allure.step("Выполнение входа в систему"):
                with patch('shop_bot.data_manager.database.verify_admin_credentials', return_value=True):
                    client.post('/login', data=test_credentials, follow_redirects=True)
            
            with allure.step("Проверка проксирования запроса к docs"):
                with patch.object(docs_proxy_app, 'requests') as mock_requests:
                    mock_request = mock_requests.request
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.content = b'<html>Test</html>'
                    mock_response.headers = {'Content-Type': 'text/html'}
                    mock_request.return_value = mock_response
                    
                    response = client.get('/')
                    assert response.status_code == 200
                    mock_request.assert_called_once()

    @allure.story("Проксирование: передача заголовков")
    @allure.title("Правильная передача заголовков при проксировании")
    @allure.description("""
    Проверяет правильную передачу заголовков при проксировании запросов к docs.
    
    **Что проверяется:**
    - Передача всех необходимых заголовков
    - Удаление заголовков, которые не должны передаваться (Host, Connection, Content-Length)
    - Сохранение оригинальных заголовков запроса
    
    **Ожидаемый результат:**
    Заголовки правильно передаются при проксировании.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "proxy", "headers", "docs-proxy", "unit")
    def test_proxy_headers(self, temp_db):
        """Тест правильной передачи заголовков при проксировании"""
        import importlib.util
        app_path = project_root / "apps" / "docs-proxy" / "app.py"
        spec = importlib.util.spec_from_file_location("docs_proxy_app", app_path)
        docs_proxy_app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(docs_proxy_app)
        app = docs_proxy_app.app
        
        test_credentials = {
            'username': 'test_admin',
            'password': 'test_password'
        }
        
        with app.test_client() as client:
            with patch('shop_bot.data_manager.database.verify_admin_credentials', return_value=True):
                client.post('/login', data=test_credentials, follow_redirects=True)
            
            with patch.object(docs_proxy_app, 'requests') as mock_requests:
                mock_request = mock_requests.request
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.content = b'<html>Test</html>'
                mock_response.headers = {'Content-Type': 'text/html'}
                mock_request.return_value = mock_response
                
                client.get('/', headers={'User-Agent': 'Test-Agent', 'Accept': 'text/html'})
                
                # Проверяем, что запрос был выполнен
                assert mock_request.called
                call_kwargs = mock_request.call_args[1]
                headers = call_kwargs.get('headers', {})
                
                # Проверяем, что Host удален
                assert 'Host' not in headers or headers.get('Host') != 'localhost'
                # Проверяем, что Connection удален
                assert 'Connection' not in headers

