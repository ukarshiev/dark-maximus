#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Создание токенов для ключей без токенов через SQL"""

import sqlite3
import secrets
from datetime import datetime, timezone
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
            
            # Создаем токен напрямую через SQL
            token = secrets.token_urlsafe(32)
            now = datetime.now(timezone.utc).isoformat()
            
            try:
                cursor.execute('''
                    INSERT INTO user_tokens (token, user_id, key_id, created_at, last_used_at, access_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (token, user_id, key_id, now, None, 0))
                
                conn.commit()
                print(f"    Created token: {token[:30]}...")
            except sqlite3.IntegrityError as e:
                print(f"    Token already exists or error: {e}")
                # Проверяем существующий токен
                cursor.execute('SELECT token FROM user_tokens WHERE user_id = ? AND key_id = ?', (user_id, key_id))
                existing = cursor.fetchone()
                if existing:
                    print(f"    Existing token: {existing[0][:30]}...")
    
    # Проверяем токен RMOt4tnFUAgSH1VjaG9dzuytDoDT7zatLZZwDUoJr88
    cursor.execute('SELECT token, user_id, key_id FROM user_tokens WHERE token = ?', 
                   ('RMOt4tnFUAgSH1VjaG9dzuytDoDT7zatLZZwDUoJr88',))
    result = cursor.fetchone()
    if result:
        print(f"\nToken RMOt4tnFUA... found: user_id={result[1]}, key_id={result[2]}")
    else:
        print(f"\nToken RMOt4tnFUA... NOT found")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

