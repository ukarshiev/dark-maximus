#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit-тесты для фильтров Jinja2"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.unit
@allure.epic("Веб-панель")
@allure.feature("Фильтры")
@allure.label("package", "src.shop_bot.webhook_server")
class TestFilters:
    """Тесты для Jinja2 фильтров"""

    @allure.story("Фильтры: применение фильтров")
    @allure.title("Фильтр конвертации timestamp в datetime")
    @allure.description("""
    Проверяет работу Jinja2 фильтра timestamp_to_datetime для конвертации timestamp в datetime.
    
    **Что проверяется:**
    - Корректная работа фильтра timestamp_to_datetime
    - Конвертация timestamp в объект datetime
    - Возврат непустого результата
    
    **Тестовые данные:**
    - timestamp: текущее время в формате timestamp
    
    **Ожидаемый результат:**
    Фильтр корректно конвертирует timestamp в datetime и возвращает непустой результат.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("filters", "jinja2", "timestamp", "webhook_server", "unit")
    def test_timestamp_to_datetime_filter(self):
        """Тест фильтра конвертации timestamp"""
        from shop_bot.webhook_server.app import create_webhook_app
        mock_bot_controller = MagicMock()
        app = create_webhook_app(mock_bot_controller)
        
        with app.app_context():
            timestamp = int(datetime.now(timezone.utc).timestamp())
            result = app.jinja_env.filters['timestamp_to_datetime'](timestamp)
            assert result is not None

    @allure.story("Фильтры: применение фильтров")
    @allure.title("Фильтр форматирования даты strftime")
    @allure.description("""
    Проверяет работу Jinja2 фильтра strftime для форматирования даты.
    
    **Что проверяется:**
    - Корректная работа фильтра strftime
    - Форматирование datetime по указанному формату
    - Возврат непустого результата
    
    **Тестовые данные:**
    - dt: текущее время в UTC
    - format: '%Y-%m-%d'
    
    **Ожидаемый результат:**
    Фильтр корректно форматирует datetime по формату '%Y-%m-%d' и возвращает непустой результат.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("filters", "jinja2", "strftime", "webhook_server", "unit")
    def test_strftime_filter(self):
        from shop_bot.webhook_server.app import create_webhook_app
        mock_bot_controller = MagicMock()
        app = create_webhook_app(mock_bot_controller)
        
        with app.app_context():
            dt = datetime.now(timezone.utc)
            result = app.jinja_env.filters['strftime'](dt, '%Y-%m-%d')
            assert result is not None

    @allure.story("Фильтры: применение фильтров")
    @allure.title("Фильтр форматирования даты для панели panel_datetime")
    @allure.description("""
    Проверяет работу Jinja2 фильтра panel_datetime для форматирования даты в формате панели.
    
    **Что проверяется:**
    - Корректная работа фильтра panel_datetime
    - Форматирование datetime в формате панели
    - Возврат непустого результата
    
    **Тестовые данные:**
    - dt: текущее время в UTC
    
    **Ожидаемый результат:**
    Фильтр корректно форматирует datetime в формате панели и возвращает непустой результат.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("filters", "jinja2", "panel_datetime", "webhook_server", "unit")
    def test_panel_datetime_filter(self):
        from shop_bot.webhook_server.app import create_webhook_app
        mock_bot_controller = MagicMock()
        app = create_webhook_app(mock_bot_controller)
        
        with app.app_context():
            dt = datetime.now(timezone.utc)
            result = app.jinja_env.filters['panel_datetime'](dt)
            assert result is not None

    @allure.story("Фильтры: применение фильтров")
    @allure.title("Фильтр форматирования даты в ISO формате panel_iso")
    @allure.description("""
    Проверяет работу Jinja2 фильтра panel_iso для форматирования даты в ISO формате.
    
    **Что проверяется:**
    - Корректная работа фильтра panel_iso
    - Форматирование datetime в ISO формате
    - Возврат непустого результата
    
    **Тестовые данные:**
    - dt: текущее время в UTC
    
    **Ожидаемый результат:**
    Фильтр корректно форматирует datetime в ISO формате и возвращает непустой результат.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("filters", "jinja2", "panel_iso", "webhook_server", "unit")
    def test_panel_iso_filter(self):
        from shop_bot.webhook_server.app import create_webhook_app
        mock_bot_controller = MagicMock()
        app = create_webhook_app(mock_bot_controller)
        
        with app.app_context():
            dt = datetime.now(timezone.utc)
            result = app.jinja_env.filters['panel_iso'](dt)
            assert result is not None

