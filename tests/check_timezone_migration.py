#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка результатов миграции timezone"""

import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).parent.parent / "users.db"

def main():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("ПРОВЕРКА МИГРАЦИИ TIMEZONE")
    print("="*60)
    
    # 1. Проверка колонки timezone
    print("\n1. Структура таблицы users (timezone):")
    cursor.execute("PRAGMA table_info(users)")
    for row in cursor.fetchall():
        if 'timezone' in row[1].lower():
            print(f"   [OK] Колонка: {row[1]}, Тип: {row[2]}, Default: {row[4]}")
    
    # 2. Проверка настроек
    print("\n2. Настройки timezone в bot_settings:")
    cursor.execute("SELECT key, value FROM bot_settings WHERE key LIKE '%timezone%'")
    for key, value in cursor.fetchall():
        print(f"   [OK] {key} = {value}")
    
    # 3. Статистика пользователей
    print("\n3. Статистика пользователей:")
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    print(f"   Всего пользователей: {total}")
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE timezone IS NOT NULL")
    with_tz = cursor.fetchone()[0]
    print(f"   С timezone: {with_tz}")
    
    cursor.execute("SELECT DISTINCT timezone FROM users WHERE timezone IS NOT NULL")
    timezones = [row[0] for row in cursor.fetchall()]
    if timezones:
        print(f"   Используемые timezones: {', '.join(timezones)}")
    
    print("\n" + "="*60)
    print("[OK] ПРОВЕРКА ЗАВЕРШЕНА")
    print("="*60 + "\n")
    
    conn.close()

if __name__ == "__main__":
    main()

