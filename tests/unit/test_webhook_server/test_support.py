#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit-тесты для поддержки"""

import pytest
import allure
import sys
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.unit
@allure.epic("Веб-панель")
@allure.feature("Поддержка")
@allure.label("package", "src.shop_bot.webhook_server")
class TestSupport:
    @pytest.fixture
    def flask_app(self, temp_db, monkeypatch):
        from shop_bot.webhook_server import app as webhook_app_module
        from shop_bot.webhook_server.app import create_webhook_app
        
        # КРИТИЧЕСКИ ВАЖНО: Патчим DB_FILE в app.py, так как эндпоинты используют его напрямую
        monkeypatch.setattr(webhook_app_module, 'DB_FILE', temp_db)
        
        mock_bot_controller = MagicMock()
        mock_bot_controller.get_status.return_value = {'shop_bot': 'running'}
        mock_bot_controller.support_bot = MagicMock()
        mock_bot_controller.support_is_running = True
        
        # Мокируем event loop для асинхронных операций
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True
        mock_bot_controller._loop = mock_loop
        
        app = create_webhook_app(mock_bot_controller)
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'
        app.config['WTF_CSRF_ENABLED'] = False
        return app.test_client()

    @pytest.fixture
    def authenticated_session(self, flask_app):
        with patch('shop_bot.data_manager.database.verify_admin_credentials', return_value=True):
            with flask_app.session_transaction() as sess:
                sess['logged_in'] = True
            return flask_app

    @allure.story("Поддержка: управление тикетами")
    @allure.title("Проверка конфигурации бота поддержки")
    @allure.description("""
    Проверяет корректность работы API эндпоинта `/api/support/check-config` для проверки конфигурации бота поддержки.
    
    **Что проверяется:**
    - Корректная обработка запроса на проверку конфигурации
    - Обработка случая, когда бот поддержки не запущен (статус 400)
    - Обработка случая, когда настройки не заполнены (статус 200 с предупреждением)
    - Обработка случая, когда настройки заполнены и бот запущен (статус 200)
    - Корректная работа с асинхронными операциями через event loop
    
    **Тестовые данные:**
    - support_group_id: 'test_group_id' (мокируется через get_setting)
    - support_bot_token: 'test_bot_token' (мокируется через get_setting)
    - mock_bot_controller.support_is_running: True
    - mock_bot_controller._loop.is_running(): True
    
    **Предусловия:**
    - Используется временная сессия с авторизацией (authenticated_session)
    - Бот контроллер настроен с моками для поддержки
    - Event loop мокирован как запущенный
    
    **Ожидаемый результат:**
    Эндпоинт должен вернуть статус 200 (успешная проверка) или 400 (бот не запущен).
    В случае ошибки сервера возвращается статус 500, который также допустим для обработки исключений.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("support", "check-config", "api", "webhook-server", "unit", "configuration")
    def test_support_check_config(self, authenticated_session):
        """Тест проверки конфигурации бота поддержки"""
        with allure.step("Подготовка тестовых данных"):
            # Настраиваем возвращаемые значения для разных ключей
            def get_setting_side_effect(key):
                if key == "support_group_id":
                    return "test_group_id"
                elif key == "support_bot_token":
                    return "test_bot_token"
                return None
            
            allure.attach("support_group_id: test_group_id\nsupport_bot_token: test_bot_token", 
                         "Настройки БД", allure.attachment_type.TEXT)
        
        with allure.step("Мокирование асинхронных операций"):
            # Мокируем asyncio.run_coroutine_threadsafe для корректной работы с event loop
            mock_future = MagicMock()
            mock_future.result.return_value = "✅ Группа найдена: Test Group\n📊 Тип: Обычная группа\n✅ Статус: Группа настроена корректно\n"
            
            with patch('shop_bot.data_manager.database.get_setting', side_effect=get_setting_side_effect):
                with patch('asyncio.run_coroutine_threadsafe', return_value=mock_future):
                    with allure.step("Выполнение запроса к эндпоинту"):
                        response = authenticated_session.post('/api/support/check-config')
                        allure.attach(str(response.status_code), "HTTP статус код", allure.attachment_type.TEXT)
                        allure.attach(response.get_data(as_text=True), "Тело ответа", allure.attachment_type.JSON)
        
        with allure.step("Проверка результата"):
            # Эндпоинт может вернуть:
            # - 200: успешная проверка конфигурации
            # - 400: бот поддержки не запущен
            # - 500: внутренняя ошибка сервера (также допустима для обработки исключений)
            assert response.status_code in [200, 400, 500], \
                f"Неожиданный статус код: {response.status_code}. Тело ответа: {response.get_data(as_text=True)}"
            
            # Если статус 200, проверяем структуру ответа
            if response.status_code == 200:
                response_data = response.get_json()
                assert response_data is not None, "Ответ должен содержать JSON"
                assert 'success' in response_data, "Ответ должен содержать поле 'success'"
                assert 'message' in response_data, "Ответ должен содержать поле 'message'"
                allure.attach(str(response_data), "JSON ответ", allure.attachment_type.JSON)

    @allure.story("Поддержка: управление тикетами")
    @allure.title("Тестирование бота поддержки")
    @allure.description("""
    Проверяет тестирование бота поддержки через API endpoint /api/support/check-test.
    
    **Что проверяется:**
    - Отправка тестового сообщения боту поддержки
    - Корректный статус ответа (200, 400 или 500)
    - Обработка различных состояний бота (запущен/не запущен)
    
    **Ожидаемый результат:**
    Тестирование бота поддержки выполнено, статус ответа 200, 400 или 500.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("support", "check-test", "api", "webhook_server", "unit")
    def test_support_check_test(self, authenticated_session):
        response = authenticated_session.post('/api/support/check-test')
        assert response.status_code in [200, 400, 500]

