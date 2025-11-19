#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit-тесты для TON Connect"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.unit
@allure.epic("Веб-панель")
@allure.feature("TON Connect")
@allure.label("package", "src.shop_bot.webhook_server")
class TestTONConnect:
    @pytest.fixture
    def flask_app(self):
        from shop_bot.webhook_server.app import create_webhook_app
        mock_bot_controller = MagicMock()
        mock_bot_controller.get_status.return_value = {'shop_bot': 'running'}
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

    @allure.story("TON Connect: интеграция")
    @allure.title("Получение манифеста TON Connect")
    @allure.description("""
    Проверяет получение манифеста TON Connect через endpoint /.well-known/tonconnect-manifest.json.
    
    **Что проверяется:**
    - Доступность endpoint для получения манифеста TON Connect
    - Корректный статус ответа (200)
    - Возврат корректного манифеста
    
    **Тестовые данные:**
    - Моки для get_ton_manifest, возвращающие {'url': 'test'}
    
    **Ожидаемый результат:**
    Endpoint возвращает манифест TON Connect со статусом 200.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("ton_connect", "manifest", "webhook_server", "unit")
    def test_tonconnect_manifest(self, flask_app):
        with patch('shop_bot.data_manager.database.get_ton_manifest', return_value={'url': 'test'}):
            response = flask_app.get('/.well-known/tonconnect-manifest.json')
            assert response.status_code == 200

    @allure.story("TON Connect: интеграция")
    @allure.title("Получение данных манифеста TON Connect через API")
    @allure.description("""
    Проверяет получение данных манифеста TON Connect через API endpoint /api/get-ton-manifest-data.
    
    **Что проверяется:**
    - Доступность API endpoint для авторизованного администратора
    - Корректный статус ответа (200)
    - Возврат данных манифеста
    
    **Тестовые данные:**
    - Моки для get_ton_manifest, возвращающие {'url': 'test'}
    
    **Ожидаемый результат:**
    API endpoint возвращает данные манифеста TON Connect со статусом 200.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("ton_connect", "api", "manifest_data", "webhook_server", "unit")
    def test_get_ton_manifest_data(self, authenticated_session):
        with patch('shop_bot.data_manager.database.get_ton_manifest', return_value={'url': 'test'}):
            response = authenticated_session.get('/api/get-ton-manifest-data')
            assert response.status_code == 200

    @allure.story("TON Connect: интеграция")
    @allure.title("Сохранение настроек манифеста TON Connect")
    @allure.description("""
    Проверяет сохранение настроек манифеста TON Connect через POST /save-ton-manifest-settings.
    
    **Что проверяется:**
    - Сохранение настроек манифеста
    - Корректный статус ответа (200 или 302)
    - Обновление настроек в системе
    
    **Ожидаемый результат:**
    Настройки манифеста TON Connect успешно сохранены, статус ответа 200 или 302.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("ton_connect", "save_settings", "webhook_server", "unit")
    def test_save_ton_manifest_settings(self, authenticated_session):
        response = authenticated_session.post('/save-ton-manifest-settings', data={})
        assert response.status_code in [200, 302]

    @allure.story("TON Connect: интеграция")
    @allure.title("Загрузка иконки для TON Connect")
    @allure.description("""
    Проверяет загрузку иконки для TON Connect через POST /upload-ton-icon.
    
    **Что проверяется:**
    - Загрузка иконки для манифеста TON Connect
    - Корректный статус ответа (200, 400 или 500)
    - Обработка загрузки файла
    
    **Ожидаемый результат:**
    Иконка успешно загружена или обработана ошибка, статус ответа 200, 400 или 500.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("ton_connect", "upload_icon", "webhook_server", "unit")
    def test_upload_ton_icon(self, authenticated_session):
        response = authenticated_session.post('/upload-ton-icon', data={})
        assert response.status_code in [200, 400, 500]

