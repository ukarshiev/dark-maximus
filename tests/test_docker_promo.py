#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тест применения промокода в Docker базе данных"""

import subprocess
import sys

def test_docker_promo():
    cmd = '''import sqlite3
conn = sqlite3.connect('/app/project/users.db')
cursor = conn.cursor()

print('Checking UNIQUE constraint in Docker database:')
cursor.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name="promo_code_usage"')
table_sql = cursor.fetchone()[0]
print('UNIQUE constraint correct:', 'UNIQUE (promo_id, user_id, bot)' in table_sql)

print('\\nTesting promo code application for user 647100722:')
cursor.execute('SELECT * FROM promo_codes WHERE code = "SKIDKA100RUB"')
promo = cursor.fetchone()
if promo:
    print(f'Promo code found: ID={promo[0]}, code={promo[1]}, bonus={promo[7]}')
    
    try:
        cursor.execute('INSERT INTO promo_code_usage (promo_id, user_id, bot, plan_id, discount_amount, discount_percent, discount_bonus, metadata, used_at, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)', (promo[0], 647100722, 'shop', None, 0.0, 0.0, promo[7], '{"test": "manual"}', 'applied'))
        
        cursor.execute('UPDATE users SET balance = balance + ? WHERE telegram_id = ?', (promo[7], 647100722))
        
        conn.commit()
        print('SUCCESS: Promo code applied and balance updated!')
        
        cursor.execute('SELECT balance FROM users WHERE telegram_id = 647100722')
        balance = cursor.fetchone()[0]
        print(f'New balance: {balance}')
        
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
    test_docker_promo()
