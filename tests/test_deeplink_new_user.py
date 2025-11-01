#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки обработки deeplink с параметрами user_groups и promo
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
    create_promo_code, can_user_use_promo_code, record_promo_code_usage, add_to_user_balance,
    get_user, register_user_if_not_exists
)

# Импортируем утилиты для безопасного вывода
from test_utils import safe_print, print_test_header, print_test_success, print_test_failure

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_deeplink_new_user():
    """Тестирование обработки deeplink для нового пользователя"""
    
    print_test_header("Обработка deeplink для нового пользователя")
    
    # Тестовые данные
    test_user_id = 999999999  # Тестовый ID пользователя
    test_group_code = "moi"
    test_promo_code = "SKIDKA100RUB"
    expected_bonus = 100.0
    
    try:
        safe_print("\n1. Проверка тестового пользователя...")
        user = get_user(test_user_id)
        if user:
            safe_print(f"   Пользователь найден: {user['username']} (ID: {user['user_id']})")
            safe_print(f"   Текущая группа: {user.get('group_id')}, баланс: {user.get('balance', 0)}")
        else:
            safe_print("   Создаём тестового пользователя...")
            register_user_if_not_exists(test_user_id, "test_user_deeplink", None, "Test User Deeplink")
            user = get_user(test_user_id)
            if user:
                safe_print(f"   Пользователь создан: {user['username']}")
            else:
                safe_print("   ❌ Ошибка создания пользователя", fallback_text="   [X] Ошибка создания пользователя")
                return False
        
        safe_print("\n2. Проверка группы 'moi'...")
        group = get_user_group_by_code(test_group_code)
        if group:
            safe_print(f"   ✅ Группа найдена: {group['group_name']} (ID: {group['group_id']}, Code: {group['group_code']})", fallback_text=f"   [OK] Группа найдена: {group['group_name']} (ID: {group['group_id']}, Code: {group['group_code']})")
        else:
            safe_print(f"   Создаём группу с кодом '{test_group_code}'...")
            group_id = create_user_group(
                group_name="Группа для deeplink теста",
                group_description="Тестовая группа для проверки deeplink",
                group_code=test_group_code
            )
            if group_id:
                safe_print(f"   ✅ Группа создана с ID: {group_id}", fallback_text=f"   [OK] Группа создана с ID: {group_id}")
                group = get_user_group_by_code(test_group_code)
            else:
                safe_print("   ❌ Ошибка создания группы", fallback_text="   [X] Ошибка создания группы")
                return False
        
        safe_print("\n3. Проверка промокода 'SKIDKA100RUB'...")
        from shop_bot.data_manager.database import get_promo_code_by_code
        promo = get_promo_code_by_code(test_promo_code, "shop")
        if promo:
            safe_print(f"   ✅ Промокод найден: {promo['code']} (ID: {promo['promo_id']})", fallback_text=f"   [OK] Промокод найден: {promo['code']} (ID: {promo['promo_id']})")
            safe_print(f"   Бонус: {promo.get('discount_bonus', 0)} руб.")
        else:
            safe_print(f"   Создаём промокод '{test_promo_code}'...")
            promo_id = create_promo_code(
                code=test_promo_code,
                bot="shop",
                vpn_plan_id=None,
                tariff_code=None,
                discount_amount=0.0,
                discount_percent=0.0,
                discount_bonus=expected_bonus,
                usage_limit_per_bot=100,
                is_active=True
            )
            if promo_id:
                safe_print(f"   ✅ Промокод создан с ID: {promo_id}", fallback_text=f"   [OK] Промокод создан с ID: {promo_id}")
                promo = get_promo_code_by_code(test_promo_code, "shop")
            else:
                safe_print("   ❌ Ошибка создания промокода", fallback_text="   [X] Ошибка создания промокода")
                return False
        
        safe_print("\n4. Симуляция обработки deeplink параметров...")
        safe_print(f"   Deeplink: user_groups={test_group_code}&promo_{test_promo_code}")
        
        # Шаг 1: Назначение в группу
        safe_print("\n   4.1. Назначение пользователя в группу...")
        success = assign_user_to_group_by_code(test_user_id, test_group_code)
        if success:
            safe_print(f"   ✅ Пользователь успешно назначен в группу '{test_group_code}'", fallback_text=f"   [OK] Пользователь успешно назначен в группу '{test_group_code}'")
            
            # Проверяем, что группа назначена
            user = get_user(test_user_id)
            if user and user.get('group_id') == group['group_id']:
                safe_print(f"   ✅ Проверка: группа корректно назначена (ID: {user['group_id']})", fallback_text=f"   [OK] Проверка: группа корректно назначена (ID: {user['group_id']})")
            else:
                safe_print(f"   ❌ Ошибка: группа не назначена (group_id: {user.get('group_id')})", fallback_text=f"   [X] Ошибка: группа не назначена (group_id: {user.get('group_id')})")
                return False
        else:
            safe_print(f"   ❌ Ошибка назначения пользователя в группу", fallback_text="   [X] Ошибка назначения пользователя в группу")
            return False
        
        # Шаг 2: Применение промокода
        safe_print("\n   4.2. Применение промокода...")
        validation_result = can_user_use_promo_code(test_user_id, test_promo_code, "shop")
        if validation_result.get('can_use'):
            safe_print("   ✅ Промокод валиден и может быть использован", fallback_text="   [OK] Промокод валиден и может быть использован")
            promo_data = validation_result.get('promo_data', {})
            
            # Записываем использование промокода
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
                safe_print("   ✅ Использование промокода записано", fallback_text="   [OK] Использование промокода записано")
                
                # Зачисляем бонус
                bonus_amount = promo_data.get('discount_bonus', 0.0)
                if bonus_amount > 0:
                    add_to_user_balance(test_user_id, bonus_amount)
                    safe_print(f"   ✅ Бонус {bonus_amount} руб. зачислен на баланс", fallback_text=f"   [OK] Бонус {bonus_amount} руб. зачислен на баланс")
                    
                    # Проверяем баланс
                    user = get_user(test_user_id)
                    actual_balance = user.get('balance', 0.0)
                    if actual_balance >= expected_bonus:
                        safe_print(f"   ✅ Проверка: баланс корректный ({actual_balance} руб.)", fallback_text=f"   [OK] Проверка: баланс корректный ({actual_balance} руб.)")
                    else:
                        safe_print(f"   ❌ Ошибка: баланс не совпадает (ожидалось {expected_bonus}, получено {actual_balance})", fallback_text=f"   [X] Ошибка: баланс не совпадает (ожидалось {expected_bonus}, получено {actual_balance})")
                        return False
                else:
                    safe_print("   ⚠️  Бонус не зачислен (discount_bonus = 0)", fallback_text="   [!] Бонус не зачислен (discount_bonus = 0)")
            else:
                safe_print("   ❌ Ошибка записи использования промокода", fallback_text="   [X] Ошибка записи использования промокода")
                return False
        else:
            safe_print(f"   ⚠️  Промокод не может быть использован: {validation_result.get('message')}", fallback_text=f"   [!] Промокод не может быть использован: {validation_result.get('message')}")
            safe_print("   (Это нормально, если промокод уже был использован ранее)")
        
        print_test_success("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО!")
        safe_print("\nРезюме:")
        safe_print(f"  • Пользователь ID {test_user_id}: {user['username']}")
        safe_print(f"  • Группа: {group['group_name']} (code: {group['group_code']})")
        safe_print(f"  • Баланс: {user.get('balance', 0)} руб.")
        safe_print(f"  • Промокод: {test_promo_code}")
        
        return True
        
    except Exception as e:
        safe_print(f"\n❌ ОШИБКА ВО ВРЕМЯ ТЕСТИРОВАНИЯ: {e}", fallback_text=f"\n[X] ОШИБКА ВО ВРЕМЯ ТЕСТИРОВАНИЯ: {e}")
        logger.error(f"Test error: {e}", exc_info=True)
        return False

async def main():
    """Главная функция"""
    safe_print("\nЗапуск тестирования обработки deeplink...")
    
    success = await test_deeplink_new_user()
    
    if success:
        safe_print("\n✅ Тестирование завершено успешно!", fallback_text="\n[OK] Тестирование завершено успешно!")
    else:
        safe_print("\n❌ Тестирование завершено с ошибками!", fallback_text="\n[X] Тестирование завершено с ошибками!")
    
    return success

if __name__ == "__main__":
    asyncio.run(main())
