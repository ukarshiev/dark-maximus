#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E2E тесты для проверки полного сценария многократного применения промокода

Тестирует полный пользовательский сценарий от перехода по deeplink ссылке
до проверки баланса после повторного перехода.
"""

import pytest
import allure
import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import (
    register_user_if_not_exists,
    create_promo_code,
    can_user_use_promo_code,
    record_promo_code_usage,
    get_user_balance,
    add_to_user_balance,
    get_user,
)


@pytest.mark.e2e
@allure.epic("E2E тесты")
@allure.feature("Пользовательские сценарии")
@allure.label("package", "tests.e2e.test_user_scenarios")
class TestPromoCodeReapplication:
    """E2E тесты для полного сценария многократного применения промокода"""

    @allure.story("Полный сценарий: переход по deeplink → проверка баланса → повторный переход → баланс не изменился")
    @allure.title("E2E: Пользователь многократно переходит по deeplink ссылке с промокодом")
    @allure.description("""
    E2E тест, проверяющий полный пользовательский сценарий многократного перехода по deeplink ссылке с промокодом.
    
    **Сценарий:**
    1. Новый пользователь переходит по deeplink ссылке с промокодом (например, реферальная ссылка)
    2. Пользователь регистрируется в системе
    3. Промокод автоматически применяется, бонус начисляется на баланс
    4. Пользователь проверяет свой баланс (должен быть 500 RUB)
    5. Пользователь повторно переходит по той же deeplink ссылке (например, случайно)
    6. Промокод обновляется, но бонус НЕ начисляется повторно
    7. Пользователь проверяет свой баланс (должен остаться 500 RUB)
    
    **Что проверяется:**
    - Регистрация нового пользователя
    - Автоматическое применение промокода при переходе по deeplink ссылке
    - Начисление бонуса на баланс при первом применении
    - Отсутствие повторного начисления бонуса при повторном переходе
    - Корректность баланса пользователя на каждом этапе
    
    **Тестовые данные:**
    - user_id: 123456950
    - promo_code: "E2E_DEEPLINK"
    - discount_bonus: 500.0
    - deeplink_url: https://t.me/bot?start=eyJwIjoiRTJFX0RFRVBMSU5LIn0=
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Промокод создан и активен
    
    **Ожидаемый результат:**
    Бонус начислен только при первом переходе по deeplink ссылке.
    При повторном переходе баланс остается без изменений.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("e2e", "deeplink", "promo_code", "bonus", "user_scenario", "critical")
    def test_user_promo_code_deeplink_reapplication(self, temp_db):
        """E2E тест: пользователь многократно переходит по deeplink ссылке с промокодом"""
        
        # ========== ПОДГОТОВКА ==========
        with allure.step("Подготовка: создание промокода с бонусом 500 RUB"):
            promo_id = create_promo_code(
                code="E2E_DEEPLINK",
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
            allure.attach("https://t.me/bot?start=eyJwIjoiRTJFX0RFRVBMSU5LIn0=", "Deeplink URL", allure.attachment_type.TEXT)
        
        # ========== ШАГ 1: ПЕРВЫЙ ПЕРЕХОД ПО DEEPLINK ССЫЛКЕ ==========
        with allure.step("ШАГ 1: Новый пользователь переходит по deeplink ссылке"):
            user_id = 123456950
            username = "e2e_test_user"
            fullname = "E2E Test User"
            
            with allure.step("1.1. Регистрация нового пользователя"):
                register_user_if_not_exists(user_id, username, None, fullname)
                user_data = get_user(user_id)
                assert user_data is not None, "Пользователь должен быть зарегистрирован"
                allure.attach(str(user_data), "Данные пользователя", allure.attachment_type.JSON)
            
            with allure.step("1.2. Проверка начального баланса"):
                initial_balance = get_user_balance(user_id)
                allure.attach(str(initial_balance), "Начальный баланс", allure.attachment_type.TEXT)
                assert initial_balance == 0.0, "Начальный баланс нового пользователя должен быть 0"
            
            with allure.step("1.3. Парсинг deeplink параметров (симуляция)"):
                # В реальном коде это делается в start_handler через parse_deeplink
                promo_code = "E2E_DEEPLINK"
                allure.attach(promo_code, "Промокод из deeplink", allure.attachment_type.TEXT)
            
            with allure.step("1.4. Проверка возможности использования промокода"):
                validation_result = can_user_use_promo_code(user_id, promo_code, "shop")
                allure.attach(str(validation_result), "Результат валидации", allure.attachment_type.JSON)
                
                assert validation_result.get('can_use') is True, "Промокод должен быть доступен для использования"
                promo_data = validation_result.get('promo_data')
                existing_usage_id = validation_result.get('existing_usage_id')
                
                assert existing_usage_id is None, "При первом применении existing_usage_id должен быть None"
            
            with allure.step("1.5. Применение промокода со статусом 'applied'"):
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
            
            with allure.step("1.6. Начисление бонуса на баланс (ТОЛЬКО если existing_usage_id отсутствует)"):
                bonus_amount = promo_data.get('discount_bonus', 0.0)
                
                # КРИТИЧЕСКАЯ ЛОГИКА: Бонус начисляется ТОЛЬКО если existing_usage_id отсутствует
                if not existing_usage_id and bonus_amount > 0:
                    add_to_user_balance(user_id, bonus_amount)
                    allure.attach(f"✅ Бонус {bonus_amount} RUB начислен на баланс", "Начисление бонуса", allure.attachment_type.TEXT)
                else:
                    allure.attach("❌ Бонус НЕ начислен (existing_usage_id присутствует)", "Начисление бонуса", allure.attachment_type.TEXT)
        
        # ========== ШАГ 2: ПРОВЕРКА БАЛАНСА ПОСЛЕ ПЕРВОГО ПЕРЕХОДА ==========
        with allure.step("ШАГ 2: Пользователь проверяет свой баланс"):
            balance_after_first = get_user_balance(user_id)
            allure.attach(str(balance_after_first), "Баланс после первого перехода", allure.attachment_type.TEXT)
            
            assert balance_after_first == 500.0, \
                f"Баланс должен быть 500 RUB после первого перехода. Получено: {balance_after_first}"
            
            allure.attach("✅ Баланс корректен: 500 RUB", "Результат проверки", allure.attachment_type.TEXT)
        
        # ========== ШАГ 3: ПОВТОРНЫЙ ПЕРЕХОД ПО DEEPLINK ССЫЛКЕ ==========
        with allure.step("ШАГ 3: Пользователь повторно переходит по той же deeplink ссылке"):
            with allure.step("3.1. Парсинг deeplink параметров (та же ссылка)"):
                promo_code = "E2E_DEEPLINK"
                allure.attach(promo_code, "Промокод из deeplink (повторный)", allure.attachment_type.TEXT)
            
            with allure.step("3.2. Проверка возможности использования промокода (должен вернуть existing_usage_id)"):
                validation_result = can_user_use_promo_code(user_id, promo_code, "shop")
                allure.attach(str(validation_result), "Результат валидации (повторный)", allure.attachment_type.JSON)
                
                assert validation_result.get('can_use') is True, "Промокод должен быть доступен для обновления"
                promo_data = validation_result.get('promo_data')
                existing_usage_id = validation_result.get('existing_usage_id')
                
                assert existing_usage_id is not None, "При повторном применении existing_usage_id должен присутствовать"
                allure.attach(str(existing_usage_id), "existing_usage_id (повторный)", allure.attachment_type.TEXT)
            
            with allure.step("3.3. Обновление записи промокода (без начисления бонуса)"):
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
            
            with allure.step("3.4. НЕ начисляем бонус повторно (existing_usage_id присутствует)"):
                bonus_amount = promo_data.get('discount_bonus', 0.0)
                
                # КРИТИЧЕСКАЯ ЛОГИКА: Бонус НЕ начисляется, если existing_usage_id присутствует
                if not existing_usage_id and bonus_amount > 0:
                    add_to_user_balance(user_id, bonus_amount)
                    allure.attach(f"✅ Бонус {bonus_amount} RUB начислен на баланс", "Начисление бонуса", allure.attachment_type.TEXT)
                else:
                    allure.attach("✅ Бонус НЕ начислен повторно (existing_usage_id присутствует)", "Начисление бонуса", allure.attachment_type.TEXT)
        
        # ========== ШАГ 4: ПРОВЕРКА БАЛАНСА ПОСЛЕ ПОВТОРНОГО ПЕРЕХОДА ==========
        with allure.step("ШАГ 4: Пользователь проверяет свой баланс (должен остаться без изменений)"):
            balance_after_second = get_user_balance(user_id)
            allure.attach(str(balance_after_second), "Баланс после повторного перехода", allure.attachment_type.TEXT)
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА
            assert balance_after_second == 500.0, \
                f"Баланс НЕ должен измениться при повторном переходе по deeplink ссылке. " \
                f"Ожидалось: 500.0, получено: {balance_after_second}"
            
            allure.attach("✅ Баланс остался без изменений: 500 RUB", "Результат проверки", allure.attachment_type.TEXT)
        
        # ========== ФИНАЛЬНАЯ ПРОВЕРКА ==========
        with allure.step("ФИНАЛЬНАЯ ПРОВЕРКА: Сравнение балансов"):
            allure.attach(
                f"Баланс после первого перехода: {balance_after_first} RUB\n"
                f"Баланс после повторного перехода: {balance_after_second} RUB\n"
                f"Разница: {balance_after_second - balance_after_first} RUB",
                "Сравнение балансов",
                allure.attachment_type.TEXT
            )
            
            assert balance_after_first == balance_after_second, \
                "Баланс не должен измениться при повторном переходе по deeplink ссылке"
            
            allure.attach("✅ ТЕСТ ПРОЙДЕН: Бонус начислен только один раз", "Результат теста", allure.attachment_type.TEXT)

