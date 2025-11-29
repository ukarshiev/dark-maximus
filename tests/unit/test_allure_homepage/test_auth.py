#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для авторизации allure-homepage сервиса

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
# Примечание: директория называется allure-homepage (с дефисом), поэтому используем динамический импорт


def setup_app_with_templates():
    """
    Вспомогательная функция для настройки Flask app с правильными путями к шаблонам.
    
    Returns:
        tuple: (app, allure_homepage_app) - настроенное приложение и модуль
    """
    import importlib.util
    app_path = project_root / "apps" / "allure-homepage" / "app.py"
    templates_path = project_root / "apps" / "allure-homepage" / "templates"
    spec = importlib.util.spec_from_file_location("allure_homepage_app", app_path)
    allure_homepage_app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(allure_homepage_app)
    app = allure_homepage_app.app
    # Настраиваем правильный путь к шаблонам для тестов
    app.jinja_loader.searchpath = [str(templates_path)]
    return app, allure_homepage_app


@pytest.mark.unit
@allure.epic("Allure Homepage")
@allure.feature("Авторизация")
@allure.label("package", "apps.allure_homepage")
class TestAllureHomepageAuth:
    """Тесты для авторизации allure-homepage"""

    @allure.story("Авторизация: отображение страницы входа")
    @allure.title("Отображение страницы входа")
    @allure.description("""
    Проверяет отображение страницы входа в allure-homepage.
    
    **Что проверяется:**
    - Доступность страницы /login
    - Наличие элементов формы входа в ответе
    - Корректный статус ответа (200)
    
    **Ожидаемый результат:**
    Страница входа успешно отображается с формой входа.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "login", "allure-homepage", "unit")
    def test_login_page_get(self, temp_db):
        """Тест отображения страницы входа"""
        app, _ = setup_app_with_templates()
        
        with app.test_client() as client:
            response = client.get('/login')
            assert response.status_code == 200
            assert b'login' in response.data.lower() or 'вход'.encode('utf-8') in response.data.lower()

    @allure.story("Авторизация: успешный вход")
    @allure.title("Успешный вход в allure-homepage")
    @allure.description("""
    Проверяет успешный вход в allure-homepage с корректными учетными данными.
    
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
    @allure.tag("auth", "login", "success", "allure-homepage", "unit")
    def test_login_success(self, temp_db, admin_credentials):
        """Тест успешного входа"""
        app, allure_homepage_app = setup_app_with_templates()
        
        with app.test_client() as client:
            # Мокируем verify_admin_credentials в database модуле
            # verify_and_login импортирует его внутри функции, поэтому патчим в database
            with patch('shop_bot.data_manager.database.verify_admin_credentials', return_value=True):
                response = client.post('/login', data=admin_credentials, follow_redirects=True)
                # Проверяем отсутствие ошибок 500 (Internal Server Error), которые могут быть связаны с AttributeError
                assert response.status_code != 500, (
                    f"Ошибка 500 при авторизации. Возможно, ошибка AttributeError не исправлена. "
                    f"Ответ: {response.data.decode('utf-8')[:500]}"
                )
                assert response.status_code == 200
                # Проверяем отсутствие упоминаний об ошибке AttributeError в ответе
                response_text = response.data.decode('utf-8').lower()
                assert 'attributerror' not in response_text and 'nonetype' not in response_text, (
                    f"Обнаружена ошибка AttributeError в ответе: {response.data.decode('utf-8')[:500]}"
                )
                # Проверяем доступ к защищенной странице вместо прямого чтения сессии
                # (для filesystem sessions session_transaction может работать некорректно)
                response = client.get('/allure-docker-service/')
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
    @allure.tag("auth", "login", "failure", "allure-homepage", "unit")
    def test_login_failure(self, temp_db):
        """Тест неверных учетных данных"""
        app, allure_homepage_app = setup_app_with_templates()
        
        with app.test_client() as client:
            # Мокируем verify_and_login в модуле allure_homepage_app, где она импортирована
            with patch.object(allure_homepage_app, 'verify_and_login', return_value=False):
                response = client.post('/login', data={
                    'username': 'wrong_user',
                    'password': 'wrong_password'
                })
                assert response.status_code == 200
                # Проверяем, что сессия не установлена
                with client.session_transaction() as sess:
                    assert sess.get('logged_in') is None

    @allure.story("Авторизация: выход из системы")
    @allure.title("Выход из системы")
    @allure.description("""
    Проверяет корректный выход пользователя из allure-homepage и очистку сессии.
    
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
    @allure.tag("auth", "logout", "session", "allure-homepage", "unit")
    def test_logout(self, temp_db):
        """Тест выхода из системы"""
        app, allure_homepage_app = setup_app_with_templates()
        
        test_credentials = {
            'username': 'test_admin',
            'password': 'test_password'
        }
        
        def mock_verify_and_login(username, password):
            from flask import session
            session['logged_in'] = True
            session.permanent = True
            return True
        
        with app.test_client() as client:
            with allure.step("Выполнение входа в систему"):
                with patch.object(allure_homepage_app, 'verify_and_login', side_effect=mock_verify_and_login):
                    response = client.post('/login', data=test_credentials, follow_redirects=True)
                    assert response.status_code == 200
            
            with allure.step("Проверка установки сессии"):
                with client.session_transaction() as sess:
                    assert sess.get('logged_in') is True
            
            with allure.step("Выполнение выхода из системы"):
                response = client.post('/logout', follow_redirects=True)
                assert response.status_code == 200
            
            with allure.step("Проверка очистки сессии"):
                with client.session_transaction() as sess:
                    assert sess.get('logged_in') is None
                
                # Проверяем, что доступ к защищенной странице запрещен
                response = client.get('/allure-docker-service/')
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
    @allure.tag("auth", "login_required", "decorator", "allure-homepage", "unit")
    def test_login_required_decorator(self, temp_db, admin_credentials):
        """Тест проверки декоратора @login_required"""
        app, allure_homepage_app = setup_app_with_templates()
        
        with app.test_client() as client:
            # Пытаемся получить доступ к защищенной странице без входа
            response = client.get('/allure-docker-service/')
            assert response.status_code == 302  # Редирект на /login
            
            # Входим - мокируем verify_admin_credentials в database модуле
            with patch('shop_bot.data_manager.database.verify_admin_credentials', return_value=True):
                client.post('/login', data=admin_credentials, follow_redirects=True)
            
            # Теперь доступ должен быть разрешен
            response = client.get('/allure-docker-service/')
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
    @allure.tag("auth", "session", "persistence", "allure-homepage", "unit")
    def test_session_persistence(self, temp_db):
        """Тест сохранения сессии на 30 дней"""
        app, allure_homepage_app = setup_app_with_templates()
        
        test_credentials = {
            'username': 'test_admin',
            'password': 'test_password'
        }
        
        def mock_verify_and_login(username, password):
            from flask import session
            session['logged_in'] = True
            session.permanent = True
            return True
        
        with app.test_client() as client:
            with allure.step("Выполнение входа в систему"):
                with patch.object(allure_homepage_app, 'verify_and_login', side_effect=mock_verify_and_login):
                    response = client.post('/login', data=test_credentials, follow_redirects=True)
                    assert response.status_code == 200
            
            with allure.step("Проверка установки сессии"):
                with client.session_transaction() as sess:
                    logged_in = sess.get('logged_in')
                    permanent = sess.get('_permanent', False)
                    assert logged_in is True
                    assert permanent is True
            
            with allure.step("Проверка доступа к защищенной странице через сохраненную сессию"):
                response = client.get('/allure-docker-service/')
                assert response.status_code == 200

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
    @allure.tag("auth", "healthcheck", "allure-homepage", "unit")
    def test_health_check_no_auth(self, temp_db):
        """Тест healthcheck без авторизации"""
        app, _ = setup_app_with_templates()
        
        with app.test_client() as client:
            response = client.get('/health')
            assert response.status_code == 200
            assert b'status' in response.data.lower()

    @allure.story("Проксирование: запросы после авторизации")
    @allure.title("Проксирование запросов к allure-service после авторизации")
    @allure.description("""
    Проверяет проксирование запросов к allure-service после успешной авторизации.
    
    **Что проверяется:**
    - После авторизации запросы проксируются к allure-service
    - Корректная передача заголовков
    - Корректная обработка ответов от allure-service
    
    **Ожидаемый результат:**
    После авторизации запросы успешно проксируются к allure-service.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "proxy", "allure-homepage", "unit")
    def test_proxy_after_auth(self, temp_db):
        """Тест проксирования запросов к allure-service после авторизации"""
        app, allure_homepage_app = setup_app_with_templates()
        
        test_credentials = {
            'username': 'test_admin',
            'password': 'test_password'
        }
        
        def mock_verify_and_login(username, password):
            from flask import session
            session['logged_in'] = True
            session.permanent = True
            return True
        
        with app.test_client() as client:
            with allure.step("Выполнение входа в систему"):
                with patch.object(allure_homepage_app, 'verify_and_login', side_effect=mock_verify_and_login):
                    client.post('/login', data=test_credentials, follow_redirects=True)
            
            with allure.step("Проверка проксирования запроса к allure-service"):
                with patch.object(allure_homepage_app, 'requests') as mock_requests:
                    mock_request = mock_requests.request
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.content = b'<html>Test</html>'
                    mock_response.headers = {'Content-Type': 'text/html'}
                    mock_request.return_value = mock_response
                    
                    response = client.get('/allure-docker-service/projects/default/reports/latest/index.html')
                    assert response.status_code == 200
                    mock_request.assert_called_once()

    @allure.story("Проксирование: обработка JSON ответов")
    @allure.title("Правильная обработка JSON ответов от allure-service")
    @allure.description("""
    Проверяет правильную обработку JSON ответов от allure-service при проксировании.
    
    **Что проверяется:**
    - Корректная обработка JSON ответов
    - Исправление путей в JSON (замена внутренних адресов на публичные)
    - Сохранение структуры JSON
    
    **Ожидаемый результат:**
    JSON ответы правильно обрабатываются и возвращаются клиенту.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "proxy", "json", "allure-homepage", "unit")
    def test_proxy_json_responses(self, temp_db):
        """Тест правильной обработки JSON ответов от allure-service"""
        app, allure_homepage_app = setup_app_with_templates()
        import json
        
        test_credentials = {
            'username': 'test_admin',
            'password': 'test_password'
        }
        
        def mock_verify_and_login(username, password):
            from flask import session
            session['logged_in'] = True
            session.permanent = True
            return True
        
        with app.test_client() as client:
            with patch.object(allure_homepage_app, 'verify_and_login', side_effect=mock_verify_and_login):
                client.post('/login', data=test_credentials, follow_redirects=True)
            
            test_json = {
                'data': {
                    'url': 'http://allure-service:5050/allure-docker-service/projects'
                }
            }
            
            with patch.object(allure_homepage_app, 'requests') as mock_requests:
                mock_get = mock_requests.get
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.content = json.dumps(test_json).encode('utf-8')
                mock_response.headers = {'Content-Type': 'application/json'}
                mock_get.return_value = mock_response
                
                response = client.get('/allure-docker-service/projects', 
                                    headers={'Accept': 'application/json'})
                assert response.status_code == 200
                # Проверяем, что пути исправлены
                response_data = json.loads(response.data)
                # URL должен быть исправлен (внутренний адрес заменен на публичный)
                assert 'allure-service:5050' not in str(response_data)

    @allure.story("Проксирование: обработка HTML ответов")
    @allure.title("Правильная обработка HTML ответов от allure-service")
    @allure.description("""
    Проверяет правильную обработку HTML ответов от allure-service при проксировании.
    
    **Что проверяется:**
    - Корректная обработка HTML ответов
    - Исправление путей в HTML (замена внутренних адресов на публичные)
    - Сохранение структуры HTML
    
    **Ожидаемый результат:**
    HTML ответы правильно обрабатываются и возвращаются клиенту.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "proxy", "html", "allure-homepage", "unit")
    def test_proxy_html_responses(self, temp_db):
        """Тест правильной обработки HTML ответов от allure-service"""
        app, allure_homepage_app = setup_app_with_templates()
        
        test_credentials = {
            'username': 'test_admin',
            'password': 'test_password'
        }
        
        def mock_verify_and_login(username, password):
            from flask import session
            session['logged_in'] = True
            session.permanent = True
            return True
        
        with app.test_client() as client:
            with patch.object(allure_homepage_app, 'verify_and_login', side_effect=mock_verify_and_login):
                client.post('/login', data=test_credentials, follow_redirects=True)
            
            test_html = '<html><body><a href="http://allure-service:5050/allure-docker-service/projects">Link</a></body></html>'
            
            with patch.object(allure_homepage_app, 'requests') as mock_requests:
                mock_request = mock_requests.request
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.content = test_html.encode('utf-8')
                mock_response.headers = {'Content-Type': 'text/html'}
                mock_request.return_value = mock_response
                
                response = client.get('/allure-docker-service/projects/default/reports/1/index.html')
                assert response.status_code == 200
                # Проверяем, что пути исправлены
                assert b'allure-service:5050' not in response.data

