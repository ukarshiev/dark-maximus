#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты для условий автопродления

Тестирует проверку условий для автопродления
"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timezone, timedelta

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.integration
@pytest.mark.bot
@allure.epic("Интеграционные тесты")
@allure.feature("Автопродление")
@allure.label("package", "tests.integration.test_auto_renewal")
class TestAutoRenewalConditions:
    """Интеграционные тесты для условий автопродления"""

    @allure.story("Проверка условий автопродления")
    @allure.title("Проверка включенного/отключенного автопродления")
    @allure.description("""
    Интеграционный тест, проверяющий включение и отключение автопродления для пользователя.
    
    **Что проверяется:**
    - Начальное состояние автопродления (по умолчанию включено)
    - Отключение автопродления через set_auto_renewal_enabled
    - Включение автопродления обратно
    - Сохранение состояния в БД
    
    **Тестовые данные:**
    - user_id: 123465
    - username: "test_user"
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован
    
    **Шаги теста:**
    1. Регистрация пользователя
    2. Проверка начального состояния (автопродление включено по умолчанию)
    3. Отключение автопродления
    4. Проверка отключения в БД
    5. Включение автопродления обратно
    6. Проверка включения в БД
    
    **Ожидаемый результат:**
    Автопродление успешно включается и отключается, состояние сохраняется в БД.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "conditions", "integration")
    def test_auto_renewal_conditions_check_enabled(self, temp_db):
        """Тест проверки включенного автопродления"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            set_auto_renewal_enabled,
            get_auto_renewal_enabled,
        )
        
        # Настройка БД
        user_id = 123465
        register_user_if_not_exists(user_id, "test_user", referrer_id=None)
        
        # Проверяем начальное состояние (по умолчанию включено)
        assert get_auto_renewal_enabled(user_id) is True
        
        # Отключаем автопродление
        set_auto_renewal_enabled(user_id, False)
        assert get_auto_renewal_enabled(user_id) is False
        
        # Включаем обратно
        set_auto_renewal_enabled(user_id, True)
        assert get_auto_renewal_enabled(user_id) is True

    @allure.story("Проверка условий автопродления")
    @allure.title("Проверка достаточности баланса для автопродления")
    @allure.description("""
    Интеграционный тест, проверяющий достаточность баланса пользователя для автопродления.
    
    **Что проверяется:**
    - Проверка недостаточного баланса (баланс < цена тарифа)
    - Пополнение баланса
    - Проверка достаточного баланса (баланс >= цена тарифа)
    - Сравнение баланса с ценой тарифа
    
    **Тестовые данные:**
    - user_id: 123466
    - username: "test_user2"
    - host_name: "test_host"
    - plan_name: "Test Plan"
    - price: 100.0
    - Начальный баланс: 50.0 (недостаточно)
    - Пополнение: +100.0
    - Итоговый баланс: 150.0 (достаточно)
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован
    - Хост и тарифный план созданы
    
    **Шаги теста:**
    1. Регистрация пользователя
    2. Создание хоста и тарифного плана
    3. Пополнение баланса на 50.0
    4. Проверка недостаточного баланса (50.0 < 100.0)
    5. Пополнение баланса на 100.0
    6. Проверка достаточного баланса (150.0 >= 100.0)
    
    **Ожидаемый результат:**
    Баланс успешно проверяется, недостаточный баланс определяется корректно, после пополнения баланс достаточен для автопродления.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "conditions", "balance", "integration")
    def test_auto_renewal_conditions_check_balance(self, temp_db):
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_to_user_balance,
            get_user_balance,
            create_host,
            create_plan,
            get_plans_for_host,
        )
        
        # Настройка БД
        user_id = 123466
        register_user_if_not_exists(user_id, "test_user2", referrer_id=None)
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        create_plan("test_host", "Test Plan", 1, 100.0, 0, 0.0, 0)
        plans = get_plans_for_host("test_host")
        plan = plans[0] if plans else None
        
        # Проверяем недостаточный баланс
        add_to_user_balance(user_id, 50.0)
        balance = get_user_balance(user_id)
        assert balance == 50.0
        if plan:
            assert balance < plan['price']  # Недостаточно для автопродления
        
        # Пополняем баланс
        add_to_user_balance(user_id, 100.0)
        balance = get_user_balance(user_id)
        assert balance == 150.0
        if plan:
            assert balance >= plan['price']  # Достаточно для автопродления

    @allure.story("Проверка условий автопродления")
    @allure.title("Проверка доступности тарифного плана для автопродления")
    @allure.description("""
    Интеграционный тест, проверяющий доступность тарифного плана для автопродления.
    
    **Что проверяется:**
    - Получение списка планов для хоста
    - Получение плана по ID
    - Проверка существования плана
    - Проверка несуществующего плана
    
    **Тестовые данные:**
    - user_id: 123467
    - username: "test_user3"
    - host_name: "test_host"
    - plan_name: "Test Plan"
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован
    - Хост и тарифный план созданы
    
    **Шаги теста:**
    1. Регистрация пользователя
    2. Создание хоста и тарифного плана
    3. Получение списка планов для хоста
    4. Получение плана по ID
    5. Проверка существования плана
    6. Проверка несуществующего плана (ID=99999)
    
    **Ожидаемый результат:**
    План успешно получается по ID, несуществующий план возвращает None.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "conditions", "plan", "integration")
    def test_auto_renewal_conditions_check_plan_available(self, temp_db):
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            create_host,
            create_plan,
            get_plans_for_host,
            get_plan_by_id,
        )
        
        # Настройка БД
        user_id = 123467
        register_user_if_not_exists(user_id, "test_user3", referrer_id=None)
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        create_plan("test_host", "Test Plan", 1, 100.0, 0, 0.0, 0)
        
        # Проверяем доступность плана
        plans = get_plans_for_host("test_host")
        assert len(plans) > 0
        
        plan_id = plans[0]['plan_id']
        plan = get_plan_by_id(plan_id)
        assert plan is not None
        assert plan['plan_name'] == "Test Plan"
        
        # Проверяем несуществующий план
        nonexistent_plan = get_plan_by_id(99999)
        assert nonexistent_plan is None

    @allure.story("Проверка условий автопродления")
    @allure.title("Проверка времени до истечения ключа для автопродления")
    @allure.description("""
    Интеграционный тест, проверяющий время до истечения ключа для автопродления.
    
    **Что проверяется:**
    - Создание ключа с истекающим сроком (через 1 час)
    - Получение ключа по ID
    - Проверка даты истечения ключа
    - Расчет времени до истечения
    
    **Тестовые данные:**
    - user_id: 123468
    - username: "test_user4"
    - host_name: "test_host"
    - key_email: "test-uuid-time@testcode.bot"
    - expiry_date: datetime.now(timezone.utc) + timedelta(hours=1)
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован
    - Хост создан
    
    **Шаги теста:**
    1. Регистрация пользователя
    2. Создание хоста
    3. Создание ключа с истекающим сроком (через 1 час)
    4. Получение ключа по ID
    5. Проверка даты истечения ключа
    6. Расчет времени до истечения
    
    **Ожидаемый результат:**
    Ключ успешно создан с корректной датой истечения, время до истечения рассчитывается правильно.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "conditions", "expiry", "integration")
    def test_auto_renewal_conditions_time_before_expiry(self, temp_db):
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            get_key_by_id,
            create_host,
        )
        
        # Настройка БД
        user_id = 123468
        register_user_if_not_exists(user_id, "test_user4", referrer_id=None)
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        
        # Создаем ключ с истекающим сроком (через 1 час)
        expiry_date = datetime.now(timezone.utc) + timedelta(hours=1)
        key_id = add_new_key(
            user_id,
            "test_host",
            "test-uuid-time",
            f"user{user_id}-key1@testcode.bot",
            int(expiry_date.timestamp() * 1000),
            connection_string="vless://test",
            plan_name="Test Plan",
            price=100.0,
        )
        
        # Проверяем, что ключ должен быть обработан (истекает через час)
        key = get_key_by_id(key_id)
        assert key is not None
        
        # Проверяем время до истечения
        expiry_timestamp_ms = key['expiry_timestamp_ms']
        expiry_datetime = datetime.fromtimestamp(expiry_timestamp_ms / 1000, tz=timezone.utc)
        time_left = expiry_datetime - datetime.now(timezone.utc)
        hours_left = time_left.total_seconds() / 3600
        
        # Ключ должен быть обработан, если истекает в течение 24 часов
        assert hours_left <= 24

