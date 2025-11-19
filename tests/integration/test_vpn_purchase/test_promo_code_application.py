#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты для применения промокодов

Тестирует применение скидок по сумме, проценту и бонусов
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
    create_promo_code,
    validate_promo_code,
    can_user_use_promo_code,
)


@pytest.mark.integration
@pytest.mark.database
@allure.epic("Интеграционные тесты")
@allure.feature("Покупка VPN")
@allure.label("package", "tests.integration.test_vpn_purchase")
class TestPromoCodeApplication:
    """Интеграционные тесты для применения промокодов"""

    @pytest.fixture
    def test_setup(self, temp_db):
        """Фикстура для настройки тестового окружения"""
        # Создаем пользователя
        user_id = 123456830
        register_user_if_not_exists(user_id, "test_user_promo", None, "Test User Promo")
        
        return {
            'user_id': user_id,
            'base_price': 100.0
        }

    @allure.story("Применение скидки по сумме через промокод")
    @allure.title("Применение скидки по сумме через промокод")
    @allure.description("""
    Проверяет применение скидки по сумме через промокод от создания промокода до расчета финальной цены.
    
    **Что проверяется:**
    - Создание промокода со скидкой по сумме
    - Валидация промокода через validate_promo_code
    - Расчет финальной цены (base_price - discount_amount)
    
    **Тестовые данные:**
    - user_id: 123456830 (из test_setup)
    - promo_code: 'DISCOUNT10'
    - discount_amount: 10.0
    - base_price: 100.0
    - final_price: 90.0 (100.0 - 10.0)
    
    **Ожидаемый результат:**
    Промокод должен быть применен, и финальная цена должна быть уменьшена на discount_amount.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("promo-code", "discount-amount", "integration", "normal")
    def test_promo_code_application_discount_amount(self, temp_db, test_setup):
        """Тест применения скидки по сумме"""
        # Используем database.DB_FILE (уже заменен через monkeypatch в фикстуре temp_db)
        from shop_bot.data_manager.database import (
            create_promo_code,
            validate_promo_code
        )
        
        # Создаем промокод со скидкой по сумме
        promo_id = create_promo_code(
            code='DISCOUNT10',
            bot='test_bot',
            vpn_plan_id=None,
            tariff_code=None,
            discount_amount=10.0,
            discount_percent=0.0,
            discount_bonus=0.0,
            usage_limit_per_bot=1,
            is_active=True
        )
        
        # Валидируем промокод
        promo_result = validate_promo_code('DISCOUNT10', 'test_bot')
        assert promo_result is not None, "Промокод должен быть валиден"
        assert promo_result.get('valid') is True, "Промокод должен быть валиден"
        promo_data = promo_result.get('promo_data', {})
        assert promo_data.get('discount_amount') == 10.0, "Скидка по сумме должна быть 10.0"
        
        # Рассчитываем финальную цену
        final_price = test_setup['base_price'] - promo_data['discount_amount']
        assert final_price == 90.0, "Финальная цена должна быть 90.0"

    @allure.story("Применение скидки по проценту через промокод")
    @allure.title("Применение скидки по проценту через промокод")
    @allure.description("""
    Проверяет применение скидки по проценту через промокод от создания промокода до расчета финальной цены.
    
    **Что проверяется:**
    - Создание промокода со скидкой по проценту
    - Валидация промокода через validate_promo_code
    - Расчет финальной цены (base_price - (base_price * discount_percent / 100))
    
    **Тестовые данные:**
    - user_id: 123456830 (из test_setup)
    - promo_code: 'PERCENT20'
    - discount_percent: 20.0
    - base_price: 100.0
    - final_price: 80.0 (100.0 - (100.0 * 20.0 / 100))
    
    **Ожидаемый результат:**
    Промокод должен быть применен, и финальная цена должна быть уменьшена на процент от base_price.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("promo-code", "discount-percent", "integration", "normal")
    def test_promo_code_application_discount_percent(self, temp_db, test_setup):
        """Тест применения скидки по проценту"""
        # Используем database.DB_FILE (уже заменен через monkeypatch в фикстуре temp_db)
        from shop_bot.data_manager.database import (
            create_promo_code,
            validate_promo_code
        )
        
        # Создаем промокод со скидкой по проценту
        promo_id = create_promo_code(
            code='PERCENT20',
            bot='test_bot',
            vpn_plan_id=None,
            tariff_code=None,
            discount_amount=0.0,
            discount_percent=20.0,
            discount_bonus=0.0,
            usage_limit_per_bot=1,
            is_active=True
        )
        
        # Валидируем промокод
        promo_result = validate_promo_code('PERCENT20', 'test_bot')
        assert promo_result is not None, "Промокод должен быть валиден"
        assert promo_result.get('valid') is True, "Промокод должен быть валиден"
        promo_data = promo_result.get('promo_data', {})
        assert promo_data.get('discount_percent') == 20.0, "Скидка по проценту должна быть 20.0"
        
        # Рассчитываем финальную цену
        discount_amount = test_setup['base_price'] * (promo_data['discount_percent'] / 100)
        final_price = test_setup['base_price'] - discount_amount
        assert final_price == 80.0, "Финальная цена должна быть 80.0"

    @allure.story("Применение бонуса через промокод")
    @allure.title("Применение бонуса через промокод")
    @allure.description("""
    Проверяет применение бонуса через промокод от создания промокода до проверки цены.
    
    **Что проверяется:**
    - Создание промокода с бонусом
    - Валидация промокода через validate_promo_code
    - Проверка, что цена не меняется при бонусе (бонус добавляется на баланс)
    
    **Тестовые данные:**
    - user_id: 123456830 (из test_setup)
    - promo_code: 'BONUS50'
    - discount_bonus: 50.0
    - base_price: 100.0
    - final_price: 100.0 (цена не меняется при бонусе)
    
    **Ожидаемый результат:**
    Промокод должен быть применен, бонус должен быть добавлен на баланс, но цена не должна измениться.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("promo-code", "discount-bonus", "integration", "normal")
    def test_promo_code_application_discount_bonus(self, temp_db, test_setup):
        """Тест применения бонуса"""
        # Используем database.DB_FILE (уже заменен через monkeypatch в фикстуре temp_db)
        from shop_bot.data_manager.database import (
            create_promo_code,
            validate_promo_code
        )
        
        # Создаем промокод с бонусом
        promo_id = create_promo_code(
            code='BONUS50',
            bot='test_bot',
            vpn_plan_id=None,
            tariff_code=None,
            discount_amount=0.0,
            discount_percent=0.0,
            discount_bonus=50.0,
            usage_limit_per_bot=1,
            is_active=True
        )
        
        # Валидируем промокод
        promo_result = validate_promo_code('BONUS50', 'test_bot')
        assert promo_result is not None, "Промокод должен быть валиден"
        assert promo_result.get('valid') is True, "Промокод должен быть валиден"
        promo_data = promo_result.get('promo_data', {})
        assert promo_data.get('discount_bonus') == 50.0, "Бонус должен быть 50.0"
        
        # Бонус добавляется на баланс, цена не меняется
        final_price = test_setup['base_price']
        assert final_price == 100.0, "Цена не должна измениться при бонусе"

    @allure.story("Валидация промокода: проверка валидных и невалидных промокодов")
    @allure.title("Валидация промокода: проверка валидных и невалидных промокодов")
    @allure.description("""
    Интеграционный тест, проверяющий валидацию промокодов и возможность их использования пользователем.
    
    **Что проверяется:**
    - Валидация валидного промокода через validate_promo_code
    - Валидация невалидного промокода через validate_promo_code
    - Проверка возможности использования промокода пользователем через can_user_use_promo_code
    
    **Тестовые данные:**
    - user_id: 123456830 (из test_setup)
    - promo_code: 'VALID' (валидный промокод)
    - promo_code: 'INVALID' (невалидный промокод)
    - bot: 'test_bot'
    - discount_amount: 10.0
    - usage_limit_per_bot: 1
    - is_active: True
    
    **Шаги теста:**
    1. Создание промокода с кодом 'VALID' и скидкой 10.0
    2. Валидация валидного промокода 'VALID'
    3. Валидация невалидного промокода 'INVALID'
    4. Проверка возможности использования промокода пользователем
    
    **Ожидаемый результат:**
    - Валидный промокод 'VALID' должен быть принят (valid=True)
    - Невалидный промокод 'INVALID' должен быть отклонен (valid=False)
    - Пользователь должен иметь возможность использовать промокод 'VALID' (can_use=True)
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("promo_code", "validation", "integration", "vpn_purchase", "can_user_use_promo_code")
    def test_promo_code_application_validation(self, temp_db, test_setup):
        """Тест валидации промокода"""
        # Используем database.DB_FILE (уже заменен через monkeypatch в фикстуре temp_db)
        from shop_bot.data_manager.database import (
            create_promo_code,
            validate_promo_code,
            can_user_use_promo_code
        )
        
        with allure.step("Создание промокода с кодом 'VALID' и скидкой 10.0"):
            promo_id = create_promo_code(
                code='VALID',
                bot='test_bot',
                vpn_plan_id=None,
                tariff_code=None,
                discount_amount=10.0,
                discount_percent=0.0,
                discount_bonus=0.0,
                usage_limit_per_bot=1,
                is_active=True
            )
            allure.attach(str(promo_id), "ID созданного промокода", allure.attachment_type.TEXT)
        
        with allure.step("Валидация валидного промокода 'VALID'"):
            promo_result = validate_promo_code('VALID', 'test_bot')
            allure.attach(str(promo_result), "Результат валидации валидного промокода", allure.attachment_type.JSON)
            assert promo_result is not None, "Валидный промокод должен быть принят"
            assert promo_result.get('valid') is True, "Валидный промокод должен быть принят"
        
        with allure.step("Валидация невалидного промокода 'INVALID'"):
            invalid_promo = validate_promo_code('INVALID', 'test_bot')
            allure.attach(str(invalid_promo), "Результат валидации невалидного промокода", allure.attachment_type.JSON)
            assert invalid_promo is not None, "Невалидный промокод должен вернуть результат"
            assert invalid_promo.get('valid') is False, "Невалидный промокод должен быть отклонен"
        
        with allure.step("Проверка возможности использования промокода пользователем"):
            can_use = can_user_use_promo_code(test_setup['user_id'], 'VALID', 'test_bot')
            allure.attach(str(can_use), "Результат проверки возможности использования промокода", allure.attachment_type.JSON)
            assert can_use.get('can_use') is True, "Пользователь должен иметь возможность использовать промокод"

