#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тест промокода для нового пользователя"""

import subprocess

def test_new_user_promo():
    cmd = '''import sqlite3
conn = sqlite3.connect('/app/project/users.db')
cursor = conn.cursor()

print('Testing deeplink with new user 888888888:')

# Создаем нового пользователя
cursor.execute('INSERT OR IGNORE INTO users (telegram_id, username, fullname, balance, created_date) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)', (888888888, 'test_user_new', 'Test User New', 0.0))

# Применяем промокод
cursor.execute('SELECT * FROM promo_codes WHERE code = "SKIDKA100RUB"')
promo = cursor.fetchone()
if promo:
    try:
        cursor.execute('INSERT INTO promo_code_usage (promo_id, user_id, bot, plan_id, discount_amount, discount_percent, discount_bonus, metadata, used_at, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)', (promo[0], 888888888, 'shop', None, 0.0, 0.0, promo[7], '{"test": "deeplink"}', 'applied'))
        
        cursor.execute('UPDATE users SET balance = balance + ? WHERE telegram_id = ?', (promo[7], 888888888))
        
        conn.commit()
        print('SUCCESS: New user can use promo code!')
        
        cursor.execute('SELECT balance FROM users WHERE telegram_id = 888888888')
        balance = cursor.fetchone()[0]
        print(f'New user balance: {balance}')
        
    except Exception as e:
        print(f'ERROR: {e}')
        conn.rollback()
else:
    print('Promo code not found')

conn.close()'''
    
    result = subprocess.run(['docker', 'exec', 'dark-maximus-bot', 'python', '-c', cmd], 
                          capture_output=True, text=True)
    
    print("STDOUT:")
    print(result.stdout)
    print("\nSTDERR:")
    print(result.stderr)
    print(f"\nReturn code: {result.returncode}")

if __name__ == "__main__":
    test_new_user_promo()
