#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Получение учетных данных для веб-панели"""

import sqlite3

conn = sqlite3.connect('users.db')
cursor = conn.cursor()

cursor.execute('SELECT key, value FROM bot_settings WHERE key IN ("panel_login", "panel_password")')
print('Login credentials:')
for row in cursor.fetchall():
    print(f'{row[0]}: {row[1]}')

conn.close()
