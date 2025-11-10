#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Скрипт для сравнения версий и баз данных локально и на сервере"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Настройка вывода UTF-8 для Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def compare_databases(local_db, server_db):
    """Сравнивает две базы данных"""
    results = {
        'local': {},
        'server': {},
        'differences': []
    }
    
    # Анализируем локальную базу
    if Path(local_db).exists():
        conn_local = sqlite3.connect(local_db)
        cursor_local = conn_local.cursor()
        cursor_local.execute("SELECT name FROM sqlite_master WHERE type='table'")
        local_tables = [row[0] for row in cursor_local.fetchall()]
        
        local_counts = {}
        for table in local_tables:
            cursor_local.execute(f"SELECT COUNT(*) FROM {table}")
            local_counts[table] = cursor_local.fetchone()[0]
        
        results['local'] = {
            'size': Path(local_db).stat().st_size,
            'tables': local_tables,
            'counts': local_counts,
            'modified': datetime.fromtimestamp(Path(local_db).stat().st_mtime)
        }
        conn_local.close()
    
    # Анализируем серверную базу
    if Path(server_db).exists():
        conn_server = sqlite3.connect(server_db)
        cursor_server = conn_server.cursor()
        cursor_server.execute("SELECT name FROM sqlite_master WHERE type='table'")
        server_tables = [row[0] for row in cursor_server.fetchall()]
        
        server_counts = {}
        for table in server_tables:
            cursor_server.execute(f"SELECT COUNT(*) FROM {table}")
            server_counts[table] = cursor_server.fetchone()[0]
        
        results['server'] = {
            'size': Path(server_db).stat().st_size,
            'tables': server_tables,
            'counts': server_counts,
            'modified': datetime.fromtimestamp(Path(server_db).stat().st_mtime)
        }
        conn_server.close()
    
    # Находим различия
    if results['local'] and results['server']:
        all_tables = set(results['local']['tables']) | set(results['server']['tables'])
        
        for table in all_tables:
            local_count = results['local']['counts'].get(table, 0)
            server_count = results['server']['counts'].get(table, 0)
            
            if local_count != server_count:
                diff = local_count - server_count
                results['differences'].append({
                    'table': table,
                    'local': local_count,
                    'server': server_count,
                    'diff': diff
                })
    
    return results

if __name__ == "__main__":
    local_db = "users.db"
    server_db = "tests/server_users.db"
    
    print("=" * 80)
    print("СРАВНЕНИЕ БАЗ ДАННЫХ")
    print("=" * 80)
    
    results = compare_databases(local_db, server_db)
    
    if results['local']:
        print(f"\n[ЛОКАЛЬНАЯ БАЗА] ({local_db}):")
        print(f"   Размер: {results['local']['size']:,} байт ({results['local']['size'] / 1024:.2f} KB)")
        print(f"   Изменена: {results['local']['modified'].strftime('%d.%m.%Y %H:%M:%S')}")
        print(f"   Таблиц: {len(results['local']['tables'])}")
    
    if results['server']:
        print(f"\n[СЕРВЕРНАЯ БАЗА] ({server_db}):")
        print(f"   Размер: {results['server']['size']:,} байт ({results['server']['size'] / 1024:.2f} KB)")
        print(f"   Изменена: {results['server']['modified'].strftime('%d.%m.%Y %H:%M:%S')}")
        print(f"   Таблиц: {len(results['server']['tables'])}")
    
    if results['differences']:
        print(f"\n[!] РАЗЛИЧИЯ В КОЛИЧЕСТВЕ ЗАПИСЕЙ:")
        print(f"{'Таблица':<25} {'Локально':<12} {'Сервер':<12} {'Разница':<12}")
        print("-" * 80)
        for diff in sorted(results['differences'], key=lambda x: abs(x['diff']), reverse=True):
            sign = "+" if diff['diff'] > 0 else ""
            print(f"{diff['table']:<25} {diff['local']:<12} {diff['server']:<12} {sign}{diff['diff']:<12}")
    else:
        print("\n[OK] Количество записей во всех таблицах совпадает")
    
    # Показываем все таблицы с количеством записей
    if results['local'] and results['server']:
        all_tables = sorted(set(results['local']['tables']) | set(results['server']['tables']))
        print(f"\n[СТАТИСТИКА] ПОЛНАЯ СТАТИСТИКА ПО ТАБЛИЦАМ:")
        print(f"{'Таблица':<25} {'Локально':<12} {'Сервер':<12}")
        print("-" * 80)
        for table in all_tables:
            local_count = results['local']['counts'].get(table, '-')
            server_count = results['server']['counts'].get(table, '-')
            marker = " [!]" if local_count != server_count else ""
            print(f"{table:<25} {str(local_count):<12} {str(server_count):<12}{marker}")

