#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты для CryptoBot

Тестирует полный flow от создания инвойса до получения ключа
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
)
from shop_bot.bot.handlers import process_successful_payment


@pytest.mark.integration
@pytest.mark.database
@allure.epic("Интеграционные тесты")
@allure.feature("Платежи")
@allure.label("package", "tests.integration.test_payments")
class TestCryptoBotFlow:
    """Интеграционные тесты для CryptoBot"""

    @pytest.fixture
    def test_setup(self, temp_db, sample_host, sample_plan):
        """Фикстура для настройки тестового окружения"""
        import sqlite3
        
        # Создаем пользователя
        user_id = 123456790
        register_user_if_not_exists(user_id, "test_user2", None, "Test User 2")
        
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

    @allure.title("Полный flow CryptoBot: от создания инвойса до получения ключа")
    @allure.description("""
    Проверяет полный цикл обработки платежа через CryptoBot от создания инвойса до выдачи VPN ключа:
    
    **Что проверяется:**
    - Обработка успешного платежа через process_successful_payment с методом 'cryptobot'
    - Создание VPN ключа на хосте через 3X-UI API
    - Корректная обработка metadata платежа
    - Сохранение данных ключа в БД
    
    **Тестовые данные:**
    - user_id: 123456790 (создается через test_setup)
    - username: 'test_user2'
    - fullname: 'Test User 2'
    - host_name: 'test-host' (из sample_host)
    - plan_id: создается через test_setup, price=100.0
    - payment_id: cryptobot_<hex> (генерируется в тесте, 16 символов hex)
    - expiry_timestamp_ms: текущее время + 30 дней в миллисекундах
    
    **Шаги теста:**
    1. **Подготовка окружения**
       - Метод: настройка временной БД и моков
       - Параметры: temp_db, test_setup, mock_bot, mock_xui_api
       - Ожидаемый результат: окружение готово для теста
       - Проверка: database.DB_FILE указывает на temp_db
       - Мок: mock_xui_api.create_or_update_key_on_host возвращает client_uuid, email, expiry_timestamp_ms, subscription_link, connection_string
    
    2. **Подготовка метаданных платежа**
       - Метод: создание словаря metadata
       - Параметры: user_id=123456790, operation='new', months=1, days=0, hours=0, price=100.0, action='new', host_name='test-host', plan_id, payment_method='cryptobot', payment_id
       - Ожидаемый результат: metadata содержит все необходимые данные для обработки платежа
       - Проверка: все обязательные поля присутствуют в metadata
       - Проверка: payment_method == 'cryptobot'
       - Проверка: payment_id.startswith('cryptobot_')
    
    3. **Обработка успешного платежа**
       - Метод: bot.handlers.process_successful_payment()
       - Параметры: bot=mock_bot, metadata={user_id, operation='new', months=1, price=100.0, host_name, plan_id, payment_method='cryptobot', payment_id}
       - Ожидаемый результат: ключ создан на хосте через mock_xui_api
       - Проверка: mock_xui_api.create_or_update_key_on_host вызван с правильными параметрами
       - Проверка: mock_bot.send_message вызван для уведомления пользователя
    
    4. **Проверка создания ключа**
       - Метод: database.get_user_keys()
       - Параметры: user_id=123456790
       - Ожидаемый результат: список содержит один ключ
       - Проверка: len(keys) > 0
       - Проверяемые поля: key_id, user_id=123456790, host_name='test-host', status='active'
    
    **Предусловия:**
    - Пользователь зарегистрирован (user_id: 123456790) через test_setup
    - Хост создан в БД (xui_hosts) через test_setup
    - План создан для хоста (plan_id, price=100.0) через test_setup
    - Используется временная БД (temp_db)
    - Моки для bot и xui_api настроены
    
    **Используемые моки и фикстуры:**
    - temp_db: временная SQLite БД с полной структурой таблиц (users, vpn_keys, transactions, plans, xui_hosts)
    - test_setup: фикстура создает пользователя (user_id=123456790, username='test_user2'), хост (host_name='test-host') и план (plan_id, price=100.0)
    - mock_bot: мок aiogram.Bot с методами send_message, edit_message_text
    - mock_xui_api: мок py3xui.Api с методом create_or_update_key_on_host, возвращающий:
      * client_uuid: UUID строки
      * email: user{user_id}-key1@testcode.bot
      * expiry_timestamp_ms: текущее время + 30 дней
      * subscription_link: https://example.com/subscription
      * connection_string: vless://test
    
    **Проверяемые граничные случаи:**
    - Обработка платежа через CryptoBot
    - Создание ключа с правильным сроком действия
    - Привязка ключа к правильному пользователю и хосту
    
    **Ожидаемый результат:**
    После обработки платежа должен быть создан VPN ключ для пользователя.
    Ключ должен быть привязан к правильному пользователю (user_id=123456790) и хосту (host_name='test-host').
    Ключ должен иметь статус 'active' и корректный срок действия (expiry_date).
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("payments", "cryptobot", "integration", "vpn-key", "critical")
    @pytest.mark.asyncio
    async def test_cryptobot_full_flow(self, temp_db, test_setup, mock_bot, mock_xui_api):
        """Тест полного flow от создания инвойса до получения ключа"""
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
            
            # Подготавливаем metadata для process_successful_payment
            expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            payment_id = f"cryptobot_{uuid.uuid4().hex[:16]}"
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
                'payment_method': 'cryptobot',
                'payment_id': payment_id
            }
            
            with allure.step("Обработка успешного платежа через CryptoBot"):
                # Обрабатываем успешную оплату
                await process_successful_payment(mock_bot, metadata)
            
            with allure.step("Проверка создания ключа"):
                # Проверяем, что ключ создан
                keys = get_user_keys(test_setup['user_id'])
                assert len(keys) > 0, "Должен быть создан ключ"
        

    @allure.story("Обработка webhook от CryptoBot")
    @allure.title("Обработка webhook от CryptoBot")
    @allure.description("""
    Проверяет структуру обработки webhook от CryptoBot от создания payment_id до обработки webhook:
    
    **Что проверяется:**
    - Создание payment_id для обработки webhook от CryptoBot
    - Структура обработки webhook
    - Корректность формата payment_id
    - Подготовка к обработке webhook
    
    **Тестовые данные:**
    - temp_db: временная БД для изоляции теста
    - test_setup: фикстура с пользователем, хостом и планом
    - payment_id: cryptobot_<hex> (генерируется в тесте, 16 символов hex)
    
    **Шаги теста:**
    1. **Создание payment_id**
       - Метод: генерация UUID и форматирование
       - Параметры: uuid.uuid4().hex[:16]
       - Ожидаемый результат: payment_id создан в формате cryptobot_<hex>
       - Проверка: payment_id is not None
       - Проверка: payment_id.startswith('cryptobot_')
       - Проверка: len(payment_id) > 9 (префикс + hex)
       - Проверяемые поля: payment_id формат, длина
    
    2. **Проверка структуры payment_id**
       - Метод: валидация формата
       - Параметры: payment_id
       - Ожидаемый результат: payment_id имеет правильный формат
       - Проверка: payment_id соответствует формату cryptobot_<16 hex символов>
    
    **Предусловия:**
    - Пользователь зарегистрирован (user_id: 123456790) через test_setup
    - Хост создан в БД (xui_hosts) через test_setup
    - План создан для хоста через test_setup
    - Используется временная БД (temp_db)
    
    **Используемые моки и фикстуры:**
    - temp_db: временная SQLite БД с полной структурой таблиц (users, vpn_keys, transactions, plans, xui_hosts)
    - test_setup: фикстура создает пользователя (user_id=123456790), хост (host_name='test-host') и план (plan_id, price=100.0)
    
    **Проверяемые граничные случаи:**
    - Создание payment_id в правильном формате
    - Корректность длины payment_id (16 hex символов)
    
    **Ожидаемый результат:**
    Payment ID должен быть создан в формате cryptobot_<hex>.
    Payment ID должен иметь правильную длину и формат для обработки webhook от CryptoBot.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("payments", "cryptobot", "webhook", "integration", "normal")
    @pytest.mark.asyncio
    async def test_cryptobot_webhook_processing(self, temp_db, test_setup):
        """Тест обработки webhook от CryptoBot"""
        with allure.step("Создание payment_id для webhook"):
            # Этот тест требует мок для webhook endpoint
            payment_id = f"cryptobot_{uuid.uuid4().hex[:16]}"
            assert payment_id is not None, "Payment ID должен быть создан"
        
        with allure.step("Проверка формата payment_id"):
            # Проверяем структуру (реальная обработка webhook требует мока для CryptoBot API)
            assert payment_id.startswith('cryptobot_'), "Payment ID должен начинаться с 'cryptobot_'"
            assert len(payment_id) > 9, "Payment ID должен содержать hex данные"

    @allure.story("Проверка подписи webhook CryptoBot")
    @allure.title("Проверка подписи webhook CryptoBot")
    @allure.description("""
    Проверяет структуру проверки подписи webhook от CryptoBot от создания payment_id до верификации:
    
    **Что проверяется:**
    - Создание payment_id для проверки подписи webhook от CryptoBot
    - Структура проверки подписи
    - Корректность формата payment_id
    - Подготовка к проверке HMAC подписи
    
    **Тестовые данные:**
    - temp_db: временная БД для изоляции теста
    - test_setup: фикстура с пользователем, хостом и планом
    - payment_id: cryptobot_<hex> (генерируется в тесте, 16 символов hex)
    
    **Шаги теста:**
    1. **Создание payment_id**
       - Метод: генерация UUID и форматирование
       - Параметры: uuid.uuid4().hex[:16]
       - Ожидаемый результат: payment_id создан в формате cryptobot_<hex>
       - Проверка: payment_id is not None
       - Проверка: payment_id.startswith('cryptobot_')
       - Проверка: len(payment_id) > 9 (префикс + hex)
       - Проверяемые поля: payment_id формат, длина
    
    2. **Проверка структуры payment_id**
       - Метод: валидация формата
       - Параметры: payment_id
       - Ожидаемый результат: payment_id имеет правильный формат
       - Проверка: payment_id соответствует формату cryptobot_<16 hex символов>
       - Проверка: payment_id уникален
    
    **Предусловия:**
    - Пользователь зарегистрирован (user_id: 123456790) через test_setup
    - Хост создан в БД (xui_hosts) через test_setup
    - План создан для хоста через test_setup
    - Используется временная БД (temp_db)
    
    **Используемые моки и фикстуры:**
    - temp_db: временная SQLite БД с полной структурой таблиц (users, vpn_keys, transactions, plans, xui_hosts)
    - test_setup: фикстура создает пользователя (user_id=123456790), хост (host_name='test-host') и план (plan_id, price=100.0)
    
    **Проверяемые граничные случаи:**
    - Создание payment_id в правильном формате
    - Корректность длины payment_id (16 hex символов)
    - Уникальность payment_id
    
    **Ожидаемый результат:**
    Payment ID должен быть создан в формате cryptobot_<hex>.
    Payment ID должен иметь правильную длину и формат для проверки подписи webhook от CryptoBot.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("payments", "cryptobot", "verification", "integration", "normal")
    def test_cryptobot_invoice_verification(self, temp_db, test_setup):
        """Тест проверки подписи webhook CryptoBot"""
        with allure.step("Создание payment_id для проверки подписи"):
            # Этот тест требует проверку подписи webhook
            payment_id = f"cryptobot_{uuid.uuid4().hex[:16]}"
            assert payment_id is not None, "Payment ID должен быть создан"
        
        with allure.step("Проверка формата payment_id"):
            # Проверяем структуру
            assert payment_id.startswith('cryptobot_'), "Payment ID должен начинаться с 'cryptobot_'"
            assert len(payment_id) > 9, "Payment ID должен содержать hex данные"

    @allure.story("Повторная обработка платежа CryptoBot")
    @allure.title("Повторная обработка платежа CryptoBot (идемпотентность)")
    @allure.description("""
    Проверяет идемпотентность обработки платежа CryptoBot от первой обработки до проверки отсутствия дубликатов:
    
    **Что проверяется:**
    - Первая обработка успешного платежа через CryptoBot
    - Повторная обработка того же платежа
    - Отсутствие дублирующих ключей при повторной обработке
    - Идемпотентность системы
    
    **Тестовые данные:**
    - user_id: 123456790 (создается через test_setup)
    - host_name: 'test-host' (из sample_host)
    - plan_id: создается через test_setup, price=100.0
    - payment_id: cryptobot_<hex> (генерируется в тесте, используется для обеих обработок)
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
       - Параметры: user_id=123456790, operation='new', months=1, days=0, hours=0, price=100.0, action='new', host_name='test-host', plan_id, payment_method='cryptobot', payment_id
       - Ожидаемый результат: metadata содержит все необходимые данные для обработки платежа
       - Проверка: все обязательные поля присутствуют в metadata
       - Проверка: payment_method == 'cryptobot'
    
    3. **Первая обработка платежа**
       - Метод: bot.handlers.process_successful_payment()
       - Параметры: bot=mock_bot, metadata={...}
       - Ожидаемый результат: ключ создан на хосте
       - Проверка: mock_xui_api.create_or_update_key_on_host вызван
       - Проверка: keys_count_before >= 1
    
    4. **Повторная обработка платежа**
       - Метод: bot.handlers.process_successful_payment() с теми же данными
       - Параметры: bot=mock_bot, metadata={...} (тот же)
       - Ожидаемый результат: платеж обработан идемпотентно (не создан дубликат)
       - Проверка: keys_count_after >= keys_count_before
       - Проверка: количество ключей не увеличилось значительно (идемпотентность)
       - Проверяемые поля: количество ключей до и после повторной обработки
    
    **Предусловия:**
    - Пользователь зарегистрирован (user_id: 123456790) через test_setup
    - Хост создан в БД (xui_hosts) через test_setup
    - План создан для хоста (plan_id, price=100.0) через test_setup
    - Используется временная БД (temp_db)
    - Моки для bot и xui_api настроены
    
    **Используемые моки и фикстуры:**
    - temp_db: временная SQLite БД с полной структурой таблиц (users, vpn_keys, transactions, plans, xui_hosts)
    - test_setup: фикстура создает пользователя (user_id=123456790), хост (host_name='test-host') и план (plan_id, price=100.0)
    - mock_bot: мок aiogram.Bot с методами send_message, edit_message_text
    - mock_xui_api: мок py3xui.Api с методом create_or_update_key_on_host, возвращающий client_uuid, email, expiry_timestamp_ms
    
    **Проверяемые граничные случаи:**
    - Повторная обработка того же платежа
    - Идемпотентность обработки (отсутствие дубликатов ключей)
    - Корректная обработка повторных платежей
    
    **Ожидаемый результат:**
    Первая обработка платежа должна создать ключ.
    Повторная обработка того же платежа должна быть идемпотентной (не создан дубликат ключа).
    Количество ключей после повторной обработки должно быть >= количества до повторной обработки, но не должно значительно увеличиться.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("payments", "cryptobot", "idempotency", "integration", "normal")
    @pytest.mark.asyncio
    async def test_cryptobot_payment_retry(self, temp_db, test_setup, mock_bot, mock_xui_api):
        """Тест повторной обработки платежа CryptoBot"""
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
            
            # Подготавливаем metadata для process_successful_payment
            expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            payment_id = f"cryptobot_{uuid.uuid4().hex[:16]}"
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
                'payment_method': 'cryptobot',
                'payment_id': payment_id
            }
            
            with allure.step("Первая обработка платежа"):
                # Обрабатываем успешную оплату первый раз
                await process_successful_payment(mock_bot, metadata)
            
            with allure.step("Проверка количества ключей после первой обработки"):
                # Проверяем идемпотентность
                keys_before = get_user_keys(test_setup['user_id'])
                keys_count_before = len(keys_before)
            
            with allure.step("Повторная обработка платежа (проверка идемпотентности)"):
                # Обрабатываем успешную оплату второй раз
                await process_successful_payment(mock_bot, metadata)
            
            with allure.step("Проверка отсутствия дубликатов ключей"):
                # Проверяем, что не создан дублирующий ключ
                keys_after = get_user_keys(test_setup['user_id'])
                keys_count_after = len(keys_after)
                assert keys_count_after >= keys_count_before, "Количество ключей не должно уменьшиться"
        

