#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для формирования User-Agent с использованием доменов

Проверяет корректность использования global_domain для формирования
User-Agent в xui_api.py.
"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import patch

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.modules.xui_api import _create_verified_panel_session
from shop_bot.data_manager.database import update_setting, get_global_domain


@pytest.mark.unit
@allure.epic("Модули")
@allure.feature("XUI API")
@allure.label("package", "src.shop_bot.modules")
class TestXuiApiDomains:
    """Тесты для формирования User-Agent с использованием доменов"""

    @allure.title("Использование global_domain в User-Agent")
    @allure.description("""
    Проверяет использование global_domain из настроек для формирования User-Agent.
    
    **Что проверяется:**
    - Установка global_domain в БД
    - Создание сессии через _create_verified_panel_session()
    - Проверка заголовка User-Agent с правильным доменом
    
    **Тестовые данные:**
    - global_domain: "https://example.com"
    - host_url: "https://test-panel.com"
    
    **Ожидаемый результат:**
    User-Agent содержит домен из global_domain.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("xui-api", "user-agent", "domain", "unit")
    def test_user_agent_uses_global_domain(self, temp_db):
        """Проверка использования global_domain в User-Agent"""
        with allure.step("Установка global_domain в БД"):
            update_setting("global_domain", "https://example.com")
            allure.attach("https://example.com", "Установленное значение", allure.attachment_type.TEXT)
        
        with allure.step("Создание сессии"):
            session = _create_verified_panel_session("https://test-panel.com")
            user_agent = session.headers.get("User-Agent", "")
            allure.attach(user_agent, "User-Agent заголовок", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert "example.com" in user_agent
            assert "DarkMaximus-XUI" in user_agent

    @allure.title("Нормализация домена в User-Agent")
    @allure.description("""
    Проверяет нормализацию домена (удаление протокола) в User-Agent.
    
    **Что проверяется:**
    - Установка global_domain с протоколом
    - Создание сессии
    - Удаление протокола из домена в User-Agent
    
    **Тестовые данные:**
    - global_domain: "https://example.com"
    
    **Ожидаемый результат:**
    User-Agent содержит домен без протокола в формате: "DarkMaximus-XUI/1.0 (+https://example.com)".
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("xui-api", "user-agent", "normalization", "unit")
    def test_user_agent_domain_normalization(self, temp_db):
        """Проверка нормализации домена в User-Agent"""
        with allure.step("Установка global_domain с протоколом"):
            update_setting("global_domain", "https://example.com")
            allure.attach("https://example.com", "Установленное значение (с протоколом)", allure.attachment_type.TEXT)
        
        with allure.step("Создание сессии"):
            session = _create_verified_panel_session("https://test-panel.com")
            user_agent = session.headers.get("User-Agent", "")
            allure.attach(user_agent, "User-Agent заголовок", allure.attachment_type.TEXT)
        
        with allure.step("Проверка нормализации"):
            # Проверяем, что в User-Agent домен используется в формате +https://example.com
            # (протокол удален из домена, но добавлен обратно в формат URL)
            assert user_agent == "DarkMaximus-XUI/1.0 (+https://example.com)"
            # Проверяем, что домен без протокола присутствует
            assert "example.com" in user_agent

    @allure.title("Fallback на дефолтное значение если global_domain отсутствует")
    @allure.description("""
    Проверяет fallback на дефолтное значение если global_domain отсутствует.
    
    **Что проверяется:**
    - Отсутствие global_domain в БД
    - Создание сессии
    - Использование дефолтного домена в User-Agent
    
    **Ожидаемый результат:**
    User-Agent содержит дефолтный домен "dark-maximus.com".
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("xui-api", "user-agent", "fallback", "unit")
    def test_user_agent_fallback_to_default(self, temp_db):
        """Проверка fallback на дефолтное значение"""
        with allure.step("Проверка отсутствия настройки"):
            global_domain = get_global_domain()
            allure.attach(str(global_domain), "Текущее значение global_domain", allure.attachment_type.TEXT)
        
        with allure.step("Создание сессии"):
            session = _create_verified_panel_session("https://test-panel.com")
            user_agent = session.headers.get("User-Agent", "")
            allure.attach(user_agent, "User-Agent заголовок", allure.attachment_type.TEXT)
        
        with allure.step("Проверка User-Agent без домена"):
            # Если global_domain отсутствует, User-Agent должен быть без домена
            assert "DarkMaximus-XUI" in user_agent
            # Не должно быть жёстко прописанного домена
            assert "dark-maximus.com" not in user_agent
            # User-Agent должен быть в формате "DarkMaximus-XUI/1.0" (без домена)
            assert user_agent == "DarkMaximus-XUI/1.0"

    @allure.title("Проверка формата User-Agent строки")
    @allure.description("""
    Проверяет корректный формат User-Agent строки.
    
    **Что проверяется:**
    - Формат: "DarkMaximus-XUI/1.0 (+https://{domain})"
    - Наличие версии
    - Наличие домена в правильном формате
    
    **Тестовые данные:**
    - global_domain: "https://example.com"
    
    **Ожидаемый результат:**
    User-Agent имеет правильный формат с версией и доменом.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("xui-api", "user-agent", "format", "unit")
    def test_user_agent_format(self, temp_db):
        """Проверка формата User-Agent строки"""
        with allure.step("Установка global_domain"):
            update_setting("global_domain", "https://example.com")
        
        with allure.step("Создание сессии"):
            session = _create_verified_panel_session("https://test-panel.com")
            user_agent = session.headers.get("User-Agent", "")
            allure.attach(user_agent, "User-Agent заголовок", allure.attachment_type.TEXT)
        
        with allure.step("Проверка формата"):
            assert user_agent.startswith("DarkMaximus-XUI/1.0")
            assert "+https://" in user_agent
            assert "example.com" in user_agent
            # Проверяем, что формат правильный
            assert user_agent == f"DarkMaximus-XUI/1.0 (+https://example.com)"

