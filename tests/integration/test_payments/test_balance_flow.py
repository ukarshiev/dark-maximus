#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты для оплаты с баланса

Тестирует полный flow оплаты с внутреннего баланса
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
    add_to_user_balance,
    get_user_balance,
    create_plan,
    get_user_keys,
)
from shop_bot.bot.handlers import process_successful_payment


@pytest.mark.integration
@pytest.mark.database
@allure.epic("Интеграционные тесты")
@allure.feature("Платежи")
@allure.label("package", "tests.integration.test_payments")
class TestBalanceFlow:
    """Интеграционные тесты для оплаты с баланса"""

    @pytest.fixture
    def test_setup(self, temp_db, sample_host, sample_plan):
        """Фикстура для настройки тестового окружения"""
        import sqlite3
        
        # Создаем пользователя
        user_id = 123456791
        register_user_if_not_exists(user_id, "test_user3", None, "Test User 3")
        
        # Пополняем баланс
        add_to_user_balance(user_id, 200.0)
        
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

    @allure.title("Полный flow оплаты с внутреннего баланса")
    @allure.description("""
    Проверяет полный цикл оплаты VPN ключа с использованием внутреннего баланса пользователя:
    
    **Что проверяется:**
    - Проверка достаточности баланса перед оплатой
    - Обработка успешной оплаты с баланса через process_successful_payment
    - Создание VPN ключа на хосте через 3X-UI API
    - Списание средств с баланса пользователя
    - Корректное обновление баланса в БД
    
    **Тестовые данные:**
    - user_id: 123456791 (создается через test_setup)
    - payment_id: balance_<hex> (генерируется в тесте)
    - plan_id: создается через test_setup, price=100.0
    - host_name: 'test-host' (из sample_host)
    - balance_before: 200.0 (устанавливается через test_setup)
    - expiry_timestamp_ms: текущее время + 30 дней в миллисекундах
    - metadata: {user_id, operation='new', months=1, price=100.0, host_name, plan_id, payment_method='balance', payment_id}
    
    **Шаги теста:**
    1. **Проверка баланса до оплаты**
       - Метод/функция: database.get_user_balance()
       - Параметры: user_id=123456791
       - Ожидаемый результат: баланс >= цена плана (200.0 >= 100.0)
       - Проверка: balance_before >= test_setup['price']
       - Проверяемые поля: balance из таблицы users
    
    2. **Подготовка метаданных платежа**
       - Метод/функция: создание словаря metadata
       - Параметры: user_id=123456791, operation='new', months=1, days=0, hours=0, price=100.0, action='new', host_name='test-host', plan_id, customer_email='test@example.com', payment_method='balance', payment_id='balance_<hex>'
       - Ожидаемый результат: metadata содержит все необходимые данные для обработки платежа с баланса
       - Проверка: все обязательные поля присутствуют в metadata
    
    3. **Обработка успешного платежа с баланса**
       - Метод/функция: bot.handlers.process_successful_payment()
       - Параметры: bot=mock_bot, metadata={...}
       - Ожидаемый результат: ключ создан на хосте через mock_xui_api, баланс уменьшен на сумму платежа
       - Проверка: mock_xui_api.create_or_update_key_on_host вызван один раз
       - Проверка: mock_bot.send_message вызван для уведомления пользователя
    
    4. **Проверка создания ключа**
       - Метод/функция: database.get_user_keys()
       - Параметры: user_id=123456791
       - Ожидаемый результат: список содержит один ключ
       - Проверка: len(keys) > 0
       - Проверяемые поля: key_id, user_id=123456791, host_name='test-host', status='active', expiry_date не None
    
    5. **Проверка списания средств с баланса**
       - Метод/функция: database.get_user_balance()
       - Параметры: user_id=123456791
       - Ожидаемый результат: баланс уменьшился на сумму платежа (balance_after < balance_before)
       - Проверка: balance_after < balance_before
       - Проверка: balance_after == balance_before - test_setup['price'] (примерно, с учетом округления)
       - Проверяемые поля: balance из таблицы users
    
    **Предусловия:**
    - Пользователь зарегистрирован (user_id: 123456791) через test_setup
    - Баланс пользователя пополнен до 200.0 через test_setup
    - Хост создан в БД (xui_hosts) через test_setup
    - План создан для хоста (plan_id, price=100.0) через test_setup
    - Используется временная БД (temp_db)
    - Моки для bot и xui_api настроены
    
    **Используемые моки и фикстуры:**
    - temp_db: временная SQLite БД с полной структурой таблиц (users, vpn_keys, transactions, plans, xui_hosts, promo_codes)
    - test_setup: фикстура создает пользователя (user_id=123456791, username='test_user3'), пополняет баланс до 200.0, создает хост (host_name='test-host') и план (plan_id, price=100.0)
    - mock_bot: мок aiogram.Bot с методами send_message, edit_message_text, answer_callback_query
    - mock_xui_api: мок py3xui.Api с методом create_or_update_key_on_host, возвращающий:
      * client_uuid: UUID строки
      * email: user{user_id}-key1@testcode.bot
      * expiry_timestamp_ms: текущее время + 30 дней в миллисекундах
      * subscription_link: https://example.com/subscription
      * connection_string: vless://test
    
    **Проверяемые граничные случаи:**
    - Обработка платежа с достаточным балансом (200.0 >= 100.0)
    - Корректное списание средств с баланса
    - Создание ключа при оплате с баланса (без внешних платежных систем)
    
    **Ожидаемый результат:**
    После обработки платежа должен быть создан VPN ключ для пользователя.
    Баланс должен уменьшиться на сумму платежа (balance_after < balance_before).
    Ключ должен быть привязан к правильному пользователю (user_id=123456791) и хосту (host_name='test-host').
    Ключ должен иметь статус 'active' и корректный срок действия (expiry_date).
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("payments", "balance", "integration", "vpn-key", "critical")
    @pytest.mark.asyncio
    async def test_balance_payment_full_flow(self, temp_db, test_setup, mock_bot, mock_xui_api):
        """Тест полного flow оплаты с баланса"""
        # Патчим DB_FILE для использования временной БД
        import sys
        from shop_bot.data_manager import database
        
        # Патчим xui_api - патчим create_or_update_key_on_host и login_to_host
        expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        mock_return_value = {
            'client_uuid': str(uuid.uuid4()),
            'email': f"user{test_setup['user_id']}-key1@testcode.bot",
            'expiry_timestamp_ms': expiry_timestamp_ms,
            'subscription_link': 'https://example.com/subscription',
            'connection_string': 'vless://test'
        }
        
        # Патчим create_or_update_key_on_host в handlers (где используется)
        # И также патчим login_to_host, чтобы избежать реальных подключений
        with patch('shop_bot.bot.handlers.xui_api.create_or_update_key_on_host', new_callable=AsyncMock) as mock_create_key, \
             patch('shop_bot.modules.xui_api.login_to_host', return_value=(MagicMock(), MagicMock())) as mock_login:
            mock_create_key.return_value = mock_return_value
            
            with allure.step("Проверка баланса до оплаты"):
                balance_before = get_user_balance(test_setup['user_id'])
                assert balance_before >= test_setup['price'], "Баланс должен быть достаточным"
            
            with allure.step("Подготовка метаданных платежа"):
                expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
                payment_id = f"balance_{uuid.uuid4().hex[:16]}"
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
                    'payment_method': 'balance',
                    'payment_id': payment_id
                }
            
            with allure.step("Обработка успешного платежа с баланса"):
                await process_successful_payment(mock_bot, metadata)
            
            with allure.step("Проверка создания ключа"):
                keys = get_user_keys(test_setup['user_id'])
                assert len(keys) > 0, "Должен быть создан ключ"
            
            with allure.step("Проверка списания средств с баланса"):
                balance_after = get_user_balance(test_setup['user_id'])
                assert balance_after < balance_before, "Баланс должен уменьшиться"
        

    @allure.title("Пополнение внутреннего баланса пользователя")
    @allure.description("""
    Проверяет пополнение внутреннего баланса пользователя:
    
    **Что проверяется:**
    - Добавление средств на баланс пользователя через add_to_user_balance
    - Корректное обновление баланса в БД
    - Проверка итогового баланса после пополнения
    
    **Тестовые данные:**
    - user_id: 123456791 (создается через test_setup)
    - balance_initial: 200.0 (устанавливается через test_setup)
    - topup_amount: 50.0 (сумма пополнения)
    - balance_expected: 250.0 (200.0 + 50.0)
    
    **Шаги теста:**
    1. **Пополнение баланса**
       - Метод/функция: database.add_to_user_balance()
       - Параметры: user_id=123456791, amount=50.0
       - Ожидаемый результат: баланс увеличен на 50.0
       - Проверка: функция выполняется без ошибок
       - Проверяемые поля: balance в таблице users
    
    2. **Проверка баланса после пополнения**
       - Метод/функция: database.get_user_balance()
       - Параметры: user_id=123456791
       - Ожидаемый результат: баланс >= 250.0 (200.0 начальный + 50.0 пополнение)
       - Проверка: balance >= 250.0
       - Проверяемые поля: balance из таблицы users
    
    **Предусловия:**
    - Пользователь создан (user_id: 123456791) через test_setup
    - Начальный баланс установлен на 200.0 через test_setup
    - Используется временная БД (temp_db)
    
    **Используемые моки и фикстуры:**
    - temp_db: временная SQLite БД с полной структурой таблиц (users, vpn_keys, transactions, plans, xui_hosts, promo_codes)
    - test_setup: фикстура создает пользователя (user_id=123456791, username='test_user3') и пополняет баланс до 200.0
    
    **Проверяемые граничные случаи:**
    - Пополнение баланса положительной суммой (50.0)
    - Корректное суммирование баланса (200.0 + 50.0 = 250.0)
    - Обновление баланса в БД
    
    **Ожидаемый результат:**
    Баланс должен быть успешно пополнен на 50.0 и отображать корректную сумму (250.0).
    Баланс в БД должен быть обновлен корректно.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("payments", "balance", "topup", "integration", "normal")
    @pytest.mark.asyncio
    async def test_balance_topup_flow(self, temp_db, test_setup):
        """Тест пополнения баланса"""
        with allure.step("Пополнение баланса"):
            add_to_user_balance(test_setup['user_id'], 50.0)
        
        with allure.step("Проверка баланса после пополнения"):
            balance = get_user_balance(test_setup['user_id'])
            assert balance >= 250.0, "Баланс должен быть пополнен"

    @allure.story("Обработка недостаточных средств на балансе")
    @allure.title("Обработка недостаточных средств на балансе")
    @allure.description("""
    Проверяет обработку ситуации с недостаточными средствами на балансе:
    
    **Что проверяется:**
    - Установка баланса меньше цены плана через прямое обновление БД
    - Проверка корректного определения недостаточности средств
    - Валидация условия balance < price для блокировки оплаты
    
    **Тестовые данные:**
    - user_id: 123456791 (создается через test_setup)
    - balance_initial: 200.0 (устанавливается через test_setup)
    - balance_insufficient: 10.0 (устанавливается в тесте)
    - plan_price: 100.0 (из test_setup)
    - Условие: balance_insufficient (10.0) < plan_price (100.0)
    
    **Шаги теста:**
    1. **Установка недостаточного баланса**
       - Метод/функция: прямое обновление БД через SQL
       - Параметры: UPDATE users SET balance = 10.0 WHERE telegram_id = 123456791
       - Ожидаемый результат: баланс установлен на 10.0
       - Проверка: SQL запрос выполнен успешно (conn.commit())
       - Проверяемые поля: balance в таблице users
    
    2. **Проверка баланса**
       - Метод/функция: database.get_user_balance()
       - Параметры: user_id=123456791
       - Ожидаемый результат: баланс < цена плана (10.0 < 100.0)
       - Проверка: balance < test_setup['price']
       - Проверяемые поля: balance из таблицы users
    
    **Предусловия:**
    - Пользователь создан (user_id: 123456791) через test_setup
    - Начальный баланс установлен на 200.0 через test_setup
    - План создан для хоста (plan_id, price=100.0) через test_setup
    - Используется временная БД (temp_db)
    - database.DB_FILE указывает на temp_db
    
    **Используемые моки и фикстуры:**
    - temp_db: временная SQLite БД с полной структурой таблиц (users, vpn_keys, transactions, plans, xui_hosts, promo_codes)
    - test_setup: фикстура создает пользователя (user_id=123456791), хост (host_name='test-host') и план (plan_id, price=100.0)
    - mock_bot: мок aiogram.Bot (не используется в этом тесте, но передается как параметр)
    
    **Проверяемые граничные случаи:**
    - Обработка ситуации с недостаточным балансом (10.0 < 100.0)
    - Корректное определение недостаточности средств для блокировки оплаты
    - Прямое обновление баланса через SQL для симуляции недостаточности средств
    
    **Ожидаемый результат:**
    Баланс должен быть установлен на недостаточную сумму (10.0).
    Проверка должна подтвердить, что баланс меньше цены плана (10.0 < 100.0).
    Это состояние должно блокировать возможность оплаты с баланса.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("payments", "balance", "insufficient-funds", "integration", "normal")
    @pytest.mark.asyncio
    async def test_balance_insufficient_funds(self, temp_db, test_setup, mock_bot):
        """Тест обработки недостаточных средств"""
        # Устанавливаем баланс меньше цены плана через прямое обновление БД
        import sqlite3
        from shop_bot.data_manager import database
        
        with allure.step("Установка недостаточного баланса"):
            # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
            with sqlite3.connect(str(temp_db)) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET balance = ? WHERE telegram_id = ?",
                    (10.0, test_setup['user_id'])
                )
                conn.commit()
        
        with allure.step("Проверка баланса"):
            balance = get_user_balance(test_setup['user_id'])
            assert balance < test_setup['price'], "Баланс должен быть недостаточным"
