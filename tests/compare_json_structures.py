#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Детальное сравнение структур баз данных из JSON файлов"""

import json

def compare_structures():
    """Сравнивает структуры из JSON файлов"""
    
    # Загружаем структуры
    with open('tests/local_db_structure.json', 'r', encoding='utf-8') as f:
        local = json.load(f)
    
    with open('tests/remote_db_structure.json', 'r', encoding='utf-8') as f:
        remote = json.load(f)
    
    print('='*70)
    print('[*] DETALNOE SRAVNENIE STRUKTUR BAZ DANNYKH')
    print('='*70)
    
    # Сравнение таблиц
    local_tables = set(local['table_list'])
    remote_tables = set(remote['table_list'])
    
    print(f'\n[*] Statistika:')
    print(f'   Localhost: {len(local_tables)} tablic')
    print(f'   Boevoy:    {len(remote_tables)} tablic')
    
    # Таблицы только на localhost
    local_only = local_tables - remote_tables
    if local_only:
        print(f'\n[-] Tablitsy TOLKO na localhost ({len(local_only)}):')
        for table in sorted(local_only):
            print(f'   - {table}')
    
    # Таблицы только на боевом
    remote_only = remote_tables - local_tables
    if remote_only:
        print(f'\n[-] Tablitsy TOLKO na boevom ({len(remote_only)}):')
        for table in sorted(remote_only):
            print(f'   - {table}')
    
    # Общие таблицы
    common_tables = local_tables & remote_tables
    print(f'\n[+] Obshchikh tablic: {len(common_tables)}')
    
    # Детальное сравнение общих таблиц
    differences_found = False
    
    for table in sorted(common_tables):
        local_cols = {col['name']: col for col in local['tables'][table]}
        remote_cols = {col['name']: col for col in remote['tables'][table]}
        
        local_col_names = set(local_cols.keys())
        remote_col_names = set(remote_cols.keys())
        
        # Различия в колонках
        local_only_cols = local_col_names - remote_col_names
        remote_only_cols = remote_col_names - local_col_names
        
        if local_only_cols or remote_only_cols:
            if not differences_found:
                print(f'\n{"="*70}')
                print('[!] NAIDENY RAZLICHIYA V TABLITSAKH:')
                print(f'{"="*70}')
                differences_found = True
            
            print(f'\n[*] Tablitsa: {table}')
            print(f'    Localhost: {len(local_col_names)} kolonok')
            print(f'    Boevoy:    {len(remote_col_names)} kolonok')
            
            if local_only_cols:
                print(f'    [-] Kolonki TOLKO na localhost:')
                for col in sorted(local_only_cols):
                    col_info = local_cols[col]
                    print(f'        - {col} ({col_info["type"]})')
            
            if remote_only_cols:
                print(f'    [-] Kolonki TOLKO na boevom:')
                for col in sorted(remote_only_cols):
                    col_info = remote_cols[col]
                    print(f'        - {col} ({col_info["type"]})')
        
        # Различия в типах колонок
        common_cols = local_col_names & remote_col_names
        type_diffs = []
        for col_name in common_cols:
            if local_cols[col_name]['type'] != remote_cols[col_name]['type']:
                type_diffs.append({
                    'name': col_name,
                    'local_type': local_cols[col_name]['type'],
                    'remote_type': remote_cols[col_name]['type']
                })
        
        if type_diffs:
            if not differences_found:
                print(f'\n{"="*70}')
                print('[!] NAIDENY RAZLICHIYA V TABLITSAKH:')
                print(f'{"="*70}')
                differences_found = True
            
            print(f'\n[*] Tablitsa: {table} - razlichiya v tipakh kolonok:')
            for diff in type_diffs:
                print(f'    [!] {diff["name"]}: localhost={diff["local_type"]}, boevoy={diff["remote_type"]}')
    
    if not differences_found:
        print(f'\n{"="*70}')
        print('[+] VSE OBSHCHIE TABLITSY IDENTICHNY!')
        print(f'{"="*70}')
    
    # Итоговая сводка
    print(f'\n{"="*70}')
    print('[*] ITOGOVAYA SVODKA:')
    print(f'{"="*70}')
    
    if not local_only and not remote_only and not differences_found:
        print('\n[+] BAZY DANNYKH POLNOSTYU IDENTICHNY!')
        print('    - Odinakoe kolichestvo tablic')
        print('    - Odinakaya struktura vsekh tablic')
        print('    - Odinakye tipy vsekh kolonok')
    else:
        print('\n[!] NAIDENY RAZLICHIYA:')
        if local_only:
            print(f'    - {len(local_only)} tablic tolko na localhost')
        if remote_only:
            print(f'    - {len(remote_only)} tablic tolko na boevom')
        if differences_found:
            print(f'    - Razlichiya v strukture nekotorykh tablic')

if __name__ == "__main__":
    compare_structures()

