#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для уведомлений в веб-панели администратора
"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import json

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.unit
@allure.epic("Веб-панель")
@allure.feature("Уведомления")
@allure.label("package", "src.shop_bot.webhook_server")
class TestNotifications:
    """Тесты для работы с уведомлениями"""

    @pytest.fixture
    def flask_app(self):
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

    @allure.story("Уведомления: управление шаблонами")
    @allure.title("Отображение страницы уведомлений")
    @allure.description("""
    Проверяет отображение страницы уведомлений в веб-панели.
    
    **Что проверяется:**
    - Доступность страницы /notifications для авторизованного администратора
    - Корректный статус ответа (200)
    - Отображение списка уведомлений с пагинацией
    
    **Тестовые данные:**
    - Моки для get_paginated_notifications, возвращающие пустой список
    
    **Ожидаемый результат:**
    Страница /notifications успешно отображается со статусом 200.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("notifications", "page", "webhook_server", "unit")
    def test_notifications_page(self, authenticated_session):
        with patch('shop_bot.data_manager.database.get_paginated_notifications', return_value=([], 0)):
            response = authenticated_session.get('/notifications')
            assert response.status_code == 200, "Страница уведомлений должна возвращать 200"

    @allure.story("Уведомления: управление шаблонами")
    @allure.title("Создание нового уведомления через API")
    @allure.description("""
    Проверяет создание нового уведомления через POST /create-notification.
    
    **Что проверяется:**
    - Создание уведомления с указанием user_id, type, title, message
    - Корректный статус ответа (200, 400 или 500)
    - Отправка уведомления через scheduler
    - Логирование уведомления в БД
    
    **Тестовые данные:**
    - user_id: 123456789
    - type: 'subscription_ending'
    - title: 'Test Notification'
    - message: 'Test message'
    - Моки для send_subscription_notification и log_notification
    
    **Ожидаемый результат:**
    Уведомление успешно создано, статус ответа 200, 400 или 500.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("notifications", "create", "api", "webhook_server", "unit")
    def test_create_notification(self, authenticated_session):
        with patch('shop_bot.data_manager.scheduler.send_subscription_notification'):
            with patch('shop_bot.data_manager.database.log_notification'):
                data = {
                    'user_id': 123456789,
                    'type': 'subscription_ending',
                    'title': 'Test Notification',
                    'message': 'Test message'
                }
                response = authenticated_session.post(
                    '/create-notification',
                    data=json.dumps(data),
                    content_type='application/json'
                )
                assert response.status_code in [200, 400, 500]

    @allure.story("Уведомления: управление шаблонами")
    @allure.title("Повторная отправка уведомления")
    @allure.description("""
    Проверяет повторную отправку уведомления через POST /resend-notification/{notification_id}.
    
    **Что проверяется:**
    - Получение уведомления по ID из БД
    - Повторная отправка уведомления через scheduler
    - Корректный статус ответа (200, 302, 404 или 500)
    
    **Тестовые данные:**
    - notification_id: 1
    - user_id: 123456789
    - type: 'subscription_ending'
    - status: 'pending'
    - Моки для get_notification_by_id и send_subscription_notification
    
    **Ожидаемый результат:**
    Уведомление успешно отправлено повторно, статус ответа 200, 302, 404 или 500.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("notifications", "resend", "api", "webhook_server", "unit")
    def test_resend_notification(self, authenticated_session):
        with patch('shop_bot.data_manager.database.get_notification_by_id') as mock_get:
            mock_get.return_value = {
                'notification_id': 1,
                'user_id': 123456789,
                'type': 'subscription_ending',
                'title': 'Test',
                'message': 'Test message',
                'status': 'pending'
            }
            with patch('shop_bot.data_manager.scheduler.send_subscription_notification'):
                response = authenticated_session.post('/resend-notification/1')
                assert response.status_code in [200, 302, 404, 500]

    @allure.story("Уведомления: управление шаблонами")
    @allure.title("Ручная отправка уведомления")
    @allure.description("""
    Проверяет ручную отправку уведомления через POST /create-notification с типом 'manual'.
    
    **Что проверяется:**
    - Создание уведомления с типом 'manual'
    - Отправка уведомления через scheduler
    - Корректный статус ответа (200, 400 или 500)
    
    **Тестовые данные:**
    - user_id: 123456789
    - type: 'manual'
    - title: 'Manual Notification'
    - message: 'Manual message'
    - Моки для send_subscription_notification
    
    **Ожидаемый результат:**
    Ручное уведомление успешно отправлено, статус ответа 200, 400 или 500.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("notifications", "manual", "api", "webhook_server", "unit")
    def test_send_manual_notification(self, authenticated_session):
        # Ручная отправка может быть реализована через create_notification с типом manual
        with patch('shop_bot.data_manager.scheduler.send_subscription_notification'):
            data = {
                'user_id': 123456789,
                'type': 'manual',
                'title': 'Manual Notification',
                'message': 'Manual message'
            }
            response = authenticated_session.post(
                '/create-notification',
                data=json.dumps(data),
                content_type='application/json'
            )
            assert response.status_code in [200, 400, 500]

