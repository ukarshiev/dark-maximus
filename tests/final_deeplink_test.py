#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Финальный тест deeplink ссылки"""

import sqlite3
import base64
import json

def check_user_balance(user_id):
    """Проверяем баланс пользователя"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            return result[0] or 0.0
        return None
    finally:
        conn.close()

def check_promo_usage(user_id):
    """Проверяем использование промокода пользователем"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT pcu.*, pc.code 
            FROM promo_code_usage pcu
            JOIN promo_codes pc ON pcu.promo_id = pc.promo_id
            WHERE pcu.user_id = ? AND pc.code = 'SKIDKA100RUB'
        ''', (user_id,))
        
        result = cursor.fetchone()
        if result:
            return dict(zip([desc[0] for desc in cursor.description], result))
        return None
    finally:
        conn.close()

def check_user_group(user_id):
    """Проверяем группу пользователя"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT u.telegram_id, ug.group_name, ug.group_code
            FROM users u
            JOIN user_groups ug ON u.group_id = ug.group_id
            WHERE u.telegram_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        if result:
            return dict(zip([desc[0] for desc in cursor.description], result))
        return None
    finally:
        conn.close()

def main():
    print("Final deeplink test...")
    
    # Проверяем пользователя 5089633490 (который уже тестировался)
    user_id = 5089633490
    
    print(f"\nChecking user {user_id}:")
    
    # Баланс
    balance = check_user_balance(user_id)
    print(f"Balance: {balance}")
    
    # Группа
    group_info = check_user_group(user_id)
    if group_info:
        print(f"Group: {group_info['group_name']} (code: {group_info['group_code']})")
    else:
        print("Group: Not found")
    
    # Использование промокода
    promo_usage = check_promo_usage(user_id)
    if promo_usage:
        print(f"Promo usage: {promo_usage['code']} - {promo_usage['status']} (bonus: {promo_usage['discount_bonus']})")
    else:
        print("Promo usage: Not found")
    
    # Проверяем все записи использования промокода SKIDKA100RUB
    print(f"\nAll usage records for SKIDKA100RUB:")
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT pcu.user_id, pcu.status, pcu.discount_bonus, pcu.used_at, pc.code
            FROM promo_code_usage pcu
            JOIN promo_codes pc ON pcu.promo_id = pc.promo_id
            WHERE pc.code = 'SKIDKA100RUB'
            ORDER BY pcu.used_at DESC
        ''')
        
        records = cursor.fetchall()
        for record in records:
            print(f"  User {record[0]}: {record[4]} - {record[1]} (bonus: {record[2]}) at {record[3]}")
            
    finally:
        conn.close()

if __name__ == "__main__":
    main()
