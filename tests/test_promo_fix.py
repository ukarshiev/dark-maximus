#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тест исправления промокода в deeplink"""

import sqlite3
import base64
import json

def test_promo_code_usage():
    """Тестируем, что промокод может быть использован разными пользователями"""
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # Проверяем структуру таблицы
    cursor.execute("PRAGMA table_info(promo_code_usage)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"Columns in promo_code_usage: {columns}")
    
    # Проверяем ограничения уникальности
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='promo_code_usage'")
    table_sql = cursor.fetchone()[0]
    print(f"Table structure:\n{table_sql}")
    
    # Проверяем существующие записи
    cursor.execute("SELECT * FROM promo_code_usage WHERE promo_id=23")
    existing_records = cursor.fetchall()
    print(f"Existing records for promo_id=23: {len(existing_records)}")
    for record in existing_records:
        print(f"  {record}")
    
    # Тестируем вставку записи для нового пользователя
    test_user_id = 123456789
    try:
        cursor.execute('''
            INSERT INTO promo_code_usage (
                promo_id, user_id, bot, plan_id,
                discount_amount, discount_percent, discount_bonus, 
                metadata, used_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        ''', (
            23,  # promo_id для SKIDKA100RUB
            test_user_id,
            'shop',
            None,
            0.0,
            0.0,
            100.0,
            '{"source": "test_fix"}',
            'applied'
        ))
        conn.commit()
        print(f"SUCCESS: Successfully inserted record for user {test_user_id}")
        
        # Проверяем, что запись действительно добавилась
        cursor.execute("SELECT * FROM promo_code_usage WHERE user_id=?", (test_user_id,))
        new_record = cursor.fetchone()
        print(f"New record: {new_record}")
        
        # Удаляем тестовую запись
        cursor.execute("DELETE FROM promo_code_usage WHERE user_id=?", (test_user_id,))
        conn.commit()
        print(f"SUCCESS: Test record cleaned up")
        
    except sqlite3.IntegrityError as e:
        print(f"ERROR: UNIQUE constraint failed: {e}")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False
    finally:
        conn.close()
    
    return True

if __name__ == "__main__":
    print("Testing promo code usage fix...")
    success = test_promo_code_usage()
    print(f"Test result: {'PASSED' if success else 'FAILED'}")
