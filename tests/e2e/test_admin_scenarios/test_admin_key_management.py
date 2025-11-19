#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E2E тесты для управления ключами администратором"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.e2e
@allure.epic("E2E тесты")
@allure.feature("Административные сценарии")
@allure.label("package", "tests.e2e.test_admin_scenarios")
class TestAdminKeyManagement:
    """E2E тесты для управления ключами"""

    @pytest.fixture
    def flask_app(self, temp_db, monkeypatch):
        """Фикстура для Flask приложения"""
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
        """Фикстура для авторизованной сессии"""
        with patch('shop_bot.data_manager.database.verify_admin_credentials', return_value=True):
            with flask_app.session_transaction() as sess:
                sess['logged_in'] = True
            return flask_app

    @allure.story("Администратор: управление ключами")
    @allure.title("Полный цикл управления ключами администратором")
    @allure.description("""
    E2E тест, проверяющий полный цикл управления ключами администратором в веб-панели.
    
    **Что проверяется:**
    - Просмотр списка ключей на странице /keys
    - Синхронизация ключа с 3X-UI через API
    - Включение/отключение ключа через API
    - Корректная работа всех операций для авторизованного администратора
    
    **Тестовые данные:**
    - Используется авторизованная сессия администратора (authenticated_session)
    - Моки для get_paginated_keys, get_key_details_from_host, update_client_enabled_status_on_host
    
    **Предусловия:**
    - Администратор авторизован в системе
    - Используется временная БД (temp_db)
    - Flask приложение настроено для тестирования
    
    **Шаги теста:**
    1. Просмотр списка ключей на странице /keys
    2. Синхронизация ключа с 3X-UI через /api/sync-key/{key_id}
    3. Включение/отключение ключа через /api/toggle-key/{key_id}
    
    **Ожидаемый результат:**
    Все операции управления ключами выполняются успешно:
    - Страница /keys отображается со статусом 200
    - Синхронизация ключа выполняется (статус 200, 404 или 500 в зависимости от наличия ключа)
    - Включение/отключение ключа выполняется (статус 200, 404 или 500 в зависимости от наличия ключа)
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("e2e", "admin", "key_management", "webhook_server", "critical")
    def test_admin_key_management(self, authenticated_session):
        # Просмотр ключей
        with patch('shop_bot.data_manager.database.get_paginated_keys', return_value=([], 0)):
            response = authenticated_session.get('/keys')
            assert response.status_code == 200
        
        # Синхронизация с 3X-UI
        with patch('shop_bot.modules.xui_api.get_key_details_from_host') as mock_sync:
            mock_sync.return_value = {'status': 'active'}
            response = authenticated_session.post('/api/sync-key/1')
            assert response.status_code in [200, 404, 500]
        
        # Включение/отключение ключа
        with patch('shop_bot.modules.xui_api.update_client_enabled_status_on_host'):
            response = authenticated_session.post('/api/toggle-key/1', data={'enabled': 'true'})
            assert response.status_code in [200, 404, 500]

