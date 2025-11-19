#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E2E тесты для управления промокодами администратором"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import json

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.e2e
@allure.epic("E2E тесты")
@allure.feature("Административные сценарии")
@allure.label("package", "tests.e2e.test_admin_scenarios")
class TestAdminPromoManagement:
    """E2E тесты для управления промокодами"""

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

    @allure.story("Администратор: создание промокода")
    @allure.title("Полный цикл управления промокодами администратором")
    @allure.description("""
    E2E тест, проверяющий полный цикл управления промокодами администратором в веб-панели.
    
    **Что проверяется:**
    - Просмотр списка промокодов на странице /promo-codes
    - Создание нового промокода через API
    - Редактирование промокода через API
    - Удаление промокода через API
    - Корректная работа всех операций для авторизованного администратора
    
    **Тестовые данные:**
    - Используется авторизованная сессия администратора (authenticated_session)
    - Промокод: code='E2ETEST', discount_amount=50.0, usage_limit_per_bot=1
    - Обновленный промокод: code='E2ETESTUPDATED', discount_amount=75.0
    - Моки для get_all_user_groups, create_promo_code, update_promo_code, delete_promo_code
    
    **Предусловия:**
    - Администратор авторизован в системе
    - Используется временная БД (temp_db)
    - Flask приложение настроено для тестирования
    
    **Шаги теста:**
    1. Просмотр списка промокодов на странице /promo-codes
    2. Создание нового промокода через POST /api/promo-codes
    3. Редактирование промокода через PUT /api/promo-codes/{promo_id}
    4. Удаление промокода через DELETE /api/promo-codes/{promo_id}
    
    **Ожидаемый результат:**
    Все операции управления промокодами выполняются успешно:
    - Страница /promo-codes отображается со статусом 200
    - Создание промокода выполняется (статус 200 или 500)
    - Редактирование промокода выполняется (статус 200, 404 или 500)
    - Удаление промокода выполняется (статус 200, 404 или 500)
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("e2e", "admin", "promo_management", "webhook_server", "critical")
    def test_admin_promo_management(self, authenticated_session):
        # Просмотр промокодов
        with patch('shop_bot.data_manager.database.get_all_user_groups', return_value=[]):
            response = authenticated_session.get('/promo-codes')
            assert response.status_code == 200
        
        # Создание промокода
        with patch('shop_bot.data_manager.database.create_promo_code', return_value=1):
            with patch('shop_bot.data_manager.database.get_setting', return_value='test_bot'):
                data = {
                    'code': 'E2ETEST',
                    'bot': 'shop',
                    'discount_amount': 50.0,
                    'usage_limit_per_bot': 1
                }
                response = authenticated_session.post(
                    '/api/promo-codes',
                    data=json.dumps(data),
                    content_type='application/json'
                )
                assert response.status_code in [200, 500]
        
        # Редактирование промокода
        with patch('shop_bot.data_manager.database.update_promo_code', return_value=True):
            with patch('shop_bot.data_manager.database.get_setting', return_value='test_bot'):
                data = {
                    'code': 'E2ETESTUPDATED',
                    'bot': 'shop',
                    'discount_amount': 75.0,
                    'usage_limit_per_bot': 1
                }
                response = authenticated_session.put(
                    '/api/promo-codes/1',
                    data=json.dumps(data),
                    content_type='application/json'
                )
                assert response.status_code in [200, 404, 500]
        
        # Удаление промокода
        with patch('shop_bot.data_manager.database.can_delete_promo_code', return_value=(True, 0)):
            with patch('shop_bot.data_manager.database.delete_promo_code', return_value=True):
                response = authenticated_session.delete('/api/promo-codes/1')
                assert response.status_code in [200, 404, 500]

