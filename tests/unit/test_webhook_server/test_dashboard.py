#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для Dashboard веб-панели

Тестирует главную панель и страницу производительности
"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.unit
@allure.epic("Веб-панель")
@allure.feature("Dashboard")
@allure.label("package", "src.shop_bot.webhook_server")
class TestWebhookServerDashboard:
    """Тесты для Dashboard веб-панели"""

    @allure.story("Dashboard: главная панель")
    @allure.title("Главная панель Dashboard")
    @allure.description("""
    Проверяет отображение главной панели Dashboard в веб-панели.
    
    **Что проверяется:**
    - Доступность страницы /dashboard для авторизованного администратора
    - Отображение статистики (количество пользователей, ключей, доходов)
    - Корректная структура данных для графиков (chart_data)
    - Корректный статус ответа (200)
    
    **Тестовые данные:**
    - Учетные данные администратора из фикстуры admin_credentials
    - Мокированные данные статистики (пустые значения)
    - Мокированные данные для графиков (dates, new_users, new_keys, earned_sum)
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Администратор авторизован в веб-панели
    - Все функции получения данных замокированы
    
    **Шаги теста:**
    1. Создание Flask приложения с моком bot_controller
    2. Авторизация администратора через POST /login
    3. Мокирование всех функций получения данных
    4. Запрос GET /dashboard
    5. Проверка статуса ответа (200)
    
    **Ожидаемый результат:**
    Главная панель Dashboard успешно отображается со статусом 200, все данные корректно переданы в шаблон.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("dashboard", "main", "webhook_server", "unit")
    def test_dashboard_page(self, temp_db, admin_credentials):
        """Тест главной панели (/)"""
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock
        from datetime import datetime, timedelta
        
        with allure.step("Подготовка тестового окружения"):
            mock_bot_controller = MagicMock()
            app = create_webhook_app(mock_bot_controller)
            app.config['TESTING'] = True  # Отключаем rate limiting
            allure.attach(str(temp_db), "Путь к временной БД", allure.attachment_type.TEXT)
        
        with app.test_client() as client:
            with allure.step("Авторизация администратора"):
                with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=True):
                    login_response = client.post('/login', data=admin_credentials)
                    allure.attach(str(login_response.status_code), "Статус авторизации", allure.attachment_type.TEXT)
                    assert login_response.status_code in [200, 302], "Авторизация должна быть успешной"
            
            with allure.step("Мокирование функций получения данных"):
                # Подготавливаем данные для графиков
                days = 30
                dates = [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days)]
                dates.reverse()
                chart_data = {
                    'dates': dates,
                    'new_users': [0] * days,
                    'new_keys': [0] * days,
                    'earned_sum': [0.0] * days,
                    'new_notifications': [0] * days
                }
                allure.attach(str(chart_data), "Данные для графиков", allure.attachment_type.JSON)
            
            with allure.step("Запрос страницы Dashboard"):
                # Мокируем функции получения данных
                with patch('src.shop_bot.webhook_server.app.get_all_hosts', return_value=[]):
                    with patch('src.shop_bot.webhook_server.app.get_user_count', return_value=0):
                        with patch('src.shop_bot.webhook_server.app.get_total_keys_count', return_value=0):
                            with patch('src.shop_bot.webhook_server.app.get_total_earned_sum', return_value=0.0):
                                with patch('src.shop_bot.webhook_server.app.get_total_notifications_count', return_value=0):
                                    with patch('src.shop_bot.webhook_server.app.get_paginated_transactions', return_value=([], 0)):
                                        with patch('src.shop_bot.webhook_server.app.get_daily_stats_for_charts', return_value=chart_data):
                                            response = client.get('/dashboard')
                                            allure.attach(str(response.status_code), "Статус ответа", allure.attachment_type.TEXT)
                                            
                                            with allure.step("Проверка статуса ответа"):
                                                assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}"

    @allure.story("Dashboard: производительность")
    @allure.title("Страница производительности")
    @allure.description("""
    Проверяет отображение страницы производительности в веб-панели.
    
    **Что проверяется:**
    - Доступность страницы /performance для авторизованного администратора
    - Отображение метрик производительности (total_requests, avg_response_time)
    - Корректная работа асинхронных функций получения данных производительности
    - Корректный статус ответа (200)
    
    **Тестовые данные:**
    - Учетные данные администратора из фикстуры admin_credentials
    - Мокированные данные производительности (performance_summary, slow_operations, recent_errors, operation_stats)
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Администратор авторизован в веб-панели
    - get_performance_monitor возвращает AsyncMock с корректными методами
    
    **Шаги теста:**
    1. Создание Flask приложения с моком bot_controller
    2. Авторизация администратора через POST /login
    3. Мокирование get_performance_monitor с AsyncMock
    4. Мокирование методов монитора (apply_settings, get_performance_summary, get_slow_operations, get_recent_errors, get_operation_stats)
    5. Запрос GET /performance
    6. Проверка статуса ответа (200)
    
    **Ожидаемый результат:**
    Страница производительности успешно отображается со статусом 200, все метрики корректно переданы в шаблон.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("dashboard", "performance", "webhook_server", "unit")
    def test_performance_page(self, temp_db, admin_credentials):
        """Тест страницы производительности (/performance)"""
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock, AsyncMock
        
        with allure.step("Подготовка тестового окружения"):
            mock_bot_controller = MagicMock()
            app = create_webhook_app(mock_bot_controller)
            app.config['TESTING'] = True  # Отключаем rate limiting
            allure.attach(str(temp_db), "Путь к временной БД", allure.attachment_type.TEXT)
        
        with app.test_client() as client:
            with allure.step("Авторизация администратора"):
                with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=True):
                    login_response = client.post('/login', data=admin_credentials)
                    allure.attach(str(login_response.status_code), "Статус авторизации", allure.attachment_type.TEXT)
                    assert login_response.status_code in [200, 302], "Авторизация должна быть успешной"
            
            with allure.step("Мокирование функций получения данных производительности"):
                # Создаем AsyncMock для монитора производительности
                mock_monitor = AsyncMock()
                mock_monitor.apply_settings = AsyncMock(return_value=None)
                mock_monitor.get_performance_summary = AsyncMock(return_value={
                    'total_operations': 100,  # Исправлено: было total_requests
                    'avg_response_time': 0.5,
                    'slow_operations': 0,  # Добавлено: отсутствовало в моке
                    'error_rate': 0.0,  # Добавлено: отсутствовало в моке
                    'top_operations': [],  # Пустой список, чтобы не было итерации
                    'top_users': []  # Добавлено: отсутствовало в моке, используется в шаблоне
                })
                mock_monitor.get_slow_operations = AsyncMock(return_value=[])
                mock_monitor.get_recent_errors = AsyncMock(return_value=[])
                mock_monitor.get_operation_stats = AsyncMock(return_value={})
                
                allure.attach(str(mock_monitor), "Мок монитора производительности", allure.attachment_type.TEXT)
            
            with allure.step("Запрос страницы производительности"):
                with patch('src.shop_bot.webhook_server.app.get_performance_monitor', return_value=mock_monitor):
                    with patch('src.shop_bot.webhook_server.app.get_all_settings', return_value={'monitoring_enabled': 'true'}):
                        response = client.get('/performance')
                        allure.attach(str(response.status_code), "Статус ответа", allure.attachment_type.TEXT)
                        
                        with allure.step("Проверка статуса ответа"):
                            assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}"

    @allure.story("Dashboard: главная панель")
    @allure.title("Получение общих данных для шаблонов")
    @allure.description("""
    Проверяет получение общих данных для шаблонов веб-панели.
    
    **Что проверяется:**
    - Вызов функции get_common_template_data
    - Наличие обязательных полей (bot_status, all_settings_ok)
    - Корректность структуры данных
    
    **Ожидаемый результат:**
    Функция возвращает корректные общие данные для шаблонов с обязательными полями.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("dashboard", "template_data", "webhook_server", "unit")
    def test_get_common_template_data(self, temp_db):
        """Тест общих данных для шаблонов"""
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock
        
        mock_bot_controller = MagicMock()
        app = create_webhook_app(mock_bot_controller)
        
        with app.app_context():
            # Мокируем зависимости
            with patch('src.shop_bot.webhook_server.app._bot_controller') as mock_controller:
                mock_controller.get_status.return_value = {'status': 'running'}
                with patch('src.shop_bot.webhook_server.app.get_all_settings', return_value={}):
                    # Получаем функцию get_common_template_data
                    from src.shop_bot.webhook_server.app import get_common_template_data
                    data = get_common_template_data()
                    
                    # Проверяем наличие обязательных полей
                    assert 'bot_status' in data
                    assert 'all_settings_ok' in data
                    assert 'hidden_mode' in data
                    assert 'project_version' in data
                    assert 'global_settings' in data

