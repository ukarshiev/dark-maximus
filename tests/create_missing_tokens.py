#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Создание токенов для ключей без токенов"""

import sqlite3
import sys
from pathlib import Path

DB_FILE = Path("users.db")

try:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Находим ключи без токенов для user_id=2206685
    cursor.execute('''
        SELECT k.key_id, k.user_id 
        FROM vpn_keys k
        LEFT JOIN user_tokens ut ON k.key_id = ut.key_id
        WHERE k.user_id = 2206685 AND ut.token IS NULL
        ORDER BY k.key_id DESC
    ''')
    
    keys_without_tokens = cursor.fetchall()
    
    if not keys_without_tokens:
        print("All keys have tokens")
    else:
        print(f"Found {len(keys_without_tokens)} keys without tokens:")
        for key_id, user_id in keys_without_tokens:
            print(f"  - key_id={key_id}, user_id={user_id}")
            
            # Создаем токен
            from shop_bot.data_manager.database import get_or_create_permanent_token
            try:
                token = get_or_create_permanent_token(user_id, key_id)
                print(f"    Created token: {token[:30]}...")
            except Exception as e:
                print(f"    ERROR creating token: {e}")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

