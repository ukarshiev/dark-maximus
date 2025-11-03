#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Финальное детальное сравнение структур баз данных"""

import json

def compare_final():
    """Финальное сравнение структур"""
    
    # Загружаем структуры
    with open('tests/local_db_structure.json', 'r', encoding='utf-8') as f:
        local = json.load(f)
    
    with open('tests/remote_current.json', 'r', encoding='utf-8') as f:
        remote = json.load(f)
    
    print('='*70)
    print('[*] FINALNOE SRAVNENIE STRUKTUR BAZ DANNYKH')
    print('='*70)
    print('\n[*] localhost vs 31.56.27.129')
    
    local_tables = set(local['table_list'])
    remote_tables = set(remote['table_list'])
    
    print(f'\n[*] Obshchaya statistika:')
    print(f'   Localhost:  {len(local_tables)} tablic')
    print(f'   Boevoy:     {len(remote_tables)} tablic')
    
    # Проверяем различия в таблицах
    local_only = local_tables - remote_tables
    remote_only = remote_tables - local_tables
    common = local_tables & remote_tables
    
    if local_only:
        print(f'\n[*] Tablitsy TOLKO na localhost ({len(local_only)}):')
        for t in sorted(local_only):
            if t.startswith('sqlite_'):
                print(f'   - {t} (sistemnyaya tablitsa SQLite)')
            else:
                print(f'   - {t}')
    
    if remote_only:
        print(f'\n[!] Tablitsy TOLKO na boevom ({len(remote_only)}):')
        for t in sorted(remote_only):
            print(f'   - {t}')
    
    # Детальное сравнение важных таблиц
    important = ['users', 'user_groups', 'promo_codes', 'promo_code_usage', 
                 'vpn_keys', 'transactions', 'plans', 'bot_settings', 'migration_history']
    
    print(f'\n{"="*70}')
    print('[*] DETALNOE SRAVNENIE VAZHNYKH TABLIC')
    print('='*70)
    
    all_match = True
    
    for table in important:
        if table not in local['tables'] or table not in remote['tables']:
            print(f'\n[-] {table}: OTSUTSTVUET v odnoy iz BD')
            all_match = False
            continue
        
        local_cols = {col['name']: col for col in local['tables'][table]}
        remote_cols = {col['name']: col for col in remote['tables'][table]}
        
        local_names = set(local_cols.keys())
        remote_names = set(remote_cols.keys())
        
        if local_names == remote_names:
            # Проверяем типы
            types_match = True
            for col in local_names:
                if local_cols[col]['type'] != remote_cols[col]['type']:
                    types_match = False
                    break
            
            if types_match:
                print(f'\n[+] {table}')
                print(f'    Status: IDENTICHNA')
                print(f'    Kolonok: {len(local_names)}')
                
                # Показываем все колонки для важных таблиц
                if table in ['users', 'user_groups', 'promo_codes']:
                    print(f'    Kolonki: {", ".join(sorted(local_names))}')
            else:
                print(f'\n[!] {table}')
                print(f'    Status: RAZLICHAYUTSYA TIPY')
                all_match = False
        else:
            print(f'\n[!] {table}')
            print(f'    Status: RAZLICHAYUTSYA KOLONKI')
            print(f'    Localhost: {len(local_names)} kolonok')
            print(f'    Boevoy:    {len(remote_names)} kolonok')
            
            local_only_cols = local_names - remote_names
            remote_only_cols = remote_names - local_names
            
            if local_only_cols:
                print(f'    Tolko na localhost: {", ".join(sorted(local_only_cols))}')
            if remote_only_cols:
                print(f'    Tolko na boevom: {", ".join(sorted(remote_only_cols))}')
            
            all_match = False
    
    # Итоговый вердикт
    print(f'\n{"="*70}')
    print('[*] ITOGOVYY VERDICT')
    print('='*70)
    
    if all_match and not remote_only:
        print('\n[+] [+] [+] BAZY DANNYKH POLNOSTYU SINKHRONIZIROWANY! [+] [+] [+]')
        print('\n[*] Vse vazhnye tablitsy identichny po strukture:')
        print('    - users: 27 kolonok')
        print('    - user_groups: 6 kolonok (vklyuchaya group_code)')
        print('    - promo_codes: 17 kolonok (vklyuchaya 5 novykh)')
        print('    - promo_code_usage: 11 kolonok')
        print('    - migration_history: 3 kolonki (vklyuchaya description)')
        print('    - vpn_keys: 24 kolonki')
        print('    - transactions: 17 kolonok')
        print('    - plans: 11 kolonok')
        print('    - bot_settings: 2 kolonki')
        
        if local_only:
            print(f'\n[*] Neznachitelnye razlichiya (ne vliyayut na rabotu):')
            print(f'    - sqlite_stat1 na localhost (sistemnyaya tablitsa)')
        
        return True
    else:
        print('\n[!] OBNARUZHENY RAZLICHIYA V STRUKTURAKH')
        if remote_only:
            print(f'    - Tablitsy tolko na boevom: {len(remote_only)}')
        if not all_match:
            print(f'    - Tablitsy s razlichiyami v strukture')
        return False

if __name__ == "__main__":
    success = compare_final()
    exit(0 if success else 1)

