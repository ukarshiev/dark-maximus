#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Симуляция нового пользователя для тестирования deeplink"""

import sqlite3
import base64
import json

def simulate_new_user_deeplink():
    """Симулируем обработку deeplink для нового пользователя"""
    
    # Новый тестовый пользователь
    new_user_id = 111222333
    username = "test_new_user"
    full_name = "Test New User"
    
    # Параметры deeplink
    deeplink_param = 'eyJnIjoibW9pIiwicCI6IlNLSURLQTEwMFJVQiJ9'
    
    print(f"Simulating new user {new_user_id} with deeplink: {deeplink_param}")
    
    # Декодируем deeplink
    try:
        padding = '=' * (4 - len(deeplink_param) % 4) if len(deeplink_param) % 4 else ''
        param_padded = deeplink_param + padding
        decoded_bytes = base64.urlsafe_b64decode(param_padded)
        decoded_str = decoded_bytes.decode('utf-8')
        data = json.loads(decoded_str)
        
        group_code = data.get('g')
        promo_code = data.get('p')
        
        print(f"Decoded: group='{group_code}', promo='{promo_code}'")
        
    except Exception as e:
        print(f"Error decoding deeplink: {e}")
        return False
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    try:
        # 1. Регистрируем пользователя
        print(f"\n1. Registering user {new_user_id}...")
        cursor.execute('''
            INSERT OR REPLACE INTO users 
            (telegram_id, username, registration_date, group_id)
            VALUES (?, ?, CURRENT_TIMESTAMP, 
                (SELECT group_id FROM user_groups WHERE group_code = 'gost' LIMIT 1))
        ''', (new_user_id, username))
        
        print(f"User {new_user_id} registered")
        
        # 2. Назначаем группу
        if group_code:
            print(f"\n2. Assigning user to group '{group_code}'...")
            cursor.execute('''
                SELECT group_id FROM user_groups WHERE group_code = ?
            ''', (group_code,))
            
            group_result = cursor.fetchone()
            if group_result:
                group_id = group_result[0]
                cursor.execute('''
                    UPDATE users SET group_id = ? WHERE telegram_id = ?
                ''', (group_id, new_user_id))
                print(f"User assigned to group {group_id} (code: {group_code})")
            else:
                print(f"Group with code '{group_code}' not found")
        
        # 3. Применяем промокод
        if promo_code:
            print(f"\n3. Applying promo code '{promo_code}'...")
            
            # Получаем промокод
            cursor.execute('''
                SELECT * FROM promo_codes 
                WHERE code = ? AND is_active = 1
            ''', (promo_code,))
            
            promo = cursor.fetchone()
            if not promo:
                print(f"Promo code '{promo_code}' not found or inactive")
                return False
            
            promo_dict = dict(zip([desc[0] for desc in cursor.description], promo))
            promo_id = promo_dict['promo_id']
            
            print(f"Promo code found: {promo_dict['code']} (ID: {promo_id})")
            
            # Проверяем, может ли пользователь использовать промокод
            cursor.execute('''
                SELECT COUNT(*) as usage_count
                FROM promo_code_usage 
                WHERE promo_id = ? AND user_id = ? AND bot = ? AND status = 'used'
            ''', (promo_id, new_user_id, 'shop'))
            
            usage_result = cursor.fetchone()
            if usage_result and usage_result[0] > 0:
                print("User already used this promo code")
                return False
            
            # Записываем использование промокода
            cursor.execute('''
                INSERT INTO promo_code_usage (
                    promo_id, user_id, bot, plan_id,
                    discount_amount, discount_percent, discount_bonus, 
                    metadata, used_at, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            ''', (
                promo_id,
                new_user_id,
                'shop',
                None,
                promo_dict['discount_amount'],
                promo_dict['discount_percent'],
                promo_dict['discount_bonus'],
                '{"source": "simulated_deeplink"}',
                'applied'
            ))
            
            # Зачисляем бонус на баланс
            bonus_amount = promo_dict['discount_bonus']
            if bonus_amount > 0:
                cursor.execute('''
                    UPDATE users SET balance = COALESCE(balance, 0) + ? 
                    WHERE telegram_id = ?
                ''', (bonus_amount, new_user_id))
                print(f"Added {bonus_amount} RUB bonus to user balance")
            
            print(f"Promo code '{promo_code}' applied successfully")
        
        conn.commit()
        
        # 4. Проверяем результат
        print(f"\n4. Checking results...")
        
        # Баланс
        cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (new_user_id,))
        balance = cursor.fetchone()[0] or 0.0
        print(f"User balance: {balance} RUB")
        
        # Группа
        cursor.execute('''
            SELECT ug.group_name, ug.group_code
            FROM users u
            JOIN user_groups ug ON u.group_id = ug.group_id
            WHERE u.telegram_id = ?
        ''', (new_user_id,))
        
        group_info = cursor.fetchone()
        if group_info:
            print(f"User group: {group_info[0]} (code: {group_info[1]})")
        
        # Использование промокода
        cursor.execute('''
            SELECT status, discount_bonus, used_at
            FROM promo_code_usage 
            WHERE user_id = ? AND promo_id = ?
        ''', (new_user_id, promo_id))
        
        promo_usage = cursor.fetchone()
        if promo_usage:
            print(f"Promo usage: {promo_usage[0]} (bonus: {promo_usage[1]}) at {promo_usage[2]}")
        
        # Очищаем тестовые данные
        print(f"\n5. Cleaning up test data...")
        cursor.execute("DELETE FROM promo_code_usage WHERE user_id = ?", (new_user_id,))
        cursor.execute("DELETE FROM users WHERE telegram_id = ?", (new_user_id,))
        conn.commit()
        print("Test data cleaned up")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("Simulating new user deeplink processing...")
    success = simulate_new_user_deeplink()
    print(f"\nSimulation result: {'SUCCESS' if success else 'FAILED'}")
