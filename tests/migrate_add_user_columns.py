#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Миграция: Добавление недостающих колонок в таблицу users
- fullname (TEXT)
- user_id (INTEGER UNIQUE)  
- group_id (INTEGER)
"""

import sqlite3
import sys
from datetime import datetime

def apply_migration(db_path='users.db'):
    """Применяет миграцию к указанной базе данных"""
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print(f'🔍 Проверка текущей структуры таблицы users в {db_path}...')
        
        # Получаем текущую структуру таблицы
        cursor.execute('PRAGMA table_info(users)')
        columns = {row[1]: row for row in cursor.fetchall()}
        existing_columns = set(columns.keys())
        
        print(f'📊 Существующие колонки: {", ".join(sorted(existing_columns))}')
        
        # Определяем, какие колонки нужно добавить
        required_columns = {
            'fullname': ('TEXT', None),
            'user_id': ('INTEGER', 'UNIQUE'),
            'group_id': ('INTEGER', None)
        }
        
        columns_to_add = []
        for col_name, (col_type, constraint) in required_columns.items():
            if col_name not in existing_columns:
                columns_to_add.append((col_name, col_type, constraint))
        
        if not columns_to_add:
            print('✅ Все необходимые колонки уже существуют. Миграция не требуется.')
            return True
        
        print(f'\n📝 Будут добавлены следующие колонки:')
        for col_name, col_type, constraint in columns_to_add:
            constraint_str = f' {constraint}' if constraint else ''
            print(f'  - {col_name} {col_type}{constraint_str}')
        
        # Добавляем колонки
        print('\n⚙️ Применение миграции...')
        
        for col_name, col_type, constraint in columns_to_add:
            try:
                # SQLite не поддерживает ADD COLUMN с UNIQUE, поэтому для user_id используем другой подход
                if col_name == 'user_id':
                    # Сначала добавляем колонку без UNIQUE
                    cursor.execute(f'ALTER TABLE users ADD COLUMN {col_name} {col_type}')
                    print(f'  ✓ Добавлена колонка {col_name}')
                    
                    # Заполняем user_id последовательными значениями начиная с 1000
                    cursor.execute('SELECT telegram_id FROM users ORDER BY telegram_id')
                    users = cursor.fetchall()
                    
                    for idx, (telegram_id,) in enumerate(users, start=1000):
                        cursor.execute('UPDATE users SET user_id = ? WHERE telegram_id = ?', (idx, telegram_id))
                    
                    print(f'  ✓ Заполнена колонка user_id для {len(users)} пользователей')
                    
                    # Создаем уникальный индекс для обеспечения UNIQUE constraint
                    cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id)')
                    print(f'  ✓ Создан уникальный индекс для user_id')
                else:
                    # Для остальных колонок просто добавляем
                    alter_sql = f'ALTER TABLE users ADD COLUMN {col_name} {col_type}'
                    cursor.execute(alter_sql)
                    print(f'  ✓ Добавлена колонка {col_name}')
                    
            except sqlite3.OperationalError as e:
                if 'duplicate column name' in str(e).lower():
                    print(f'  ⚠️  Колонка {col_name} уже существует, пропускаем')
                else:
                    raise
        
        # Создаем индексы для производительности
        print('\n🔍 Создание индексов...')
        indexes = [
            ('idx_users_group_id', 'users', 'group_id'),
            ('idx_users_fullname', 'users', 'fullname')
        ]
        
        for index_name, table_name, column_name in indexes:
            try:
                cursor.execute(f'CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({column_name})')
                print(f'  ✓ Создан индекс {index_name}')
            except Exception as e:
                print(f'  ⚠️  Не удалось создать индекс {index_name}: {e}')
        
        # Записываем миграцию в историю
        print('\n📝 Запись в историю миграций...')
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS migration_history (
                    migration_id TEXT PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            migration_id = 'add_user_columns_fullname_userid_groupid'
            cursor.execute(
                'INSERT OR IGNORE INTO migration_history (migration_id) VALUES (?)',
                (migration_id,)
            )
            print(f'  ✓ Миграция записана: {migration_id}')
        except Exception as e:
            print(f'  ⚠️  Не удалось записать в историю: {e}')
        
        # Коммитим изменения
        conn.commit()
        
        # Проверяем результат
        print('\n✅ Миграция успешно применена!')
        print('\n📊 Новая структура таблицы users:')
        cursor.execute('PRAGMA table_info(users)')
        for row in cursor.fetchall():
            print(f'  - {row[1]} ({row[2]})')
        
        return True
        
    except Exception as e:
        print(f'\n❌ Ошибка при применении миграции: {e}')
        import traceback
        traceback.print_exc()
        if 'conn' in locals():
            conn.rollback()
        return False
        
    finally:
        if 'conn' in locals():
            conn.close()

def main():
    """Точка входа скрипта"""
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = 'users.db'
    
    print('='*60)
    print('🔄 МИГРАЦИЯ: Добавление колонок в таблицу users')
    print('='*60)
    print(f'📁 База данных: {db_path}')
    print(f'📅 Дата: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('='*60)
    print()
    
    success = apply_migration(db_path)
    
    if success:
        print('\n' + '='*60)
        print('✅ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО')
        print('='*60)
        sys.exit(0)
    else:
        print('\n' + '='*60)
        print('❌ МИГРАЦИЯ ЗАВЕРШИЛАСЬ С ОШИБКОЙ')
        print('='*60)
        sys.exit(1)

if __name__ == "__main__":
    main()

