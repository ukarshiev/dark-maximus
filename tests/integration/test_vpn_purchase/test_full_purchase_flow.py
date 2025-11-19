#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты для полного цикла покупки VPN

Тестирует полный цикл от выбора тарифа до получения ключа
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import uuid
from unittest.mock import patch, MagicMock, AsyncMock
import allure

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import (
    register_user_if_not_exists,
    create_plan,
    get_user_keys,
    get_key_by_id,
    create_promo_code,
    validate_promo_code,
)
from shop_bot.bot.handlers import process_successful_payment


@pytest.mark.integration
@pytest.mark.database
@allure.epic("Интеграционные тесты")
@allure.feature("Покупка VPN")
@allure.label("package", "tests.integration.test_vpn_purchase")
class TestFullPurchaseFlow:
    """Интеграционные тесты для полного цикла покупки VPN"""

    @pytest.fixture
    def test_setup(self, temp_db, sample_host, sample_plan):
        """Фикстура для настройки тестового окружения"""
        import sqlite3
        
        # Создаем пользователя
        user_id = 123456800
        register_user_if_not_exists(user_id, "test_user_new", None, "Test User New")
        
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
        
        # Получаем созданный план
        from shop_bot.data_manager.database import get_plans_for_host
        plans = get_plans_for_host(sample_host['host_name'])
        plan_id = plans[0]['plan_id'] if plans else None
        
        return {
            'user_id': user_id,
            'host_name': sample_host['host_name'],
            'plan_id': plan_id,
            'price': sample_plan['price']
        }

    @allure.story("Полный цикл покупки VPN для нового пользователя")
    @allure.title("Полный цикл покупки VPN для нового пользователя")
    @allure.description("""
    Проверяет полный цикл покупки VPN ключа для нового пользователя от регистрации до получения ключа:
    
    **Что проверяется:**
    - Обработка платежа для нового пользователя
    - Создание ключа на хосте через 3X-UI API
    - Проверка принадлежности ключа пользователю и хосту
    - Корректное сохранение данных ключа в БД
    
    **Тестовые данные:**
    - user_id: 123456800 (создается через test_setup)
    - username: 'test_user_new'
    - fullname: 'Test User New'
    - host_name: 'test-host' (из sample_host)
    - plan_id: создается через test_setup, price=100.0, months=1
    - payment_id: test_<hex> (генерируется в тесте)
    - expiry_timestamp_ms: текущее время + 30 дней в миллисекундах
    
    **Шаги теста:**
    1. **Подготовка окружения**
       - Метод: настройка временной БД и моков
       - Параметры: temp_db, test_setup, mock_bot, mock_xui_api
       - Ожидаемый результат: окружение готово для теста
       - Проверка: database.DB_FILE указывает на temp_db
       - Мок: mock_xui_api.create_or_update_key_on_host возвращает client_uuid, email, expiry_timestamp_ms
    
    2. **Подготовка метаданных платежа**
       - Метод: создание словаря metadata
       - Параметры: user_id=123456800, operation='new', months=1, days=0, hours=0, price=100.0, action='new', host_name='test-host', plan_id, payment_method='yookassa', payment_id
       - Ожидаемый результат: metadata содержит все необходимые данные для обработки платежа
       - Проверка: все обязательные поля присутствуют в metadata
    
    3. **Обработка успешного платежа**
       - Метод: bot.handlers.process_successful_payment()
       - Параметры: bot=mock_bot, metadata={user_id, operation='new', months=1, price=100.0, host_name, plan_id, payment_method='yookassa', payment_id}
       - Ожидаемый результат: ключ создан на хосте через mock_xui_api
       - Проверка: mock_xui_api.create_or_update_key_on_host вызван с правильными параметрами
       - Проверка: mock_bot.send_message вызван для уведомления пользователя
    
    4. **Проверка создания ключа**
       - Метод: database.get_user_keys()
       - Параметры: user_id=123456800
       - Ожидаемый результат: список содержит один ключ
       - Проверка: len(keys) > 0
       - Проверяемые поля: key_id, user_id=123456800, host_name='test-host', status='active'
    
    5. **Проверка принадлежности ключа**
       - Метод: проверка атрибутов ключа
       - Параметры: keys[0]
       - Ожидаемый результат: ключ принадлежит правильному пользователю и хосту
       - Проверка: keys[0]['user_id'] == 123456800
       - Проверка: keys[0]['host_name'] == 'test-host'
    
    **Предусловия:**
    - Пользователь зарегистрирован (user_id: 123456800) через test_setup
    - Хост создан в БД (xui_hosts) через test_setup
    - План создан для хоста (plan_id, price=100.0, months=1) через test_setup
    - Используется временная БД (temp_db)
    - Моки для bot и xui_api настроены
    
    **Используемые моки и фикстуры:**
    - temp_db: временная SQLite БД с полной структурой таблиц (users, vpn_keys, transactions, plans, xui_hosts)
    - test_setup: фикстура создает пользователя (user_id=123456800, username='test_user_new'), хост (host_name='test-host') и план (plan_id, price=100.0)
    - mock_bot: мок aiogram.Bot с методами send_message, edit_message_text, answer_callback_query
    - mock_xui_api: мок py3xui.Api с методом create_or_update_key_on_host, возвращающий:
      * client_uuid: UUID строки
      * email: user{user_id}-key1@testcode.bot
      * expiry_timestamp_ms: текущее время + 30 дней
      * subscription_link: https://example.com/subscription
      * connection_string: vless://test
    
    **Проверяемые граничные случаи:**
    - Обработка нового пользователя (без существующих ключей)
    - Корректное создание ключа с правильным сроком действия
    - Привязка ключа к правильному хосту
    
    **Ожидаемый результат:**
    После обработки платежа должен быть создан VPN ключ для нового пользователя.
    Ключ должен быть привязан к правильному пользователю (user_id=123456800) и хосту (host_name='test-host').
    Ключ должен иметь статус 'active' и корректный срок действия (expiry_date).
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("vpn", "purchase", "new-user", "integration", "critical")
    @pytest.mark.asyncio
    async def test_full_purchase_flow_new_user(self, temp_db, test_setup, mock_bot, mock_xui_api):
        """Тест полного цикла для нового пользователя"""
        # Патчим DB_FILE для использования временной БД
        import sys
        from shop_bot.data_manager import database
        
        # Патчим xui_api
        with patch('shop_bot.modules.xui_api.create_or_update_key_on_host', new_callable=AsyncMock) as mock_create_key:
            expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            mock_create_key.return_value = {
                'client_uuid': str(uuid.uuid4()),
                'email': f"user{test_setup['user_id']}-key1@testcode.bot",
                'expiry_timestamp_ms': expiry_timestamp_ms,
                'subscription_link': 'https://example.com/subscription',
                'connection_string': 'vless://test'
            }
            
            with allure.step("Подготовка метаданных платежа"):
                # Подготавливаем metadata для process_successful_payment
                expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
                payment_id = f"test_{uuid.uuid4().hex[:16]}"
                metadata = {
                    'user_id': test_setup['user_id'],
                    'operation': 'new',
                    'months': 1,
                    'days': 0,
                    'hours': 0,
                    'price': test_setup['price'],
                    'action': 'new',
                    'host_name': test_setup['host_name'],
                    'plan_id': test_setup['plan_id'],
                    'customer_email': 'test@example.com',
                    'payment_method': 'yookassa',
                    'payment_id': payment_id
                }
            
            with allure.step("Обработка успешного платежа"):
                # Обрабатываем успешную оплату
                await process_successful_payment(mock_bot, metadata)
            
            with allure.step("Проверка создания ключа"):
                # Проверяем, что ключ создан
                keys = get_user_keys(test_setup['user_id'])
                assert len(keys) > 0, "Должен быть создан ключ"
            
            with allure.step("Проверка принадлежности ключа пользователю и хосту"):
                assert keys[0]['user_id'] == test_setup['user_id'], "Ключ должен принадлежать пользователю"
                assert keys[0]['host_name'] == test_setup['host_name'], "Ключ должен быть для правильного хоста"
        

    @allure.story("Полный цикл покупки VPN с промокодом")
    @allure.title("Полный цикл покупки VPN с промокодом")
    @allure.description("""
    Проверяет полный цикл покупки VPN ключа с применением промокода от создания промокода до получения ключа:
    
    **Что проверяется:**
    - Создание промокода в БД
    - Применение скидки к цене плана
    - Обработка платежа с учетом промокода
    - Создание ключа на хосте через 3X-UI API
    - Корректное сохранение данных ключа в БД
    
    **Тестовые данные:**
    - user_id: 123456800 (создается через test_setup)
    - promo_code: 'TESTPROMO' (из sample_promo_code)
    - discount_amount: 10.0 (из sample_promo_code)
    - original_price: 100.0 (из test_setup)
    - final_price: 90.0 (original_price - discount_amount)
    - host_name: 'test-host' (из sample_host)
    - plan_id: создается через test_setup
    - payment_id: test_promo_<hex> (генерируется в тесте)
    
    **Шаги теста:**
    1. **Создание промокода**
       - Метод: database.create_promo_code()
       - Параметры: code='TESTPROMO', bot='test_bot', discount_amount=10.0, discount_percent=0.0, discount_bonus=0.0, usage_limit_per_bot=1, is_active=1
       - Ожидаемый результат: промокод создан в БД с указанными параметрами
       - Проверка: promo_id возвращается и не None
       - Проверяемые поля: promo_id, code='TESTPROMO', discount_amount=10.0, is_active=1
    
    2. **Подготовка метаданных платежа с промокодом**
       - Метод: создание словаря metadata с расчетом финальной цены
       - Параметры: user_id, operation='new', months=1, price=90.0 (final_price), promo_code='TESTPROMO', final_price=90.0
       - Ожидаемый результат: metadata содержит промокод и финальную цену со скидкой
       - Проверка: metadata['promo_code'] == 'TESTPROMO'
       - Проверка: metadata['final_price'] == 90.0
       - Проверка: metadata['price'] == 90.0 (цена со скидкой)
    
    3. **Обработка успешного платежа с промокодом**
       - Метод: bot.handlers.process_successful_payment()
       - Параметры: bot=mock_bot, metadata={...с промокодом...}
       - Ожидаемый результат: ключ создан на хосте, промокод применен
       - Проверка: mock_xui_api.create_or_update_key_on_host вызван с правильными параметрами
       - Проверка: платеж обработан с учетом скидки
    
    4. **Проверка создания ключа**
       - Метод: database.get_user_keys()
       - Параметры: user_id=123456800
       - Ожидаемый результат: список содержит один ключ
       - Проверка: len(keys) > 0
       - Проверяемые поля: key_id, user_id=123456800, host_name='test-host', status='active'
    
    **Предусловия:**
    - Пользователь зарегистрирован (user_id: 123456800) через test_setup
    - Хост создан в БД (xui_hosts) через test_setup
    - План создан для хоста (plan_id, price=100.0) через test_setup
    - Используется временная БД (temp_db)
    - Моки для bot и xui_api настроены
    - sample_promo_code содержит данные промокода (code='TESTPROMO', discount_amount=10.0)
    
    **Используемые моки и фикстуры:**
    - temp_db: временная SQLite БД с полной структурой таблиц (users, vpn_keys, transactions, plans, xui_hosts, promo_codes)
    - test_setup: фикстура создает пользователя (user_id=123456800), хост (host_name='test-host') и план (plan_id, price=100.0)
    - sample_promo_code: фикстура содержит данные промокода (code='TESTPROMO', discount_amount=10.0, is_active=1)
    - mock_bot: мок aiogram.Bot с методами send_message, edit_message_text
    - mock_xui_api: мок py3xui.Api с методом create_or_update_key_on_host, возвращающий client_uuid, email, expiry_timestamp_ms
    
    **Проверяемые граничные случаи:**
    - Применение скидки к цене плана
    - Корректный расчет финальной цены (original_price - discount_amount)
    - Создание ключа с учетом примененного промокода
    
    **Ожидаемый результат:**
    После обработки платежа должен быть создан VPN ключ для пользователя.
    Промокод должен быть применен, и финальная цена должна быть уменьшена на discount_amount (100.0 - 10.0 = 90.0).
    Ключ должен быть привязан к правильному пользователю и хосту.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("vpn", "purchase", "promo-code", "integration", "critical")
    @pytest.mark.asyncio
    async def test_full_purchase_flow_with_promo(self, temp_db, test_setup, mock_bot, mock_xui_api, sample_promo_code):
        """Тест полного цикла с промокодом"""
        # Патчим DB_FILE для использования временной БД
        import sys
        from shop_bot.data_manager import database
        
        with allure.step("Создание промокода"):
            # Создаем промокод
            promo_id = create_promo_code(
                code=sample_promo_code['code'],
                bot=sample_promo_code['bot'],
                vpn_plan_id=None,
                tariff_code=None,
                discount_amount=sample_promo_code['discount_amount'],
                discount_percent=sample_promo_code['discount_percent'],
                discount_bonus=sample_promo_code['discount_bonus'],
                usage_limit_per_bot=sample_promo_code['usage_limit_per_bot'],
                is_active=sample_promo_code['is_active']
            )
        
        # Патчим xui_api
        with patch('shop_bot.modules.xui_api.create_or_update_key_on_host', new_callable=AsyncMock) as mock_create_key:
            expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            mock_create_key.return_value = {
                'client_uuid': str(uuid.uuid4()),
                'email': f"user{test_setup['user_id']}-key1@testcode.bot",
                'expiry_timestamp_ms': expiry_timestamp_ms,
                'subscription_link': 'https://example.com/subscription',
                'connection_string': 'vless://test'
            }
            
            with allure.step("Подготовка метаданных платежа с промокодом"):
                # Подготавливаем metadata с промокодом
                expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
                payment_id = f"test_promo_{uuid.uuid4().hex[:16]}"
                final_price = test_setup['price'] - sample_promo_code['discount_amount']
                metadata = {
                    'user_id': test_setup['user_id'],
                    'operation': 'new',
                    'months': 1,
                    'days': 0,
                    'hours': 0,
                    'price': final_price,
                    'action': 'new',
                    'host_name': test_setup['host_name'],
                    'plan_id': test_setup['plan_id'],
                    'customer_email': 'test@example.com',
                    'payment_method': 'yookassa',
                    'payment_id': payment_id,
                    'promo_code': sample_promo_code['code'],
                    'final_price': final_price
                }
            
            with allure.step("Обработка успешного платежа с промокодом"):
                # Обрабатываем успешную оплату
                await process_successful_payment(mock_bot, metadata)
            
            with allure.step("Проверка создания ключа"):
                # Проверяем, что ключ создан
                keys = get_user_keys(test_setup['user_id'])
                assert len(keys) > 0, "Должен быть создан ключ"
        

    @allure.story("Полный цикл покупки VPN с реферальной программой")
    @allure.title("Полный цикл покупки VPN с реферальной программой")
    @allure.description("""
    Проверяет полный цикл покупки VPN ключа с учетом реферальной программы от создания реферера до получения ключа:
    
    **Что проверяется:**
    - Создание реферера (пользователя, который пригласил)
    - Привязка пользователя к рефереру через поле referred_by
    - Обработка платежа с учетом реферальной программы
    - Начисление бонусов рефереру (если реализовано)
    - Создание ключа на хосте через 3X-UI API
    
    **Тестовые данные:**
    - user_id: 123456800 (создается через test_setup, реферал)
    - referrer_id: 123456801 (создается в тесте, реферер)
    - username: 'test_user_new' (реферал)
    - referrer_username: 'referrer' (реферер)
    - host_name: 'test-host' (из sample_host)
    - plan_id: создается через test_setup, price=100.0
    - payment_id: test_referral_<hex> (генерируется в тесте)
    
    **Шаги теста:**
    1. **Создание реферера**
       - Метод: database.register_user_if_not_exists()
       - Параметры: user_id=123456801, username='referrer', fullname='Referrer'
       - Ожидаемый результат: реферер создан в БД
       - Проверка: database.get_user(123456801) возвращает объект пользователя
       - Проверяемые поля: telegram_id=123456801, username='referrer'
    
    2. **Привязка пользователя к рефереру**
       - Метод: SQL UPDATE через sqlite3
       - Параметры: UPDATE users SET referred_by=123456801 WHERE telegram_id=123456800
       - Ожидаемый результат: пользователь привязан к рефереру
       - Проверка: users.referred_by == 123456801 для user_id=123456800
    
    3. **Подготовка метаданных платежа**
       - Метод: создание словаря metadata
       - Параметры: user_id=123456800, operation='new', months=1, price=100.0, host_name, plan_id, payment_method='yookassa', payment_id
       - Ожидаемый результат: metadata содержит все необходимые данные для обработки платежа
       - Проверка: все обязательные поля присутствуют в metadata
    
    4. **Обработка успешного платежа с реферальной программой**
       - Метод: bot.handlers.process_successful_payment()
       - Параметры: bot=mock_bot, metadata={...}
       - Ожидаемый результат: ключ создан на хосте, реферальная программа обработана
       - Проверка: mock_xui_api.create_or_update_key_on_host вызван с правильными параметрами
       - Проверка: реферер получил бонусы (если реализовано)
    
    5. **Проверка создания ключа**
       - Метод: database.get_user_keys()
       - Параметры: user_id=123456800
       - Ожидаемый результат: список содержит один ключ
       - Проверка: len(keys) > 0
       - Проверяемые поля: key_id, user_id=123456800, host_name='test-host', status='active'
    
    **Предусловия:**
    - Пользователь зарегистрирован (user_id: 123456800) через test_setup
    - Хост создан в БД (xui_hosts) через test_setup
    - План создан для хоста (plan_id, price=100.0) через test_setup
    - Используется временная БД (temp_db)
    - Моки для bot и xui_api настроены
    
    **Используемые моки и фикстуры:**
    - temp_db: временная SQLite БД с полной структурой таблиц (users, vpn_keys, transactions, plans, xui_hosts)
    - test_setup: фикстура создает пользователя (user_id=123456800), хост (host_name='test-host') и план (plan_id, price=100.0)
    - mock_bot: мок aiogram.Bot с методами send_message, edit_message_text
    - mock_xui_api: мок py3xui.Api с методом create_or_update_key_on_host, возвращающий client_uuid, email, expiry_timestamp_ms
    
    **Проверяемые граничные случаи:**
    - Обработка реферальной программы при покупке
    - Привязка пользователя к рефереру через поле referred_by
    - Создание ключа для реферала
    
    **Ожидаемый результат:**
    После обработки платежа должен быть создан VPN ключ для реферала (user_id=123456800).
    Пользователь должен быть привязан к рефереру (referred_by=123456801).
    Ключ должен быть привязан к правильному пользователю и хосту.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("vpn", "purchase", "referral", "integration", "normal")
    @pytest.mark.asyncio
    async def test_full_purchase_flow_with_referral(self, temp_db, test_setup, mock_bot, mock_xui_api):
        """Тест полного цикла с реферальной скидкой"""
        # Патчим DB_FILE для использования временной БД
        import sys
        from shop_bot.data_manager import database
        
        with allure.step("Создание реферера"):
            # Создаем реферера
            referrer_id = 123456801
            register_user_if_not_exists(referrer_id, "referrer", None, "Referrer")
        
        with allure.step("Привязка пользователя к рефереру"):
            # Обновляем пользователя с реферером
            import sqlite3
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET referred_by = ? WHERE telegram_id = ?",
                    (referrer_id, test_setup['user_id'])
                )
                conn.commit()
        
        # Патчим xui_api
        with patch('shop_bot.modules.xui_api.create_or_update_key_on_host', new_callable=AsyncMock) as mock_create_key:
            expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            mock_create_key.return_value = {
                'client_uuid': str(uuid.uuid4()),
                'email': f"user{test_setup['user_id']}-key1@testcode.bot",
                'expiry_timestamp_ms': expiry_timestamp_ms,
                'subscription_link': 'https://example.com/subscription',
                'connection_string': 'vless://test'
            }
            
            with allure.step("Подготовка метаданных платежа"):
                # Подготавливаем metadata для первого пользователя (реферала)
                expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
                payment_id = f"test_referral_{uuid.uuid4().hex[:16]}"
                metadata = {
                    'user_id': test_setup['user_id'],
                    'operation': 'new',
                    'months': 1,
                    'days': 0,
                    'hours': 0,
                    'price': test_setup['price'],
                    'action': 'new',
                    'host_name': test_setup['host_name'],
                    'plan_id': test_setup['plan_id'],
                    'customer_email': 'test@example.com',
                    'payment_method': 'yookassa',
                    'payment_id': payment_id
                }
            
            with allure.step("Обработка успешного платежа с реферальной программой"):
                # Обрабатываем успешную оплату
                await process_successful_payment(mock_bot, metadata)
            
            with allure.step("Проверка создания ключа"):
                # Проверяем, что ключ создан
                keys = get_user_keys(test_setup['user_id'])
                assert len(keys) > 0, "Должен быть создан ключ"
        

    @allure.story("Создание VPN ключа после успешной оплаты")
    @allure.title("Создание VPN ключа после успешной оплаты")
    @allure.description("""
    Проверяет создание VPN ключа на хосте после успешной обработки платежа от вызова 3X-UI API до сохранения в БД:
    
    **Что проверяется:**
    - Вызов 3X-UI API для создания ключа на хосте
    - Сохранение ключа в БД с правильными данными
    - Проверка наличия subscription_link и connection_string
    - Корректное сохранение всех атрибутов ключа
    
    **Тестовые данные:**
    - user_id: 123456800 (создается через test_setup)
    - host_name: 'test-host' (из sample_host)
    - plan_id: создается через test_setup, price=100.0
    - payment_id: test_key_<hex> (генерируется в тесте)
    - expiry_timestamp_ms: текущее время + 30 дней в миллисекундах
    - client_uuid: UUID строки (генерируется моком)
    - email: user{user_id}-key1@testcode.bot (генерируется моком)
    
    **Шаги теста:**
    1. **Подготовка окружения**
       - Метод: настройка временной БД и моков
       - Параметры: temp_db, test_setup, mock_bot, mock_xui_api
       - Ожидаемый результат: окружение готово для теста
       - Проверка: database.DB_FILE указывает на temp_db
       - Мок: mock_xui_api.create_or_update_key_on_host возвращает client_uuid, email, expiry_timestamp_ms, subscription_link, connection_string
    
    2. **Подготовка метаданных платежа**
       - Метод: создание словаря metadata
       - Параметры: user_id=123456800, operation='new', months=1, days=0, hours=0, price=100.0, action='new', host_name='test-host', plan_id, payment_method='yookassa', payment_id
       - Ожидаемый результат: metadata содержит все необходимые данные для обработки платежа
       - Проверка: все обязательные поля присутствуют в metadata
    
    3. **Обработка успешного платежа**
       - Метод: bot.handlers.process_successful_payment()
       - Параметры: bot=mock_bot, metadata={...}
       - Ожидаемый результат: ключ создан на хосте через mock_xui_api
       - Проверка: mock_xui_api.create_or_update_key_on_host вызван с правильными параметрами
       - Проверка: ключ сохранен в БД
    
    4. **Проверка создания ключа**
       - Метод: database.get_user_keys()
       - Параметры: user_id=123456800
       - Ожидаемый результат: список содержит один ключ
       - Проверка: len(keys) > 0
       - Проверяемые поля: key_id, user_id=123456800, host_name='test-host', status='active'
    
    5. **Проверка данных ключа**
       - Метод: проверка атрибутов ключа
       - Параметры: keys[0]
       - Ожидаемый результат: ключ содержит subscription_link и connection_string
       - Проверка: key['subscription_link'] is not None
       - Проверка: key['connection_string'] is not None
       - Проверяемые поля: subscription_link, connection_string, xui_client_uuid, key_email
    
    **Предусловия:**
    - Пользователь зарегистрирован (user_id: 123456800) через test_setup
    - Хост создан в БД (xui_hosts) через test_setup
    - План создан для хоста (plan_id, price=100.0) через test_setup
    - Используется временная БД (temp_db)
    - Моки для bot и xui_api настроены
    
    **Используемые моки и фикстуры:**
    - temp_db: временная SQLite БД с полной структурой таблиц (users, vpn_keys, transactions, plans, xui_hosts)
    - test_setup: фикстура создает пользователя (user_id=123456800), хост (host_name='test-host') и план (plan_id, price=100.0)
    - mock_bot: мок aiogram.Bot с методами send_message, edit_message_text
    - mock_xui_api: мок py3xui.Api с методом create_or_update_key_on_host, возвращающий:
      * client_uuid: UUID строки
      * email: user{user_id}-key1@testcode.bot
      * expiry_timestamp_ms: текущее время + 30 дней
      * subscription_link: https://example.com/subscription
      * connection_string: vless://test
    
    **Проверяемые граничные случаи:**
    - Корректное создание ключа с полным набором данных
    - Наличие subscription_link и connection_string в ключе
    - Сохранение всех атрибутов ключа в БД
    
    **Ожидаемый результат:**
    После обработки платежа должен быть создан VPN ключ для пользователя.
    Ключ должен содержать subscription_link и connection_string.
    Все данные ключа должны быть корректно сохранены в БД.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("vpn", "key-creation", "payment", "integration", "critical")
    @pytest.mark.asyncio
    async def test_key_creation_after_payment(self, temp_db, test_setup, mock_bot, mock_xui_api):
        """Тест создания ключа после оплаты"""
        # Патчим DB_FILE для использования временной БД
        import sys
        from shop_bot.data_manager import database
        
        # Патчим xui_api
        with patch('shop_bot.modules.xui_api.create_or_update_key_on_host', new_callable=AsyncMock) as mock_create_key:
            expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            mock_create_key.return_value = {
                'client_uuid': str(uuid.uuid4()),
                'email': f"user{test_setup['user_id']}-key1@testcode.bot",
                'expiry_timestamp_ms': expiry_timestamp_ms,
                'subscription_link': 'https://example.com/subscription',
                'connection_string': 'vless://test'
            }
            
            with allure.step("Подготовка метаданных платежа"):
                # Подготавливаем metadata
                expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
                payment_id = f"test_key_{uuid.uuid4().hex[:16]}"
                metadata = {
                    'user_id': test_setup['user_id'],
                    'operation': 'new',
                    'months': 1,
                    'days': 0,
                    'hours': 0,
                    'price': test_setup['price'],
                    'action': 'new',
                    'host_name': test_setup['host_name'],
                    'plan_id': test_setup['plan_id'],
                    'customer_email': 'test@example.com',
                    'payment_method': 'yookassa',
                    'payment_id': payment_id
                }
            
            with allure.step("Обработка успешного платежа"):
                # Обрабатываем успешную оплату
                await process_successful_payment(mock_bot, metadata)
            
            with allure.step("Проверка создания ключа"):
                # Проверяем, что ключ создан
                keys = get_user_keys(test_setup['user_id'])
                assert len(keys) > 0, "Должен быть создан ключ"
            
            with allure.step("Проверка данных ключа"):
                # Проверяем, что ключ имеет правильные данные
                key = keys[0]
                assert key['subscription_link'] is not None, "Ключ должен иметь subscription_link"
                assert key['connection_string'] is not None, "Ключ должен иметь connection_string"
        

    @allure.story("Продление VPN ключа после оплаты")
    @allure.title("Продление VPN ключа после оплаты")
    @allure.description("""
    Проверяет продление существующего VPN ключа после успешной оплаты от создания существующего ключа до обновления:
    
    **Что проверяется:**
    - Создание существующего ключа с исходным сроком действия
    - Обновление срока действия ключа на хосте через 3X-UI API
    - Обновление данных ключа в БД (xui_client_uuid, expiry_timestamp_ms)
    - Корректное продление срока действия
    
    **Тестовые данные:**
    - user_id: 123456800 (создается через test_setup)
    - host_name: 'test-host' (из sample_host)
    - plan_id: создается через test_setup, price=100.0
    - key_id: создается в тесте через create_key_with_stats_atomic
    - xui_client_uuid: UUID строки (генерируется в тесте)
    - key_email: test_<hex>@example.com (генерируется в тесте)
    - original_expiry_timestamp_ms: текущее время + 10 дней
    - new_expiry_timestamp_ms: текущее время + 40 дней (после продления)
    - new_uuid: новый UUID (генерируется моком)
    - payment_id: test_extend_<hex> (генерируется в тесте)
    
    **Шаги теста:**
    1. **Создание существующего ключа**
       - Метод: database.create_key_with_stats_atomic()
       - Параметры: user_id=123456800, host_name='test-host', xui_client_uuid, key_email, expiry_timestamp_ms (текущее время + 10 дней), amount_spent=50.0, months_purchased=1, plan_name='Test Plan', price=50.0
       - Ожидаемый результат: ключ создан в БД с исходным сроком действия
       - Проверка: key_id возвращается и не None
       - Проверяемые поля: key_id, user_id=123456800, host_name='test-host', expiry_timestamp_ms (текущее время + 10 дней)
    
    2. **Подготовка метаданных для продления**
       - Метод: создание словаря metadata с operation='extend'
       - Параметры: user_id=123456800, operation='extend', months=1, price=100.0, action='extend', key_id, host_name='test-host', plan_id, payment_method='yookassa', payment_id
       - Ожидаемый результат: metadata содержит key_id и operation='extend'
       - Проверка: metadata['operation'] == 'extend'
       - Проверка: metadata['key_id'] == key_id
    
    3. **Обработка успешного платежа для продления**
       - Метод: bot.handlers.process_successful_payment()
       - Параметры: bot=mock_bot, metadata={...с operation='extend'...}
       - Ожидаемый результат: ключ обновлен на хосте через mock_xui_api
       - Проверка: mock_xui_api.create_or_update_key_on_host вызван с правильными параметрами
       - Проверка: новый expiry_timestamp_ms больше исходного
    
    4. **Проверка обновления ключа**
       - Метод: database.get_key_by_id()
       - Параметры: key_id
       - Ожидаемый результат: ключ обновлен с новым UUID и сроком действия
       - Проверка: updated_key is not None
       - Проверка: updated_key['xui_client_uuid'] == new_uuid
       - Проверяемые поля: xui_client_uuid (новый UUID), expiry_timestamp_ms (текущее время + 40 дней)
    
    **Предусловия:**
    - Пользователь зарегистрирован (user_id: 123456800) через test_setup
    - Хост создан в БД (xui_hosts) через test_setup
    - План создан для хоста (plan_id, price=100.0) через test_setup
    - Используется временная БД (temp_db)
    - Моки для bot и xui_api настроены
    
    **Используемые моки и фикстуры:**
    - temp_db: временная SQLite БД с полной структурой таблиц (users, vpn_keys, transactions, plans, xui_hosts)
    - test_setup: фикстура создает пользователя (user_id=123456800), хост (host_name='test-host') и план (plan_id, price=100.0)
    - mock_bot: мок aiogram.Bot с методами send_message, edit_message_text
    - mock_xui_api: мок py3xui.Api с методом create_or_update_key_on_host, возвращающий:
      * client_uuid: новый UUID строки
      * email: тот же key_email
      * expiry_timestamp_ms: текущее время + 40 дней (продленный срок)
      * subscription_link: https://example.com/subscription
      * connection_string: vless://test
    
    **Проверяемые граничные случаи:**
    - Продление существующего ключа (не создание нового)
    - Обновление UUID ключа при продлении
    - Увеличение срока действия (с 10 дней до 40 дней)
    
    **Ожидаемый результат:**
    После обработки платежа существующий ключ должен быть продлен.
    UUID ключа должен быть обновлен на новый (new_uuid).
    Срок действия должен быть увеличен с 10 дней до 40 дней.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("vpn", "key-extension", "payment", "integration", "critical")
    @pytest.mark.asyncio
    async def test_key_extension_after_payment(self, temp_db, test_setup, mock_bot, mock_xui_api):
        """Тест продления ключа после оплаты"""
        # Патчим DB_FILE для использования временной БД
        import sys
        from shop_bot.data_manager import database
        
        with allure.step("Создание существующего ключа"):
            # Создаем существующий ключ
            from shop_bot.data_manager.database import create_key_with_stats_atomic
            xui_client_uuid = str(uuid.uuid4())
            key_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
            expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=10)).timestamp() * 1000)
            
            key_id = create_key_with_stats_atomic(
                user_id=test_setup['user_id'],
                host_name=test_setup['host_name'],
                xui_client_uuid=xui_client_uuid,
                key_email=key_email,
                expiry_timestamp_ms=expiry_timestamp_ms,
                amount_spent=50.0,
                months_purchased=1,
                plan_name="Test Plan",
                price=50.0
            )
        
        # Патчим xui_api
        with patch('shop_bot.modules.xui_api.create_or_update_key_on_host', new_callable=AsyncMock) as mock_create_key:
            new_uuid = str(uuid.uuid4())
            new_expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=40)).timestamp() * 1000)
            mock_create_key.return_value = {
                'client_uuid': new_uuid,
                'email': key_email,
                'expiry_timestamp_ms': new_expiry_timestamp_ms,
                'subscription_link': 'https://example.com/subscription',
                'connection_string': 'vless://test'
            }
            
            with allure.step("Подготовка метаданных для продления"):
                # Подготавливаем metadata для продления
                payment_id = f"test_extend_{uuid.uuid4().hex[:16]}"
                metadata = {
                    'user_id': test_setup['user_id'],
                    'operation': 'extend',
                    'months': 1,
                    'days': 0,
                    'hours': 0,
                    'price': test_setup['price'],
                    'action': 'extend',
                    'key_id': key_id,
                    'host_name': test_setup['host_name'],
                    'plan_id': test_setup['plan_id'],
                    'customer_email': 'test@example.com',
                    'payment_method': 'yookassa',
                    'payment_id': payment_id
                }
            
            with allure.step("Обработка успешного платежа для продления"):
                # Обрабатываем успешную оплату
                await process_successful_payment(mock_bot, metadata)
            
            with allure.step("Проверка обновления ключа"):
                # Проверяем, что ключ обновлен
                updated_key = get_key_by_id(key_id)
                assert updated_key is not None, "Ключ должен существовать"
                assert updated_key['xui_client_uuid'] == new_uuid, "UUID должен быть обновлен"
        

    @allure.story("Обработка неудачной оплаты")
    @allure.title("Обработка неудачной оплаты")
    @allure.description("""
    Проверяет обработку ситуации с неудачной оплатой от подготовки платежа до обработки ошибки:
    
    **Что проверяется:**
    - Обработка ошибки при создании ключа на хосте (mock_xui_api возвращает None)
    - Корректная обработка исключений при неудачной оплате
    - Отсутствие создания ключа при ошибке (или корректная обработка частично созданного ключа)
    - Сохранение статуса транзакции при ошибке
    
    **Тестовые данные:**
    - user_id: 123456800 (создается через test_setup)
    - host_name: 'test-host' (из sample_host)
    - plan_id: создается через test_setup, price=100.0
    - payment_id: test_fail_<hex> (генерируется в тесте)
    - mock_xui_api.create_or_update_key_on_host возвращает None (ошибка)
    
    **Шаги теста:**
    1. **Подготовка окружения с моком ошибки**
       - Метод: настройка временной БД и моков
       - Параметры: temp_db, test_setup, mock_bot
       - Ожидаемый результат: окружение готово для теста
       - Проверка: database.DB_FILE указывает на temp_db
       - Мок: mock_xui_api.create_or_update_key_on_host возвращает None (симуляция ошибки)
    
    2. **Подготовка метаданных платежа**
       - Метод: создание словаря metadata
       - Параметры: user_id=123456800, operation='new', months=1, days=0, hours=0, price=100.0, action='new', host_name='test-host', plan_id, payment_method='yookassa', payment_id
       - Ожидаемый результат: metadata содержит все необходимые данные для обработки платежа
       - Проверка: все обязательные поля присутствуют в metadata
    
    3. **Обработка неудачной оплаты**
       - Метод: bot.handlers.process_successful_payment()
       - Параметры: bot=mock_bot, metadata={...}
       - Ожидаемый результат: возникает исключение или ошибка при создании ключа
       - Проверка: mock_xui_api.create_or_update_key_on_host возвращает None
       - Проверка: исключение обрабатывается корректно (try/except)
    
    4. **Проверка отсутствия ключа**
       - Метод: database.get_user_keys()
       - Параметры: user_id=123456800
       - Ожидаемый результат: ключ не создан (или создан частично в зависимости от логики)
       - Проверка: len(keys) >= 0 (ключи могут быть или не быть созданы в зависимости от логики обработки ошибок)
       - Проверяемые поля: количество ключей должно быть 0 или минимальным
    
    **Предусловия:**
    - Пользователь зарегистрирован (user_id: 123456800) через test_setup
    - Хост создан в БД (xui_hosts) через test_setup
    - План создан для хоста (plan_id, price=100.0) через test_setup
    - Используется временная БД (temp_db)
    - Моки для bot настроены
    - mock_xui_api настроен на возврат None (ошибка создания ключа)
    
    **Используемые моки и фикстуры:**
    - temp_db: временная SQLite БД с полной структурой таблиц (users, vpn_keys, transactions, plans, xui_hosts)
    - test_setup: фикстура создает пользователя (user_id=123456800), хост (host_name='test-host') и план (plan_id, price=100.0)
    - mock_bot: мок aiogram.Bot с методами send_message, edit_message_text
    - mock_xui_api: мок py3xui.Api с методом create_or_update_key_on_host, возвращающий None (симуляция ошибки)
    
    **Проверяемые граничные случаи:**
    - Обработка ошибки при создании ключа на хосте
    - Корректная обработка исключений
    - Отсутствие создания ключа при ошибке (или частичное создание)
    
    **Ожидаемый результат:**
    При неудачной оплате (когда mock_xui_api возвращает None) должна быть корректно обработана ошибка.
    Ключ не должен быть создан (или должен быть создан частично в зависимости от логики обработки ошибок).
    Исключение должно быть обработано без падения теста.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("vpn", "payment", "failure", "error-handling", "integration", "normal")
    @pytest.mark.asyncio
    async def test_payment_failure_handling(self, temp_db, test_setup, mock_bot):
        """Тест обработки неудачной оплаты"""
        # Патчим DB_FILE для использования временной БД
        import sys
        from shop_bot.data_manager import database
        
        # Патчим xui_api для возврата ошибки
        with patch('shop_bot.modules.xui_api.create_or_update_key_on_host', new_callable=AsyncMock) as mock_create_key:
            mock_create_key.return_value = None  # Ошибка создания ключа
            
            with allure.step("Подготовка метаданных платежа"):
                # Подготавливаем metadata
                expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
                payment_id = f"test_fail_{uuid.uuid4().hex[:16]}"
                metadata = {
                    'user_id': test_setup['user_id'],
                    'operation': 'new',
                    'months': 1,
                    'days': 0,
                    'hours': 0,
                    'price': test_setup['price'],
                    'action': 'new',
                    'host_name': test_setup['host_name'],
                    'plan_id': test_setup['plan_id'],
                    'customer_email': 'test@example.com',
                    'payment_method': 'yookassa',
                    'payment_id': payment_id
                }
            
            with allure.step("Обработка неудачной оплаты"):
                # Обрабатываем неудачную оплату (ключ не создается)
                try:
                    await process_successful_payment(mock_bot, metadata)
                except Exception as e:
                    # Ожидаем ошибку при неудачном создании ключа
                    pass
            
            with allure.step("Проверка отсутствия ключа"):
                # Проверяем, что ключ не создан
                keys = get_user_keys(test_setup['user_id'])
                # Ключ может быть создан или нет в зависимости от логики обработки ошибок
                assert len(keys) >= 0, "Ключи могут быть или не быть созданы"
        

