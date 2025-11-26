#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для fallback генерации subscription_link
"""

import pytest
import allure
from unittest.mock import patch, AsyncMock
from pathlib import Path


@allure.epic("База данных")
@allure.feature("Fallback генерация subscription_link")
@allure.label("package", "src.shop_bot.database")
@pytest.mark.unit
@pytest.mark.database
class TestSubscriptionLinkFallback:
    """Тесты для автоматической генерации subscription_link на лету"""
    
    @allure.title("Fallback генерация subscription_link в validate_permanent_token")
    @allure.description("""
    Проверяет автоматическую генерацию subscription_link на лету в функции validate_permanent_token,
    когда поле subscription_link пустое, но есть subscription (sub_id).
    
    **Что проверяется:**
    - Обнаружение пустого subscription_link при наличии subscription
    - Вызов get_client_subscription_link для получения ссылки через API 3X-UI
    - Сохранение полученной ссылки в БД
    - Возврат ссылки в token_data
    
    **Тестовые данные:**
    - user_id: 123456
    - key_id: 1
    - subscription: "test-sub-id-123"
    - host_name: "test_host"
    - key_email: "test@example.com"
    - subscription_link: None (пустое)
    
    **Ожидаемый результат:**
    - subscription_link генерируется через API
    - Ссылка сохраняется в БД
    - token_data содержит сгенерированную ссылку
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("subscription_link", "fallback", "validate_permanent_token", "unit", "critical")
    def test_validate_permanent_token_fallback_generation(self, temp_db):
        """Тест fallback генерации subscription_link в validate_permanent_token"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            create_host,
            create_key_with_stats_atomic,
            get_or_create_permanent_token,
            validate_permanent_token
        )
        
        with allure.step("Подготовка тестовых данных"):
            # Регистрируем пользователя
            user_id = 123456
            register_user_if_not_exists(user_id, "test_user", referrer_id=None)
            
            # Создаем хост
            create_host(
                name="test_host",
                url="http://test-host.com",
                user="admin",
                passwd="password",
                inbound=1,
                host_code="TH"
            )
            
            # Создаем ключ БЕЗ subscription_link, но С subscription
            key_id = create_key_with_stats_atomic(
                user_id=user_id,
                host_name="test_host",
                xui_client_uuid="test-uuid-123",
                key_email="test@example.com",
                expiry_timestamp_ms=9999999999999,
                connection_string="vless://test",
                plan_name="Test Plan",
                price=100.0,
                amount_spent=100.0,
                months_purchased=1.0,
                subscription="test-sub-id-123",  # sub_id присутствует
                subscription_link=None  # subscription_link пустой
            )
            
            allure.attach(str(key_id), "Created key_id", allure.attachment_type.TEXT)
            
            # Создаем токен
            token = get_or_create_permanent_token(user_id, key_id)
            allure.attach(token[:20] + "...", "Generated token", allure.attachment_type.TEXT)
        
        with allure.step("Мокируем get_client_subscription_link для возврата тестовой ссылки"):
            mock_subscription_link = "https://test-host.com/sub/test-sub-id-123"
            
            with patch('shop_bot.modules.xui_api.get_client_subscription_link', new_callable=AsyncMock) as mock_get_link:
                mock_get_link.return_value = mock_subscription_link
                
                with allure.step("Вызываем validate_permanent_token"):
                    token_data = validate_permanent_token(token)
                    
                    allure.attach(str(token_data), "Token data", allure.attachment_type.JSON)
        
        with allure.step("Проверяем результат"):
            assert token_data is not None, "Token data should not be None"
            assert token_data.get('subscription_link') == mock_subscription_link, \
                f"Expected subscription_link to be {mock_subscription_link}, got {token_data.get('subscription_link')}"
            
            # Проверяем, что ссылка сохранена в БД
            from shop_bot.data_manager.database import get_key_by_id
            key_data = get_key_by_id(key_id)
            
            assert key_data is not None, "Key data should not be None"
            assert key_data.get('subscription_link') == mock_subscription_link, \
                f"Expected subscription_link in DB to be {mock_subscription_link}, got {key_data.get('subscription_link')}"
            
            allure.attach(
                f"subscription_link correctly generated and saved: {mock_subscription_link}",
                "Success",
                allure.attachment_type.TEXT
            )
    
    @allure.title("Fallback генерация subscription_link в get_key_by_id")
    @allure.description("""
    Проверяет автоматическую генерацию subscription_link на лету в функции get_key_by_id,
    когда поле subscription_link пустое, но есть subscription (sub_id).
    
    **Что проверяется:**
    - Обнаружение пустого subscription_link при наличии subscription
    - Вызов get_client_subscription_link для получения ссылки через API 3X-UI
    - Сохранение полученной ссылки в БД
    - Возврат ссылки в key_dict
    
    **Тестовые данные:**
    - user_id: 123457
    - key_id: 2
    - subscription: "test-sub-id-456"
    - host_name: "test_host"
    - key_email: "test2@example.com"
    - subscription_link: None (пустое)
    
    **Ожидаемый результат:**
    - subscription_link генерируется через API
    - Ссылка сохраняется в БД
    - key_dict содержит сгенерированную ссылку
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("subscription_link", "fallback", "get_key_by_id", "unit", "critical")
    def test_get_key_by_id_fallback_generation(self, temp_db):
        """Тест fallback генерации subscription_link в get_key_by_id"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            create_host,
            create_key_with_stats_atomic,
            get_key_by_id
        )
        
        with allure.step("Подготовка тестовых данных"):
            # Регистрируем пользователя
            user_id = 123457
            register_user_if_not_exists(user_id, "test_user2", referrer_id=None)
            
            # Создаем хост
            create_host(
                name="test_host",
                url="http://test-host.com",
                user="admin",
                passwd="password",
                inbound=1,
                host_code="TH"
            )
            
            # Создаем ключ БЕЗ subscription_link, но С subscription
            key_id = create_key_with_stats_atomic(
                user_id=user_id,
                host_name="test_host",
                xui_client_uuid="test-uuid-456",
                key_email="test2@example.com",
                expiry_timestamp_ms=9999999999999,
                connection_string="vless://test2",
                plan_name="Test Plan",
                price=100.0,
                amount_spent=100.0,
                months_purchased=1.0,
                subscription="test-sub-id-456",  # sub_id присутствует
                subscription_link=None  # subscription_link пустой
            )
            
            allure.attach(str(key_id), "Created key_id", allure.attachment_type.TEXT)
        
        with allure.step("Мокируем get_client_subscription_link для возврата тестовой ссылки"):
            mock_subscription_link = "https://test-host.com/sub/test-sub-id-456"
            
            with patch('shop_bot.data_manager.database.get_client_subscription_link', new_callable=AsyncMock) as mock_get_link:
                mock_get_link.return_value = mock_subscription_link
                
                with allure.step("Вызываем get_key_by_id"):
                    key_data = get_key_by_id(key_id)
                    
                    allure.attach(str(key_data), "Key data", allure.attachment_type.JSON)
        
        with allure.step("Проверяем результат"):
            assert key_data is not None, "Key data should not be None"
            assert key_data.get('subscription_link') == mock_subscription_link, \
                f"Expected subscription_link to be {mock_subscription_link}, got {key_data.get('subscription_link')}"
            
            # Проверяем, что ссылка сохранена в БД (повторный вызов без мока)
            key_data_from_db = get_key_by_id(key_id)
            
            assert key_data_from_db is not None, "Key data from DB should not be None"
            assert key_data_from_db.get('subscription_link') == mock_subscription_link, \
                f"Expected subscription_link in DB to be {mock_subscription_link}, got {key_data_from_db.get('subscription_link')}"
            
            allure.attach(
                f"subscription_link correctly generated and saved: {mock_subscription_link}",
                "Success",
                allure.attachment_type.TEXT
            )
    
    @allure.title("Fallback не срабатывает если subscription_link уже заполнен")
    @allure.description("""
    Проверяет, что fallback генерация НЕ срабатывает, если subscription_link уже заполнен в БД.
    
    **Что проверяется:**
    - Если subscription_link заполнен, fallback не вызывается
    - Существующая ссылка не перезаписывается
    - get_client_subscription_link НЕ вызывается
    
    **Тестовые данные:**
    - subscription_link: "https://existing-link.com/sub/existing-id"
    - subscription: "existing-sub-id"
    
    **Ожидаемый результат:**
    - Возвращается существующая ссылка
    - API не вызывается
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("subscription_link", "fallback", "unit")
    def test_fallback_not_triggered_when_link_exists(self, temp_db):
        """Тест что fallback не срабатывает если subscription_link уже есть"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            create_host,
            create_key_with_stats_atomic,
            get_key_by_id
        )
        
        with allure.step("Подготовка тестовых данных"):
            # Регистрируем пользователя
            user_id = 123458
            register_user_if_not_exists(user_id, "test_user3", referrer_id=None)
            
            # Создаем хост
            create_host(
                name="test_host",
                url="http://test-host.com",
                user="admin",
                passwd="password",
                inbound=1,
                host_code="TH"
            )
            
            existing_link = "https://existing-link.com/sub/existing-id"
            
            # Создаем ключ С subscription_link
            key_id = create_key_with_stats_atomic(
                user_id=user_id,
                host_name="test_host",
                xui_client_uuid="test-uuid-789",
                key_email="test3@example.com",
                expiry_timestamp_ms=9999999999999,
                connection_string="vless://test3",
                plan_name="Test Plan",
                price=100.0,
                amount_spent=100.0,
                months_purchased=1.0,
                subscription="existing-sub-id",
                subscription_link=existing_link  # subscription_link уже заполнен
            )
            
            allure.attach(str(key_id), "Created key_id", allure.attachment_type.TEXT)
            allure.attach(existing_link, "Existing subscription_link", allure.attachment_type.TEXT)
        
        with allure.step("Мокируем get_client_subscription_link (не должен вызваться)"):
            with patch('shop_bot.modules.xui_api.get_client_subscription_link', new_callable=AsyncMock) as mock_get_link:
                mock_get_link.return_value = "https://should-not-be-called.com/sub/test"
                
                with allure.step("Вызываем get_key_by_id"):
                    key_data = get_key_by_id(key_id)
                    
                    allure.attach(str(key_data), "Key data", allure.attachment_type.JSON)
        
        with allure.step("Проверяем результат"):
            assert key_data is not None, "Key data should not be None"
            assert key_data.get('subscription_link') == existing_link, \
                f"Expected subscription_link to remain {existing_link}, got {key_data.get('subscription_link')}"
            
            # Проверяем, что API НЕ вызывался
            mock_get_link.assert_not_called()
            
            allure.attach(
                f"Existing subscription_link preserved: {existing_link}",
                "Success",
                allure.attachment_type.TEXT
            )
    
    @allure.title("Fallback обрабатывает ошибки API корректно")
    @allure.description("""
    Проверяет корректную обработку ошибок при fallback генерации subscription_link.
    
    **Что проверяется:**
    - Если API возвращает None, ошибка логируется
    - Если API выбрасывает исключение, ошибка логируется
    - Функция не падает с ошибкой
    - Возвращается key_data без subscription_link
    
    **Тестовые данные:**
    - subscription: "test-sub-id-error"
    - subscription_link: None
    
    **Ожидаемый результат:**
    - Функция возвращает key_data
    - subscription_link остается None
    - Ошибка залогирована
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("subscription_link", "fallback", "error_handling", "unit")
    def test_fallback_handles_api_errors(self, temp_db):
        """Тест обработки ошибок при fallback генерации"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            create_host,
            create_key_with_stats_atomic,
            get_key_by_id
        )
        
        with allure.step("Подготовка тестовых данных"):
            # Регистрируем пользователя
            user_id = 123459
            register_user_if_not_exists(user_id, "test_user4", referrer_id=None)
            
            # Создаем хост
            create_host(
                name="test_host",
                url="http://test-host.com",
                user="admin",
                passwd="password",
                inbound=1,
                host_code="TH"
            )
            
            # Создаем ключ БЕЗ subscription_link
            key_id = create_key_with_stats_atomic(
                user_id=user_id,
                host_name="test_host",
                xui_client_uuid="test-uuid-error",
                key_email="test4@example.com",
                expiry_timestamp_ms=9999999999999,
                connection_string="vless://test4",
                plan_name="Test Plan",
                price=100.0,
                amount_spent=100.0,
                months_purchased=1.0,
                subscription="test-sub-id-error",
                subscription_link=None
            )
            
            allure.attach(str(key_id), "Created key_id", allure.attachment_type.TEXT)
        
        with allure.step("Мокируем get_client_subscription_link для возврата None (ошибка API)"):
            with patch('shop_bot.modules.xui_api.get_client_subscription_link', new_callable=AsyncMock) as mock_get_link:
                mock_get_link.return_value = None  # API вернул None (ошибка)
                
                with allure.step("Вызываем get_key_by_id"):
                    key_data = get_key_by_id(key_id)
                    
                    allure.attach(str(key_data), "Key data", allure.attachment_type.JSON)
        
        with allure.step("Проверяем результат"):
            assert key_data is not None, "Key data should not be None even if API fails"
            assert key_data.get('subscription_link') is None, \
                f"Expected subscription_link to be None when API fails, got {key_data.get('subscription_link')}"
            
            allure.attach(
                "Function handled API error gracefully without crashing",
                "Success",
                allure.attachment_type.TEXT
            )

