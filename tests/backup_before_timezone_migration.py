#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для создания бэкапа БД перед миграцией timezone

Использование:
    python tests/backup_before_timezone_migration.py
    
Создаёт копию users.db с временной меткой в имени файла.
"""

import sys
import shutil
from datetime import datetime
from pathlib import Path

# Добавляем путь к модулям проекта
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import DB_FILE


def create_backup():
    """Создаёт бэкап БД с временной меткой"""
    
    print("=" * 80)
    print("СОЗДАНИЕ БЭКАПА БД ПЕРЕД МИГРАЦИЕЙ TIMEZONE")
    print("=" * 80 + "\n")
    
    # Проверяем существование БД
    if not DB_FILE.exists():
        print(f"[ERROR] БД не найдена: {DB_FILE}")
        return False
    
    # Генерируем имя файла бэкапа
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = DB_FILE.parent / f"users_backup_{timestamp}.db"
    
    try:
        # Создаём бэкап
        print(f"[INFO] Исходный файл: {DB_FILE}")
        print(f"[INFO] Создание бэкапа: {backup_file}")
        
        shutil.copy2(DB_FILE, backup_file)
        
        # Проверяем размер
        original_size = DB_FILE.stat().st_size
        backup_size = backup_file.stat().st_size
        
        if original_size != backup_size:
            print(f"[ERROR] Размеры файлов не совпадают!")
            print(f"         Оригинал: {original_size} байт")
            print(f"         Бэкап: {backup_size} байт")
            return False
        
        print(f"\n[OK] Бэкап успешно создан!")
        print(f"     Размер: {original_size:,} байт ({original_size / 1024 / 1024:.2f} МБ)")
        print(f"     Путь: {backup_file}")
        
        # Инструкции по восстановлению
        print("\n" + "=" * 80)
        print("ИНСТРУКЦИИ ПО ВОССТАНОВЛЕНИЮ")
        print("=" * 80)
        print("\nЕсли что-то пойдёт не так, восстановите БД:")
        print(f"\n  Windows PowerShell:")
        print(f"  npx nx stop bot")
        print(f"  Copy-Item -Path '{backup_file}' -Destination '{DB_FILE}' -Force")
        print(f"  npx nx serve bot")
        print(f"\n  Linux/Mac:")
        print(f"  npx nx stop bot")
        print(f"  cp {backup_file} {DB_FILE}")
        print(f"  npx nx serve bot")
        print("\n" + "=" * 80 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Ошибка при создании бэкапа: {e}")
        return False


def main():
    """Главная функция"""
    success = create_backup()
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())

