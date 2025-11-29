#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты для проверки многократного применения промокода через deeplink

Тестирует сценарий, когда пользователь многократно переходит по одной и той же deeplink ссылке
с промокодом и проверяет, что бонус начисляется только один раз.
"""

import pytest
import allure
import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import (
    register_user_if_not_exists,
    create_promo_code,
    can_user_use_promo_code,
    record_promo_code_usage,
    get_user_balance,
    add_to_user_balance,
    get_promo_code_usage_by_user,
)


@pytest.mark.integration
@pytest.mark.database
@allure.epic("Интеграционные тесты")
@allure.feature("Deeplink")
@allure.label("package", "tests.integration")
class TestDeeplinkPromoCodeReapplication:
    """Интеграционные тесты для многократного применения промокода через deeplink"""

    @allure.story("Многократный переход по deeplink ссылке с промокодом")
    @allure.title("Многократный переход по deeplink ссылке → бонус начисляется только один раз")
    @allure.description("""
    Интеграционный тест, проверяющий что при многократном переходе по deeplink ссылке с промокодом
    бонус начисляется только один раз.
    
    **Что проверяется:**
    - Первый переход по deeplink ссылке → промокод применен, бонус начислен
    - Повторный переход по той же ссылке → промокод не применяется повторно
    - Бонус не начисляется повторно при повторном переходе
    - Баланс пользователя не изменяется при повторном переходе
    
    **Тестовые данные:**
    - user_id: 123456900
    - promo_code: "DEEPLINK_BONUS"
    - discount_bonus: 500.0
    - initial_balance: 0.0
    
    **Шаги теста:**
    1. Создание промокода с бонусом 500 RUB
    2. Создание пользователя с нулевым балансом
    3. Первый переход по deeplink ссылке (симуляция)
       - Проверка возможности использования промокода
       - Применение промокода со статусом 'applied'
       - Начисление бонуса на баланс
    4. Проверка баланса после первого перехода (должен быть 500 RUB)
    5. Повторный переход по той же deeplink ссылке (симуляция)
       - Проверка возможности использования промокода (existing_usage_id)
       - Обновление записи промокода (без начисления бонуса)
    6. Проверка баланса после повторного перехода (должен остаться 500 RUB)
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован
    - Промокод создан и активен
    
    **Ожидаемый результат:**
    Бонус начислен только при первом переходе по deeplink ссылке.
    При повторном переходе баланс не изменяется.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("deeplink", "promo_code", "bonus", "reapplication", "integration", "critical")
    def test_deeplink_promo_code_multiple_clicks(self, temp_db):
        """Тест многократного перехода по deeplink ссылке с промокодом"""
        
        with allure.step("Создание промокода с бонусом 500 RUB"):
            promo_id = create_promo_code(
                code="DEEPLINK_BONUS",
                bot="shop",
                vpn_plan_id=None,
                tariff_code=None,
                discount_amount=0.0,
                discount_percent=0.0,
                discount_bonus=500.0,
                usage_limit_per_bot=10,
                is_active=True
            )
            allure.attach(str(promo_id), "ID промокода", allure.attachment_type.TEXT)
        
        with allure.step("Создание пользователя с нулевым балансом"):
            user_id = 123456900
            register_user_if_not_exists(user_id, "test_deeplink_user", None, "Test Deeplink User")
            initial_balance = get_user_balance(user_id)
            allure.attach(str(initial_balance), "Начальный баланс", allure.attachment_type.TEXT)
            assert initial_balance == 0.0, "Начальный баланс должен быть 0"
        
        # ========== ПЕРВЫЙ ПЕРЕХОД ПО DEEPLINK ССЫЛКЕ ==========
        with allure.step("ПЕРВЫЙ переход по deeplink ссылке"):
            with allure.step("Проверка возможности использования промокода"):
                validation_result = can_user_use_promo_code(user_id, "DEEPLINK_BONUS", "shop")
                allure.attach(str(validation_result), "Результат валидации", allure.attachment_type.JSON)
                
                assert validation_result.get('can_use') is True, "Промокод должен быть доступен для использования"
                promo_data = validation_result.get('promo_data')
                existing_usage_id = validation_result.get('existing_usage_id')
                
                allure.attach(str(existing_usage_id), "existing_usage_id (первый переход)", allure.attachment_type.TEXT)
                assert existing_usage_id is None, "При первом переходе existing_usage_id должен быть None"
            
            with allure.step("Применение промокода со статусом 'applied'"):
                success = record_promo_code_usage(
                    promo_id=promo_data.get('promo_id'),
                    user_id=user_id,
                    bot="shop",
                    plan_id=None,
                    discount_amount=promo_data.get('discount_amount', 0.0),
                    discount_percent=promo_data.get('discount_percent', 0.0),
                    discount_bonus=promo_data.get('discount_bonus', 0.0),
                    metadata={"source": "deep_link"},
                    status='applied',
                    existing_usage_id=existing_usage_id
                )
                assert success is True, "Применение промокода должно быть успешным"
            
            with allure.step("Начисление бонуса на баланс (ТОЛЬКО если existing_usage_id отсутствует)"):
                bonus_amount = promo_data.get('discount_bonus', 0.0)
                
                # КРИТИЧЕСКАЯ ЛОГИКА: Бонус начисляется ТОЛЬКО если existing_usage_id отсутствует
                if not existing_usage_id and bonus_amount > 0:
                    add_to_user_balance(user_id, bonus_amount)
                    allure.attach(f"Бонус {bonus_amount} RUB начислен", "Начисление бонуса", allure.attachment_type.TEXT)
                else:
                    allure.attach("Бонус НЕ начислен (existing_usage_id присутствует)", "Начисление бонуса", allure.attachment_type.TEXT)
        
        with allure.step("Проверка баланса после первого перехода"):
            balance_after_first = get_user_balance(user_id)
            allure.attach(str(balance_after_first), "Баланс после первого перехода", allure.attachment_type.TEXT)
            assert balance_after_first == 500.0, f"Баланс должен быть 500 RUB, получено: {balance_after_first}"
        
        # ========== ПОВТОРНЫЙ ПЕРЕХОД ПО DEEPLINK ССЫЛКЕ ==========
        with allure.step("ПОВТОРНЫЙ переход по той же deeplink ссылке"):
            with allure.step("Проверка возможности использования промокода (должен вернуть existing_usage_id)"):
                validation_result = can_user_use_promo_code(user_id, "DEEPLINK_BONUS", "shop")
                allure.attach(str(validation_result), "Результат валидации (повторный)", allure.attachment_type.JSON)
                
                assert validation_result.get('can_use') is True, "Промокод должен быть доступен для обновления"
                promo_data = validation_result.get('promo_data')
                existing_usage_id = validation_result.get('existing_usage_id')
                
                allure.attach(str(existing_usage_id), "existing_usage_id (повторный переход)", allure.attachment_type.TEXT)
                assert existing_usage_id is not None, "При повторном переходе existing_usage_id должен присутствовать"
            
            with allure.step("Обновление записи промокода (без начисления бонуса)"):
                success = record_promo_code_usage(
                    promo_id=promo_data.get('promo_id'),
                    user_id=user_id,
                    bot="shop",
                    plan_id=None,
                    discount_amount=promo_data.get('discount_amount', 0.0),
                    discount_percent=promo_data.get('discount_percent', 0.0),
                    discount_bonus=promo_data.get('discount_bonus', 0.0),
                    metadata={"source": "deep_link"},
                    status='applied',
                    existing_usage_id=existing_usage_id
                )
                assert success is True, "Обновление записи должно быть успешным"
            
            with allure.step("НЕ начисляем бонус повторно (existing_usage_id присутствует)"):
                bonus_amount = promo_data.get('discount_bonus', 0.0)
                
                # КРИТИЧЕСКАЯ ЛОГИКА: Бонус НЕ начисляется, если existing_usage_id присутствует
                if not existing_usage_id and bonus_amount > 0:
                    add_to_user_balance(user_id, bonus_amount)
                    allure.attach(f"Бонус {bonus_amount} RUB начислен", "Начисление бонуса", allure.attachment_type.TEXT)
                else:
                    allure.attach("Бонус НЕ начислен (existing_usage_id присутствует)", "Начисление бонуса", allure.attachment_type.TEXT)
        
        with allure.step("КРИТИЧЕСКАЯ ПРОВЕРКА: Баланс НЕ изменился после повторного перехода"):
            balance_after_second = get_user_balance(user_id)
            allure.attach(str(balance_after_second), "Баланс после повторного перехода", allure.attachment_type.TEXT)
            
            assert balance_after_second == 500.0, \
                f"Баланс НЕ должен измениться при повторном переходе по deeplink ссылке. " \
                f"Ожидалось: 500.0, получено: {balance_after_second}"
        
        with allure.step("Проверка записи в promo_code_usage"):
            usage_record = get_promo_code_usage_by_user(promo_id, user_id, "shop")
            allure.attach(str(usage_record), "Запись в promo_code_usage", allure.attachment_type.JSON)
            
            assert usage_record is not None, "Запись в promo_code_usage должна существовать"
            assert usage_record.get('status') == 'applied', "Статус должен быть 'applied'"
            assert usage_record.get('discount_bonus') == 500.0, "Бонус в записи должен быть 500.0"

    @allure.story("Проверка, что промокод со статусом 'used' нельзя применить повторно")
    @allure.title("Промокод со статусом 'used' нельзя применить повторно")
    @allure.description("""
    Проверяет, что промокод со статусом 'used' (использован при покупке) нельзя применить повторно.
    
    **Что проверяется:**
    - Применение промокода со статусом 'applied'
    - Обновление статуса на 'used' (симуляция покупки)
    - Попытка повторного применения промокода
    - Возврат can_use: False для промокода со статусом 'used'
    
    **Тестовые данные:**
    - user_id: 123456901
    - promo_code: "USED_PROMO"
    - discount_bonus: 100.0
    
    **Ожидаемый результат:**
    Промокод со статусом 'used' нельзя применить повторно.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("deeplink", "promo_code", "used_status", "integration")
    def test_used_promo_code_cannot_be_reapplied(self, temp_db):
        """Тест, что промокод со статусом 'used' нельзя применить повторно"""
        
        with allure.step("Создание промокода"):
            promo_id = create_promo_code(
                code="USED_PROMO",
                bot="shop",
                vpn_plan_id=None,
                tariff_code=None,
                discount_amount=0.0,
                discount_percent=0.0,
                discount_bonus=100.0,
                usage_limit_per_bot=10,
                is_active=True
            )
        
        with allure.step("Создание пользователя"):
            user_id = 123456901
            register_user_if_not_exists(user_id, "test_used_promo", None, "Test Used Promo")
        
        with allure.step("Применение промокода со статусом 'applied'"):
            success = record_promo_code_usage(
                promo_id=promo_id,
                user_id=user_id,
                bot="shop",
                plan_id=None,
                discount_amount=0.0,
                discount_percent=0.0,
                discount_bonus=100.0,
                metadata={"source": "deep_link"},
                status='applied'
            )
            assert success is True
        
        with allure.step("Обновление статуса на 'used' (симуляция покупки)"):
            from shop_bot.data_manager.database import update_promo_usage_status, get_promo_usage_id
            usage_id = get_promo_usage_id(promo_id, user_id, "shop")
            assert usage_id is not None
            
            success = update_promo_usage_status(usage_id, plan_id=1)
            assert success is True
        
        with allure.step("Попытка повторного применения промокода со статусом 'used'"):
            validation_result = can_user_use_promo_code(user_id, "USED_PROMO", "shop")
            allure.attach(str(validation_result), "Результат валидации", allure.attachment_type.JSON)
            
            # Промокод со статусом 'used' нельзя применить повторно
            assert validation_result.get('can_use') is False, \
                "Промокод со статусом 'used' не должен быть доступен для повторного применения"
            assert 'уже использовали' in validation_result.get('message', '').lower(), \
                "Сообщение должно указывать, что промокод уже использован"

