#!/usr/bin/env python3
"""
Тест для проверки исправления бага с редактированием групп пользователей.
Проверяет, что при редактировании существующей группы создается новая запись
вместо обновления существующей.
"""

import requests
import json
import sys
import os
from pathlib import Path

# Добавляем путь к модулям проекта
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tests"))

from shop_bot.data_manager.database import (
    get_all_user_groups, 
    create_user_group, 
    update_user_group,
    delete_user_group
)

# Импортируем утилиты для безопасного вывода
from test_utils import safe_print, print_test_header, print_test_success, print_test_failure

def test_group_edit_fix():
    """Тест исправления бага с редактированием групп"""
    print_test_header("Исправление бага с редактированием групп пользователей")
    
    # Получаем текущие группы
    groups_before = get_all_user_groups()
    initial_count = len(groups_before)
    safe_print(f"Начальное количество групп: {initial_count}")
    
    # Создаем тестовую группу
    test_group_name = "Тестовая группа для исправления"
    test_group_code = "test_fix_group"
    test_group_description = "Группа для тестирования исправления бага"
    
    safe_print(f"Создаем тестовую группу: {test_group_name}")
    success = create_user_group(test_group_name, test_group_description, test_group_code)
    
    if not success:
        safe_print("Ошибка создания тестовой группы")
        return False
    
    # Получаем ID созданной группы
    groups_after_create = get_all_user_groups()
    test_group = None
    for group in groups_after_create:
        if group['group_name'] == test_group_name:
            test_group = group
            break
    
    if not test_group:
        safe_print("Не удалось найти созданную тестовую группу")
        return False
    
    test_group_id = test_group['group_id']
    safe_print(f"Тестовая группа создана с ID: {test_group_id}")
    
    # Проверяем количество групп после создания
    groups_count_after_create = len(groups_after_create)
    safe_print(f"Количество групп после создания: {groups_count_after_create}")
    
    # Теперь редактируем группу (это должно обновить существующую, а не создать новую)
    updated_name = "Обновленная тестовая группа"
    updated_description = "Обновленное описание группы"
    updated_code = "updated_test_group"
    
    safe_print(f"Редактируем группу ID {test_group_id}: {updated_name}")
    success = update_user_group(test_group_id, updated_name, updated_description, updated_code)
    
    if not success:
        safe_print("Ошибка обновления группы")
        # Очищаем тестовые данные
        delete_user_group(test_group_id)
        return False
    
    # Получаем группы после обновления
    groups_after_update = get_all_user_groups()
    groups_count_after_update = len(groups_after_update)
    safe_print(f"Количество групп после обновления: {groups_count_after_update}")
    
    # Проверяем, что количество групп не изменилось (не создалась новая)
    if groups_count_after_update != groups_count_after_create:
        safe_print(f"БАГ НЕ ИСПРАВЛЕН! Количество групп изменилось с {groups_count_after_create} на {groups_count_after_update}")
        safe_print("   Это означает, что создается новая группа вместо обновления существующей")
        return False
    
    # Проверяем, что группа действительно обновилась
    updated_group = None
    for group in groups_after_update:
        if group['group_id'] == test_group_id:
            updated_group = group
            break
    
    if not updated_group:
        safe_print("Не удалось найти обновленную группу")
        return False
    
    # Проверяем, что данные действительно обновились
    if (updated_group['group_name'] != updated_name or 
        updated_group['group_description'] != updated_description or 
        updated_group['group_code'] != updated_code):
        safe_print("Данные группы не обновились корректно")
        safe_print(f"   Ожидалось: name={updated_name}, description={updated_description}, code={updated_code}")
        safe_print(f"   Получено: name={updated_group['group_name']}, description={updated_group['group_description']}, code={updated_group['group_code']}")
        return False
    
    safe_print("Данные группы обновились корректно")
    safe_print("Количество групп не изменилось - баг исправлен!")
    
    # Очищаем тестовые данные
    safe_print(f"Удаляем тестовую группу ID {test_group_id}")
    delete_user_group(test_group_id)
    
    # Проверяем финальное количество групп
    groups_final = get_all_user_groups()
    final_count = len(groups_final)
    safe_print(f"Финальное количество групп: {final_count}")
    
    if final_count != initial_count:
        safe_print(f"Внимание: Финальное количество групп ({final_count}) не совпадает с начальным ({initial_count})")
    
    print_test_success("Тест завершен успешно! Баг с редактированием групп исправлен.")
    return True

if __name__ == "__main__":
    try:
        success = test_group_edit_fix()
        if success:
            safe_print("\nВсе тесты прошли успешно!")
            sys.exit(0)
        else:
            safe_print("\nТесты не прошли!")
            sys.exit(1)
    except Exception as e:
        safe_print(f"\nОшибка во время выполнения тестов: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)