#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Скрипт для сравнения баз данных"""

import sqlite3
import sys
from pathlib import Path

def analyze_db(db_path):
    """Анализирует базу данных и возвращает информацию"""
    if not Path(db_path).exists():
        return None
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Получаем список таблиц
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    # Получаем количество записей в каждой таблице
    table_counts = {}
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            table_counts[table] = cursor.fetchone()[0]
        except Exception as e:
            table_counts[table] = f"Error: {e}"
    
    # Получаем схему таблиц
    schemas = {}
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        schemas[table] = cursor.fetchall()
    
    file_size = Path(db_path).stat().st_size
    
    conn.close()
    
    return {
        'path': db_path,
        'size': file_size,
        'tables': tables,
        'counts': table_counts,
        'schemas': schemas
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python test_compare_db.py <путь_к_базе>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    info = analyze_db(db_path)
    
    if info is None:
        print(f"База данных {db_path} не найдена")
        sys.exit(1)
    
    print(f"База данных: {info['path']}")
    print(f"Размер: {info['size']} байт ({info['size'] / 1024:.2f} KB)")
    print(f"\nТаблицы: {', '.join(info['tables'])}")
    print("\nКоличество записей:")
    for table, count in info['counts'].items():
        print(f"  {table}: {count}")
    
    print("\nСхемы таблиц:")
    for table, schema in info['schemas'].items():
        print(f"\n{table}:")
        for col in schema:
            print(f"  {col[1]} ({col[2]})")







