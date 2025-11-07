#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для проверки и добавления настройки admin_timezone в БД
"""

import sqlite3
import sys

DB_PATH = '/app/project/users.db'

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Проверяем наличие настройки admin_timezone
    cursor.execute("SELECT key, value FROM bot_settings WHERE key = ?", ('admin_timezone',))
    result = cursor.fetchone()
    
    if result:
        print(f"FOUND: admin_timezone = {result[1]}")
        sys.exit(0)
    else:
        print("NOT_FOUND: admin_timezone")
        
        # Добавляем настройку со значением по умолчанию
        cursor.execute(
            "INSERT INTO bot_settings (key, value) VALUES (?, ?)",
            ('admin_timezone', 'Europe/Moscow')
        )
        conn.commit()
        print("ADDED: admin_timezone = Europe/Moscow")
        sys.exit(0)
    
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(2)

