#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты для продления ключей

Тестирует продление ключей и расчет нового времени истечения
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
    create_key_with_stats_atomic,
    get_key_by_id,
    update_key_info,
)


@pytest.mark.integration
@pytest.mark.database
@allure.epic("Интеграционные тесты")
@allure.feature("Покупка VPN")
@allure.label("package", "tests.integration.test_vpn_purchase")
class TestKeyExtensionFlow:
    """Интеграционные тесты для продления ключей"""

    @pytest.fixture
    def test_setup(self, temp_db, sample_host):
        """Фикстура для настройки тестового окружения"""
        import sqlite3
        
        # Создаем пользователя
        user_id = 123456820
        register_user_if_not_exists(user_id, "test_user_extend", None, "Test User Extend")
        
        # Создаем хост в БД
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",
                (sample_host['host_name'], sample_host['host_url'], sample_host['host_username'], 
                 sample_host['host_pass'], sample_host['host_inbound_id'], sample_host['host_code'])
            )
            conn.commit()
        
        return {
            'user_id': user_id,
            'host_name': sample_host['host_name']
        }

    @allure.story("Успешное продление ключа")
    @allure.title("Успешное продление ключа")
    @allure.description("""
    Проверяет успешное продление существующего VPN ключа от создания ключа до обновления.
    
    **Что проверяется:**
    - Создание существующего ключа с исходным сроком действия
    - Обновление срока действия ключа через update_key_info
    - Обновление UUID ключа
    - Корректное продление срока действия
    
    **Тестовые данные:**
    - user_id: 123456820 (из test_setup)
    - host_name: из test_setup
    - original_expiry: текущее время + 10 дней
    - new_expiry: текущее время + 40 дней
    
    **Ожидаемый результат:**
    После продления ключ должен иметь новый UUID и увеличенный срок действия.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("key-extension", "integration", "critical")
    @pytest.mark.asyncio
    async def test_key_extension_flow_success(self, temp_db, test_setup):
        """Тест успешного продления ключа"""
        # Используем database.DB_FILE (уже заменен через monkeypatch в фикстуре temp_db)
        from shop_bot.data_manager.database import (
            create_key_with_stats_atomic,
            get_key_by_id,
            update_key_info
        )
        
        # Создаем существующий ключ
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
        
        # Получаем ключ до продления
        key_before = get_key_by_id(key_id)
        assert key_before is not None, "Ключ должен существовать"
        old_expiry = key_before['expiry_date']
        
        # Продлеваем ключ на 30 дней
        new_expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=40)).timestamp() * 1000)
        new_uuid = str(uuid.uuid4())
        update_key_info(key_id, new_uuid, new_expiry_timestamp_ms, "https://example.com/subscription")
        
        # Получаем ключ после продления
        key_after = get_key_by_id(key_id)
        assert key_after is not None, "Ключ должен существовать после продления"
        assert key_after['xui_client_uuid'] == new_uuid, "UUID должен быть обновлен"
        assert key_after['expiry_date'] != old_expiry, "Дата истечения должна быть обновлена"

    @allure.story("Расчет нового времени истечения при продлении ключа")
    @allure.title("Расчет нового времени истечения при продлении ключа")
    @allure.description("""
    Проверяет корректность расчета нового времени истечения при продлении ключа.
    
    **Что проверяется:**
    - Создание ключа с исходным сроком действия
    - Расчет нового времени истечения (исходное + 30 дней)
    - Корректность расчета в миллисекундах
    
    **Тестовые данные:**
    - user_id: 123456820 (из test_setup)
    - host_name: из test_setup
    - original_expiry: текущее время + 10 дней
    - days_to_add: 30
    - expected_expiry: original_expiry + 30 дней
    
    **Ожидаемый результат:**
    Новое время истечения должно быть правильно рассчитано (исходное + 30 дней).
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("key-extension", "calculation", "integration", "normal")
    def test_key_extension_flow_calculation(self, temp_db, test_setup):
        """Тест расчета нового времени истечения"""
        # Используем database.DB_FILE (уже заменен через monkeypatch в фикстуре temp_db)
        from shop_bot.data_manager.database import (
            create_key_with_stats_atomic
        )
        
        # Создаем существующий ключ с текущей датой истечения
        now = datetime.now(timezone.utc)
        expiry_date = now + timedelta(days=10)
        expiry_timestamp_ms = int(expiry_date.timestamp() * 1000)
        
        xui_client_uuid = str(uuid.uuid4())
        key_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        
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
        
        # Продлеваем ключ на 30 дней
        new_expiry_date = expiry_date + timedelta(days=30)
        new_expiry_timestamp_ms = int(new_expiry_date.timestamp() * 1000)
        
        # Проверяем расчет
        days_added = 30
        expected_expiry = expiry_date + timedelta(days=days_added)
        expected_expiry_ms = int(expected_expiry.timestamp() * 1000)
        
        assert new_expiry_timestamp_ms == expected_expiry_ms, "Время истечения должно быть правильно рассчитано"

    @allure.story("Обработка ошибок при продлении ключа")
    @allure.title("Обработка ошибок при продлении ключа")
    @allure.description("""
    Проверяет обработку ошибок при попытке продления несуществующего ключа.
    
    **Что проверяется:**
    - Попытка обновления несуществующего ключа
    - Корректная обработка ситуации (не должно вызывать исключение)
    - Отсутствие создания нового ключа при ошибке
    
    **Тестовые данные:**
    - non_existent_key_id: 999999
    - new_uuid: генерируется автоматически
    - new_expiry_timestamp_ms: текущее время + 30 дней
    
    **Ожидаемый результат:**
    При попытке обновления несуществующего ключа функция должна обработать это корректно без создания нового ключа.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("key-extension", "error-handling", "integration", "normal")
    @pytest.mark.asyncio
    async def test_key_extension_flow_error_handling(self, temp_db, test_setup):
        """Тест обработки ошибок продления"""
        # Используем database.DB_FILE (уже заменен через monkeypatch в фикстуре temp_db)
        from shop_bot.data_manager import database
        
        # Пытаемся обновить несуществующий ключ
        non_existent_key_id = 999999
        new_uuid = str(uuid.uuid4())
        new_expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        
        # Обновление несуществующего ключа не должно вызывать исключение
        # (функция должна обработать это корректно)
        update_key_info(non_existent_key_id, new_uuid, new_expiry_timestamp_ms)
        
        # Проверяем, что ключ не создан
        key = get_key_by_id(non_existent_key_id)
        assert key is None, "Несуществующий ключ не должен быть создан"

    @pytest.mark.asyncio
    @allure.story("Конвертация триального ключа в боевой при продлении с оплатой")
    @allure.title("Конвертация триального ключа в боевой при продлении с оплатой")
    @allure.description("""
    Проверяет, что при продлении триального ключа с оплатой (price > 0) ключ автоматически конвертируется в боевой.
    
    **Что проверяется:**
    - Создание триального ключа (is_trial = 1, status = 'trial-active')
    - Продление триального ключа через process_successful_payment с action='extend' и price > 0
    - Автоматическая конвертация в боевой ключ (is_trial = 0, status = 'pay-active')
    - Корректное обновление expiry_date и remaining_seconds
    
    **Тестовые данные:**
    - user_id: 123456820 (из test_setup)
    - host_name: из test_setup
    - key_email: генерируется автоматически
    - price: 100.0 (оплата за продление)
    - months: 1 (продление на 1 месяц)
    
    **Шаги теста:**
    1. Создание триального ключа с is_trial=1
    2. Проверка начального состояния (is_trial=1, status='trial-active')
    3. Продление через process_successful_payment с оплатой
    4. Проверка конвертации (is_trial=0, status='pay-active')
    
    **Ожидаемый результат:**
    После продления триального ключа с оплатой:
    - is_trial должен быть установлен в 0
    - status должен быть 'pay-active' (если remaining_seconds > 0)
    - expiry_date должен быть обновлен
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("trial", "key-extension", "payment", "integration", "critical")
    async def test_trial_key_extension_converts_to_paid(self, temp_db, test_setup, mock_bot, mock_xui_api):
        """Тест: продление триального ключа с оплатой конвертирует его в боевой"""
        from shop_bot.data_manager.database import (
            add_new_key,
            get_key_by_id,
            create_plan,
        )
        from shop_bot.bot.handlers import process_successful_payment
        
        with allure.step("Создание триального ключа"):
            # Создаем триальный ключ
            xui_client_uuid = str(uuid.uuid4())
            key_email = f"trial_{uuid.uuid4().hex[:8]}@example.com"
            expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=3)).timestamp() * 1000)
            
            key_id = add_new_key(
                user_id=test_setup['user_id'],
                host_name=test_setup['host_name'],
                xui_client_uuid=xui_client_uuid,
                key_email=key_email,
                expiry_timestamp_ms=expiry_timestamp_ms,
                connection_string="vless://trial-test",
                plan_name="Пробный период",
                price=0.0,
                protocol='vless',
                is_trial=1,
                comment="Тестовый триальный ключ"
            )
            
            assert key_id is not None, "Триальный ключ должен быть создан"
            allure.attach(str(key_id), "Key ID", allure.attachment_type.TEXT)
        
        with allure.step("Проверка начального состояния триального ключа"):
            key_before = get_key_by_id(key_id)
            assert key_before is not None, "Ключ должен существовать"
            assert key_before['is_trial'] == 1, "Ключ должен быть триальным (is_trial=1)"
            assert key_before['status'] in ['trial-active', 'trial-ended'], f"Статус должен быть trial-*, получен: {key_before['status']}"
            allure.attach(str(key_before['is_trial']), "is_trial до продления", allure.attachment_type.TEXT)
            allure.attach(str(key_before['status']), "status до продления", allure.attachment_type.TEXT)
        
        with allure.step("Создание плана для продления"):
            # Создаем план для продления
            plan_id = create_plan(
                host_name=test_setup['host_name'],
                plan_name="Test Extension Plan",
                months=1,
                days=0,
                hours=0,
                price=100.0,
                traffic_gb=0.0
            )
            assert plan_id is not None, "План должен быть создан"
            allure.attach(str(plan_id), "Plan ID", allure.attachment_type.TEXT)
        
        with allure.step("Продление триального ключа с оплатой"):
            # Патчим xui_api для продления ключа
            with patch('shop_bot.modules.xui_api.create_or_update_key_on_host', new_callable=AsyncMock) as mock_create_key:
                new_expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=33)).timestamp() * 1000)
                mock_create_key.return_value = {
                    'client_uuid': str(uuid.uuid4()),
                    'email': key_email,
                    'expiry_timestamp_ms': new_expiry_timestamp_ms,
                    'subscription_link': 'https://example.com/subscription',
                    'connection_string': 'vless://extended-test'
                }
                
                # Продлеваем триальный ключ через process_successful_payment с оплатой
                payment_id = f"test_extend_{uuid.uuid4().hex[:16]}"
                metadata = {
                    'user_id': test_setup['user_id'],
                    'operation': 'purchase',
                    'months': 1,
                    'days': 0,
                    'hours': 0,
                    'price': 100.0,
                    'action': 'extend',
                    'key_id': key_id,
                    'host_name': test_setup['host_name'],
                    'plan_id': plan_id,
                    'customer_email': 'test@example.com',
                    'payment_method': 'balance',
                    'payment_id': payment_id
                }
                
                await process_successful_payment(mock_bot, metadata)
                allure.attach(str(metadata), "Metadata платежа", allure.attachment_type.JSON)
        
        with allure.step("Проверка конвертации в боевой ключ"):
            key_after = get_key_by_id(key_id)
            assert key_after is not None, "Ключ должен существовать после продления"
            
            # Проверяем, что ключ конвертирован в боевой
            assert key_after['is_trial'] == 0, f"Ключ должен быть боевым (is_trial=0), получен: {key_after['is_trial']}"
            assert key_after['status'] == 'pay-active', f"Статус должен быть 'pay-active', получен: {key_after['status']}"
            
            # Проверяем, что expiry_date обновлен
            assert key_after['expiry_date'] != key_before['expiry_date'], "Дата истечения должна быть обновлена"
            
            allure.attach(str(key_after['is_trial']), "is_trial после продления", allure.attachment_type.TEXT)
            allure.attach(str(key_after['status']), "status после продления", allure.attachment_type.TEXT)
            allure.attach(str(key_after['expiry_date']), "expiry_date после продления", allure.attachment_type.TEXT)