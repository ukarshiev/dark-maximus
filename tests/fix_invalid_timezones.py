#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Исправление невалидных timezone в базе данных"""

import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).parent.parent / "users.db"

def main():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    print("\nИсправление невалидных timezone...")
    
    # Обновляем все невалидные timezone на Europe/Moscow
    cursor.execute("""
        UPDATE users 
        SET timezone = 'Europe/Moscow' 
        WHERE timezone NOT IN ('Europe/Moscow', 'Asia/Tokyo', 'America/New_York')
           OR timezone IS NULL
    """)
    
    affected = cursor.rowcount
    conn.commit()
    
    print(f"Обновлено записей: {affected}")
    
    # Проверяем результат
    cursor.execute("SELECT DISTINCT timezone FROM users")
    timezones = [row[0] for row in cursor.fetchall()]
    print(f"Текущие timezone в базе: {', '.join(timezones)}")
    
    conn.close()
    print("\n[OK] Готово!\n")

if __name__ == "__main__":
    main()

