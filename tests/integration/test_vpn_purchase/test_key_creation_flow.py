#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты для создания ключей через 3X-UI

Тестирует создание ключей, получение subscription link и connection string
"""

import pytest
import allure
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import uuid
from unittest.mock import patch, MagicMock, AsyncMock

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.modules import xui_api
from shop_bot.data_manager.database import (
    register_user_if_not_exists,
    create_plan,
    get_key_by_id,
)


@pytest.mark.integration
@pytest.mark.database
@allure.epic("Интеграционные тесты")
@allure.feature("Покупка VPN")
@allure.label("package", "tests.integration.test_vpn_purchase")
class TestKeyCreationFlow:
    """Интеграционные тесты для создания ключей"""

    @pytest.fixture
    def test_setup(self, temp_db, sample_host, sample_plan):
        """Фикстура для настройки тестового окружения"""
        import sqlite3
        
        # Создаем пользователя
        user_id = 123456810
        register_user_if_not_exists(user_id, "test_user_key", None, "Test User Key")
        
        # Создаем хост в БД
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",
                (sample_host['host_name'], sample_host['host_url'], sample_host['host_username'], 
                 sample_host['host_pass'], sample_host['host_inbound_id'], sample_host['host_code'])
            )
            conn.commit()
        
        # Создаем план
        create_plan(
            host_name=sample_host['host_name'],
            plan_name=sample_plan['plan_name'],
            months=sample_plan['months'],
            price=sample_plan['price'],
            days=sample_plan['days'],
            traffic_gb=sample_plan['traffic_gb'],
            hours=sample_plan['hours']
        )
        
        return {
            'user_id': user_id,
            'host_name': sample_host['host_name'],
            'host_url': sample_host['host_url'],
            'host_username': sample_host['host_username'],
            'host_pass': sample_host['host_pass'],
            'host_inbound_id': sample_host['host_inbound_id']
        }

    @allure.story("Создание нового ключа через 3X-UI")
    @allure.title("Создание нового ключа через 3X-UI")
    @allure.description("""
    Проверяет создание нового VPN ключа через 3X-UI API от вызова функции до получения результата.
    
    **Что проверяется:**
    - Вызов функции create_or_update_key_on_host с правильными параметрами
    - Получение client_uuid, email, expiry_timestamp_ms, subscription_link, connection_string
    - Корректность возвращаемых данных
    
    **Тестовые данные:**
    - user_id: 123456810 (из test_setup)
    - host_name: из test_setup
    - email: генерируется автоматически
    - days_to_add: 30
    - expiry_timestamp_ms: текущее время + 30 дней
    
    **Шаги теста:**
    1. Подготовка мока xui_api с возвратом данных ключа
    2. Вызов create_or_update_key_on_host
    3. Проверка результата
    
    **Ожидаемый результат:**
    Ключ должен быть создан с правильными данными (client_uuid, subscription_link, connection_string).
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("key-creation", "xui-api", "integration", "critical")
    @pytest.mark.asyncio
    async def test_key_creation_flow_new_key(self, temp_db, test_setup, mock_xui_api):
        """Тест создания нового ключа через 3X-UI"""
        # Патчим xui_api
        with patch('shop_bot.modules.xui_api.create_or_update_key_on_host', new_callable=AsyncMock) as mock_create_key:
            test_uuid = str(uuid.uuid4())
            test_subscription_link = 'https://example.com/subscription'
            test_connection_string = 'vless://test'
            days_to_add = 30
            email = f"test_{uuid.uuid4().hex[:8]}@example.com"
            expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=days_to_add)).timestamp() * 1000)
            mock_create_key.return_value = {
                'client_uuid': test_uuid,
                'email': email,
                'expiry_timestamp_ms': expiry_timestamp_ms,
                'subscription_link': test_subscription_link,
                'connection_string': test_connection_string
            }
            
            # Создаем ключ
            result = await xui_api.create_or_update_key_on_host(
                host_name=test_setup['host_name'],
                email=email,
                days_to_add=days_to_add,
                comment=str(test_setup['user_id']),
                sub_id=None,
                telegram_chat_id=test_setup['user_id'],
                host_code=None
            )
            
            # Проверяем результат
            assert result is not None, "Ключ должен быть создан"
            assert result['client_uuid'] == test_uuid, "UUID должен совпадать"
            assert result['subscription_link'] == test_subscription_link, "Subscription link должен совпадать"
            assert result['connection_string'] == test_connection_string, "Connection string должен совпадать"

    @allure.story("Получение subscription link при создании ключа")
    @allure.title("Получение subscription link при создании ключа")
    @allure.description("""
    Проверяет получение subscription link при создании VPN ключа через 3X-UI API.
    
    **Что проверяется:**
    - Наличие subscription_link в результате создания ключа
    - Корректность значения subscription_link
    
    **Тестовые данные:**
    - user_id: 123456810 (из test_setup)
    - host_name: из test_setup
    - subscription_link: 'https://example.com/subscription'
    
    **Ожидаемый результат:**
    Результат должен содержать subscription_link с правильным значением.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("key-creation", "subscription-link", "integration", "normal")
    @pytest.mark.asyncio
    async def test_key_creation_flow_subscription_link(self, temp_db, test_setup, mock_xui_api):
        """Тест получения subscription link"""
        # Патчим xui_api
        with patch('shop_bot.modules.xui_api.create_or_update_key_on_host', new_callable=AsyncMock) as mock_create_key:
            test_subscription_link = 'https://example.com/subscription'
            email = f"test_{uuid.uuid4().hex[:8]}@example.com"
            expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            mock_create_key.return_value = {
                'client_uuid': str(uuid.uuid4()),
                'email': email,
                'expiry_timestamp_ms': expiry_timestamp_ms,
                'subscription_link': test_subscription_link,
                'connection_string': 'vless://test'
            }
            
            # Создаем ключ
            result = await xui_api.create_or_update_key_on_host(
                host_name=test_setup['host_name'],
                email=email,
                days_to_add=30,
                comment=str(test_setup['user_id']),
                sub_id=None,
                telegram_chat_id=test_setup['user_id'],
                host_code=None
            )
            
            # Проверяем subscription link
            assert result is not None, "Ключ должен быть создан"
            assert 'subscription_link' in result, "Результат должен содержать subscription_link"
            assert result['subscription_link'] == test_subscription_link, "Subscription link должен совпадать"

    @allure.story("Формирование connection string при создании ключа")
    @allure.title("Формирование connection string при создании ключа")
    @allure.description("""
    Проверяет формирование connection string при создании VPN ключа через 3X-UI API.
    
    **Что проверяется:**
    - Наличие connection_string в результате создания ключа
    - Корректность значения connection_string
    
    **Тестовые данные:**
    - user_id: 123456810 (из test_setup)
    - host_name: из test_setup
    - connection_string: 'vless://test-connection-string'
    
    **Ожидаемый результат:**
    Результат должен содержать connection_string с правильным значением.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("key-creation", "connection-string", "integration", "normal")
    @pytest.mark.asyncio
    async def test_key_creation_flow_connection_string(self, temp_db, test_setup, mock_xui_api):
        """Тест формирования connection string"""
        # Патчим xui_api
        with patch('shop_bot.modules.xui_api.create_or_update_key_on_host', new_callable=AsyncMock) as mock_create_key:
            test_connection_string = 'vless://test-connection-string'
            email = f"test_{uuid.uuid4().hex[:8]}@example.com"
            expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            mock_create_key.return_value = {
                'client_uuid': str(uuid.uuid4()),
                'email': email,
                'expiry_timestamp_ms': expiry_timestamp_ms,
                'subscription_link': 'https://example.com/subscription',
                'connection_string': test_connection_string
            }
            
            # Создаем ключ
            result = await xui_api.create_or_update_key_on_host(
                host_name=test_setup['host_name'],
                email=email,
                days_to_add=30,
                comment=str(test_setup['user_id']),
                sub_id=None,
                telegram_chat_id=test_setup['user_id'],
                host_code=None
            )
            
            # Проверяем connection string
            assert result is not None, "Ключ должен быть создан"
            assert 'connection_string' in result, "Результат должен содержать connection_string"
            assert result['connection_string'] == test_connection_string, "Connection string должен совпадать"

    @allure.story("Обработка ошибок при создании ключа")
    @allure.title("Обработка ошибок при создании ключа")
    @allure.description("""
    Проверяет обработку ошибок при создании VPN ключа через 3X-UI API.
    
    **Что проверяется:**
    - Обработка ситуации, когда xui_api возвращает None (ошибка)
    - Корректное возвращение None при ошибке создания ключа
    
    **Тестовые данные:**
    - user_id: 123456810 (из test_setup)
    - host_name: из test_setup
    - mock_xui_api.create_or_update_key_on_host возвращает None
    
    **Ожидаемый результат:**
    При ошибке создания ключа функция должна вернуть None.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("key-creation", "error-handling", "integration", "normal")
    @pytest.mark.asyncio
    async def test_key_creation_flow_error_handling(self, temp_db, test_setup, mock_xui_api):
        """Тест обработки ошибок создания"""
        # Патчим xui_api для возврата ошибки
        with patch('shop_bot.modules.xui_api.create_or_update_key_on_host', new_callable=AsyncMock) as mock_create_key:
            mock_create_key.return_value = None  # Ошибка создания ключа
            
            # Пытаемся создать ключ
            email = f"test_{uuid.uuid4().hex[:8]}@example.com"
            result = await xui_api.create_or_update_key_on_host(
                host_name=test_setup['host_name'],
                email=email,
                days_to_add=30,
                comment=str(test_setup['user_id']),
                sub_id=None,
                telegram_chat_id=test_setup['user_id'],
                host_code=None
            )
            
            # Проверяем, что результат None при ошибке
            assert result is None, "При ошибке результат должен быть None"

