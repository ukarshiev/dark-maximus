#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка токена в БД"""

import sqlite3
import sys
from pathlib import Path

DB_FILE = Path("users.db")

token_to_check = "RMOt4tnFUAgSH1VjaG9dzuytDoDT7zatLZZwDUoJr88"

try:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Проверяем наличие токена
    cursor.execute('SELECT token, user_id, key_id FROM user_tokens WHERE token = ?', (token_to_check,))
    result = cursor.fetchone()
    
    if result:
        print(f"Token found: user_id={result[1]}, key_id={result[2]}")
    else:
        print(f"Token NOT found in DB")
        
        # Проверяем все токены для user_id=2206685
        cursor.execute('SELECT token, key_id FROM user_tokens WHERE user_id = 2206685')
        user_tokens = cursor.fetchall()
        print(f"\nТокены для user_id=2206685: {len(user_tokens)} шт.")
        for token, key_id in user_tokens:
            print(f"  - key_id={key_id}, token={token[:30]}...")
    
    # Проверяем ключ #9
    cursor.execute('SELECT key_id, user_id FROM vpn_keys WHERE user_id = 2206685 ORDER BY key_id DESC LIMIT 5')
    keys = cursor.fetchall()
    print(f"\nПоследние ключи для user_id=2206685:")
    for key_id, user_id in keys:
        cursor.execute('SELECT token FROM user_tokens WHERE key_id = ?', (key_id,))
        token_result = cursor.fetchone()
        token_status = f"token={token_result[0][:30]}..." if token_result else "НЕТ ТОКЕНА"
        print(f"  - key_id={key_id}: {token_status}")
    
    conn.close()
except Exception as e:
    print(f"Ошибка: {e}")
    sys.exit(1)

