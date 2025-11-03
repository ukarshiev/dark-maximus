#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Скрипт для сравнения структуры базы данных"""

import sqlite3
import sys
from collections import defaultdict

def get_database_structure(db_path):
    """Получает полную структуру базы данных"""
    
    structure = {
        'tables': {},
        'indexes': {}
    }
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Получаем список таблиц
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    for table in tables:
        # Получаем структуру таблицы
        cursor.execute(f'PRAGMA table_info({table})')
        columns = []
        for row in cursor.fetchall():
            col_info = {
                'cid': row[0],
                'name': row[1],
                'type': row[2],
                'notnull': row[3],
                'default': row[4],
                'pk': row[5]
            }
            columns.append(col_info)
        
        structure['tables'][table] = columns
        
        # Получаем индексы таблицы
        cursor.execute(f'PRAGMA index_list({table})')
        indexes = []
        for row in cursor.fetchall():
            index_name = row[1]
            cursor.execute(f'PRAGMA index_info({index_name})')
            index_columns = [col[2] for col in cursor.fetchall()]
            indexes.append({
                'name': index_name,
                'unique': row[2],
                'columns': index_columns
            })
        
        if indexes:
            structure['indexes'][table] = indexes
    
    conn.close()
    return structure, tables

def compare_structures(local_struct, remote_struct, local_tables, remote_tables):
    """Сравнивает структуры двух баз данных"""
    
    differences = []
    
    # Сравниваем списки таблиц
    local_only = set(local_tables) - set(remote_tables)
    remote_only = set(remote_tables) - set(local_tables)
    
    if local_only:
        differences.append(f"[-] Tablitsy tolko v localhost: {', '.join(local_only)}")
    
    if remote_only:
        differences.append(f"[-] Tablitsy tolko na boevom: {', '.join(remote_only)}")
    
    # Сравниваем структуру общих таблиц
    common_tables = set(local_tables) & set(remote_tables)
    
    for table in sorted(common_tables):
        local_cols = {col['name']: col for col in local_struct['tables'][table]}
        remote_cols = {col['name']: col for col in remote_struct['tables'][table]}
        
        local_col_names = set(local_cols.keys())
        remote_col_names = set(remote_cols.keys())
        
        # Колонки только в одной из БД
        local_only_cols = local_col_names - remote_col_names
        remote_only_cols = remote_col_names - local_col_names
        
        if local_only_cols or remote_only_cols:
            differences.append(f"\n[*] Tablitsa '{table}':")
            
            if local_only_cols:
                differences.append(f"  [-] Kolonki tolko v localhost: {', '.join(local_only_cols)}")
            
            if remote_only_cols:
                differences.append(f"  [-] Kolonki tolko na boevom: {', '.join(remote_only_cols)}")
        
        # Сравниваем типы общих колонок
        common_cols = local_col_names & remote_col_names
        for col_name in common_cols:
            local_col = local_cols[col_name]
            remote_col = remote_cols[col_name]
            
            if local_col['type'] != remote_col['type']:
                differences.append(f"  [!] Tablitsa '{table}', kolonka '{col_name}': tip razlichaetsya (localhost: {local_col['type']}, boevoy: {remote_col['type']})")
    
    return differences

def print_structure(struct, tables, label):
    """Выводит структуру базы данных"""
    
    print(f"\n{'='*70}")
    print(f"[*] STRUKTURA BAZY DANNYKH: {label}")
    print(f"{'='*70}")
    print(f"\n[*] Vsego tablic: {len(tables)}")
    
    # Группируем таблицы по типу
    system_tables = [t for t in tables if t.startswith('sqlite_')]
    user_tables = [t for t in tables if not t.startswith('sqlite_')]
    
    print(f"   - Polzovatelskikh: {len(user_tables)}")
    if system_tables:
        print(f"   - Sistemnykh: {len(system_tables)}")
    
    # Выводим важные таблицы
    important_tables = ['users', 'user_groups', 'vpn_keys', 'transactions', 'plans', 
                       'promo_codes', 'promo_code_usage', 'bot_settings', 'migration_history']
    
    print(f"\n[*] Vazhnye tablitsy:")
    for table in important_tables:
        if table in struct['tables']:
            cols = struct['tables'][table]
            col_names = [c['name'] for c in cols]
            print(f"   [+] {table} ({len(cols)} kolonok)")
            print(f"      Kolonki: {', '.join(col_names[:10])}")
            if len(col_names) > 10:
                print(f"      ... i eshchyo {len(col_names) - 10}")
        else:
            print(f"   [-] {table} (otsutstvuet)")

def main():
    print('='*70)
    print('[*] SRAVNENIE STRUKTURY BAZ DANNYKH')
    print('='*70)
    
    # Локальная база
    print('\n[*] Analiz localhost...')
    local_struct, local_tables = get_database_structure('users.db')
    print(f'   [+] Naideno tablic: {len(local_tables)}')
    
    # Выводим структуру localhost
    print_structure(local_struct, local_tables, 'LOCALHOST')
    
    # Временно сохраняем для удалённой БД
    print('\n[*] Struktura localhost sokhranena dlya sravneniya')
    
    print('\n' + '='*70)
    print('[+] Analiz zavershen')
    print('='*70)
    
    # Выводим JSON для последующего сравнения
    import json
    with open('tests/local_db_structure.json', 'w', encoding='utf-8') as f:
        json.dump({
            'tables': {k: v for k, v in local_struct['tables'].items()},
            'table_list': local_tables
        }, f, indent=2, ensure_ascii=False)
    
    print('\n[*] Struktura sokhranena v tests/local_db_structure.json')

if __name__ == "__main__":
    main()

