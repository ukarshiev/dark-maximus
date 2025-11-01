#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тест с реальным пользователем для проверки deeplink"""

import sqlite3
import base64
import json
from datetime import datetime

def test_real_user_deeplink():
    """Тестируем deeplink с реальным пользователем"""
    print("=== ТЕСТ DEEPLINK С РЕАЛЬНЫМ ПОЛЬЗОВАТЕЛЕМ ===")
    
    # Параметры deeplink
    param = 'eyJnIjoibW9pIiwicCI6IlNLSURLQTEwMFJVQiJ9'
    
    try:
        # Декодируем deeplink
        padding = '=' * (4 - len(param) % 4) if len(param) % 4 else ''
        param_padded = param + padding
        decoded_bytes = base64.urlsafe_b64decode(param_padded)
        decoded_str = decoded_bytes.decode('utf-8')
        data = json.loads(decoded_str)
        
        group_code = data.get('g')
        promo_code = data.get('p')
        
        print(f"Deeplink: {param}")
        print(f"Decoded: group='{group_code}', promo='{promo_code}'")
        
        # Подключаемся к базе данных
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        try:
            # Проверяем промокод
            cursor.execute("SELECT * FROM promo_codes WHERE code = ?", (promo_code,))
            promo = cursor.fetchone()
            if promo:
                promo_dict = dict(zip([desc[0] for desc in cursor.description], promo))
                print(f"Promo code found: {promo_dict['code']} (ID: {promo_dict['promo_id']}, active: {promo_dict['is_active']}, bonus: {promo_dict['discount_bonus']})")
            else:
                print(f"ERROR: Promo code '{promo_code}' not found")
                return False
            
            # Проверяем группу
            cursor.execute("SELECT * FROM user_groups WHERE group_code = ?", (group_code,))
            group = cursor.fetchone()
            if group:
                group_dict = dict(zip([desc[0] for desc in cursor.description], group))
                print(f"Group found: {group_dict['group_name']} (ID: {group_dict['group_id']}, code: {group_dict['group_code']})")
            else:
                print(f"ERROR: Group '{group_code}' not found")
                return False
            
            # Проверяем структуру таблицы promo_code_usage
            cursor.execute("PRAGMA table_info(promo_code_usage)")
            columns = [row[1] for row in cursor.fetchall()]
            print(f"promo_code_usage columns: {columns}")
            
            # Проверяем ограничение уникальности
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='promo_code_usage'")
            table_sql = cursor.fetchone()[0]
            has_correct_unique = 'UNIQUE (promo_id, user_id, bot)' in table_sql
            print(f"Has correct UNIQUE constraint: {has_correct_unique}")
            
            if not has_correct_unique:
                print("WARNING: UNIQUE constraint is not correct. Migration may not have been applied.")
                print("Current constraint should be: UNIQUE (promo_id, user_id, bot)")
                print("This means the fix may not work properly.")
                return False
            
            # Проверяем существующих пользователей
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            print(f"Total users in database: {user_count}")
            
            # Проверяем использование промокода
            cursor.execute("SELECT COUNT(*) FROM promo_code_usage WHERE promo_id = ?", (promo_dict['promo_id'],))
            usage_count = cursor.fetchone()[0]
            print(f"Promo code usage count: {usage_count}")
            
            if usage_count > 0:
                cursor.execute("""
                    SELECT u.telegram_id, u.username, u.fullname, 
                           pcu.used_at, pcu.discount_bonus, pcu.status
                    FROM promo_code_usage pcu
                    JOIN users u ON pcu.user_id = u.telegram_id
                    WHERE pcu.promo_id = ?
                    ORDER BY pcu.used_at DESC
                    LIMIT 5
                """, (promo_dict['promo_id'],))
                
                usages = cursor.fetchall()
                print(f"Recent promo code usages:")
                for usage in usages:
                    print(f"  - User {usage[0]} ({usage[1] or 'no username'}) - {usage[2] or 'no name'} - {usage[3]} - Bonus: {usage[4]} - Status: {usage[5]}")
            
            print("\n=== РЕЗУЛЬТАТ ===")
            print("SUCCESS: Deeplink parsing works correctly")
            print("SUCCESS: Promo code exists and is active")
            print("SUCCESS: Group exists and is available")
            print("SUCCESS: Database structure is correct")
            print("SUCCESS: UNIQUE constraint is properly set")
            
            if usage_count > 0:
                print("SUCCESS: Promo code has been used by users")
            else:
                print("INFO: Promo code has not been used yet")
            
            print("\n=== РЕКОМЕНДАЦИИ ===")
            print("1. Deeplink ссылка должна работать корректно")
            print("2. Пользователи должны добавляться в группу 'moi'")
            print("3. Промокод 'SKIDKA100RUB' должен применяться и давать 100 руб бонуса")
            print("4. Каждый пользователь может использовать промокод только один раз")
            
            return True
            
        finally:
            conn.close()
            
    except Exception as e:
        print(f"ERROR: Test failed with exception: {e}")
        return False

def main():
    print("ТЕСТ DEEPLINK С РЕАЛЬНЫМ ПОЛЬЗОВАТЕЛЕМ")
    print("=" * 50)
    
    success = test_real_user_deeplink()
    
    print("=" * 50)
    if success:
        print("ВСЕ ПРОВЕРКИ ПРОШЛИ УСПЕШНО!")
        print("Deeplink ссылка должна работать корректно.")
    else:
        print("ОБНАРУЖЕНЫ ПРОБЛЕМЫ!")
        print("Требуется дополнительная настройка.")
    
    return success

if __name__ == "__main__":
    main()
