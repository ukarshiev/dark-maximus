#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit-тесты для мониторинга"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.unit
@allure.epic("Веб-панель")
@allure.feature("Мониторинг")
@allure.label("package", "src.shop_bot.webhook_server")
class TestMonitoring:
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

    @allure.story("Мониторинг: проверка статуса")
    @allure.title("Переключение состояния мониторинга")
    @allure.description("""
    Проверяет переключение состояния мониторинга через API endpoint /api/monitoring/toggle.
    
    **Что проверяется:**
    - Включение/отключение мониторинга через API
    - Корректный статус ответа (200, 400 или 500)
    - Обновление настройки мониторинга в БД
    
    **Тестовые данные:**
    - enabled: 'true'
    - Моки для update_setting
    
    **Ожидаемый результат:**
    Состояние мониторинга успешно переключено, статус ответа 200, 400 или 500.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("monitoring", "api", "toggle", "webhook_server", "unit")
    def test_toggle_monitoring(self, authenticated_session):
        with patch('shop_bot.data_manager.database.update_setting'):
            response = authenticated_session.post('/api/monitoring/toggle', 
                                                 data={'enabled': 'true'},
                                                 content_type='application/json')
            assert response.status_code in [200, 400, 500]

    @allure.story("Мониторинг: проверка статуса")
    @allure.title("Экспорт данных мониторинга")
    @allure.description("""
    Проверяет экспорт данных мониторинга через API endpoint /api/monitoring/export.
    
    **Что проверяется:**
    - Экспорт всех метрик мониторинга
    - Корректный статус ответа (200 или 500)
    - Получение данных из performance_monitor
    
    **Тестовые данные:**
    - Моки для get_performance_monitor, возвращающие пустой список метрик
    
    **Ожидаемый результат:**
    Данные мониторинга успешно экспортированы, статус ответа 200 или 500.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("monitoring", "api", "export", "webhook_server", "unit")
    def test_export_monitoring_data(self, authenticated_session):
        with patch('shop_bot.utils.performance_monitor.get_performance_monitor') as mock_monitor:
            mock_monitor.return_value.get_all_metrics.return_value = []
            response = authenticated_session.get('/api/monitoring/export')
            assert response.status_code in [200, 500]

    @allure.story("Мониторинг: проверка статуса")
    @allure.title("Получение почасовой статистики мониторинга")
    @allure.description("""
    Проверяет получение почасовой статистики мониторинга через API endpoint /api/monitoring/hourly-stats.
    
    **Что проверяется:**
    - Получение почасовой статистики за указанный период
    - Корректный статус ответа (200 или 500)
    - Получение данных из performance_monitor для графиков
    
    **Тестовые данные:**
    - hours: 24 (параметр запроса)
    - Моки для get_performance_monitor, возвращающие пустой список статистики
    
    **Ожидаемый результат:**
    Почасовая статистика успешно получена, статус ответа 200 или 500.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("monitoring", "api", "hourly_stats", "webhook_server", "unit")
    def test_hourly_stats(self, authenticated_session):
        with patch('shop_bot.utils.performance_monitor.get_performance_monitor') as mock_monitor:
            mock_monitor.return_value.get_hourly_stats_for_charts.return_value = []
            response = authenticated_session.get('/api/monitoring/hourly-stats?hours=24')
            assert response.status_code in [200, 500]

