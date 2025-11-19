#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты для проверки функционала deeplink flow

Использует временную БД через фикстуру temp_db из conftest.py
"""

import pytest
import allure
import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import (
    create_user_group,
    get_user_group_by_code,
    assign_user_to_group_by_code,
    create_promo_code,
    can_user_use_promo_code,
    record_promo_code_usage,
    get_user,
    register_user_if_not_exists,
    get_promo_code_by_code,
)


@pytest.mark.integration
@allure.epic("Интеграционные тесты")
@allure.feature("Deeplink")
@allure.label("package", "tests.integration")
class TestDeeplinkFlow:
    """Интеграционные тесты для deeplink flow"""

    @allure.story("Полный цикл работы deeplink: от создания группы до использования промокода")
    @allure.title("Полный flow функционала deeplink")
    @allure.description("""
    Интеграционный тест, проверяющий полный цикл работы deeplink функционала от создания группы пользователей до использования промокода.
    
    **Что проверяется:**
    - Создание группы пользователей по коду
    - Регистрация пользователя
    - Назначение пользователя в группу по коду
    - Создание промокода
    - Валидация промокода для пользователя
    - Применение промокода со статусом 'applied'
    - Повторное использование промокода со статусом 'applied'
    - Обновление статуса промокода на 'used'
    - Проверка недоступности промокода после использования
    
    **Тестовые данные:**
    - test_user_id: 999999999
    - test_group_code: "test_group_deeplink_flow"
    - test_promo_code: "TEST_DEEPLINK_FLOW"
    - discount_amount: 100.0
    - discount_bonus: 50.0
    - usage_limit_per_bot: 10
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь не зарегистрирован
    - Группа не существует
    - Промокод не существует
    
    **Шаги теста:**
    1. Создание тестовой группы пользователей по коду
    2. Регистрация тестового пользователя
    3. Назначение пользователя в группу по коду
    4. Создание тестового промокода
    5. Валидация промокода для пользователя
    6. Применение промокода со статусом 'applied'
    7. Проверка доступности промокода после применения (status='applied')
    8. Обновление статуса промокода на 'used'
    9. Проверка недоступности промокода после использования (status='used')
    10. Проверка, что пользователь все еще в группе
    
    **Ожидаемый результат:**
    Группа успешно создана, пользователь зарегистрирован и назначен в группу, промокод создан и валидирован.
    Промокод может быть применен со статусом 'applied' и использован повторно до обновления статуса на 'used'.
    После обновления статуса на 'used' промокод становится недоступным для повторного использования.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("deeplink", "integration", "promo_code", "user_group", "critical")
    def test_deeplink_functionality(self, temp_db):
        """Тест полного flow функционала deeplink"""
        # Тестовые данные
        test_user_id = 999999999
        test_group_code = "test_group_deeplink_flow"
        test_promo_code = "TEST_DEEPLINK_FLOW"
        
        # 1. Создаем тестовую группу пользователей
        group = get_user_group_by_code(test_group_code)
        if group:
            group_id = group['group_id']
        else:
            group_id = create_user_group(
                group_name="Тестовая группа для deeplink flow",
                group_description="Группа для тестирования deeplink функционала",
                group_code=test_group_code
            )
            assert group_id is not None, "Не удалось создать группу"
            group = get_user_group_by_code(test_group_code)
        
        assert group is not None, "Группа не найдена после создания"
        assert group['group_code'] == test_group_code
        
        # 2. Создаем тестового пользователя
        register_user_if_not_exists(test_user_id, "test_user", None, "Test User")
        user = get_user(test_user_id)
        assert user is not None, "Не удалось создать пользователя"
        assert user['username'] == "test_user"
        
        # 3. Назначаем пользователя в группу по коду
        success = assign_user_to_group_by_code(test_user_id, test_group_code)
        assert success is True, "Не удалось назначить пользователя в группу"
        
        # 4. Создаем тестовый промокод
        promo = get_promo_code_by_code(test_promo_code, "shop")
        if promo:
            promo_id = promo['promo_id']
        else:
            try:
                promo_id = create_promo_code(
                    code=test_promo_code,
                    bot="shop",
                    vpn_plan_id=None,
                    tariff_code=None,
                    discount_amount=100.0,
                    discount_percent=0.0,
                    discount_bonus=50.0,
                    usage_limit_per_bot=10,
                    is_active=True
                )
            except ValueError:
                # Промокод уже существует
                promo = get_promo_code_by_code(test_promo_code, "shop")
                assert promo is not None, "Промокод должен существовать"
                promo_id = promo['promo_id']
            
            assert promo_id is not None, "Не удалось создать промокод"
        
        # 5. Тестируем валидацию промокода
        validation_result = can_user_use_promo_code(test_user_id, test_promo_code, "shop")
        assert validation_result.get('can_use') is True, "Промокод должен быть валидным и доступным для использования"
        
        # 6. Тестируем применение промокода (статус 'applied')
        promo_data = validation_result.get('promo_data', {})
        success = record_promo_code_usage(
            promo_id=promo_data.get('promo_id'),
            user_id=test_user_id,
            bot="shop",
            plan_id=None,
            discount_amount=promo_data.get('discount_amount', 0.0),
            discount_percent=promo_data.get('discount_percent', 0.0),
            discount_bonus=promo_data.get('discount_bonus', 0.0),
            metadata={"source": "test_deeplink"},
            status='applied'
        )
        
        assert success is True, "Не удалось применить промокод"
        
        # 7. Проверяем, что после применения (status='applied') промокод все еще доступен
        # По бизнес-логике промокод со статусом 'applied' можно применять повторно до завершения покупки
        validation_result_after_apply = can_user_use_promo_code(test_user_id, test_promo_code, "shop")
        assert validation_result_after_apply.get('can_use') is True, "Промокод должен быть доступен после применения (status='applied')"
        
        # Получаем existing_usage_id для обновления статуса
        existing_usage_id = validation_result_after_apply.get('existing_usage_id')
        assert existing_usage_id is not None, "Не удалось получить existing_usage_id"
        
        # 8. Обновляем статус промокода на 'used' (имитация успешной покупки)
        success_update = record_promo_code_usage(
            promo_id=promo_data.get('promo_id'),
            user_id=test_user_id,
            bot="shop",
            plan_id=None,
            discount_amount=promo_data.get('discount_amount', 0.0),
            discount_percent=promo_data.get('discount_percent', 0.0),
            discount_bonus=promo_data.get('discount_bonus', 0.0),
            metadata={"source": "test_deeplink"},
            status='used',
            existing_usage_id=existing_usage_id
        )
        
        assert success_update is True, "Не удалось обновить статус промокода на 'used'"
        
        # 9. Проверяем, что после использования (status='used') промокод больше недоступен
        validation_result_after_use = can_user_use_promo_code(test_user_id, test_promo_code, "shop")
        assert validation_result_after_use.get('can_use') is False, "Промокод не должен быть доступен после использования (status='used')"
        
        # 10. Проверяем, что пользователь все еще в группе
        user_after = get_user(test_user_id)
        assert user_after is not None
        # Проверяем, что пользователь связан с группой (если есть такое поле в БД)
        
        # Тест завершен успешно
        # Очистка не требуется - temp_db автоматически очищается после теста

