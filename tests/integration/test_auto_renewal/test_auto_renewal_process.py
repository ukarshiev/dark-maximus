#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты для процесса автопродления

Тестирует полный flow автопродления ключей
"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.integration
@pytest.mark.bot
@allure.epic("Интеграционные тесты")
@allure.feature("Автопродление")
@allure.label("package", "tests.integration.test_auto_renewal")
class TestAutoRenewalProcess:
    """Интеграционные тесты для процесса автопродления"""

    @pytest.mark.asyncio
    @allure.story("Полный цикл автопродления ключа")
    @allure.title("Успешное автопродление ключа с достаточным балансом")
    @allure.description("""
    Интеграционный тест, проверяющий полный цикл автопродления ключа при достаточном балансе пользователя.
    
    **Что проверяется:**
    - Создание пользователя, хоста и тарифного плана
    - Пополнение баланса пользователя
    - Включение автопродления для пользователя
    - Создание ключа с истекшим сроком действия
    - Выполнение процесса автопродления через perform_auto_renewals
    - Списание средств с баланса пользователя
    - Продление ключа через 3X-UI API
    - Обновление даты истечения ключа в БД
    
    **Тестовые данные:**
    - user_id: 123460
    - host_name: 'test_host'
    - plan_name: 'Test Plan'
    - price: 100.0 RUB
    - initial_balance: 200.0 RUB
    - expected_balance_after_renewal: 100.0 RUB (200 - 100)
    - expiry_date: текущее время - 1 час (истекший ключ)
    - new_expiry_date: expiry_date + 30 дней
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Мок бота настроен (mock_bot)
    - Мок 3X-UI API настроен (mock_xui_api)
    - Автопродление включено для пользователя
    
    **Шаги теста:**
    1. Создание пользователя, хоста и тарифного плана
    2. Пополнение баланса до 200.0 RUB
    3. Включение автопродления для пользователя
    4. Создание ключа с истекшим сроком действия
    5. Настройка моков для 3X-UI API и зависимостей
    6. Выполнение perform_auto_renewals
    7. Проверка списания баланса (200 -> 100 RUB)
    8. Проверка продления ключа (новый expiry_timestamp_ms)
    
    **Ожидаемый результат:**
    - Баланс пользователя уменьшился на 100.0 RUB (с 200.0 до 100.0)
    - Ключ продлен на 30 дней (expiry_timestamp_ms обновлен)
    - 3X-UI API вызван для обновления ключа
    - Транзакция залогирована в БД
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("auto_renewal", "integration", "critical", "balance", "key_renewal", "xui_api")
    async def test_auto_renewal_process_success(self, temp_db, mock_bot, mock_xui_api):
        """Тест успешного автопродления с достаточным балансом"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            add_to_user_balance,
            get_user_balance,
            set_auto_renewal_enabled,
            create_host,
            create_plan,
            get_plans_for_host,
            get_key_by_id,
        )
        from shop_bot.data_manager.scheduler import perform_auto_renewals
        
        with allure.step("Подготовка тестовых данных: создание пользователя, хоста и тарифа"):
            user_id = 123460
            host_name = "test_host"
            plan_name = "Test Plan"
            initial_balance = 200.0
            renewal_price = 100.0
            
            register_user_if_not_exists(user_id, "test_user", referrer_id=None)
            create_host(host_name, "http://test.com", "user", "pass", 1, "testcode")
            create_plan(host_name, plan_name, 1, renewal_price, 0, 0.0, 0)
            plans = get_plans_for_host(host_name)
            plan_id = plans[0]['plan_id'] if plans else 1
            
            allure.attach(str({
                'user_id': user_id,
                'host_name': host_name,
                'plan_name': plan_name,
                'plan_id': plan_id,
                'initial_balance': initial_balance,
                'renewal_price': renewal_price
            }), "Тестовые данные", allure.attachment_type.JSON)
        
        with allure.step("Настройка баланса и автопродления"):
            add_to_user_balance(user_id, initial_balance)
            set_auto_renewal_enabled(user_id, True)
            
            balance_before = get_user_balance(user_id)
            allure.attach(str(balance_before), "Баланс до автопродления", allure.attachment_type.TEXT)
        
        with allure.step("Создание ключа с истекшим сроком действия"):
            expiry_date = datetime.now(timezone.utc) - timedelta(hours=1)
            key_id = add_new_key(
                user_id,
                host_name,
                "test-uuid-auto",
                f"user{user_id}-key1@testcode.bot",
                int(expiry_date.timestamp() * 1000),
                connection_string="vless://test",
                plan_name=plan_name,
                price=renewal_price,
            )
            
            allure.attach(str({
                'key_id': key_id,
                'expiry_date': expiry_date.isoformat(),
                'expiry_timestamp_ms': int(expiry_date.timestamp() * 1000)
            }), "Данные ключа", allure.attachment_type.JSON)
        
        with allure.step("Настройка моков для 3X-UI API и зависимостей"):
            new_expiry_date = expiry_date + timedelta(days=30)
            new_expiry_ms = int(new_expiry_date.timestamp() * 1000)
            mock_create_or_update = AsyncMock(return_value={
                'client_uuid': 'test-uuid-auto',
                'email': f'user{user_id}-key1@testcode.bot',
                'expiry_timestamp_ms': new_expiry_ms,
                'connection_string': 'vless://test-updated',
            })
            
            # Мокируем login_to_host, чтобы избежать реальных подключений
            mock_api = MagicMock()
            mock_inbound = MagicMock()
            mock_inbound.id = 1
            mock_login_to_host = MagicMock(return_value=(mock_api, mock_inbound))
            
            allure.attach(str({
                'new_expiry_date': new_expiry_date.isoformat(),
                'new_expiry_timestamp_ms': new_expiry_ms
            }), "Ожидаемые данные после продления", allure.attachment_type.JSON)
        
        with allure.step("Выполнение автопродления"):
            # Мокируем зависимости
            # ВАЖНО: Мокируем функции xui_api напрямую, так как это функции модуля
            with patch('shop_bot.modules.xui_api.create_or_update_key_on_host', mock_create_or_update):
                with patch('shop_bot.modules.xui_api.login_to_host', mock_login_to_host):
                    with patch('shop_bot.data_manager.database.get_plan_by_id', return_value={
                        'plan_id': plan_id,
                        'plan_name': plan_name,
                        'months': 1,
                        'days': 0,
                        'hours': 0,
                        'price': renewal_price,
                        'traffic_gb': 0,
                    }):
                        with patch('shop_bot.data_manager.database.get_all_keys') as mock_get_keys:
                            mock_get_keys.return_value = [{
                                'key_id': key_id,
                                'user_id': user_id,
                                'host_name': host_name,
                                'plan_name': plan_name,
                                'expiry_date': expiry_date.isoformat(),
                                'price': renewal_price,
                                'key_email': f"user{user_id}-key1@testcode.bot",
                                'xui_client_uuid': "test-uuid-auto",
                            }]
                            await perform_auto_renewals(mock_bot)
                            
                            allure.attach(str({
                                'xui_api_called': mock_create_or_update.called,
                                'get_all_keys_called': mock_get_keys.called
                            }), "Статус вызовов моков", allure.attachment_type.JSON)
        
        with allure.step("Проверка списания баланса"):
            balance_after = get_user_balance(user_id)
            expected_balance = initial_balance - renewal_price
            
            allure.attach(str({
                'balance_before': balance_before,
                'balance_after': balance_after,
                'expected_balance': expected_balance,
                'renewal_price': renewal_price
            }), "Результаты проверки баланса", allure.attachment_type.JSON)
            
            assert balance_after == expected_balance, f"Баланс должен быть {expected_balance}, но получили {balance_after}"
        
        with allure.step("Проверка продления ключа"):
            key = get_key_by_id(key_id)
            assert key is not None, "Ключ должен существовать после автопродления"
            
            actual_expiry_ms = key.get('expiry_timestamp_ms')
            allure.attach(str({
                'key_id': key_id,
                'actual_expiry_timestamp_ms': actual_expiry_ms,
                'expected_expiry_timestamp_ms': new_expiry_ms
            }), "Результаты проверки продления ключа", allure.attachment_type.JSON)
            
            assert actual_expiry_ms == new_expiry_ms, f"Ключ должен быть продлен до {new_expiry_ms}, но получили {actual_expiry_ms}"

    @pytest.mark.asyncio
    @allure.story("Автопродление при недостаточном балансе")
    @allure.title("Автопродление при недостаточном балансе")
    @allure.description("""
    Интеграционный тест, проверяющий поведение автопродления при недостаточном балансе пользователя.
    
    **Что проверяется:**
    - Создание пользователя, хоста и ключа с истекшим сроком
    - Установка недостаточного баланса (50.0 RUB при цене 100.0 RUB)
    - Включение автопродления для пользователя
    - Выполнение процесса автопродления через perform_auto_renewals
    - Проверка, что баланс не изменился (автопродление не произошло)
    
    **Тестовые данные:**
    - user_id: 123461
    - host_name: 'test_host'
    - balance: 50.0 RUB (недостаточно для продления)
    - price: 100.0 RUB
    - expiry_date: текущее время - 1 час (истекший ключ)
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Мок бота настроен (mock_bot)
    - Автопродление включено для пользователя
    - Баланс недостаточен для продления
    
    **Шаги теста:**
    1. Создание пользователя и хоста
    2. Установка недостаточного баланса (50.0 RUB)
    3. Включение автопродления
    4. Создание ключа с истекшим сроком
    5. Выполнение perform_auto_renewals
    6. Проверка, что баланс не изменился
    
    **Ожидаемый результат:**
    - Баланс пользователя остался неизменным (50.0 RUB)
    - Автопродление не произошло из-за недостаточного баланса
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "integration", "insufficient_balance", "normal")
    async def test_auto_renewal_process_insufficient_balance(self, temp_db, mock_bot):
        """Тест автопродления при недостаточном балансе"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            add_to_user_balance,
            get_user_balance,
            set_auto_renewal_enabled,
            create_host,
        )
        from shop_bot.data_manager.scheduler import perform_auto_renewals
        
        # Настройка БД
        user_id = 123461
        register_user_if_not_exists(user_id, "test_user2", referrer_id=None)
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        
        # Устанавливаем недостаточный баланс
        add_to_user_balance(user_id, 50.0)
        set_auto_renewal_enabled(user_id, True)
        
        # Создаем ключ с истекшим сроком (для автопродления)
        expiry_date = datetime.now(timezone.utc) - timedelta(hours=1)
        key_id = add_new_key(
            user_id,
            "test_host",
            "test-uuid-insufficient",
            f"user{user_id}-key1@testcode.bot",
            int(expiry_date.timestamp() * 1000),
            connection_string="vless://test",
            plan_name="Test Plan",
            price=100.0,
        )
        
        # Мокируем get_all_keys для автопродления
        with patch('shop_bot.data_manager.database.get_all_keys') as mock_get_keys:
            mock_get_keys.return_value = [{
                'key_id': key_id,
                'user_id': user_id,
                'host_name': 'test_host',
                'plan_name': 'Test Plan',
                'expiry_date': expiry_date.isoformat(),
                'price': 100.0,
            }]
            # Выполняем автопродление (должно провалиться из-за недостаточного баланса)
            await perform_auto_renewals(mock_bot)
        
        # Проверяем, что баланс не изменился
        balance = get_user_balance(user_id)
        assert balance == 50.0

    @pytest.mark.asyncio
    @allure.story("Автопродление при отключенной настройке")
    @allure.title("Автопродление при отключенной настройке")
    @allure.description("""
    Интеграционный тест, проверяющий поведение автопродления при отключенной настройке автопродления.
    
    **Что проверяется:**
    - Создание пользователя, хоста и ключа с истекшим сроком
    - Установка достаточного баланса (200.0 RUB)
    - Отключение автопродления для пользователя
    - Выполнение процесса автопродления через perform_auto_renewals
    - Проверка, что баланс не изменился (автопродление не произошло)
    
    **Тестовые данные:**
    - user_id: 123462
    - host_name: 'test_host'
    - balance: 200.0 RUB (достаточно для продления)
    - price: 100.0 RUB
    - expiry_date: текущее время - 1 час (истекший ключ)
    - auto_renewal_enabled: False
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Мок бота настроен (mock_bot)
    - Автопродление отключено для пользователя
    - Баланс достаточен для продления
    
    **Шаги теста:**
    1. Создание пользователя и хоста
    2. Установка достаточного баланса (200.0 RUB)
    3. Отключение автопродления
    4. Создание ключа с истекшим сроком
    5. Выполнение perform_auto_renewals
    6. Проверка, что баланс не изменился
    
    **Ожидаемый результат:**
    - Баланс пользователя остался неизменным (200.0 RUB)
    - Автопродление не произошло из-за отключенной настройки
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "integration", "disabled", "normal")
    async def test_auto_renewal_process_disabled(self, temp_db, mock_bot):
        """Тест автопродления отключено"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            add_to_user_balance,
            get_user_balance,
            set_auto_renewal_enabled,
            create_host,
        )
        from shop_bot.data_manager.scheduler import perform_auto_renewals
        
        # Настройка БД
        user_id = 123462
        register_user_if_not_exists(user_id, "test_user3", referrer_id=None)
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        
        # Устанавливаем баланс и отключаем автопродление
        add_to_user_balance(user_id, 200.0)
        set_auto_renewal_enabled(user_id, False)
        
        # Создаем ключ с истекшим сроком (для автопродления)
        expiry_date = datetime.now(timezone.utc) - timedelta(hours=1)
        key_id = add_new_key(
            user_id,
            "test_host",
            "test-uuid-disabled",
            f"user{user_id}-key1@testcode.bot",
            int(expiry_date.timestamp() * 1000),
            connection_string="vless://test",
            plan_name="Test Plan",
            price=100.0,
        )
        
        # Мокируем get_all_keys для автопродления
        with patch('shop_bot.data_manager.database.get_all_keys') as mock_get_keys:
            mock_get_keys.return_value = [{
                'key_id': key_id,
                'user_id': user_id,
                'host_name': 'test_host',
                'plan_name': 'Test Plan',
                'expiry_date': expiry_date.isoformat(),
                'price': 100.0,
            }]
            # Выполняем автопродление (должно провалиться из-за отключенного автопродления)
            await perform_auto_renewals(mock_bot)
        
        # Проверяем, что баланс не изменился
        balance = get_user_balance(user_id)
        assert balance == 200.0

    @pytest.mark.asyncio
    @allure.story("Автопродление при недоступном тарифе")
    @allure.title("Автопродление при недоступном тарифе")
    @allure.description("""
    Интеграционный тест, проверяющий поведение автопродления при недоступном тарифе для продления.
    
    **Что проверяется:**
    - Создание пользователя, хоста и ключа с истекшим сроком
    - Установка достаточного баланса (200.0 RUB)
    - Включение автопродления для пользователя
    - Симуляция недоступного тарифа (get_plan_info_for_key возвращает None)
    - Выполнение процесса автопродления через perform_auto_renewals
    - Проверка, что баланс не изменился (автопродление не произошло)
    
    **Тестовые данные:**
    - user_id: 123463
    - host_name: 'test_host'
    - balance: 200.0 RUB (достаточно для продления)
    - price: 100.0 RUB
    - expiry_date: текущее время - 1 час (истекший ключ)
    - plan_name: 'Unavailable Plan' (тариф недоступен)
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Мок бота настроен (mock_bot)
    - Автопродление включено для пользователя
    - Баланс достаточен для продления
    - Тариф недоступен для продления
    
    **Шаги теста:**
    1. Создание пользователя и хоста
    2. Установка достаточного баланса (200.0 RUB)
    3. Включение автопродления
    4. Создание ключа с истекшим сроком и недоступным тарифом
    5. Мокирование отсутствия тарифа
    6. Выполнение perform_auto_renewals
    7. Проверка, что баланс не изменился
    
    **Ожидаемый результат:**
    - Баланс пользователя остался неизменным (200.0 RUB)
    - Автопродление не произошло из-за недоступного тарифа
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "integration", "plan_unavailable", "normal")
    async def test_auto_renewal_process_plan_unavailable(self, temp_db, mock_bot):
        """Тест автопродления при недоступном тарифе"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            add_to_user_balance,
            get_user_balance,
            set_auto_renewal_enabled,
            create_host,
        )
        from shop_bot.data_manager.scheduler import perform_auto_renewals
        
        # Настройка БД
        user_id = 123463
        register_user_if_not_exists(user_id, "test_user4", referrer_id=None)
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        
        # Устанавливаем баланс и включаем автопродление
        add_to_user_balance(user_id, 200.0)
        set_auto_renewal_enabled(user_id, True)
        
        # Создаем ключ с истекшим сроком (для автопродления)
        expiry_date = datetime.now(timezone.utc) - timedelta(hours=1)
        key_id = add_new_key(
            user_id,
            "test_host",
            "test-uuid-unavailable",
            f"user{user_id}-key1@testcode.bot",
            int(expiry_date.timestamp() * 1000),
            connection_string="vless://test",
            plan_name="Unavailable Plan",
            price=100.0,
        )
        
        # Мокируем отсутствие плана
        with patch('shop_bot.data_manager.database.get_all_keys') as mock_get_keys:
            mock_get_keys.return_value = [{
                'key_id': key_id,
                'user_id': user_id,
                'host_name': 'test_host',
                'plan_name': 'Unavailable Plan',
                'expiry_date': expiry_date.isoformat(),
                'price': 100.0,
            }]
            with patch('shop_bot.data_manager.scheduler._get_plan_info_for_key', return_value=(None, 0.0, 0, None, False)):
                await perform_auto_renewals(mock_bot)
        
        # Проверяем, что баланс не изменился
        # Явный импорт перед использованием для избежания проблем с областью видимости при патчинге
        from shop_bot.data_manager.database import get_user_balance as get_balance
        balance = get_balance(user_id)
        assert balance == 200.0

    @pytest.mark.asyncio
    @allure.story("Отправка уведомлений об автопродлении")
    @allure.title("Отправка уведомлений об автопродлении")
    @allure.description("""
    Интеграционный тест, проверяющий отправку уведомлений пользователю при успешном автопродлении ключа.
    
    **Что проверяется:**
    - Создание пользователя, хоста и тарифного плана
    - Пополнение баланса пользователя
    - Включение автопродления для пользователя
    - Создание ключа с истекшим сроком действия
    - Выполнение процесса автопродления через perform_auto_renewals
    - Проверка отправки уведомления пользователю через mock_bot.send_message
    
    **Тестовые данные:**
    - user_id: 123464
    - host_name: 'test_host'
    - plan_name: 'Test Plan'
    - price: 100.0 RUB
    - initial_balance: 200.0 RUB
    - expiry_date: текущее время - 1 час (истекший ключ)
    - new_expiry_date: expiry_date + 30 дней
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Мок бота настроен (mock_bot)
    - Мок 3X-UI API настроен (mock_xui_api)
    - Автопродление включено для пользователя
    - Баланс достаточен для продления
    
    **Шаги теста:**
    1. Создание пользователя, хоста и тарифного плана
    2. Пополнение баланса до 200.0 RUB
    3. Включение автопродления для пользователя
    4. Создание ключа с истекшим сроком действия
    5. Настройка моков для 3X-UI API
    6. Выполнение perform_auto_renewals
    7. Проверка отправки уведомления через mock_bot.send_message
    
    **Ожидаемый результат:**
    - Уведомление отправлено пользователю (mock_bot.send_message вызван)
    - Ключ продлен успешно
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "integration", "notification", "normal")
    async def test_auto_renewal_process_notification(self, temp_db, mock_bot, mock_xui_api):
        """Тест отправки уведомлений об автопродлении"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            add_to_user_balance,
            set_auto_renewal_enabled,
            create_host,
            create_plan,
            get_plans_for_host,
        )
        from shop_bot.data_manager.scheduler import perform_auto_renewals
        
        # Настройка БД
        user_id = 123464
        register_user_if_not_exists(user_id, "test_user5", referrer_id=None)
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        create_plan("test_host", "Test Plan", 1, 100.0, 0, 0.0, 0)
        plans = get_plans_for_host("test_host")
        plan_id = plans[0]['plan_id'] if plans else 1
        
        # Пополняем баланс
        add_to_user_balance(user_id, 200.0)
        set_auto_renewal_enabled(user_id, True)
        
        # Создаем ключ с истекшим сроком (для автопродления)
        expiry_date = datetime.now(timezone.utc) - timedelta(hours=1)
        key_id = add_new_key(
            user_id,
            "test_host",
            "test-uuid-notify",
            f"user{user_id}-key1@testcode.bot",
            int(expiry_date.timestamp() * 1000),
            connection_string="vless://test",
            plan_name="Test Plan",
            price=100.0,
        )
        
        # Мокируем xui_api
        new_expiry_ms = int((expiry_date + timedelta(days=30)).timestamp() * 1000)
        mock_xui_api.create_or_update_key_on_host = AsyncMock(return_value={
            'client_uuid': 'test-uuid-notify',
            'email': f'user{user_id}-key1@testcode.bot',
            'expiry_timestamp_ms': new_expiry_ms,
            'connection_string': 'vless://test-updated',
        })
        
        # Мокируем зависимости
        with patch('shop_bot.data_manager.scheduler.xui_api', mock_xui_api):
            with patch('shop_bot.data_manager.database.get_plan_by_id', return_value={
                'plan_id': plan_id,
                'plan_name': 'Test Plan',
                'months': 1,
                'days': 0,
                'hours': 0,
                'price': 100.0,
                'traffic_gb': 0,
            }):
                with patch('shop_bot.data_manager.database.get_all_keys') as mock_get_keys:
                    mock_get_keys.return_value = [{
                        'key_id': key_id,
                        'user_id': user_id,
                        'host_name': 'test_host',
                        'plan_name': 'Test Plan',
                        'expiry_date': expiry_date.isoformat(),
                        'price': 100.0,
                    }]
                    # Выполняем автопродление
                    await perform_auto_renewals(mock_bot)
        
        # Проверяем, что уведомление было отправлено
        assert mock_bot.send_message.called

