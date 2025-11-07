#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для проверки таблиц с настройками в БД
"""

import sqlite3

DB_PATH = '/app/project/users.db'

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Найти все таблицы с настройками
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%setting%'")
    tables = cursor.fetchall()
    
    print("=== Таблицы с настройками ===")
    for table in tables:
        print(f"  - {table[0]}")
    
    # Проверить admin_timezone в каждой таблице
    print("\n=== Проверка admin_timezone в каждой таблице ===")
    for table in tables:
        table_name = table[0]
        try:
            cursor.execute(f"SELECT * FROM {table_name} WHERE key = 'admin_timezone' OR key LIKE '%timezone%'")
            results = cursor.fetchall()
            if results:
                print(f"\n{table_name}:")
                for row in results:
                    print(f"  {row}")
            else:
                print(f"\n{table_name}: (нет записей с timezone)")
        except Exception as e:
            print(f"\n{table_name}: Ошибка - {e}")
    
    conn.close()
    
except Exception as e:
    print(f"ERROR: {e}")

