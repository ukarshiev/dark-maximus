#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Список пользователей с timezone"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'src')

import sqlite3

DB_FILE = "users.db"

print("=" * 60)
print("Spisok polzovateley s timezone")
print("=" * 60)

try:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Проверяем структуру таблицы users
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    print("\nKolonki v tablice users:")
    for col in columns:
        print(f"  - {col['name']} ({col['type']})")
    
    # Получаем всех пользователей
    cursor.execute("SELECT telegram_id, username, timezone FROM users LIMIT 10")
    users = cursor.fetchall()
    
    print(f"\nNaydeno polzovateley: {len(users)}")
    print("\nPervye 10 polzovateley:")
    for user in users:
        tz = user['timezone'] if 'timezone' in user.keys() else 'NO COLUMN'
        print(f"  ID: {user['telegram_id']}, Username: {user['username']}, TZ: {tz}")
    
    conn.close()

except Exception as e:
    print(f"[ERROR] {e}")

print("=" * 60)

