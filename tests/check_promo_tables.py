#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка таблиц promo_code"""

import sqlite3

conn = sqlite3.connect('users.db')
cursor = conn.cursor()

# Все таблицы с promo_code
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'promo_code%' ORDER BY name")
tables = cursor.fetchall()

print('Promo tables:')
for table in tables:
    print(f'  - {table[0]}')
    
    # Количество записей
    cursor.execute(f'SELECT COUNT(*) FROM {table[0]}')
    count = cursor.fetchone()[0]
    print(f'    Records: {count}')

# Проверяем структуру promo_code_usage
print('\nStructure of promo_code_usage:')
cursor.execute("PRAGMA table_info(promo_code_usage)")
for row in cursor.fetchall():
    print(f'  {row[1]} ({row[2]})')

# Проверяем структуру promo_code_usage_new (если есть)
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='promo_code_usage_new'")
result = cursor.fetchone()
if result:
    print('\n[!] Table promo_code_usage_new EXISTS!')
    print('Structure:')
    cursor.execute("PRAGMA table_info(promo_code_usage_new)")
    for row in cursor.fetchall():
        print(f'  {row[1]} ({row[2]})')
else:
    print('\n[+] Table promo_code_usage_new does NOT exist')

conn.close()

