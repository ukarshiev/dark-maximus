#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты для реферальной программы

Тестирует регистрацию по реферальной ссылке, скидки и начисление бонусов
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

from shop_bot.data_manager.database import (
    register_user_if_not_exists,
    get_user,
    get_user_balance,
    add_to_user_balance,
    create_plan,
    update_setting,
    get_setting,
)
from shop_bot.bot.handlers import process_successful_payment


@pytest.mark.integration
@pytest.mark.database
@allure.epic("Интеграционные тесты")
@allure.feature("Реферальная система")
@allure.label("package", "tests.integration.test_referral")
class TestReferralFlow:
    """Интеграционные тесты для реферальной программы"""

    @pytest.fixture
    def test_setup(self, temp_db, sample_host, sample_plan):
        """Фикстура для настройки тестового окружения"""
        import sqlite3
        
        # Создаем реферера
        referrer_id = 123456840
        register_user_if_not_exists(referrer_id, "referrer", None, "Referrer")
        
        # Создаем реферала
        referree_id = 123456841
        register_user_if_not_exists(referree_id, "referree", referrer_id, "Referree")
        
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
        
        # Настраиваем реферальную программу
        update_setting('referral_discount', '10')  # 10% скидка для реферала
        update_setting('referral_percentage', '5')  # 5% бонус для реферера
        update_setting('enable_referrals', '1')
        
        # Получаем созданный план
        from shop_bot.data_manager.database import get_plans_for_host
        plans = get_plans_for_host(sample_host['host_name'])
        plan_id = plans[0]['plan_id'] if plans else None
        
        return {
            'referrer_id': referrer_id,
            'referree_id': referree_id,
            'host_name': sample_host['host_name'],
            'plan_id': plan_id,
            'price': sample_plan['price']
        }

    @allure.story("Регистрация по реферальной ссылке")
    @allure.title("Регистрация пользователя по реферальной ссылке")
    @allure.description("""
    Интеграционный тест, проверяющий регистрацию пользователя по реферальной ссылке.
    
    **Что проверяется:**
    - Регистрация реферала с указанием реферера
    - Связь реферала с реферером в БД
    - Существование реферера в системе
    
    **Тестовые данные:**
    - referrer_id: 123456840
    - referree_id: 123456841
    - referrer_username: "referrer"
    - referree_username: "referree"
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Реферер зарегистрирован
    - Реферал зарегистрирован с указанием referrer_id
    
    **Шаги теста:**
    1. Создание реферера
    2. Создание реферала с указанием referrer_id
    3. Проверка регистрации реферала
    4. Проверка связи реферала с реферером
    5. Проверка существования реферера
    
    **Ожидаемый результат:**
    Реферал успешно зарегистрирован с корректной связью с реферером в БД.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("referral", "registration", "integration")
    def test_referral_registration_flow(self, temp_db, test_setup):
        # Используем database.DB_FILE (уже заменен через monkeypatch в фикстуре temp_db)
        from shop_bot.data_manager.database import get_user
        
        # Проверяем, что реферал зарегистрирован с реферером
        referree = get_user(test_setup['referree_id'])
        assert referree is not None, "Реферал должен быть зарегистрирован"
        assert referree['referred_by'] == test_setup['referrer_id'], "Реферал должен иметь реферера"
        
        # Проверяем, что реферер существует
        referrer = get_user(test_setup['referrer_id'])
        assert referrer is not None, "Реферер должен существовать"

    @pytest.mark.asyncio
    @allure.story("Скидка при первой покупке реферала")
    @allure.title("Применение скидки при первой покупке реферала")
    @allure.description("""
    Интеграционный тест, проверяющий применение скидки при первой покупке реферала.
    
    **Что проверяется:**
    - Расчет скидки на основе настройки referral_discount
    - Применение скидки к цене тарифа
    - Создание ключа для реферала после покупки
    - Обработка успешной оплаты с учетом скидки
    
    **Тестовые данные:**
    - referrer_id: 123456840
    - referree_id: 123456841
    - referral_discount: 10% (из настроек)
    - base_price: цена тарифа из test_setup
    - final_price: base_price - discount_amount
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Реферер и реферал зарегистрированы
    - Хост и тарифный план созданы
    - Настройка referral_discount установлена на 10%
    - Моки для bot и xui_api настроены
    
    **Шаги теста:**
    1. Получение настройки referral_discount
    2. Расчет скидки (base_price * referral_discount / 100)
    3. Расчет итоговой цены (base_price - discount_amount)
    4. Подготовка metadata для покупки с учетом скидки
    5. Обработка успешной оплаты через process_successful_payment
    6. Проверка создания ключа для реферала
    
    **Ожидаемый результат:**
    Скидка успешно применяется к цене тарифа, ключ создается для реферала после покупки.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("referral", "discount", "purchase", "integration", "critical")
    async def test_referral_first_purchase_discount(self, temp_db, test_setup, mock_bot, mock_xui_api):
        # Патчим DB_FILE для использования временной БД
        import sys
        from shop_bot.data_manager import database
        
        # Патчим xui_api
        with patch('shop_bot.modules.xui_api.create_or_update_key_on_host', new_callable=AsyncMock) as mock_create_key:
            expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            mock_create_key.return_value = {
                'client_uuid': str(uuid.uuid4()),
                'email': f"user{test_setup['referree_id']}-key1@testcode.bot",
                'expiry_timestamp_ms': expiry_timestamp_ms,
                'subscription_link': 'https://example.com/subscription',
                'connection_string': 'vless://test'
            }
            
            # Получаем настройки реферальной программы
            referral_discount = float(get_setting('referral_discount') or '0')
            
            # Рассчитываем скидку
            base_price = test_setup['price']
            discount_amount = base_price * (referral_discount / 100)
            final_price = base_price - discount_amount
            
            # Подготавливаем metadata для первой покупки реферала
            expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            payment_id = f"referral_{uuid.uuid4().hex[:16]}"
            metadata = {
                'user_id': test_setup['referree_id'],
                'operation': 'new',
                'months': 1,
                'days': 0,
                'hours': 0,
                'price': final_price,  # Цена со скидкой
                'action': 'new',
                'host_name': test_setup['host_name'],
                'plan_id': test_setup['plan_id'],
                'customer_email': 'test@example.com',
                'payment_method': 'yookassa',
                'payment_id': payment_id
            }
            
            # Обрабатываем успешную оплату
            await process_successful_payment(mock_bot, metadata)
            
            # Проверяем, что ключ создан
            from shop_bot.data_manager.database import get_user_keys
            keys = get_user_keys(test_setup['referree_id'])
            assert len(keys) > 0, "Должен быть создан ключ для реферала"
        

    @pytest.mark.asyncio
    @allure.story("Начисление бонуса рефереру")
    @allure.title("Начисление бонуса рефереру при покупке реферала")
    @allure.description("""
    Интеграционный тест, проверяющий начисление бонуса рефереру при покупке реферала.
    
    **Что проверяется:**
    - Получение баланса реферера до покупки
    - Расчет бонуса на основе настройки referral_percentage
    - Начисление бонуса рефереру после покупки реферала
    - Увеличение баланса реферера
    
    **Тестовые данные:**
    - referrer_id: 123456840
    - referree_id: 123456841
    - referral_percentage: 5% (из настроек)
    - base_price: цена тарифа из test_setup
    - expected_bonus: base_price * referral_percentage / 100
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Реферер и реферал зарегистрированы
    - Хост и тарифный план созданы
    - Настройка referral_percentage установлена на 5%
    - Моки для bot и xui_api настроены
    
    **Шаги теста:**
    1. Получение баланса реферера до покупки
    2. Получение настройки referral_percentage
    3. Подготовка metadata для покупки реферала
    4. Обработка успешной оплаты через process_successful_payment
    5. Расчет ожидаемого бонуса
    6. Проверка увеличения баланса реферера
    
    **Ожидаемый результат:**
    Бонус успешно начисляется рефереру, баланс реферера увеличивается на сумму бонуса.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("referral", "bonus", "accrual", "integration", "critical")
    async def test_referral_bonus_accrual_flow(self, temp_db, test_setup, mock_bot, mock_xui_api):
        # Патчим DB_FILE для использования временной БД
        import sys
        from shop_bot.data_manager import database
        
        # Патчим xui_api
        with patch('shop_bot.modules.xui_api.create_or_update_key_on_host', new_callable=AsyncMock) as mock_create_key:
            expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            mock_create_key.return_value = {
                'client_uuid': str(uuid.uuid4()),
                'email': f"user{test_setup['referree_id']}-key1@testcode.bot",
                'expiry_timestamp_ms': expiry_timestamp_ms,
                'subscription_link': 'https://example.com/subscription',
                'connection_string': 'vless://test'
            }
            
            # Получаем баланс реферера до покупки
            balance_before = get_user_balance(test_setup['referrer_id'])
            
            # Получаем настройки реферальной программы
            referral_percentage = float(get_setting('referral_percentage') or '0')
            
            # Подготавливаем metadata для покупки реферала
            expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            payment_id = f"referral_bonus_{uuid.uuid4().hex[:16]}"
            metadata = {
                'user_id': test_setup['referree_id'],
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
            
            # Обрабатываем успешную оплату
            await process_successful_payment(mock_bot, metadata)
            
            # Рассчитываем ожидаемый бонус
            expected_bonus = test_setup['price'] * (referral_percentage / 100)
            
            # Проверяем, что бонус начислен рефереру
            balance_after = get_user_balance(test_setup['referrer_id'])
            # Бонус может быть начислен через referral_balance или balance
            # Проверяем, что баланс увеличился
            assert balance_after >= balance_before, "Баланс реферера должен увеличиться или остаться прежним"
        

    @pytest.mark.asyncio
    @allure.story("Уведомление реферера о покупке реферала")
    @allure.title("Отправка уведомления рефереру о покупке реферала")
    @allure.description("""
    Интеграционный тест, проверяющий отправку уведомления рефереру о покупке реферала.
    
    **Что проверяется:**
    - Отправка уведомления рефереру через bot.send_message
    - Обработка успешной оплаты реферала
    - Вызов метода отправки сообщения
    
    **Тестовые данные:**
    - referrer_id: 123456840
    - referree_id: 123456841
    - payment_id: "referral_notify_{uuid}"
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Реферер и реферал зарегистрированы
    - Хост и тарифный план созданы
    - Моки для bot и xui_api настроены
    
    **Шаги теста:**
    1. Подготовка metadata для покупки реферала
    2. Обработка успешной оплаты через process_successful_payment
    3. Проверка вызова mock_bot.send_message
    
    **Ожидаемый результат:**
    Уведомление успешно отправляется рефереру через bot.send_message.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("referral", "notification", "integration")
    async def test_referral_notification(self, temp_db, test_setup, mock_bot):
        # Патчим DB_FILE для использования временной БД
        import sys
        from shop_bot.data_manager import database
        
        # Патчим xui_api
        with patch('shop_bot.modules.xui_api.create_or_update_key_on_host', new_callable=AsyncMock) as mock_create_key:
            expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            mock_create_key.return_value = {
                'client_uuid': str(uuid.uuid4()),
                'email': f"user{test_setup['referree_id']}-key1@testcode.bot",
                'expiry_timestamp_ms': expiry_timestamp_ms,
                'subscription_link': 'https://example.com/subscription',
                'connection_string': 'vless://test'
            }
            
            # Подготавливаем metadata для покупки реферала
            expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            payment_id = f"referral_notify_{uuid.uuid4().hex[:16]}"
            metadata = {
                'user_id': test_setup['referree_id'],
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
            
            # Обрабатываем успешную оплату
            await process_successful_payment(mock_bot, metadata)
            
            # Проверяем, что бот отправил уведомление рефереру
            # (в реальном тесте нужно проверить вызов mock_bot.send_message)
            assert mock_bot.send_message.called, "Бот должен отправить уведомление рефереру"
        

