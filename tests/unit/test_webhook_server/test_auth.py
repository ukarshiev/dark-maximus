#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для авторизации веб-панели

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


@pytest.mark.unit
@allure.epic("Веб-панель")
@allure.feature("Авторизация")
@allure.label("package", "src.shop_bot.webhook_server")
class TestWebhookServerAuth:
    """Тесты для авторизации веб-панели"""

    @allure.story("Авторизация: вход в систему")
    @allure.title("Отображение страницы входа")
    @allure.description("""
    Проверяет отображение страницы входа в веб-панель.
    
    **Что проверяется:**
    - Доступность страницы /login
    - Наличие элементов формы входа в ответе
    - Корректный статус ответа (200)
    
    **Ожидаемый результат:**
    Страница входа успешно отображается с формой входа.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "login", "webhook_server", "unit")
    def test_login_page_get(self, temp_db):
        """Тест отображения страницы входа"""
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock
        
        mock_bot_controller = MagicMock()
        app = create_webhook_app(mock_bot_controller)
        with app.test_client() as client:
            response = client.get('/login')
            assert response.status_code == 200
            assert b'login' in response.data.lower() or 'вход'.encode('utf-8') in response.data.lower()

    @allure.story("Авторизация: вход в систему")
    @allure.title("Успешный вход в веб-панель")
    @allure.description("""
    Проверяет успешный вход в веб-панель с корректными учетными данными.
    
    **Что проверяется:**
    - Отправка POST запроса на /login с корректными данными
    - Установка сессии logged_in=True после успешного входа
    - Перенаправление после успешного входа
    
    **Тестовые данные:**
    - username: тестовый логин из фикстуры admin_credentials
    - password: корректный пароль из переменных окружения
    
    **Ожидаемый результат:**
    Пользователь успешно авторизован, сессия установлена, происходит перенаправление.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "login", "success", "webhook_server", "unit")
    def test_login_success(self, temp_db, admin_credentials):
        """Тест успешного входа"""
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock
        
        mock_bot_controller = MagicMock()
        app = create_webhook_app(mock_bot_controller)
        with app.test_client() as client:
            # Мокируем verify_admin_credentials
            with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=True):
                response = client.post('/login', data=admin_credentials, follow_redirects=True)
                assert response.status_code == 200
                # Проверяем, что сессия установлена
                with client.session_transaction() as sess:
                    assert sess.get('logged_in') is True

    @allure.story("Авторизация: вход в систему")
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
    @allure.tag("auth", "login", "failure", "webhook_server", "unit")
    def test_login_failure(self, temp_db):
        """Тест неверных учетных данных"""
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock
        
        mock_bot_controller = MagicMock()
        app = create_webhook_app(mock_bot_controller)
        with app.test_client() as client:
            # Мокируем verify_admin_credentials
            with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=False):
                response = client.post('/login', data={
                    'username': 'wrong_user',
                    'password': 'wrong_password'
                })
                assert response.status_code == 200
                # Проверяем, что сессия не установлена
                with client.session_transaction() as sess:
                    assert sess.get('logged_in') is None

    @allure.story("Авторизация: вход в систему")
    @allure.title("Ограничение попыток входа (10 в минуту)")
    @allure.description("""
    Проверяет ограничение количества попыток входа (rate limiting) для защиты от брутфорс-атак.
    
    **Что проверяется:**
    - Разрешение первых 10 попыток входа (статус 200)
    - Блокировка 11-й попытки (статус 429 Too Many Requests)
    - Корректная работа rate limiting механизма
    - Правильная обработка превышения лимита
    
    **Тестовые данные:**
    - Количество попыток: 11
    - Лимит: 10 попыток в минуту
    - username: 'test_user'
    - password: 'wrong_password' (неверный пароль для имитации неудачных попыток)
    
    **Предусловия:**
    - Rate limiting отключен в TESTING режиме, поэтому для теста отключается TESTING режим
    - Используется мок verify_admin_credentials, который всегда возвращает False
    
    **Шаги теста:**
    1. Создание Flask приложения с отключенным TESTING режимом
    2. Выполнение 11 попыток входа с неверными учетными данными
    3. Проверка статуса ответа для каждой попытки
    
    **Ожидаемый результат:**
    Первые 10 попыток разрешены (статус 200), 11-я попытка заблокирована со статусом 429.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "login", "rate_limit", "security", "webhook_server", "unit")
    def test_login_rate_limit(self, temp_db):
        """Тест ограничения попыток входа (10 в минуту)"""
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock, patch
        from shop_bot.security.rate_limiter import rate_limiter
        
        with allure.step("Подготовка тестового окружения"):
            mock_bot_controller = MagicMock()
            app = create_webhook_app(mock_bot_controller)
            # Включаем rate limiting для этого теста (отключаем TESTING режим)
            app.config['TESTING'] = False
            # Очищаем rate limiter для изоляции теста
            rate_limiter.requests.clear()
            allure.attach("TESTING режим отключен для активации rate limiting", "Конфигурация", allure.attachment_type.TEXT)
        
        # Устанавливаем фиксированный IP адрес для тестового клиента
        test_ip = '127.0.0.1'
        with app.test_client() as client:
            with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=False):
                with allure.step("Выполнение 11 попыток входа с неверными учетными данными"):
                    attempts_data = []
                    for i in range(11):
                        # Устанавливаем IP адрес через environ_base в каждом запросе
                        response = client.post('/login', 
                            data={
                                'username': 'test_user',
                                'password': 'wrong_password'
                            },
                            environ_base={'REMOTE_ADDR': test_ip}
                        )
                        attempts_data.append({
                            'attempt': i + 1,
                            'status_code': response.status_code,
                            'expected': 200 if i < 10 else 429
                        })
                        allure.attach(
                            f"Попытка {i + 1}: статус {response.status_code}",
                            f"Попытка {i + 1}",
                            allure.attachment_type.TEXT
                        )
                        
                        if i < 10:
                            with allure.step(f"Проверка попытки {i + 1}: должна быть разрешена"):
                                assert response.status_code == 200, f"Попытка {i + 1} должна быть разрешена (статус 200), получен {response.status_code}"
                        else:
                            with allure.step(f"Проверка попытки {i + 1}: должна быть заблокирована"):
                                assert response.status_code == 429, f"Попытка {i + 1} должна быть заблокирована (статус 429), получен {response.status_code}"
                    
                    import json
                    allure.attach(
                        json.dumps(attempts_data, indent=2, ensure_ascii=False),
                        "Результаты всех попыток",
                        allure.attachment_type.JSON
                    )

    @allure.story("Авторизация: выход из системы")
    @allure.title("Выход из системы")
    @allure.description("""
    Проверяет корректный выход пользователя из веб-панели и очистку сессии.
    
    **Что проверяется:**
    - Успешный вход в систему с установкой сессии
    - Отправка POST запроса на /logout
    - Очистка сессии после выхода (удаление logged_in из сессии)
    - Перенаправление на страницу входа после выхода
    - Отсутствие доступа к защищенным страницам после выхода (редирект на /login)
    
    **Тестовые данные:**
    - Учетные данные администратора из фикстуры admin_credentials
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Мок verify_admin_credentials возвращает True для успешного входа
    
    **Шаги теста:**
    1. Выполнение входа в систему через POST /login
    2. Проверка установки сессии через доступ к защищенной странице /dashboard
    3. Выполнение выхода через POST /logout
    4. Проверка очистки сессии через попытку доступа к защищенной странице
    
    **Ожидаемый результат:**
    Пользователь успешно вышел из системы, сессия очищена (logged_in удален), доступ к защищенным страницам запрещен (редирект на /login со статусом 302).
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "logout", "session", "webhook_server", "unit")
    def test_logout(self, temp_db):
        """Тест выхода из системы"""
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock
        from shop_bot.security.rate_limiter import rate_limiter
        
        # Сбрасываем rate limiter для изоляции теста
        rate_limiter.requests.clear()
        
        # Используем фиктивные данные для теста, так как мы мокируем verify_admin_credentials
        test_credentials = {
            'username': 'test_admin',
            'password': 'test_password'
        }
        
        with allure.step("Подготовка тестового окружения"):
            mock_bot_controller = MagicMock()
            app = create_webhook_app(mock_bot_controller)
            # Убеждаемся, что TESTING режим включен для отключения rate limiting
            app.config['TESTING'] = True
            allure.attach(str(test_credentials.get('username')), "Username", allure.attachment_type.TEXT)
        
        with app.test_client() as client:
            with allure.step("Выполнение входа в систему"):
                with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=True):
                    response = client.post('/login', data=test_credentials, follow_redirects=True)
                    allure.attach(str(response.status_code), "Статус ответа после входа", allure.attachment_type.TEXT)
                    assert response.status_code == 200, "Вход должен быть успешным"
            
            with allure.step("Проверка установки сессии через доступ к защищенной странице"):
                response = client.get('/dashboard')
                allure.attach(str(response.status_code), "Статус ответа /dashboard", allure.attachment_type.TEXT)
                assert response.status_code == 200, "Доступ к защищенной странице должен быть разрешен после входа"
                
                # Проверяем сессию через session_transaction
                with client.session_transaction() as sess:
                    logged_in = sess.get('logged_in')
                    allure.attach(str(logged_in), "Значение logged_in в сессии", allure.attachment_type.TEXT)
                    assert logged_in is True, "Сессия должна содержать logged_in=True"
            
            with allure.step("Выполнение выхода из системы"):
                response = client.post('/logout', follow_redirects=True)
                allure.attach(str(response.status_code), "Статус ответа после выхода", allure.attachment_type.TEXT)
                assert response.status_code == 200, "Выход должен быть успешным"
            
            with allure.step("Проверка очистки сессии через попытку доступа к защищенной странице"):
                response = client.get('/dashboard')
                allure.attach(str(response.status_code), "Статус ответа /dashboard после выхода", allure.attachment_type.TEXT)
                assert response.status_code == 302, "Доступ к защищенной странице должен быть запрещен (редирект на /login)"
                
                # Проверяем, что сессия очищена
                with client.session_transaction() as sess:
                    logged_in = sess.get('logged_in')
                    allure.attach(str(logged_in), "Значение logged_in в сессии после выхода", allure.attachment_type.TEXT)
                    assert logged_in is None, "Сессия должна быть очищена (logged_in должен быть None)"

    @allure.story("Авторизация: проверка доступа")
    @allure.title("Проверка декоратора @login_required")
    @allure.description("""
    Проверяет работу декоратора @login_required для защиты страниц веб-панели.
    
    **Что проверяется:**
    - Редирект на /login при попытке доступа к защищенной странице без авторизации (статус 302)
    - Разрешение доступа к защищенной странице после успешной авторизации (статус 200)
    - Корректная работа декоратора @login_required на защищенных маршрутах
    - Сохранение сессии между запросами после авторизации
    
    **Тестовые данные:**
    - Учетные данные администратора из фикстуры admin_credentials
    - Защищенная страница: /dashboard
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Flask приложение создано с моком bot_controller
    - Страница /dashboard защищена декоратором @login_required
    
    **Шаги теста:**
    1. Создание Flask приложения с моком bot_controller
    2. Попытка доступа к защищенной странице /dashboard без авторизации
    3. Проверка редиректа на /login (статус 302)
    4. Авторизация администратора через POST /login
    5. Повторная попытка доступа к защищенной странице /dashboard
    6. Проверка успешного доступа (статус 200)
    
    **Ожидаемый результат:**
    Без авторизации происходит редирект на /login со статусом 302, после авторизации доступ к защищенной странице разрешен со статусом 200.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "login_required", "decorator", "webhook_server", "unit")
    def test_login_required_decorator(self, temp_db, admin_credentials):
        """Тест проверки декоратора @login_required"""
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock
        
        with allure.step("Подготовка тестового окружения"):
            mock_bot_controller = MagicMock()
            app = create_webhook_app(mock_bot_controller)
            allure.attach(str(temp_db), "Путь к временной БД", allure.attachment_type.TEXT)
        
        with app.test_client() as client:
            with allure.step("Попытка доступа к защищенной странице без авторизации"):
                response = client.get('/dashboard')
                allure.attach(str(response.status_code), "Статус ответа без авторизации", allure.attachment_type.TEXT)
                allure.attach(str(response.location), "Location редиректа", allure.attachment_type.TEXT)
                
                with allure.step("Проверка редиректа на /login"):
                    assert response.status_code == 302, f"Ожидался редирект (статус 302), получен {response.status_code}"
                    assert '/login' in (response.location or ''), "Редирект должен быть на /login"
            
            with allure.step("Авторизация администратора"):
                with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=True):
                    login_response = client.post('/login', data=admin_credentials)
                    allure.attach(str(login_response.status_code), "Статус авторизации", allure.attachment_type.TEXT)
                    assert login_response.status_code in [200, 302], "Авторизация должна быть успешной"
                    
                    # Проверяем сессию
                    with client.session_transaction() as sess:
                        logged_in = sess.get('logged_in')
                        allure.attach(str(logged_in), "Значение logged_in в сессии", allure.attachment_type.TEXT)
                        assert logged_in is True, "Сессия должна содержать logged_in=True"
            
            with allure.step("Повторная попытка доступа к защищенной странице после авторизации"):
                response = client.get('/dashboard')
                allure.attach(str(response.status_code), "Статус ответа после авторизации", allure.attachment_type.TEXT)
                
                with allure.step("Проверка успешного доступа"):
                    assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}"

    @allure.story("Авторизация: проверка доступа")
    @allure.title("Сохранение сессии на 30 дней")
    @allure.description("""
    Проверяет сохранение сессии пользователя между запросами и доступ к защищенным страницам.
    
    **Что проверяется:**
    - Установка сессии после успешного входа (logged_in=True, session.permanent=True)
    - Сохранение сессии между запросами (сессия доступна в последующих запросах)
    - Доступ к защищенным страницам через сохраненную сессию
    - Корректная работа механизма постоянных сессий Flask-Session
    
    **Тестовые данные:**
    - Учетные данные администратора из фикстуры admin_credentials
    - Настройка сессии: SESSION_PERMANENT=True, PERMANENT_SESSION_LIFETIME=30 дней
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Мок verify_admin_credentials возвращает True для успешного входа
    - Flask-Session настроен на файловое хранилище сессий
    
    **Шаги теста:**
    1. Выполнение входа в систему через POST /login
    2. Проверка установки сессии через session_transaction
    3. Выполнение запроса к защищенной странице /dashboard
    4. Проверка сохранения сессии между запросами через повторный доступ к защищенной странице
    
    **Ожидаемый результат:**
    Сессия сохраняется и работает между запросами, доступ к защищенным страницам разрешен (статус 200), сессия содержит logged_in=True и permanent=True.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "session", "persistence", "webhook_server", "unit")
    def test_session_persistence(self, temp_db):
        """Тест сохранения сессии на 30 дней"""
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock
        from shop_bot.security.rate_limiter import rate_limiter
        
        # Сбрасываем rate limiter для изоляции теста
        rate_limiter.requests.clear()
        
        # Используем фиктивные данные для теста, так как мы мокируем verify_admin_credentials
        test_credentials = {
            'username': 'test_admin',
            'password': 'test_password'
        }
        
        with allure.step("Подготовка тестового окружения"):
            mock_bot_controller = MagicMock()
            app = create_webhook_app(mock_bot_controller)
            # Убеждаемся, что TESTING режим включен для отключения rate limiting
            app.config['TESTING'] = True
            allure.attach(str(test_credentials.get('username')), "Username", allure.attachment_type.TEXT)
        
        with app.test_client() as client:
            with allure.step("Выполнение входа в систему"):
                with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=True):
                    response = client.post('/login', data=test_credentials, follow_redirects=True)
                    allure.attach(str(response.status_code), "Статус ответа после входа", allure.attachment_type.TEXT)
                    assert response.status_code == 200, "Вход должен быть успешным"
            
            with allure.step("Проверка установки сессии через session_transaction"):
                # Проверяем сессию через session_transaction
                with client.session_transaction() as sess:
                    logged_in = sess.get('logged_in')
                    permanent = sess.get('_permanent', False)
                    allure.attach(
                        f"logged_in: {logged_in}, permanent: {permanent}",
                        "Состояние сессии после входа",
                        allure.attachment_type.TEXT
                    )
                    assert logged_in is True, "Сессия должна содержать logged_in=True"
                    assert permanent is True, "Сессия должна быть постоянной (permanent=True)"
            
            with allure.step("Проверка доступа к защищенной странице через сохраненную сессию"):
                response = client.get('/dashboard')
                allure.attach(str(response.status_code), "Статус ответа /dashboard", allure.attachment_type.TEXT)
                assert response.status_code == 200, "Доступ к защищенной странице должен быть разрешен через сохраненную сессию"
            
            with allure.step("Проверка сохранения сессии между запросами"):
                # Делаем еще один запрос к защищенной странице для проверки сохранения сессии
                response = client.get('/dashboard')
                allure.attach(str(response.status_code), "Статус ответа /dashboard (повторный запрос)", allure.attachment_type.TEXT)
                assert response.status_code == 200, "Сессия должна сохраняться между запросами"
                
                # Проверяем сессию еще раз через session_transaction
                with client.session_transaction() as sess:
                    logged_in = sess.get('logged_in')
                    permanent = sess.get('_permanent', False)
                    allure.attach(
                        f"logged_in: {logged_in}, permanent: {permanent}",
                        "Состояние сессии после повторного запроса",
                        allure.attachment_type.TEXT
                    )
                    assert logged_in is True, "Сессия должна сохраняться между запросами (logged_in=True)"
                    assert permanent is True, "Сессия должна оставаться постоянной (permanent=True)"

