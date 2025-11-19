#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для логики применения промокодов

Тестирует логику работы с промокодами без зависимости от БД (используя моки)
"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import (
    can_user_use_promo_code,
    record_promo_code_usage,
)


@pytest.mark.unit
@pytest.mark.bot
@allure.epic("Обработчики бота")
@allure.feature("Промокоды")
@allure.label("package", "src.shop_bot.handlers")
class TestPromoCodeLogic:
    """Тесты для логики применения промокодов"""

    @allure.title("Расчет скидки по промокоду с фиксированной суммой")
    @allure.description("""
    Проверяет расчет скидки по промокоду с фиксированной суммой скидки.
    
    **Что проверяется:**
    - Создание промокода с discount_amount
    - Проверка возможности использования промокода
    - Корректность значения discount_amount в результате
    
    **Тестовые данные:**
    - code: "FIXED_100"
    - discount_amount: 100.0
    - user_id: 123456820
    
    **Ожидаемый результат:**
    Промокод доступен для использования, discount_amount равен 100.0.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("promo_code", "discount_amount", "bot", "unit")
    def test_calculate_discount_amount(self, temp_db):
        """Тест расчета скидки по промокоду с фиксированной суммой"""
        from shop_bot.data_manager.database import create_promo_code, register_user_if_not_exists
        
        # Создаем промокод с фиксированной скидкой
        promo_id = create_promo_code(
            code="FIXED_100",
            bot="shop",
            vpn_plan_id=None,
            tariff_code=None,
            discount_amount=100.0,
            discount_percent=0.0,
            discount_bonus=0.0,
            usage_limit_per_bot=10,
            is_active=True
        )
        
        # Создаем пользователя
        user_id = 123456820
        register_user_if_not_exists(user_id, "test_user10", None, "Test User 10")
        
        # Проверяем возможность использования
        result = can_user_use_promo_code(user_id, "FIXED_100", "shop")
        assert result.get('can_use') is True
        
        promo_data = result.get('promo_data', {})
        assert promo_data.get('discount_amount') == 100.0

    @allure.title("Расчет скидки по промокоду с процентом")
    @allure.description("""
    Проверяет расчет скидки по промокоду с процентной скидкой.
    
    **Что проверяется:**
    - Создание промокода с discount_percent
    - Проверка возможности использования промокода
    - Корректность значения discount_percent в результате
    
    **Тестовые данные:**
    - code: "PERCENT_50"
    - discount_percent: 50.0
    - user_id: 123456821
    
    **Ожидаемый результат:**
    Промокод доступен для использования, discount_percent равен 50.0.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("promo_code", "discount_percent", "bot", "unit")
    def test_calculate_discount_percent(self, temp_db):
        """Тест расчета скидки по промокоду с процентом"""
        from shop_bot.data_manager.database import create_promo_code, register_user_if_not_exists
        
        # Создаем промокод с процентной скидкой
        promo_id = create_promo_code(
            code="PERCENT_50",
            bot="shop",
            vpn_plan_id=None,
            tariff_code=None,
            discount_amount=0.0,
            discount_percent=50.0,
            discount_bonus=0.0,
            usage_limit_per_bot=10,
            is_active=True
        )
        
        # Создаем пользователя
        user_id = 123456821
        register_user_if_not_exists(user_id, "test_user11", None, "Test User 11")
        
        # Проверяем возможность использования
        result = can_user_use_promo_code(user_id, "PERCENT_50", "shop")
        assert result.get('can_use') is True
        
        promo_data = result.get('promo_data', {})
        assert promo_data.get('discount_percent') == 50.0

    @allure.title("Промокод нельзя использовать после достижения лимита")
    @allure.description("""
    Проверяет, что промокод нельзя использовать после достижения лимита использования.
    
    **Что проверяется:**
    - Создание промокода с usage_limit_per_bot=1
    - Использование промокода один раз
    - Попытка повторного использования промокода
    - Возврат can_use=False после достижения лимита
    
    **Тестовые данные:**
    - code: "LIMIT_1"
    - usage_limit_per_bot: 1
    - user_id: 123456822
    
    **Ожидаемый результат:**
    Промокод можно использовать один раз, после достижения лимита can_use=False.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("promo_code", "limit", "bot", "unit")
    def test_promo_code_limit_reached(self, temp_db):
        """Тест, что промокод нельзя использовать после достижения лимита"""
        from shop_bot.data_manager.database import create_promo_code, register_user_if_not_exists
        
        # Создаем промокод с лимитом использования 1
        promo_id = create_promo_code(
            code="LIMIT_1",
            bot="shop",
            vpn_plan_id=None,
            tariff_code=None,
            discount_amount=100.0,
            discount_percent=0.0,
            discount_bonus=0.0,
            usage_limit_per_bot=1,
            is_active=True
        )
        
        # Создаем первого пользователя
        user_id_1 = 123456822
        register_user_if_not_exists(user_id_1, "test_user12", None, "Test User 12")
        
        # Применяем промокод первым пользователем
        record_promo_code_usage(
            promo_id=promo_id,
            user_id=user_id_1,
            bot="shop",
            plan_id=None,
            discount_amount=100.0,
            discount_percent=0.0,
            discount_bonus=0.0,
            metadata={"source": "test"},
            status='applied'
        )
        
        # Создаем второго пользователя
        user_id_2 = 123456823
        register_user_if_not_exists(user_id_2, "test_user13", None, "Test User 13")
        
        # Проверяем, что второй пользователь не может использовать промокод
        result = can_user_use_promo_code(user_id_2, "LIMIT_1", "shop")
        assert result.get('can_use') is False, "Промокод не должен быть доступен после достижения лимита"

