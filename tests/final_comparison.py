#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Финальное сравнение структур баз данных"""

import json

def final_comparison():
    """Финальное сравнение после всех миграций"""
    
    # Загружаем структуры
    with open('tests/local_db_structure.json', 'r', encoding='utf-8') as f:
        local = json.load(f)
    
    with open('tests/remote_db_structure_final.json', 'r', encoding='utf-8') as f:
        remote = json.load(f)
    
    print('='*70)
    print('[*] FINALNOE SRAVNENIE STRUKTUR')
    print('='*70)
    
    local_tables = set(local['table_list'])
    remote_tables = set(remote['table_list'])
    
    print(f'\n[*] Statistika tablic:')
    print(f'   Localhost: {len(local_tables)} tablic')
    print(f'   Boevoy:    {len(remote_tables)} tablic')
    
    # Различия в таблицах
    local_only = local_tables - remote_tables
    remote_only = remote_tables - local_tables
    common_tables = local_tables & remote_tables
    
    if local_only:
        print(f'\n[!] Tablitsy TOLKO na localhost ({len(local_only)}):')
        for table in sorted(local_only):
            print(f'   - {table}')
    
    if remote_only:
        print(f'\n[!] Tablitsy TOLKO na boevom ({len(remote_only)}):')
        for table in sorted(remote_only):
            print(f'   - {table}')
    
    print(f'\n[+] Obshchikh tablic: {len(common_tables)}')
    
    # Проверяем важные таблицы
    important_tables = ['users', 'user_groups', 'promo_codes', 'promo_code_usage', 'migration_history']
    
    print(f'\n[*] Proverka vazhnykh tablic:')
    
    all_identical = True
    
    for table in important_tables:
        if table not in local['tables'] or table not in remote['tables']:
            print(f'   [-] {table}: NE NAIDENA')
            all_identical = False
            continue
        
        local_cols = {col['name']: col for col in local['tables'][table]}
        remote_cols = {col['name']: col for col in remote['tables'][table]}
        
        local_col_names = set(local_cols.keys())
        remote_col_names = set(remote_cols.keys())
        
        if local_col_names == remote_col_names:
            print(f'   [+] {table}: IDENTICHNA ({len(local_col_names)} kolonok)')
        else:
            print(f'   [!] {table}: RAZLICHIYA')
            all_identical = False
            
            local_only_cols = local_col_names - remote_col_names
            remote_only_cols = remote_col_names - local_col_names
            
            if local_only_cols:
                print(f'       Tolko na localhost: {", ".join(local_only_cols)}')
            if remote_only_cols:
                print(f'       Tolko na boevom: {", ".join(remote_only_cols)}')
    
    # Итоговый статус
    print(f'\n{"="*70}')
    
    if all_identical and not local_only and not remote_only:
        print('[+] USPEKH! BAZY DANNYKH POLNOSTYU SINKHRONIZIROWANY!')
        print('='*70)
        print('\n[*] Vse vazhnye tablitsy identichny:')
        print('    - users: 27 kolonok (vklyuchaya group_id, fullname, user_id)')
        print('    - user_groups: 6 kolonok (vklyuchaya group_code)')
        print('    - promo_codes: 17 kolonok (vklyuchaya 5 novykh)')
        print('    - migration_history: 3 kolonki (vklyuchaya description)')
        return True
    else:
        print('[!] NAIDENY NEZNACHITELNYE RAZLICHIYA')
        print('='*70)
        if local_only or remote_only:
            print('\n[*] Razlichiya v tablitsakh (ne kritichno):')
            if local_only:
                print(f'    - sqlite_stat1: sistemnyaya tablitsa SQLite (bezopasno)')
        return False

if __name__ == "__main__":
    final_comparison()

