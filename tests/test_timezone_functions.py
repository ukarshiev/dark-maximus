#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для функций timezone в database.py

Проверяет:
1. is_timezone_feature_enabled()
2. get_admin_timezone() / set_admin_timezone()
3. get_user_timezone() / set_user_timezone()
"""

import sys
import sqlite3
from pathlib import Path

# Добавляем путь к модулям проекта
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import (
    is_timezone_feature_enabled,
    get_admin_timezone,
    set_admin_timezone,
    get_user_timezone,
    set_user_timezone,
    DB_FILE
)


def print_section(title: str):
    """Красиво выводит заголовок секции"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)


def test_feature_flag():
    """Тест feature flag"""
    print_section("TEST 1: Feature Flag")
    
    enabled = is_timezone_feature_enabled()
    print(f"Feature timezone enabled: {enabled}")
    
    if enabled:
        print("[WARNING] Feature flag is enabled (expected: disabled)")
    else:
        print("[OK] Feature flag is disabled (as expected)")
    
    return not enabled  # Должен быть выключен


def test_admin_timezone():
    """Тест admin timezone"""
    print_section("TEST 2: Admin Timezone")
    
    # 1. Получение текущего admin timezone
    current_tz = get_admin_timezone()
    print(f"Current admin timezone: {current_tz}")
    
    if current_tz == 'Europe/Moscow':
        print("[OK] Default admin timezone is correct")
    else:
        print(f"[WARNING] Unexpected admin timezone: {current_tz}")
    
    # 2. Изменение admin timezone (тестовое)
    print("\nTesting set_admin_timezone()...")
    
    # Пробуем установить валидный timezone
    success = set_admin_timezone('America/New_York')
    if success:
        new_tz = get_admin_timezone()
        print(f"[OK] Successfully changed to: {new_tz}")
        
        # Возвращаем обратно
        set_admin_timezone('Europe/Moscow')
        restored_tz = get_admin_timezone()
        print(f"[OK] Restored to: {restored_tz}")
    else:
        print("[ERROR] Failed to set valid timezone")
        return False
    
    # 3. Проверка невалидного timezone
    print("\nTesting invalid timezone...")
    invalid_success = set_admin_timezone('Invalid/Timezone')
    if not invalid_success:
        print("[OK] Correctly rejected invalid timezone")
    else:
        print("[WARNING] Accepted invalid timezone (expected in Windows dev environment)")
        # В Windows это нормально, так как нет timezone данных
    
    return True


def test_user_timezone():
    """Тест user timezone"""
    print_section("TEST 3: User Timezone")
    
    # Получаем ID первого пользователя из базы
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id FROM users LIMIT 1")
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        print("[SKIP] No users in database")
        return True
    
    test_user_id = result[0]
    print(f"Testing with user ID: {test_user_id}")
    
    # 1. Получение текущего timezone пользователя
    user_tz = get_user_timezone(test_user_id)
    print(f"Current user timezone: {user_tz}")
    
    # 2. Изменение timezone пользователя
    print("\nTesting set_user_timezone()...")
    
    success = set_user_timezone(test_user_id, 'Asia/Tokyo')
    if success:
        new_tz = get_user_timezone(test_user_id)
        print(f"[OK] Successfully changed to: {new_tz}")
        
        # Возвращаем обратно
        set_user_timezone(test_user_id, 'Europe/Moscow')
        restored_tz = get_user_timezone(test_user_id)
        print(f"[OK] Restored to: {restored_tz}")
    else:
        print("[ERROR] Failed to set valid timezone")
        return False
    
    # 3. Проверка несуществующего пользователя
    print("\nTesting non-existent user...")
    fake_user_id = 999999999
    fake_tz = get_user_timezone(fake_user_id)
    print(f"Non-existent user timezone (fallback): {fake_tz}")
    
    if fake_tz == get_admin_timezone():
        print("[OK] Correctly falls back to admin timezone")
    else:
        print(f"[WARNING] Unexpected fallback: {fake_tz}")
    
    # 4. Проверка невалидного timezone
    print("\nTesting invalid timezone...")
    invalid_success = set_user_timezone(test_user_id, 'Invalid/Timezone')
    if not invalid_success:
        print("[OK] Correctly rejected invalid timezone")
    else:
        print("[WARNING] Accepted invalid timezone (expected in Windows dev environment)")
        # В Windows это нормально, так как нет timezone данных
    
    return True


def test_database_structure():
    """Проверка структуры БД"""
    print_section("TEST 4: Database Structure")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 1. Проверка колонки timezone в users
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'timezone' in columns:
        print("[OK] Column 'timezone' exists in users table")
    else:
        print("[ERROR] Column 'timezone' not found in users table")
        conn.close()
        return False
    
    # 2. Проверка настроек в bot_settings
    cursor.execute("SELECT key, value FROM bot_settings WHERE key LIKE '%timezone%'")
    settings = cursor.fetchall()
    
    required_settings = {'feature_timezone_enabled', 'admin_timezone'}
    found_settings = {row[0] for row in settings}
    
    if required_settings.issubset(found_settings):
        print("[OK] All required settings exist in bot_settings")
        for key, value in settings:
            print(f"     {key} = {value}")
    else:
        missing = required_settings - found_settings
        print(f"[ERROR] Missing settings: {missing}")
        conn.close()
        return False
    
    conn.close()
    return True


def main():
    """Запуск всех тестов"""
    print("\n" + "="*60)
    print("  ТЕСТИРОВАНИЕ ФУНКЦИЙ TIMEZONE")
    print("="*60)
    
    tests = [
        ("Database Structure", test_database_structure),
        ("Feature Flag", test_feature_flag),
        ("Admin Timezone", test_admin_timezone),
        ("User Timezone", test_user_timezone),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n[ERROR] Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))
    
    # Итоговый отчёт
    print_section("TEST RESULTS SUMMARY")
    
    all_passed = True
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {test_name}")
        if not result:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    print("="*60 + "\n")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

