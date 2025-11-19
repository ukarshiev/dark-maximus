# -*- coding: utf-8 -*-
"""
E2E тест для функционала индивидуального автопродления ключей

Тестирует полный flow работы с автопродлением ключа:
1. Создание ключа с автопродлением
2. Переключение автопродления через интерфейс бота
3. Проверка автопродления с разными настройками
"""

import pytest
import allure
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch

from shop_bot.data_manager import database
from shop_bot.data_manager.scheduler import perform_auto_renewals


@allure.epic("E2E тесты")
@allure.feature("Автопродление ключей")
@allure.label("package", "tests.e2e")
@pytest.mark.e2e
@pytest.mark.database
class TestKeyAutoRenewalE2E:
    """E2E тесты для функционала индивидуального автопродления ключей"""

    @pytest.mark.asyncio
    @allure.story("Полный цикл работы с автопродлением ключа")
    @allure.title("E2E тест: управление автопродлением ключа через интерфейс бота")
    @allure.description("""
    E2E тест, проверяющий полный цикл работы с индивидуальным автопродлением ключа.
    
    **Что проверяется:**
    - Создание ключа с автопродлением включенным по умолчанию
    - Получение статуса автопродления ключа
    - Переключение автопродления через функции БД
    - Автопродление с включенным автопродлением ключа
    - Автопродление с отключенным автопродлением ключа
    - Взаимодействие глобального и индивидуального автопродления
    
    **Тестовые данные:**
    - user_id: 123600
    - host_name: 'test_host_e2e'
    - plan_name: 'Test Plan E2E'
    
    **Шаги теста:**
    1. Создание пользователя и ключа
    2. Проверка автопродления по умолчанию (включено)
    3. Отключение автопродления ключа
    4. Проверка, что автопродление не происходит
    5. Включение автопродления ключа
    6. Проверка, что автопродление происходит
    
    **Ожидаемый результат:**
    Все шаги выполняются успешно, автопродление работает корректно с учетом индивидуальных настроек ключа.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("e2e", "auto-renewal", "key-management", "critical", "full-flow")
    async def test_key_auto_renewal_full_flow(self, temp_db, mock_bot, mock_xui_api):
        """E2E тест полного цикла работы с автопродлением ключа"""
        with allure.step("Подготовка тестовых данных"):
            from shop_bot.data_manager.database import (
                register_user_if_not_exists,
                add_new_key,
                add_to_user_balance,
                set_auto_renewal_enabled,
                get_key_auto_renewal_enabled,
                set_key_auto_renewal_enabled,
                get_key_by_id,
                initialize_db,
            )
            
            # Инициализируем БД и выполняем миграции
            initialize_db()
            from shop_bot.data_manager.database import run_migration
            run_migration()
            
            user_id = 123600
            username = "test_user_e2e_autorenew"
            
            # Регистрируем пользователя
            user = register_user_if_not_exists(user_id, username, referrer_id=None)
            assert user is not None
            allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
            
            # Устанавливаем баланс
            add_to_user_balance(user_id, 2000.0)
            balance = database.get_user_balance(user_id)
            allure.attach(str(balance), "User Balance", allure.attachment_type.TEXT)
            
            # Включаем глобальное автопродление
            set_auto_renewal_enabled(user_id, True)
            assert database.get_auto_renewal_enabled(user_id) is True
            
            # Создаем хост и тариф
            from shop_bot.data_manager.database import create_host, create_plan
            host_name = "test_host_e2e"
            create_host(host_name, "http://test.com", "user", "pass", 1, "code")
            create_plan(host_name, "Test Plan E2E", 1, 150.0, 0, 0.0, 0)
            
            # Создаем ключ с истекшим сроком
            expiry_date = datetime.now(timezone.utc) - timedelta(days=1)
            expiry_timestamp_ms = int(expiry_date.timestamp() * 1000)
            key_id = add_new_key(
                user_id=user_id,
                host_name=host_name,
                xui_client_uuid="test-uuid-e2e-autorenew",
                key_email=f"test-e2e-autorenew@{host_name}.com",
                expiry_timestamp_ms=expiry_timestamp_ms,
                connection_string="vless://test-e2e",
                plan_name="Test Plan E2E",
                price=150.0,
            )
            assert key_id is not None
            allure.attach(str(key_id), "Key ID", allure.attachment_type.TEXT)

        with allure.step("Проверка автопродления по умолчанию (включено)"):
            # Проверяем, что автопродление включено по умолчанию
            auto_renewal_status = get_key_auto_renewal_enabled(key_id)
            assert auto_renewal_status is True, "Автопродление должно быть включено по умолчанию"
            allure.attach(str(auto_renewal_status), "Auto-renewal status (default)", allure.attachment_type.TEXT)

        with allure.step("Отключение автопродления ключа"):
            # Отключаем автопродление для ключа
            result = set_key_auto_renewal_enabled(key_id, False)
            assert result is True, "set_key_auto_renewal_enabled должна вернуть True"
            
            # Проверяем, что автопродление отключено
            auto_renewal_status = get_key_auto_renewal_enabled(key_id)
            assert auto_renewal_status is False, "Автопродление должно быть отключено"
            allure.attach(str(auto_renewal_status), "Auto-renewal status (disabled)", allure.attachment_type.TEXT)

        with allure.step("Проверка, что автопродление не происходит при отключенном автопродлении ключа"):
            # Получаем старое expiry_date
            old_key = get_key_by_id(key_id)
            old_expiry = datetime.fromisoformat(old_key['expiry_date'])
            allure.attach(str(old_expiry), "Old expiry date", allure.attachment_type.TEXT)
            
            # Выполняем автопродление
            await perform_auto_renewals(mock_bot)
            
            # Проверяем, что ключ НЕ был продлен
            updated_key = get_key_by_id(key_id)
            new_expiry = datetime.fromisoformat(updated_key['expiry_date'])
            allure.attach(str(new_expiry), "New expiry date (should be same)", allure.attachment_type.TEXT)
            
            assert new_expiry == old_expiry, "Ключ с отключенным автопродлением не должен быть продлен"

        with allure.step("Включение автопродления ключа"):
            # Включаем автопродление для ключа
            result = set_key_auto_renewal_enabled(key_id, True)
            assert result is True, "set_key_auto_renewal_enabled должна вернуть True"
            
            # Проверяем, что автопродление включено
            auto_renewal_status = get_key_auto_renewal_enabled(key_id)
            assert auto_renewal_status is True, "Автопродление должно быть включено"
            allure.attach(str(auto_renewal_status), "Auto-renewal status (enabled)", allure.attachment_type.TEXT)

        with allure.step("Проверка, что автопродление происходит при включенном автопродлении ключа"):
            # Обновляем expiry_date для повторной проверки через SQL
            import sqlite3
            expiry_date = datetime.now(timezone.utc) - timedelta(days=1)
            expiry_date_str = expiry_date.strftime('%Y-%m-%d %H:%M:%S')
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            cursor.execute("UPDATE vpn_keys SET expiry_date = ? WHERE key_id = ?", (expiry_date_str, key_id))
            conn.commit()
            conn.close()
            
            # Получаем старое expiry_date
            old_key = get_key_by_id(key_id)
            old_expiry = datetime.fromisoformat(old_key['expiry_date'])
            allure.attach(str(old_expiry), "Old expiry date (before renewal)", allure.attachment_type.TEXT)
            
            # Мокируем xui_api для продления
            from unittest.mock import patch, AsyncMock
            new_expiry_date = datetime.now(timezone.utc) + timedelta(days=30)
            new_expiry_ms = int(new_expiry_date.timestamp() * 1000)
            mock_xui_api.create_or_update_key_on_host = AsyncMock(return_value={
                'client_uuid': 'test-uuid-e2e-autorenew',
                'email': f'test-e2e-autorenew@{host_name}.com',
                'expiry_timestamp_ms': new_expiry_ms,
                'connection_string': 'vless://test-e2e-updated',
            })
            
            # Мокируем зависимости
            with patch('shop_bot.modules.xui_api', mock_xui_api):
                with patch('shop_bot.data_manager.scheduler.xui_api', mock_xui_api):
                    with patch('shop_bot.data_manager.database.get_plan_by_id', return_value={
                        'plan_id': 1,
                        'plan_name': 'Test Plan E2E',
                        'months': 1,
                        'days': 0,
                        'hours': 0,
                        'price': 150.0,
                        'traffic_gb': 0,
                    }):
                        with patch('shop_bot.data_manager.database.get_all_keys') as mock_get_keys:
                            mock_get_keys.return_value = [{
                                'key_id': key_id,
                                'user_id': user_id,
                                'host_name': host_name,
                                'plan_name': 'Test Plan E2E',
                                'expiry_date': expiry_date_str,
                                'price': 150.0,
                            }]
                            # Мокируем process_successful_payment, чтобы он использовал мок xui_api
                            async def mock_process_successful_payment(bot, metadata, tx_hash=None):
                                from shop_bot.data_manager.database import (
                                    get_key_by_id, update_key_info, get_user
                                )
                                key_id_from_meta = metadata.get('key_id')
                                if key_id_from_meta:
                                    key_data = get_key_by_id(key_id_from_meta)
                                    if key_data:
                                        # Симулируем продление через мок xui_api
                                        result = await mock_xui_api.create_or_update_key_on_host(
                                            host_name=metadata.get('host_name'),
                                            key_email=key_data.get('key_email'),
                                            months=metadata.get('months', 1),
                                            days=metadata.get('days', 0),
                                            hours=metadata.get('hours', 0),
                                        )
                                        if result:
                                            update_key_info(
                                                key_id_from_meta,
                                                result.get('client_uuid'),
                                                result.get('expiry_timestamp_ms'),
                                                result.get('subscription_link')
                                            )
                            
                            with patch('shop_bot.bot.handlers.process_successful_payment', mock_process_successful_payment):
                                # Выполняем автопродление
                                await perform_auto_renewals(mock_bot)
            
            # Проверяем, что ключ был продлен
            updated_key = get_key_by_id(key_id)
            new_expiry = datetime.fromisoformat(updated_key['expiry_date'])
            allure.attach(str(new_expiry), "New expiry date (should be extended)", allure.attachment_type.TEXT)
            
            assert new_expiry > old_expiry, "Ключ с включенным автопродлением должен быть продлен"

        with allure.step("Проверка взаимодействия глобального и индивидуального автопродления"):
            # Отключаем глобальное автопродление
            set_auto_renewal_enabled(user_id, False)
            assert database.get_auto_renewal_enabled(user_id) is False
            
            # Обновляем expiry_date для проверки через SQL
            import sqlite3
            expiry_date = datetime.now(timezone.utc) - timedelta(days=1)
            expiry_date_str = expiry_date.strftime('%Y-%m-%d %H:%M:%S')
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            cursor.execute("UPDATE vpn_keys SET expiry_date = ? WHERE key_id = ?", (expiry_date_str, key_id))
            conn.commit()
            conn.close()
            
            old_key = get_key_by_id(key_id)
            old_expiry = datetime.fromisoformat(old_key['expiry_date'])
            
            # Выполняем автопродление
            await perform_auto_renewals(mock_bot)
            
            # Проверяем, что ключ НЕ был продлен (глобальное отключено)
            updated_key = get_key_by_id(key_id)
            new_expiry = datetime.fromisoformat(updated_key['expiry_date'])
            
            assert new_expiry == old_expiry, "Ключ не должен быть продлен, если глобальное автопродление отключено"

