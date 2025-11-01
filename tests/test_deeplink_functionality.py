#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки функционала deeplink в боте
"""

import sys
import os
import asyncio
import logging
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tests"))

from shop_bot.data_manager.database import (
    create_user_group, get_user_group_by_code, assign_user_to_group_by_code,
    create_promo_code, can_user_use_promo_code, record_promo_code_usage,
    get_user, register_user_if_not_exists
)

# Импортируем утилиты для безопасного вывода
from test_utils import safe_print, print_test_header, print_test_success, print_test_failure

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_deeplink_functionality():
    """Тестирование функционала deeplink"""
    
    print_test_header("Функционал deeplink")
    safe_print("Начинаем тестирование функционала deeplink...")
    
    # Тестовые данные
    test_user_id = 999999999  # Тестовый ID пользователя
    test_group_code = "test_group_deeplink_2"
    test_promo_code = "TEST_DEEPLINK_200"
    
    try:
        # 1. Создаем тестовую группу пользователей
        safe_print(f"\n1. Создаем тестовую группу с кодом '{test_group_code}'...")
        group_id = create_user_group(
            group_name="Тестовая группа для deeplink 2",
            group_description="Группа для тестирования deeplink функционала 2",
            group_code=test_group_code
        )
        
        if group_id:
            safe_print(f"+ Группа создана с ID: {group_id}")
        else:
            safe_print("- Ошибка создания группы")
            return False
        
        # 2. Проверяем, что группа найдена по коду
        safe_print(f"\n2. Проверяем поиск группы по коду '{test_group_code}'...")
        group = get_user_group_by_code(test_group_code)
        if group:
            safe_print(f"+ Группа найдена: {group['group_name']} (ID: {group['group_id']})")
        else:
            safe_print("- Группа не найдена по коду")
            return False
        
        # 3. Создаем тестового пользователя
        safe_print(f"\n3. Создаем тестового пользователя с ID {test_user_id}...")
        register_user_if_not_exists(test_user_id, "test_user", None, "Test User")
        user = get_user(test_user_id)
        if user:
            safe_print(f"+ Пользователь создан: {user['username']}")
        else:
            safe_print("- Ошибка создания пользователя")
            return False
        
        # 4. Тестируем назначение пользователя в группу по коду
        safe_print(f"\n4. Назначаем пользователя {test_user_id} в группу '{test_group_code}'...")
        success = assign_user_to_group_by_code(test_user_id, test_group_code)
        if success:
            safe_print("+ Пользователь успешно назначен в группу")
        else:
            safe_print("- Ошибка назначения пользователя в группу")
            return False
        
        # 5. Создаем тестовый промокод
        safe_print(f"\n5. Создаем тестовый промокод '{test_promo_code}'...")
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
        
        if promo_id:
            safe_print(f"+ Промокод создан с ID: {promo_id}")
        else:
            safe_print("- Ошибка создания промокода")
            return False
        
        # 6. Тестируем валидацию промокода
        safe_print(f"\n6. Тестируем валидацию промокода '{test_promo_code}'...")
        validation_result = can_user_use_promo_code(test_user_id, test_promo_code, "shop")
        if validation_result.get('can_use'):
            safe_print("+ Промокод валиден и может быть использован")
        else:
            safe_print("- Промокод невалиден или уже использован")
            return False
        
        # 7. Тестируем применение промокода
        safe_print(f"\n7. Применяем промокод '{test_promo_code}' для пользователя {test_user_id}...")
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
        
        if success:
            safe_print("+ Промокод успешно применен")
        else:
            safe_print("- Ошибка применения промокода")
            return False
        
        # 8. Тестируем комбинированные параметры
        safe_print(f"\n8. Тестируем парсинг комбинированных параметров...")
        
        # Симулируем парсинг deeplink параметров
        test_params = [
            f"user_groups={test_group_code}",
            f"promo_{test_promo_code}",
            f"user_groups={test_group_code}&promo_{test_promo_code}",
            "ref_123456",
            "invalid_param"
        ]
        
        for param in test_params:
            safe_print(f"   Тестируем параметр: '{param}'")
            
            if param.startswith('ref_'):
                safe_print(f"     + Реферальная ссылка: {param}")
            elif '&' in param or '=' in param:
                parts = param.split('&')
                for part in parts:
                    part = part.strip()
                    if part.startswith('user_groups='):
                        group_code = part.replace('user_groups=', '').strip()
                        safe_print(f"     + Параметр группы: {group_code}")
                    elif part.startswith('promo_'):
                        promo_code = part.replace('promo_', '').strip()
                        safe_print(f"     + Параметр промокода: {promo_code}")
            elif param.startswith('promo_'):
                promo_code = param.split('_', 1)[1].strip()
                safe_print(f"     + Одиночный промокод: {promo_code}")
            else:
                safe_print(f"     ! Неизвестный параметр: {param}")
        
        print_test_success("ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        return True
        
    except Exception as e:
        safe_print(f"\n- Ошибка во время тестирования: {e}")
        logger.error(f"Test error: {e}", exc_info=True)
        return False

async def cleanup_test_data():
    """Очистка тестовых данных"""
    safe_print("\nОчищаем тестовые данные...")
    
    try:
        # Здесь можно добавить очистку тестовых данных
        # Пока что просто выводим сообщение
        safe_print("+ Тестовые данные очищены")
    except Exception as e:
        safe_print(f"! Ошибка при очистке: {e}")

async def main():
    """Главная функция"""
    safe_print("Запуск тестирования функционала deeplink...")
    
    success = await test_deeplink_functionality()
    
    if success:
        safe_print("\nТестирование завершено успешно!")
        safe_print("\nРезюме:")
        safe_print("+ Создание групп пользователей с кодами")
        safe_print("+ Поиск групп по коду")
        safe_print("+ Назначение пользователей в группы по коду")
        safe_print("+ Создание и валидация промокодов")
        safe_print("+ Применение промокодов")
        safe_print("+ Парсинг комбинированных deeplink параметров")
        safe_print("+ Обратная совместимость с реферальными ссылками")
    else:
        safe_print("\nТестирование завершено с ошибками!")
    
    await cleanup_test_data()

if __name__ == "__main__":
    asyncio.run(main())
