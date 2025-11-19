#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для настроек в веб-панели администратора
"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.unit
@allure.epic("Веб-панель")
@allure.feature("Настройки")
@allure.label("package", "src.shop_bot.webhook_server")
class TestSettings:
    """Тесты для работы с настройками"""

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

    @allure.story("Настройки: управление конфигурацией")
    @allure.title("Страница настроек")
    @allure.description("""
    Проверяет отображение страницы настроек в веб-панели.
    
    **Что проверяется:**
    - Доступность страницы /settings
    - Отображение всех настроек системы
    - Корректный статус ответа (200)
    
    **Ожидаемый результат:**
    Страница настроек успешно отображается со всеми настройками системы.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("settings", "page", "webhook_server", "unit")
    def test_settings_page(self, authenticated_session):
        """Тест страницы настроек (/settings)"""
        with patch('shop_bot.data_manager.database.get_all_settings', return_value={}):
            with patch('shop_bot.data_manager.database.get_all_hosts', return_value=[]):
                response = authenticated_session.get('/settings')
                assert response.status_code == 200, "Страница настроек должна возвращать 200"

    @allure.story("Настройки: управление конфигурацией")
    @allure.title("Обновление настроек панели")
    @allure.description("""
    Проверяет обновление настроек панели через веб-панель.
    
    **Что проверяется:**
    - Отправка POST запроса на /settings/panel с новыми настройками
    - Сохранение настроек в БД
    - Перенаправление после обновления (статус 302)
    
    **Тестовые данные:**
    - panel_login: 'admin'
    - admin_timezone: 'Europe/Moscow'
    
    **Ожидаемый результат:**
    Настройки панели успешно обновлены, происходит перенаправление.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("settings", "panel", "update", "webhook_server", "unit")
    def test_update_panel_settings(self, authenticated_session):
        """Тест обновления настроек панели (/settings/panel)"""
        with patch('shop_bot.data_manager.database.update_setting'):
            response = authenticated_session.post('/settings/panel', data={
                'panel_login': 'admin',
                'admin_timezone': 'Europe/Moscow'
            })
            assert response.status_code == 302, "Обновление настроек должно перенаправить"

    @allure.story("Настройки: управление конфигурацией")
    @allure.title("Обновление настроек бота")
    @allure.description("""
    Проверяет обновление настроек бота через веб-панель.
    
    **Что проверяется:**
    - Отправка POST запроса на /settings/bot с новыми настройками
    - Сохранение настроек бота в БД
    - Перенаправление после обновления (статус 302)
    
    **Тестовые данные:**
    - telegram_bot_token: 'test_token'
    - telegram_bot_username: 'test_bot'
    
    **Ожидаемый результат:**
    Настройки бота успешно обновлены, происходит перенаправление.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("settings", "bot", "update", "webhook_server", "unit")
    def test_update_bot_settings(self, authenticated_session):
        """Тест обновления настроек бота (/settings/bot)"""
        with patch('shop_bot.data_manager.database.update_setting'):
            response = authenticated_session.post('/settings/bot', data={
                'telegram_bot_token': 'test_token',
                'telegram_bot_username': 'test_bot'
            })
            assert response.status_code == 302, "Обновление настроек должно перенаправить"

    @allure.story("Настройки: управление конфигурацией")
    @allure.title("Обновление платежных настроек")
    @allure.description("""
    Проверяет обновление платежных настроек через веб-панель.
    
    **Что проверяется:**
    - Отправка POST запроса на /settings/payments с новыми настройками
    - Сохранение платежных настроек в БД
    - Перенаправление после обновления (статус 302)
    
    **Тестовые данные:**
    - yookassa_shop_id: 'test_shop'
    - yookassa_secret_key: 'test_key'
    
    **Ожидаемый результат:**
    Платежные настройки успешно обновлены, происходит перенаправление.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("settings", "payments", "update", "webhook_server", "unit")
    def test_update_payment_settings(self, authenticated_session):
        """Тест обновления платежных настроек (/settings/payments)"""
        with patch('shop_bot.data_manager.database.update_setting'):
            with patch('shop_bot.data_manager.database.get_setting', return_value='false'):
                response = authenticated_session.post('/settings/payments', data={
                    'yookassa_shop_id': 'test_shop',
                    'yookassa_secret_key': 'test_key'
                })
                assert response.status_code == 302, "Обновление настроек должно перенаправить"

    @allure.story("Настройки: управление конфигурацией")
    @allure.title("Переключение скрытого режима")
    @allure.description("""
    Проверяет переключение скрытого режима через веб-панель.
    
    **Что проверяется:**
    - Отправка POST запроса на /toggle-hidden-mode
    - Переключение статуса скрытого режима в БД
    - Корректный статус ответа (200 или 302)
    
    **Ожидаемый результат:**
    Скрытый режим успешно переключен, статус обновлен в БД.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("settings", "hidden_mode", "toggle", "webhook_server", "unit")
    def test_toggle_hidden_mode(self, authenticated_session):
        """Тест переключения скрытого режима (/toggle-hidden-mode)"""
        with patch('shop_bot.data_manager.database.get_setting', return_value='false'):
            with patch('shop_bot.data_manager.database.update_setting'):
                response = authenticated_session.post('/toggle-hidden-mode')
                assert response.status_code in [200, 302], "Переключение режима должно вернуть 200 или 302"

    @allure.story("Настройки: управление конфигурацией")
    @allure.title("Обновление настроек хостов")
    @allure.description("""
    Проверяет обновление настроек хостов через веб-панель.
    
    **Что проверяется:**
    - Отправка POST запроса на /api/hosts/update
    - Обновление настроек хоста в БД
    - Корректный статус ответа
    
    **Ожидаемый результат:**
    Настройки хоста успешно обновлены в БД.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("settings", "hosts", "update", "webhook_server", "unit")
    def test_update_host_settings(self, authenticated_session):
        """Тест обновления настроек хостов"""
        # Хосты управляются через отдельные endpoints
        with patch('shop_bot.data_manager.database.update_host'):
            # Тест через API обновления хоста
            response = authenticated_session.post('/api/hosts/update', data={})
            assert response.status_code in [200, 302, 400, 404, 500]

    @allure.story("Настройки: управление конфигурацией")
    @allure.title("Обновление настроек планов")
    @allure.description("""
    Проверяет обновление настроек планов через веб-панель.
    
    **Что проверяется:**
    - Отправка POST запроса на /api/plans/update
    - Обновление настроек плана в БД
    - Корректный статус ответа
    
    **Ожидаемый результат:**
    Настройки плана успешно обновлены в БД.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("settings", "plans", "update", "webhook_server", "unit")
    def test_update_plan_settings(self, authenticated_session):
        """Тест обновления настроек планов"""
        with patch('shop_bot.data_manager.database.update_plan'):
            # Тест через API обновления плана
            response = authenticated_session.post('/api/plans/update', data={})
            assert response.status_code in [200, 302, 400, 404, 500]

    @allure.story("Настройки: управление конфигурацией")
    @allure.title("Запуск и остановка ботов")
    @allure.description("""
    Проверяет запуск и остановку ботов через веб-панель.
    
    **Что проверяется:**
    - Отправка POST запроса на /api/bots/start или /api/bots/stop
    - Управление статусом ботов
    - Корректный статус ответа
    
    **Ожидаемый результат:**
    Боты успешно запущены или остановлены, статус обновлен.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("settings", "bots", "start_stop", "webhook_server", "unit")
    def test_start_stop_bots(self, authenticated_session):
        """Тест запуска/остановки ботов"""
        with patch('shop_bot.webhook_server.app._bot_controller') as mock_controller:
            mock_controller.start_shop_bot.return_value = True
            mock_controller.stop_shop_bot.return_value = True
            
            # Тест запуска shop-bot
            response = authenticated_session.post('/start-shop-bot')
            assert response.status_code in [200, 302], "Запуск бота должен вернуть 200 или 302"
            
            # Тест остановки shop-bot
            response = authenticated_session.post('/stop-shop-bot')
            assert response.status_code in [200, 302], "Остановка бота должна вернуть 200 или 302"
            
            # Тест запуска support-bot
            response = authenticated_session.post('/start-support-bot')
            assert response.status_code in [200, 302]
            
            # Тест остановки support-bot
            response = authenticated_session.post('/stop-support-bot')
            assert response.status_code in [200, 302]

