#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Миграция: Добавление колонки timezone в таблицу users

Добавляет:
1. Колонку timezone в users (DEFAULT 'Europe/Moscow')
2. Настройки в bot_settings:
   - feature_timezone_enabled (по умолчанию '0')
   - admin_timezone (по умолчанию 'Europe/Moscow')

БЕЗОПАСНОСТЬ:
- ALTER TABLE ADD COLUMN безопасна в SQLite
- Проверяет существование колонки перед добавлением
- Не блокирует таблицу
- Feature flag остаётся выключенным
"""

import sys
import sqlite3
import logging
from pathlib import Path
from zoneinfo import ZoneInfo, available_timezones

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Путь к базе данных
PROJECT_ROOT = Path(__file__).parent.parent
DB_FILE = PROJECT_ROOT / "users.db"

# Валидные timezones
VALID_TIMEZONES = available_timezones()


def validate_timezone(tz_name: str) -> bool:
    """
    Проверяет, что timezone валиден через zoneinfo.
    
    Args:
        tz_name: Название timezone (например, 'Europe/Moscow')
        
    Returns:
        True если timezone валиден, иначе False
    """
    try:
        ZoneInfo(tz_name)
        return True
    except Exception as e:
        logger.error(f"Невалидный timezone '{tz_name}': {e}")
        return False


def column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    """
    Проверяет существование колонки в таблице.
    
    Args:
        cursor: Курсор базы данных
        table: Название таблицы
        column: Название колонки
        
    Returns:
        True если колонка существует, иначе False
    """
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def setting_exists(cursor: sqlite3.Cursor, key: str) -> bool:
    """
    Проверяет существование настройки в bot_settings.
    
    Args:
        cursor: Курсор базы данных
        key: Ключ настройки
        
    Returns:
        True если настройка существует, иначе False
    """
    cursor.execute("SELECT COUNT(*) FROM bot_settings WHERE key = ?", (key,))
    count = cursor.fetchone()[0]
    return count > 0


def add_timezone_column(conn: sqlite3.Connection) -> bool:
    """
    Добавляет колонку timezone в таблицу users.
    
    Args:
        conn: Соединение с базой данных
        
    Returns:
        True если колонка добавлена или уже существует, иначе False
    """
    try:
        cursor = conn.cursor()
        
        # Проверяем существование колонки
        if column_exists(cursor, 'users', 'timezone'):
            logger.info("✅ Колонка 'timezone' уже существует в таблице 'users'")
            return True
        
        # Добавляем колонку с DEFAULT значением
        logger.info("Добавляю колонку 'timezone' в таблицу 'users'...")
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN timezone TEXT DEFAULT 'Europe/Moscow'
        """)
        conn.commit()
        
        logger.info("✅ Колонка 'timezone' успешно добавлена")
        
        # Проверяем, что колонка действительно добавлена
        if not column_exists(cursor, 'users', 'timezone'):
            logger.error("❌ ОШИБКА: Колонка не была добавлена!")
            return False
        
        # Проверяем DEFAULT значение
        cursor.execute("PRAGMA table_info(users)")
        for row in cursor.fetchall():
            if row[1] == 'timezone':
                default_value = row[4]
                logger.info(f"   DEFAULT значение: {default_value}")
                if default_value != "'Europe/Moscow'":
                    logger.warning(f"⚠️ DEFAULT значение отличается от ожидаемого: {default_value}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении колонки timezone: {e}")
        conn.rollback()
        return False


def add_bot_settings(conn: sqlite3.Connection) -> bool:
    """
    Добавляет настройки timezone в bot_settings.
    
    Args:
        conn: Соединение с базой данных
        
    Returns:
        True если настройки добавлены, иначе False
    """
    try:
        cursor = conn.cursor()
        
        # 1. feature_timezone_enabled (по умолчанию выключен)
        if setting_exists(cursor, 'feature_timezone_enabled'):
            logger.info("✅ Настройка 'feature_timezone_enabled' уже существует")
        else:
            logger.info("Добавляю настройку 'feature_timezone_enabled'...")
            cursor.execute("""
                INSERT INTO bot_settings (key, value) 
                VALUES ('feature_timezone_enabled', '0')
            """)
            logger.info("✅ Настройка 'feature_timezone_enabled' добавлена (значение: 0)")
        
        # 2. admin_timezone (по умолчанию 'Europe/Moscow')
        if setting_exists(cursor, 'admin_timezone'):
            logger.info("✅ Настройка 'admin_timezone' уже существует")
        else:
            logger.info("Добавляю настройку 'admin_timezone'...")
            cursor.execute("""
                INSERT INTO bot_settings (key, value) 
                VALUES ('admin_timezone', 'Europe/Moscow')
            """)
            logger.info("✅ Настройка 'admin_timezone' добавлена (значение: Europe/Moscow)")
        
        conn.commit()
        
        # Проверяем добавленные настройки
        cursor.execute("SELECT key, value FROM bot_settings WHERE key LIKE '%timezone%'")
        settings = cursor.fetchall()
        logger.info("\nТекущие настройки timezone:")
        for key, value in settings:
            logger.info(f"  {key} = {value}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении настроек: {e}")
        conn.rollback()
        return False


