#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для тестирования функции get_setting
"""

import sqlite3

DB_PATH = '/app/project/users.db'

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Прямой запрос к БД
    cursor.execute("SELECT value FROM bot_settings WHERE key = ?", ('admin_timezone',))
    result = cursor.fetchone()
    
    print(f"Direct query result: {result}")
    print(f"Value: {result[0] if result else None}")
    
    # Проверка типа
    if result:
        print(f"Type: {type(result[0])}")
        print(f"Length: {len(result[0]) if result[0] else 0}")
        print(f"Repr: {repr(result[0])}")
    
    conn.close()
    
except Exception as e:
    print(f"ERROR: {e}")

