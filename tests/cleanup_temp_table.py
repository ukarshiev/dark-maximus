#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Удаление временной таблицы promo_code_usage_new"""

import sqlite3

def cleanup_temp_table(db_path='users.db'):
    """Удаляет временную таблицу promo_code_usage_new"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Проверяем существование таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='promo_code_usage_new'")
        if not cursor.fetchone():
            print('[+] Table promo_code_usage_new does not exist')
            return True
        
        # Проверяем количество записей
        cursor.execute('SELECT COUNT(*) FROM promo_code_usage_new')
        count = cursor.fetchone()[0]
        
        if count > 0:
            print(f'[!] WARNING: Table contains {count} records!')
            print('[!] Aborting deletion to prevent data loss')
            return False
        
        print('[*] Deleting empty temporary table promo_code_usage_new...')
        cursor.execute('DROP TABLE promo_code_usage_new')
        conn.commit()
        
        print('[+] Table promo_code_usage_new successfully deleted')
        return True
        
    except Exception as e:
        print(f'[-] Error: {e}')
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print('='*70)
    print('[*] CLEANUP: Deleting temporary table')
    print('='*70)
    cleanup_temp_table()

