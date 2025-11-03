#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Полная миграция схемы базы данных Dark Maximus Bot

Миграции:
1. Добавление колонок в таблицу users: fullname, user_id, group_id
2. Создание/обновление таблицы user_groups с колонкой group_code
3. Создание группы по умолчанию
"""

import sqlite3
import sys
from datetime import datetime

def check_table_exists(cursor, table_name):
    """Проверяет существование таблицы"""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None

def get_table_columns(cursor, table_name):
    """Получает список колонок таблицы"""
    cursor.execute(f'PRAGMA table_info({table_name})')
    return {row[1]: row for row in cursor.fetchall()}

def migrate_user_groups_table(cursor):
    """Миграция таблицы user_groups"""
    print('\n📦 Миграция таблицы user_groups...')
    
    table_exists = check_table_exists(cursor, 'user_groups')
    
    if not table_exists:
        print('  ℹ️  Таблица user_groups не существует, создаём...')
        cursor.execute('''
            CREATE TABLE user_groups (
                group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_name TEXT NOT NULL UNIQUE,
                group_description TEXT,
                is_default BOOLEAN DEFAULT 0,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                group_code TEXT UNIQUE
            )
        ''')
        print('  ✓ Таблица user_groups создана')
        
        # Создаём группу по умолчанию
        cursor.execute('''
            INSERT INTO user_groups (group_name, group_description, is_default)
            VALUES ('Базовая', 'Группа пользователей по умолчанию', 1)
        ''')
        print('  ✓ Создана группа по умолчанию')
        
        return True
    
    # Таблица существует, проверяем наличие колонки group_code
    columns = get_table_columns(cursor, 'user_groups')
    
    if 'group_code' not in columns:
        print('  ℹ️  Добавляем колонку group_code...')
        # SQLite не позволяет добавлять колонку с UNIQUE через ALTER TABLE
        cursor.execute('ALTER TABLE user_groups ADD COLUMN group_code TEXT')
        print('  ✓ Колонка group_code добавлена')
        
        # Создаём уникальный индекс
        cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_user_groups_code ON user_groups(group_code)')
        print('  ✓ Создан уникальный индекс для group_code')
        return True
    
    print('  ✓ Таблица user_groups актуальна')
    return True

def migrate_users_table(cursor):
    """Миграция таблицы users"""
    print('\n👤 Миграция таблицы users...')
    
    # Получаем текущую структуру
    columns = get_table_columns(cursor, 'users')
    existing_columns = set(columns.keys())
    
    print(f'  📊 Существующие колонки: {len(existing_columns)} шт.')
    
    # Определяем необходимые колонки
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
        print('  ✓ Все необходимые колонки уже существуют')
        return True
    
    print(f'  📝 Нужно добавить {len(columns_to_add)} колонок:')
    for col_name, col_type, constraint in columns_to_add:
        constraint_str = f' {constraint}' if constraint else ''
        print(f'     - {col_name} {col_type}{constraint_str}')
    
    # Добавляем колонки
    for col_name, col_type, constraint in columns_to_add:
        try:
            if col_name == 'user_id':
                # Добавляем колонку
                cursor.execute(f'ALTER TABLE users ADD COLUMN {col_name} {col_type}')
                print(f'  ✓ Добавлена колонка {col_name}')
                
                # Заполняем значениями
                cursor.execute('SELECT telegram_id FROM users ORDER BY telegram_id')
                users = cursor.fetchall()
                
                for idx, (telegram_id,) in enumerate(users, start=1000):
                    cursor.execute(
                        'UPDATE users SET user_id = ? WHERE telegram_id = ?',
                        (idx, telegram_id)
                    )
                
                print(f'  ✓ Заполнено user_id для {len(users)} пользователей')
                
                # Создаём уникальный индекс
                cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id)')
                print(f'  ✓ Создан уникальный индекс для user_id')
                
            else:
                # Для остальных колонок
                cursor.execute(f'ALTER TABLE users ADD COLUMN {col_name} {col_type}')
                print(f'  ✓ Добавлена колонка {col_name}')
                
        except sqlite3.OperationalError as e:
            if 'duplicate column name' in str(e).lower():
                print(f'  ⚠️  Колонка {col_name} уже существует')
            else:
                raise
    
    # Создаём индексы
    print('  🔍 Создание индексов...')
    indexes = [
        ('idx_users_group_id', 'group_id'),
        ('idx_users_fullname', 'fullname')
    ]
    
    for index_name, column_name in indexes:
        try:
            cursor.execute(f'CREATE INDEX IF NOT EXISTS {index_name} ON users({column_name})')
            print(f'     ✓ {index_name}')
        except Exception as e:
            print(f'     ⚠️  {index_name}: {e}')
    
    return True

def assign_users_to_default_group(cursor):
    """Назначает всех пользователей без группы в группу по умолчанию"""
    print('\n🔗 Назначение пользователей в группу по умолчанию...')
    
    # Проверяем, есть ли user_groups
    if not check_table_exists(cursor, 'user_groups'):
        print('  ⚠️  Таблица user_groups не существует, пропускаем')
        return True
    
    # Получаем ID группы по умолчанию
    cursor.execute('SELECT group_id FROM user_groups WHERE is_default = 1 LIMIT 1')
    default_group = cursor.fetchone()
    
    if not default_group:
        print('  ⚠️  Группа по умолчанию не найдена, пропускаем')
        return True
    
    default_group_id = default_group[0]
    print(f'  ℹ️  ID группы по умолчанию: {default_group_id}')
    
    # Проверяем, есть ли колонка group_id в users
    columns = get_table_columns(cursor, 'users')
    if 'group_id' not in columns:
        print('  ⚠️  Колонка group_id отсутствует в таблице users, пропускаем')
        return True
    
    # Назначаем пользователей без группы в группу по умолчанию
    cursor.execute('UPDATE users SET group_id = ? WHERE group_id IS NULL', (default_group_id,))
    updated_count = cursor.rowcount
    
    if updated_count > 0:
        print(f'  ✓ Назначено пользователей: {updated_count}')
    else:
        print('  ✓ Все пользователи уже в группах')
    
    return True

def create_migration_history(cursor):
    """Создаёт таблицу истории миграций"""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS migration_history (
            migration_id TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT
        )
    ''')

def record_migration(cursor, migration_id, description):
    """Записывает миграцию в историю"""
    cursor.execute(
        'INSERT OR IGNORE INTO migration_history (migration_id, description) VALUES (?, ?)',
        (migration_id, description)
    )

def apply_migration(db_path='users.db'):
    """Применяет все миграции"""
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print(f'🔍 Подключение к базе данных: {db_path}')
        
        # Создаём таблицу истории миграций
        create_migration_history(cursor)
        
        # Применяем миграции
        migrations = []
        
        # 1. Миграция user_groups
        if migrate_user_groups_table(cursor):
            migrations.append((
                'create_user_groups_table',
                'Создание/обновление таблицы user_groups с group_code'
            ))
        
        # 2. Миграция users
        if migrate_users_table(cursor):
            migrations.append((
                'add_users_columns',
                'Добавление колонок fullname, user_id, group_id в таблицу users'
            ))
        
        # 3. Назначение пользователей в группы
        if assign_users_to_default_group(cursor):
            migrations.append((
                'assign_users_to_default_group',
                'Назначение пользователей в группу по умолчанию'
            ))
        
        # Записываем миграции в историю
        print('\n📝 Запись в историю миграций...')
        for migration_id, description in migrations:
            record_migration(cursor, migration_id, description)
            print(f'  ✓ {migration_id}')
        
        # Коммитим все изменения
        conn.commit()
        
        # Выводим итоговую статистику
        print('\n📊 Статистика базы данных:')
        
        # Количество пользователей
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        print(f'  👥 Пользователей: {user_count}')
        
        # Количество групп
        if check_table_exists(cursor, 'user_groups'):
            cursor.execute('SELECT COUNT(*) FROM user_groups')
            group_count = cursor.fetchone()[0]
            print(f'  📦 Групп: {group_count}')
            
            # Пользователи по группам
            cursor.execute('''
                SELECT ug.group_name, COUNT(u.telegram_id) as count
                FROM user_groups ug
                LEFT JOIN users u ON ug.group_id = u.group_id
                GROUP BY ug.group_id, ug.group_name
            ''')
            for group_name, count in cursor.fetchall():
                print(f'     - {group_name}: {count} чел.')
        
        # Применённые миграции
        cursor.execute('SELECT COUNT(*) FROM migration_history')
        migration_count = cursor.fetchone()[0]
        print(f'  🔄 Применено миграций: {migration_count}')
        
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
    """Точка входа"""
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = 'users.db'
    
    print('='*70)
    print('🔄 МИГРАЦИЯ СХЕМЫ БАЗЫ ДАННЫХ DARK MAXIMUS BOT')
    print('='*70)
    print(f'📁 База данных: {db_path}')
    print(f'📅 Дата: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('='*70)
    
    success = apply_migration(db_path)
    
    print('\n' + '='*70)
    if success:
        print('✅ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО')
        print('='*70)
        print('\n💡 Перезапустите бота для применения изменений:')
        print('   docker restart dark-maximus-bot')
        sys.exit(0)
    else:
        print('❌ МИГРАЦИЯ ЗАВЕРШИЛАСЬ С ОШИБКОЙ')
        print('='*70)
        sys.exit(1)

if __name__ == "__main__":
    main()

