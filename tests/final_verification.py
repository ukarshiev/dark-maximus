#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Финальная проверка исправления промокода в deeplink"""

import sqlite3
import base64
import json

def check_database_structure():
    """Проверяем структуру базы данных"""
    print("=== ПРОВЕРКА СТРУКТУРЫ БАЗЫ ДАННЫХ ===")
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    try:
        # Проверяем структуру таблицы promo_code_usage
        cursor.execute("PRAGMA table_info(promo_code_usage)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"Columns in promo_code_usage: {columns}")
        
        # Проверяем ограничения уникальности
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='promo_code_usage'")
        table_sql = cursor.fetchone()[0]
        print(f"Table structure contains UNIQUE (promo_id, user_id, bot): {'UNIQUE (promo_id, user_id, bot)' in table_sql}")
        
        # Проверяем промокод SKIDKA100RUB
        cursor.execute("SELECT * FROM promo_codes WHERE code = 'SKIDKA100RUB'")
        promo = cursor.fetchone()
        if promo:
            promo_dict = dict(zip([desc[0] for desc in cursor.description], promo))
            print(f"Promo code SKIDKA100RUB: {promo_dict['code']} (ID: {promo_dict['promo_id']}, active: {promo_dict['is_active']}, bonus: {promo_dict['discount_bonus']})")
        else:
            print("ERROR: Promo code SKIDKA100RUB not found")
            return False
        
        # Проверяем группу moi
        cursor.execute("SELECT * FROM user_groups WHERE group_code = 'moi'")
        group = cursor.fetchone()
        if group:
            group_dict = dict(zip([desc[0] for desc in cursor.description], group))
            print(f"Group moi: {group_dict['group_name']} (ID: {group_dict['group_id']}, code: {group_dict['group_code']})")
        else:
            print("ERROR: Group 'moi' not found")
            return False
        
        return True
        
    finally:
        conn.close()

def test_deeplink_parsing():
    """Тестируем парсинг deeplink"""
    print("\n=== ТЕСТ ПАРСИНГА DEEPLINK ===")
    
    param = 'eyJnIjoibW9pIiwicCI6IlNLSURLQTEwMFJVQiJ9'
    
    try:
        padding = '=' * (4 - len(param) % 4) if len(param) % 4 else ''
        param_padded = param + padding
        decoded_bytes = base64.urlsafe_b64decode(param_padded)
        decoded_str = decoded_bytes.decode('utf-8')
        data = json.loads(decoded_str)
        
        group_code = data.get('g')
        promo_code = data.get('p')
        
        print(f"Decoded deeplink: group='{group_code}', promo='{promo_code}'")
        
        if group_code == 'moi' and promo_code == 'SKIDKA100RUB':
            print("SUCCESS: Deeplink parsing works correctly")
            return True
        else:
            print("ERROR: Deeplink parsing failed")
            return False
            
    except Exception as e:
        print(f"ERROR: Deeplink parsing failed: {e}")
        return False

def test_promo_usage_constraint():
    """Тестируем ограничение уникальности промокода"""
    print("\n=== ТЕСТ ОГРАНИЧЕНИЯ УНИКАЛЬНОСТИ ===")
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    try:
        # Тестовые пользователи
        user1 = 111111111
        user2 = 222222222
        
        # Очищаем тестовые данные
        cursor.execute("DELETE FROM promo_code_usage WHERE user_id IN (?, ?)", (user1, user2))
        cursor.execute("DELETE FROM users WHERE telegram_id IN (?, ?)", (user1, user2))
        
        # Тест 1: Первый пользователь может использовать промокод
        print("Test 1: First user can use promo code")
        cursor.execute('''
            INSERT INTO promo_code_usage (
                promo_id, user_id, bot, plan_id,
                discount_amount, discount_percent, discount_bonus, 
                metadata, used_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        ''', (23, user1, 'shop', None, 0.0, 0.0, 100.0, '{"test": "user1"}', 'applied'))
        
        print("SUCCESS: First user can use promo code")
        
        # Тест 2: Второй пользователь может использовать тот же промокод
        print("Test 2: Second user can use same promo code")
        cursor.execute('''
            INSERT INTO promo_code_usage (
                promo_id, user_id, bot, plan_id,
                discount_amount, discount_percent, discount_bonus, 
                metadata, used_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        ''', (23, user2, 'shop', None, 0.0, 0.0, 100.0, '{"test": "user2"}', 'applied'))
        
        print("SUCCESS: Second user can use same promo code")
        
        # Тест 3: Первый пользователь НЕ может использовать промокод повторно
        print("Test 3: First user cannot use promo code again")
        try:
            cursor.execute('''
                INSERT INTO promo_code_usage (
                    promo_id, user_id, bot, plan_id,
                    discount_amount, discount_percent, discount_bonus, 
                    metadata, used_at, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            ''', (23, user1, 'shop', None, 0.0, 0.0, 100.0, '{"test": "user1_duplicate"}', 'applied'))
            print("ERROR: First user was able to use promo code again (should fail)")
            return False
        except sqlite3.IntegrityError:
            print("SUCCESS: First user cannot use promo code again (correctly blocked)")
        
        conn.commit()
        
        # Очищаем тестовые данные
        cursor.execute("DELETE FROM promo_code_usage WHERE user_id IN (?, ?)", (user1, user2))
        cursor.execute("DELETE FROM users WHERE telegram_id IN (?, ?)", (user1, user2))
        conn.commit()
        
        print("SUCCESS: All constraint tests passed")
        return True
        
    except Exception as e:
        print(f"ERROR: Constraint test failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def check_migration_status():
    """Проверяем статус миграции"""
    print("\n=== ПРОВЕРКА СТАТУСА МИГРАЦИИ ===")
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT migration_id FROM migration_history WHERE migration_id = 'promo_code_usage_fix_unique_constraint'")
        migration = cursor.fetchone()
        
        if migration:
            print("SUCCESS: Migration 'promo_code_usage_fix_unique_constraint' has been applied")
            return True
        else:
            print("ERROR: Migration 'promo_code_usage_fix_unique_constraint' has not been applied")
            return False
            
    finally:
        conn.close()

def main():
    print("ФИНАЛЬНАЯ ПРОВЕРКА ИСПРАВЛЕНИЯ ПРОМОКОДА В DEEPLINK")
    print("=" * 60)
    
    tests = [
        ("Database Structure", check_database_structure),
        ("Deeplink Parsing", test_deeplink_parsing),
        ("Migration Status", check_migration_status),
        ("Promo Usage Constraint", test_promo_usage_constraint),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"ERROR: {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ ПРОВЕРКИ:")
    print("=" * 60)
    
    all_passed = True
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        print("Исправление промокода в deeplink работает корректно")
    else:
        print("НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")
        print("Требуется дополнительная настройка")
    
    return all_passed

if __name__ == "__main__":
    main()
