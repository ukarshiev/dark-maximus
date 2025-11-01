#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Скрипт для проверки структуры таблицы promo_code_usage"""

import sqlite3

conn = sqlite3.connect('users.db')
cursor = conn.cursor()

# Получаем структуру таблицы
cursor.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name="promo_code_usage"')
result = cursor.fetchone()
print('Table structure:')
print(result[0] if result else 'Table not found')

print('\n--- Existing records for promo_id=23 ---')
cursor.execute('SELECT * FROM promo_code_usage WHERE promo_id=23')
rows = cursor.fetchall()
print(f'Found {len(rows)} records')
for row in rows:
    print(row)

print('\n--- All promo_code_usage records ---')
cursor.execute('SELECT usage_id, promo_id, user_id, bot, status FROM promo_code_usage')
rows = cursor.fetchall()
print(f'Total records: {len(rows)}')
for row in rows:
    print(row)

conn.close()

