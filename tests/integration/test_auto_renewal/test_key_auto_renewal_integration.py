# -*- coding: utf-8 -*-
"""
Интеграционные тесты для автопродления с индивидуальными настройками ключей
"""

import pytest
import allure
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch

from shop_bot.data_manager import database
from shop_bot.data_manager.scheduler import perform_auto_renewals


@allure.epic("Интеграционные тесты")
@allure.feature("Автопродление ключей")
@allure.label("package", "tests.integration.test_auto_renewal")
@pytest.mark.integration
@pytest.mark.database
class TestKeyAutoRenewalIntegration:
    """Интеграционные тесты для автопродления с индивидуальными настройками ключей"""

    @pytest.mark.asyncio
    @allure.story("Автопродление с отключенным индивидуальным автопродлением ключа")
    @allure.title("Автопродление не происходит для ключа с отключенным автопродлением")
    @allure.description("""
    Интеграционный тест, проверяющий поведение автопродления при отключенном индивидуальном автопродлении ключа.
    
    **Что проверяется:**
    - Создание пользователя, хоста и тарифа
    - Создание ключа с истекшим сроком действия
    - Отключение индивидуального автопродления для ключа (set_key_auto_renewal_enabled(key_id, False))
    - Включение глобального автопродления для пользователя
    - Выполнение процесса автопродления через perform_auto_renewals
    - Проверка, что ключ не был продлен (expiry_date не изменился)
    
    **Тестовые данные:**
    - user_id: 123500
    - host_name: 'test_host_key_autorenew'
    - balance: 1000.0 RUB (достаточно для продления)
    - expiry_date: текущее время - 1 день (истекший ключ)
    - key_auto_renewal_enabled: False (отключено для ключа)
    - global_auto_renewal_enabled: True (включено для пользователя)
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Мок бота настроен (mock_bot)
    - Мок 3X-UI API настроен (mock_xui_api)
    - Глобальное автопродление включено для пользователя
    - Индивидуальное автопродление отключено для ключа
    
    **Шаги теста:**
    1. Создание пользователя, хоста и тарифа
    2. Пополнение баланса до 1000.0 RUB
    3. Включение глобального автопродления
    4. Создание ключа с истекшим сроком
    5. Отключение индивидуального автопродления для ключа
    6. Выполнение perform_auto_renewals
    7. Проверка, что ключ не был продлен
    
    **Ожидаемый результат:**
    - Ключ не был продлен (expiry_date остался неизменным)
    - Индивидуальное отключение автопродления имеет приоритет над глобальным
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("auto_renewal", "integration", "key_auto_renewal", "disabled", "critical")
    async def test_auto_renewal_with_disabled_key_auto_renewal(self, temp_db, mock_bot, mock_xui_api):
        """Тест: автопродление не происходит для ключа с отключенным автопродлением"""
        with allure.step("Подготовка тестовых данных"):
            from shop_bot.data_manager.database import (
                register_user_if_not_exists,
                create_key_for_user,
                add_to_user_balance,
                set_auto_renewal_enabled,
                set_key_auto_renewal_enabled,
                get_key_by_id,
            )
            
            user_id = 123500
            username = "test_user_key_autorenew"
            
            # Регистрируем пользователя
            user = register_user_if_not_exists(user_id, username)
            assert user is not None
            
            # Устанавливаем баланс
            add_to_user_balance(user_id, 1000.0)
            
            # Включаем глобальное автопродление
            set_auto_renewal_enabled(user_id, True)
            
            # Создаем хост и тариф
            from shop_bot.data_manager.database import create_host, create_plan
            host_name = "test_host_key_autorenew"
            create_host(host_name, "http://test.com", "user", "pass", 1, "code")
            create_plan(host_name, "Test Plan", 1, 0, 0, 100.0)
            
            # Создаем ключ с истекшим сроком
            expiry_date = datetime.now(timezone.utc) - timedelta(days=1)
            expiry_timestamp_ms = int(expiry_date.timestamp() * 1000)
            key_id = add_new_key(
                user_id=user_id,
                host_name=host_name,
                xui_client_uuid="test-uuid-key-autorenew",
                key_email=f"test-key-autorenew@{host_name}.com",
                expiry_timestamp_ms=expiry_timestamp_ms,
                connection_string="vless://test",
                plan_name="Test Plan",
                price=100.0,
            )
            assert key_id is not None
            
            # Отключаем автопродление для ключа
            set_key_auto_renewal_enabled(key_id, False)
            
            # Проверяем, что автопродление отключено для ключа
            assert get_key_auto_renewal_enabled(key_id) is False
            
            # Получаем старое expiry_date
            old_key = get_key_by_id(key_id)
            old_expiry = datetime.fromisoformat(old_key['expiry_date'])

        with allure.step("Выполнение автопродления"):
            await perform_auto_renewals(mock_bot)

        with allure.step("Проверка результата"):
            # Проверяем, что ключ НЕ был продлен
            updated_key = get_key_by_id(key_id)
            new_expiry = datetime.fromisoformat(updated_key['expiry_date'])
            
            assert new_expiry == old_expiry, "Ключ с отключенным автопродлением не должен быть продлен"

    @pytest.mark.asyncio
    @allure.story("Автопродление при включенном глобальном, но отключенном индивидуальном")
    @allure.title("Автопродление не происходит при включенном глобальном, но отключенном индивидуальном")
    @allure.description("""
    Интеграционный тест, проверяющий поведение автопродления при включенном глобальном автопродлении, но отключенном индивидуальном для ключа.
    
    **Что проверяется:**
    - Создание пользователя, хоста и тарифа
    - Создание ключа с истекшим сроком действия
    - Включение глобального автопродления для пользователя
    - Отключение индивидуального автопродления для ключа
    - Выполнение процесса автопродления через perform_auto_renewals
    - Проверка, что ключ не был продлен (expiry_date не изменился)
    
    **Тестовые данные:**
    - user_id: 123501
    - host_name: 'test_host_mixed_autorenew'
    - balance: 1000.0 RUB (достаточно для продления)
    - expiry_date: текущее время - 1 день (истекший ключ)
    - key_auto_renewal_enabled: False (отключено для ключа)
    - global_auto_renewal_enabled: True (включено для пользователя)
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Мок бота настроен (mock_bot)
    - Мок 3X-UI API настроен (mock_xui_api)
    - Глобальное автопродление включено для пользователя
    - Индивидуальное автопродление отключено для ключа
    
    **Шаги теста:**
    1. Создание пользователя, хоста и тарифа
    2. Пополнение баланса до 1000.0 RUB
    3. Включение глобального автопродления
    4. Создание ключа с истекшим сроком
    5. Отключение индивидуального автопродления для ключа
    6. Выполнение perform_auto_renewals
    7. Проверка, что ключ не был продлен
    
    **Ожидаемый результат:**
    - Ключ не был продлен (expiry_date остался неизменным)
    - Индивидуальное отключение автопродления имеет приоритет над глобальным
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("auto_renewal", "integration", "key_auto_renewal", "mixed", "critical")
    async def test_auto_renewal_with_enabled_global_disabled_key(self, temp_db, mock_bot, mock_xui_api):
        """Тест: автопродление не происходит при включенном глобальном, но отключенном индивидуальном"""
        with allure.step("Подготовка тестовых данных"):
            from shop_bot.data_manager.database import (
                register_user_if_not_exists,
                add_new_key,
                add_to_user_balance,
                set_auto_renewal_enabled,
                set_key_auto_renewal_enabled,
                get_key_by_id,
            )
            
            user_id = 123501
            username = "test_user_mixed_autorenew"
            
            user = register_user_if_not_exists(user_id, username)
            add_to_user_balance(user_id, 1000.0)
            
            # Включаем глобальное автопродление
            set_auto_renewal_enabled(user_id, True)
            
            from shop_bot.data_manager.database import create_host, create_plan
            host_name = "test_host_mixed_autorenew"
            create_host(host_name, "http://test.com", "user", "pass", 1, "code")
            create_plan(host_name, "Test Plan", 1, 0, 0, 100.0)
            
            expiry_date = datetime.now(timezone.utc) - timedelta(days=1)
            expiry_timestamp_ms = int(expiry_date.timestamp() * 1000)
            key_id = add_new_key(
                user_id=user_id,
                host_name=host_name,
                xui_client_uuid="test-uuid-mixed-autorenew",
                key_email=f"test-mixed-autorenew@{host_name}.com",
                expiry_timestamp_ms=expiry_timestamp_ms,
                connection_string="vless://test",
                plan_name="Test Plan",
                price=100.0,
            )
            
            # Глобальное включено, но для ключа отключено
            set_key_auto_renewal_enabled(key_id, False)
            
            old_key = get_key_by_id(key_id)
            old_expiry = datetime.fromisoformat(old_key['expiry_date'])

        with allure.step("Выполнение автопродления"):
            await perform_auto_renewals(mock_bot)

        with allure.step("Проверка результата"):
            updated_key = get_key_by_id(key_id)
            new_expiry = datetime.fromisoformat(updated_key['expiry_date'])
            
            assert new_expiry == old_expiry, "Ключ не должен быть продлен, если его автопродление отключено"

    @pytest.mark.asyncio
    @allure.story("Автопродление при включенном глобальном и индивидуальном")
    @allure.title("Автопродление происходит при включенном глобальном И индивидуальном")
    @allure.description("""
    Интеграционный тест, проверяющий поведение автопродления при включенном глобальном и индивидуальном автопродлении.
    
    **Что проверяется:**
    - Создание пользователя, хоста и тарифа
    - Создание ключа с истекшим сроком действия
    - Включение глобального автопродления для пользователя
    - Проверка, что индивидуальное автопродление включено для ключа по умолчанию
    - Выполнение процесса автопродления через perform_auto_renewals
    - Проверка, что ключ был продлен (expiry_date увеличился)
    
    **Тестовые данные:**
    - user_id: 123502
    - host_name: 'test_host_both_enabled'
    - balance: 1000.0 RUB (достаточно для продления)
    - expiry_date: текущее время - 1 день (истекший ключ)
    - key_auto_renewal_enabled: True (включено для ключа по умолчанию)
    - global_auto_renewal_enabled: True (включено для пользователя)
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Мок бота настроен (mock_bot)
    - Мок 3X-UI API настроен (mock_xui_api)
    - Глобальное автопродление включено для пользователя
    - Индивидуальное автопродление включено для ключа (по умолчанию)
    
    **Шаги теста:**
    1. Создание пользователя, хоста и тарифа
    2. Пополнение баланса до 1000.0 RUB
    3. Включение глобального автопродления
    4. Создание ключа с истекшим сроком
    5. Проверка, что индивидуальное автопродление включено по умолчанию
    6. Выполнение perform_auto_renewals
    7. Проверка, что ключ был продлен
    
    **Ожидаемый результат:**
    - Ключ был продлен (expiry_date увеличился)
    - Автопродление работает при включенных обоих настройках
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("auto_renewal", "integration", "key_auto_renewal", "both_enabled", "critical")
    async def test_auto_renewal_with_both_enabled(self, temp_db, mock_bot, mock_xui_api):
        """Тест: автопродление происходит при включенном глобальном И индивидуальном"""
        with allure.step("Подготовка тестовых данных"):
            from shop_bot.data_manager.database import (
                register_user_if_not_exists,
                add_new_key,
                add_to_user_balance,
                set_auto_renewal_enabled,
                set_key_auto_renewal_enabled,
                get_key_by_id,
            )
            
            user_id = 123502
            username = "test_user_both_enabled"
            
            user = register_user_if_not_exists(user_id, username)
            add_to_user_balance(user_id, 1000.0)
            
            # Включаем оба автопродления
            set_auto_renewal_enabled(user_id, True)
            
            from shop_bot.data_manager.database import create_host, create_plan
            host_name = "test_host_both_enabled"
            create_host(host_name, "http://test.com", "user", "pass", 1, "code")
            create_plan(host_name, "Test Plan", 1, 0, 0, 100.0)
            
            expiry_date = datetime.now(timezone.utc) - timedelta(days=1)
            expiry_timestamp_ms = int(expiry_date.timestamp() * 1000)
            key_id = add_new_key(
                user_id=user_id,
                host_name=host_name,
                xui_client_uuid="test-uuid-both-enabled",
                key_email=f"test-both-enabled@{host_name}.com",
                expiry_timestamp_ms=expiry_timestamp_ms,
                connection_string="vless://test",
                plan_name="Test Plan",
                price=100.0,
            )
            
            # Оба включены (по умолчанию ключ имеет автопродление включенным)
            assert get_key_auto_renewal_enabled(key_id) is True
            
            old_key = get_key_by_id(key_id)
            old_expiry = datetime.fromisoformat(old_key['expiry_date'])

        with allure.step("Выполнение автопродления"):
            await perform_auto_renewals(mock_bot)

        with allure.step("Проверка результата"):
            updated_key = get_key_by_id(key_id)
            new_expiry = datetime.fromisoformat(updated_key['expiry_date'])
            
            assert new_expiry > old_expiry, "Ключ должен быть продлен, если оба автопродления включены"