def verify_migration(conn: sqlite3.Connection) -> bool:
    """
    Проверяет результаты миграции.
    
    Args:
        conn: Соединение с базой данных
        
    Returns:
        True если всё в порядке, иначе False
    """
    try:
        cursor = conn.cursor()
        
        logger.info("\n" + "="*60)
        logger.info("ПРОВЕРКА МИГРАЦИИ")
        logger.info("="*60)
        
        # 1. Проверка колонки timezone
        if not column_exists(cursor, 'users', 'timezone'):
            logger.error("❌ Колонка 'timezone' не найдена в таблице 'users'")
            return False
        logger.info("✅ Колонка 'timezone' существует")
        
        # 2. Проверка настроек
        required_settings = {
            'feature_timezone_enabled': '0',
            'admin_timezone': 'Europe/Moscow'
        }
        
        for key, expected_value in required_settings.items():
            if not setting_exists(cursor, key):
                logger.error(f"❌ Настройка '{key}' не найдена")
                return False
            
            cursor.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
            actual_value = cursor.fetchone()[0]
            
            if actual_value != expected_value:
                logger.warning(f"⚠️ Настройка '{key}': ожидалось '{expected_value}', получено '{actual_value}'")
            else:
                logger.info(f"✅ Настройка '{key}' = {actual_value}")
        
        # 3. Проверка количества пользователей с timezone
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE timezone IS NOT NULL")
        users_with_tz = cursor.fetchone()[0]
        
        logger.info(f"\nСтатистика пользователей:")
        logger.info(f"  Всего пользователей: {total_users}")
        logger.info(f"  С timezone: {users_with_tz}")
        
        if total_users > 0 and users_with_tz != total_users:
            logger.warning(f"⚠️ Не все пользователи имеют timezone!")
        
        # 4. Валидация timezone в базе
        cursor.execute("SELECT DISTINCT timezone FROM users WHERE timezone IS NOT NULL")
        timezones = [row[0] for row in cursor.fetchall()]
        
        if timezones:
            logger.info(f"\nИспользуемые timezones:")
            for tz in timezones:
                is_valid = validate_timezone(tz)
                status = "✅" if is_valid else "❌"
                logger.info(f"  {status} {tz}")
                if not is_valid:
                    logger.error(f"❌ Невалидный timezone в базе: {tz}")
                    return False
        
        logger.info("\n" + "="*60)
        logger.info("✅ МИГРАЦИЯ УСПЕШНО ЗАВЕРШЕНА")
        logger.info("="*60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке миграции: {e}")
        return False


def main():
    """Основная функция миграции."""
    logger.info("="*60)
    logger.info("МИГРАЦИЯ: Добавление поддержки timezone")
    logger.info("="*60)
    logger.info(f"База данных: {DB_FILE}")
    
    # Проверяем существование базы данных
    if not DB_FILE.exists():
        logger.error(f"❌ База данных не найдена: {DB_FILE}")
        return False
    
    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect(DB_FILE)
        logger.info("✅ Подключение к базе данных установлено")
        
        # Шаг 1: Добавляем колонку timezone
        logger.info("\n" + "-"*60)
        logger.info("Шаг 1: Добавление колонки timezone")
        logger.info("-"*60)
        if not add_timezone_column(conn):
            logger.error("❌ Не удалось добавить колонку timezone")
            return False
        
        # Шаг 2: Добавляем настройки в bot_settings
        logger.info("\n" + "-"*60)
        logger.info("Шаг 2: Добавление настроек в bot_settings")
        logger.info("-"*60)
        if not add_bot_settings(conn):
            logger.error("❌ Не удалось добавить настройки")
            return False
        
        # Шаг 3: Проверяем результаты
        if not verify_migration(conn):
            logger.error("❌ Проверка миграции не пройдена")
            return False
        
        conn.close()
        logger.info("\n✅ Миграция успешно завершена!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при миграции: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

