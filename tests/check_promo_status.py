#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка статуса промокода"""

import sqlite3

def check_promo_status():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    try:
        print('Checking promo_code_usage table structure:')
        cursor.execute('PRAGMA table_info(promo_code_usage)')
        columns = [row[1] for row in cursor.fetchall()]
        print('Columns:', columns)
        
        print('\nChecking UNIQUE constraint:')
        cursor.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name="promo_code_usage"')
        table_sql = cursor.fetchone()[0]
        print('UNIQUE constraint correct:', 'UNIQUE (promo_id, user_id, bot)' in table_sql)
        
        print('\nChecking existing promo usage:')
        cursor.execute('SELECT * FROM promo_code_usage WHERE promo_id = 23')
        usages = cursor.fetchall()
        print('Existing usages:', len(usages))
        for usage in usages:
            print(f'  Usage: promo_id={usage[1]}, user_id={usage[2]}, bot={usage[3]}, bonus={usage[7]}')
        
        print('\nChecking if user 647100722 can use promo:')
        cursor.execute('SELECT * FROM promo_code_usage WHERE promo_id = 23 AND user_id = 647100722')
        user_usage = cursor.fetchone()
        print('User 647100722 usage:', user_usage)
        
        print('\nChecking user 647100722 balance:')
        cursor.execute('SELECT balance FROM users WHERE telegram_id = 647100722')
        balance = cursor.fetchone()
        print('User balance:', balance[0] if balance else 'User not found')
        
        return True
        
    except Exception as e:
        print(f'Error: {e}')
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    check_promo_status()
