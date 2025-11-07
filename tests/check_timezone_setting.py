#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для проверки наличия настройки admin_timezone в БД
"""

import sqlite3
import sys

DB_PATH = '/app/data/shop_bot.db'

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Проверяем наличие настройки admin_timezone
    cursor.execute("SELECT key, value FROM bot_settings WHERE key = 'admin_timezone'")
    result = cursor.fetchone()
    
    if result:
        print(f"✅ Настройка найдена: {result[0]} = {result[1]}")
    else:
        print("❌ Настройка 'admin_timezone' отсутствует в таблице bot_settings")
        
        # Показываем все настройки с timezone в названии
        cursor.execute("SELECT key, value FROM bot_settings WHERE key LIKE '%timezone%'")
        all_tz = cursor.fetchall()
        if all_tz:
            print("\n📋 Найдены другие настройки с 'timezone':")
            for key, value in all_tz:
                print(f"  - {key} = {value}")
        else:
            print("\n📋 Настроек с 'timezone' в названии не найдено")
    
    conn.close()
    sys.exit(0 if result else 1)
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    sys.exit(2)

