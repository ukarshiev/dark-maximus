#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Добавление колонки description в migration_history"""

import sqlite3

def add_description_column(db_path='users.db'):
    """Добавляет колонку description в migration_history"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Проверяем существование таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='migration_history'")
        if not cursor.fetchone():
            print('[!] Table migration_history does not exist')
            return False
        
        # Проверяем существование колонки
        cursor.execute("PRAGMA table_info(migration_history)")
        columns = {row[1] for row in cursor.fetchall()}
        
        if 'description' in columns:
            print('[+] Column description already exists')
            return True
        
        print('[*] Adding column description to migration_history...')
        cursor.execute('ALTER TABLE migration_history ADD COLUMN description TEXT')
        conn.commit()
        
        print('[+] Column description successfully added')
        
        # Показываем текущую структуру
        print('\n[*] Current structure:')
        cursor.execute("PRAGMA table_info(migration_history)")
        for row in cursor.fetchall():
            print(f'    {row[1]} ({row[2]})')
        
        return True
        
    except Exception as e:
        print(f'[-] Error: {e}')
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print('='*70)
    print('[*] Adding description column to migration_history')
    print('='*70)
    add_description_column()

