#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для копирования тарифных планов с хоста Эстония на другие хосты.
Использование: python test_copy_plans.py
"""

import sqlite3
import json
import sys
from pathlib import Path

# Путь к базе данных
DB_FILE = Path("users.db")

def get_all_hosts():
    """Получить все хосты из базы данных"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM xui_hosts ORDER BY host_name")
            hosts = cursor.fetchall()
            return [dict(row) for row in hosts]
    except sqlite3.Error as e:
        print(f"Ошибка при получении списка хостов: {e}")
        return []

def get_plans_for_host(host_name: str):
    """Получить все планы для указанного хоста"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Убедимся, что все колонки существуют
            col_types = {
                'hours': 'INTEGER DEFAULT 0',
                'key_provision_mode': 'TEXT DEFAULT "key"',
                'display_mode': 'TEXT DEFAULT "all"',
                'display_mode_groups': 'TEXT DEFAULT NULL',
                'days': 'INTEGER DEFAULT 0',
                'traffic_gb': 'REAL DEFAULT 0'
            }
            for col in ['hours', 'key_provision_mode', 'display_mode', 'display_mode_groups', 'days', 'traffic_gb']:
                try:
                    cursor.execute(f"ALTER TABLE plans ADD COLUMN {col} {col_types[col]}")
                except Exception:
                    pass
            
            cursor.execute("SELECT * FROM plans WHERE host_name = ? ORDER BY months, days, hours", (host_name,))
            plans = cursor.fetchall()
            return [dict(row) for row in plans]
    except sqlite3.Error as e:
        print(f"Ошибка при получении планов для хоста '{host_name}': {e}")
        return []

def create_plan(host_name: str, plan_name: str, months: int, price: float, days: int = 0, 
                traffic_gb: float = 0.0, hours: int = 0, key_provision_mode: str = 'key', 
                display_mode: str = 'all', display_mode_groups: str = None):
    """Создать новый план для хоста"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Убедимся, что все колонки существуют
            col_types = {
                'hours': 'INTEGER DEFAULT 0',
                'key_provision_mode': 'TEXT DEFAULT "key"',
                'display_mode': 'TEXT DEFAULT "all"',
                'display_mode_groups': 'TEXT DEFAULT NULL',
                'days': 'INTEGER DEFAULT 0',
                'traffic_gb': 'REAL DEFAULT 0'
            }
            for col in ['hours', 'key_provision_mode', 'display_mode', 'display_mode_groups', 'days', 'traffic_gb']:
                try:
                    cursor.execute(f"ALTER TABLE plans ADD COLUMN {col} {col_types[col]}")
                except Exception:
                    pass
            
            cursor.execute(
                """INSERT INTO plans (host_name, plan_name, months, price, days, traffic_gb, hours, 
                   key_provision_mode, display_mode, display_mode_groups) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (host_name, plan_name, months, price, days, traffic_gb, hours, 
                 key_provision_mode, display_mode, display_mode_groups)
            )
            conn.commit()
            print(f"✓ Создан план '{plan_name}' для хоста '{host_name}'")
            return True
    except sqlite3.Error as e:
        print(f"✗ Ошибка при создании плана '{plan_name}' для хоста '{host_name}': {e}")
        return False

def copy_plans_from_source_to_targets(source_host_name: str, target_host_names: list):
    """Скопировать все планы с исходного хоста на целевые хосты"""
    if not DB_FILE.exists():
        print(f"✗ База данных не найдена: {DB_FILE}")
        return False
    
    # Получаем все хосты
    all_hosts = get_all_hosts()
    print(f"\nНайдено хостов в базе: {len(all_hosts)}")
    for host in all_hosts:
        print(f"  - {host['host_name']}")
    
    # Находим исходный хост
    source_host = None
    for host in all_hosts:
        if source_host_name.lower() in host['host_name'].lower() or host['host_name'].lower() in source_host_name.lower():
            source_host = host
            break
    
    if not source_host:
        print(f"\n✗ Исходный хост '{source_host_name}' не найден!")
        return False
    
    print(f"\n✓ Исходный хост найден: {source_host['host_name']}")
    
    # Получаем планы исходного хоста
    source_plans = get_plans_for_host(source_host['host_name'])
    if not source_plans:
        print(f"✗ Планы для хоста '{source_host['host_name']}' не найдены!")
        return False
    
    print(f"\n✓ Найдено планов на исходном хосте: {len(source_plans)}")
    for plan in source_plans:
        print(f"  - {plan['plan_name']} ({plan['months']} мес., {plan.get('days', 0)} дн., {plan.get('hours', 0)} ч., {plan['price']} руб.)")
    
    # Находим целевые хосты
    target_hosts = []
    for target_name in target_host_names:
        found = False
        for host in all_hosts:
            if target_name.lower() in host['host_name'].lower() or host['host_name'].lower() in target_name.lower():
                target_hosts.append(host)
                found = True
                print(f"\n✓ Целевой хост найден: {host['host_name']}")
                break
        if not found:
            print(f"\n⚠ Целевой хост '{target_name}' не найден, пропускаем")
    
    if not target_hosts:
        print("\n✗ Не найдено ни одного целевого хоста!")
        return False
    
    # Копируем планы на каждый целевой хост
    total_copied = 0
    for target_host in target_hosts:
        print(f"\n📋 Копирование планов на хост: {target_host['host_name']}")
        
        # Проверяем существующие планы
        existing_plans = get_plans_for_host(target_host['host_name'])
        existing_plan_names = {p['plan_name'] for p in existing_plans}
        
        copied_count = 0
        skipped_count = 0
        
        for plan in source_plans:
            # Пропускаем, если план уже существует
            if plan['plan_name'] in existing_plan_names:
                print(f"  ⚠ План '{plan['plan_name']}' уже существует, пропускаем")
                skipped_count += 1
                continue
            
            # Копируем план
            success = create_plan(
                host_name=target_host['host_name'],
                plan_name=plan['plan_name'],
                months=plan['months'],
                price=plan['price'],
                days=plan.get('days', 0),
                traffic_gb=plan.get('traffic_gb', 0.0),
                hours=plan.get('hours', 0),
                key_provision_mode=plan.get('key_provision_mode', 'key'),
                display_mode=plan.get('display_mode', 'all'),
                display_mode_groups=plan.get('display_mode_groups')
            )
            
            if success:
                copied_count += 1
                total_copied += 1
        
        print(f"  ✓ Скопировано: {copied_count}, пропущено: {skipped_count}")
    
    print(f"\n✅ Всего скопировано планов: {total_copied}")
    return True

def main():
    """Основная функция"""
    print("=" * 60)
    print("Копирование тарифных планов между хостами")
    print("=" * 60)
    
    # Определяем исходный и целевые хосты
    source_host = "🇪🇪 Эстония"
    target_hosts = [
        "🇫🇮 Финляндия 1",
        "🇳🇱 Нидерланды 1",
        "🇩🇪 Германия 1"
    ]
    
    print(f"\nИсходный хост: {source_host}")
    print(f"Целевые хосты: {', '.join(target_hosts)}")
    
    # Выполняем копирование
    success = copy_plans_from_source_to_targets(source_host, target_hosts)
    
    if success:
        print("\n✅ Операция завершена успешно!")
        return 0
    else:
        print("\n✗ Операция завершена с ошибками!")
        return 1

if __name__ == "__main__":
    sys.exit(main())

