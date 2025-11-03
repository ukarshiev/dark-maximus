#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Миграция: Добавление новых колонок в таблицу promo_codes

Добавляемые колонки:
- bot_username (TEXT) - имя пользователя бота для промокода
- burn_after_unit (TEXT) - единица времени для автоуничтожения (days, hours, uses)
- burn_after_value (INTEGER) - значение для автоуничтожения
- target_group_ids (TEXT) - ID целевых групп (JSON array)
- valid_until (TIMESTAMP) - дата истечения срока действия
"""

import sqlite3
import sys
from datetime import datetime

def check_column_exists(cursor, table_name, column_name):
    """Проверяет существование колонки в таблице"""
    cursor.execute(f'PRAGMA table_info({table_name})')
    columns = {row[1] for row in cursor.fetchall()}
    return column_name in columns

def migrate_promo_codes(db_path='users.db'):
    """Добавляет новые колонки в promo_codes"""
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print(f'[*] Connecting to database: {db_path}')
        
        # Проверяем существование таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='promo_codes'")
        if not cursor.fetchone():
            print('[-] Table promo_codes does not exist!')
            return False
        
        # Определяем колонки для добавления
        columns_to_add = [
            ('bot_username', 'TEXT', 'Bot username for promo code'),
            ('burn_after_unit', 'TEXT', 'Auto-burn time unit (days/hours/uses)'),
            ('burn_after_value', 'INTEGER', 'Auto-burn value'),
            ('target_group_ids', 'TEXT', 'Target group IDs (JSON array)'),
            ('valid_until', 'TIMESTAMP', 'Expiration date')
        ]
        
        # Проверяем существующие колонки
        cursor.execute('PRAGMA table_info(promo_codes)')
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        print(f'\n[*] Current columns in promo_codes: {len(existing_columns)}')
        
        # Фильтруем колонки, которые нужно добавить
        to_add = [(name, type_, desc) for name, type_, desc in columns_to_add 
                  if name not in existing_columns]
        
        if not to_add:
            print('[+] All columns already exist!')
            return True
        
        print(f'\n[*] Adding {len(to_add)} new columns:')
        for name, type_, desc in to_add:
            print(f'    - {name} ({type_}) - {desc}')
        
        # Добавляем колонки
        for col_name, col_type, description in to_add:
            try:
                print(f'\n[*] Adding column: {col_name}...')
                cursor.execute(f'ALTER TABLE promo_codes ADD COLUMN {col_name} {col_type}')
                print(f'    [+] Added {col_name}')
            except sqlite3.OperationalError as e:
                if 'duplicate column' in str(e).lower():
                    print(f'    [!] Column {col_name} already exists, skipping')
                else:
                    raise
        
        # Записываем миграцию в историю
        print('\n[*] Recording migration in history...')
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS migration_history (
                    migration_id TEXT PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT
                )
            ''')
            
            migration_id = 'add_promo_codes_extended_columns'
            description = 'Added bot_username, burn_after_unit, burn_after_value, target_group_ids, valid_until'
            
            cursor.execute(
                'INSERT OR IGNORE INTO migration_history (migration_id, description) VALUES (?, ?)',
                (migration_id, description)
            )
            print(f'    [+] Migration recorded: {migration_id}')
        except Exception as e:
            print(f'    [!] Could not record migration: {e}')
        
        # Коммитим изменения
        conn.commit()
        
        # Показываем итоговую структуру
        print('\n[*] Final structure of promo_codes:')
        cursor.execute('PRAGMA table_info(promo_codes)')
        columns = cursor.fetchall()
        print(f'    Total columns: {len(columns)}')
        for row in columns:
            print(f'    - {row[1]} ({row[2]})')
        
        print('\n[+] Migration completed successfully!')
        return True
        
    except Exception as e:
        print(f'\n[-] Error during migration: {e}')
        import traceback
        traceback.print_exc()
        if 'conn' in locals():
            conn.rollback()
        return False
        
    finally:
        if 'conn' in locals():
            conn.close()

def main():
    """Точка входа"""
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = 'users.db'
    
    print('='*70)
    print('[*] MIGRATION: Adding extended columns to promo_codes')
    print('='*70)
    print(f'[*] Database: {db_path}')
    print(f'[*] Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('='*70)
    
    success = migrate_promo_codes(db_path)
    
    print('\n' + '='*70)
    if success:
        print('[+] MIGRATION COMPLETED SUCCESSFULLY')
    else:
        print('[-] MIGRATION FAILED')
    print('='*70)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

