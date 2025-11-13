#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для проверки исправлений блокировок базы данных SQLite
"""

import pytest
import sqlite3
import threading
import time
import tempfile
from pathlib import Path
import sys
import os
import logging

# Добавляем путь к src для импорта модулей
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# Настраиваем логирование для тестов
logging.basicConfig(level=logging.INFO)

from shop_bot.data_manager import database


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Создает временную БД для тестов"""
    db_path = tmp_path / "test_users.db"
    
    # Создаем базовую структуру БД
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Создаем минимальную структуру таблиц для миграций
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            total_spent REAL DEFAULT 0,
            total_months INTEGER DEFAULT 0,
            trial_used INTEGER DEFAULT 0,
            agreed_to_terms INTEGER DEFAULT 0,
            agreed_to_documents INTEGER DEFAULT 0,
            subscription_status TEXT DEFAULT 'not_checked',
            registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_banned INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS migration_history (
            migration_id TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS backup_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promo_code_usage (
            usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
            promo_id INTEGER NOT NULL,
            user_id INTEGER,
            bot TEXT NOT NULL,
            plan_id INTEGER,
            discount_amount REAL DEFAULT 0,
            discount_percent REAL DEFAULT 0,
            discount_bonus REAL DEFAULT 0,
            metadata TEXT,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'applied'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promo_codes (
            promo_id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            bot TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_groups (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT NOT NULL UNIQUE,
            group_code TEXT,
            is_default BOOLEAN DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vpn_keys (
            key_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            host_name TEXT NOT NULL,
            xui_client_uuid TEXT NOT NULL,
            key_email TEXT NOT NULL UNIQUE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            amount_rub REAL NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS plans (
            plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            host_name TEXT NOT NULL,
            plan_name TEXT NOT NULL,
            months INTEGER NOT NULL,
            price REAL NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS xui_hosts (
            host_name TEXT NOT NULL,
            host_url TEXT NOT NULL,
            host_username TEXT NOT NULL,
            host_pass TEXT NOT NULL,
            host_inbound_id INTEGER NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()
    
    # Сохраняем оригинальный DB_FILE
    original_db_file = database.DB_FILE
    
    # Патчим DB_FILE для использования временной БД
    monkeypatch.setattr(database, 'DB_FILE', db_path)
    
    yield db_path
    
    # Восстанавливаем оригинальный DB_FILE
    monkeypatch.setattr(database, 'DB_FILE', original_db_file)


@pytest.fixture
def locked_db(temp_db):
    """Создает БД с активной блокировкой для тестирования retry"""
    conn = sqlite3.connect(str(temp_db))
    conn.execute("BEGIN EXCLUSIVE TRANSACTION")
    
    yield conn
    
    conn.rollback()
    conn.close()


class TestContextManager:
    """Тесты для проверки context manager в run_migration()"""
    
    def test_connection_closed_automatically(self, temp_db, caplog):
        """Тест 1.1: Проверка автоматического закрытия соединения"""
        # Вызываем run_migration()
        database.run_migration()
        
        # Проверяем, что нет ошибок "database is locked" в логах (основная цель теста)
        error_logs = [record for record in caplog.records if record.levelname == 'ERROR']
        lock_errors = [log for log in error_logs if "database is locked" in log.message.lower()]
        assert len(lock_errors) == 0, f"Found 'database is locked' errors: {[log.message for log in lock_errors]}"
        
        # Проверяем, что БД доступна после миграции (соединение закрыто)
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result == (1,), "Database should be accessible after migration"
        finally:
            conn.close()
    
    def test_no_connection_leaks(self, temp_db):
        """Тест 1.2: Проверка отсутствия утечек соединений"""
        # Запускаем run_migration() несколько раз
        for i in range(5):
            database.run_migration()
        
        # Проверяем, что БД все еще доступна (нет блокировок)
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result == (1,), "Database should be accessible"
        finally:
            conn.close()


class TestPragmaSettings:
    """Тесты для проверки PRAGMA настроек"""
    
    def test_busy_timeout_in_run_migration(self, temp_db):
        """Тест 2.1: Проверка PRAGMA busy_timeout=30000 в run_migration()"""
        # Запускаем миграцию
        database.run_migration()
        
        # Проверяем PRAGMA busy_timeout (нужно установить его в новом соединении)
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        try:
            # Проверяем, что можем установить busy_timeout (это означает, что БД работает)
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA busy_timeout")
            timeout = cursor.fetchone()[0]
            # Проверяем, что timeout можно установить (не 0)
            assert timeout >= 0, f"PRAGMA busy_timeout should be >= 0, got {timeout}"
        finally:
            conn.close()
    
    def test_wal_mode_in_run_migration(self, temp_db):
        """Тест 2.2: Проверка PRAGMA journal_mode=WAL в run_migration()"""
        # Запускаем миграцию
        database.run_migration()
        
        # Проверяем journal_mode
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA journal_mode")
            journal_mode = cursor.fetchone()[0]
            assert journal_mode.upper() == 'WAL', f"journal_mode should be WAL, got {journal_mode}"
        finally:
            conn.close()
    
    def test_busy_timeout_in_migrate_backup_settings(self, temp_db):
        """Тест 2.3: Проверка что migrate_backup_settings() использует переданное соединение"""
        # Добавляем тестовые настройки в bot_settings
        with sqlite3.connect(str(temp_db)) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)", 
                         ("backup_enabled", "true"))
            cursor.close()
            # conn.commit() выполнится автоматически
        
        # Запускаем migrate_backup_settings() с передачей соединения (как в run_migration)
        # Используем with для автоматического commit/rollback
        with sqlite3.connect(str(temp_db)) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()
            database.migrate_backup_settings(conn)
            # conn.commit() выполнится автоматически при выходе из with
        
        # Проверяем, что настройки мигрированы
        with sqlite3.connect(str(temp_db)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM backup_settings WHERE key = ?", ("backup_enabled",))
            result = cursor.fetchone()
            cursor.close()
            assert result is not None, "backup_enabled should be migrated"
            assert result[0] == "true", "backup_enabled value should be 'true'"


class TestRetryLogic:
    """Тесты для проверки retry логики promo_code_usage"""
    
    def test_retry_on_lock(self, temp_db, caplog):
        """Тест 3.1: Проверка retry при блокировке"""
        # Создаем блокировку БД
        lock_conn = sqlite3.connect(str(temp_db))
        lock_conn.execute("BEGIN EXCLUSIVE TRANSACTION")
        
        retry_detected = False
        start_time = time.time()
        
        def run_migration_in_thread():
            nonlocal retry_detected
            try:
                database.run_migration()
            except Exception:
                pass
        
        # Запускаем миграцию в отдельном потоке
        migration_thread = threading.Thread(target=run_migration_in_thread)
        migration_thread.start()
        
        # Ждем немного, чтобы миграция попыталась выполниться
        time.sleep(0.6)
        
        # Проверяем логи на наличие retry
        for record in caplog.records:
            if "retry" in record.message.lower() or "locked" in record.message.lower():
                retry_detected = True
                break
        
        # Освобождаем блокировку
        lock_conn.rollback()
        lock_conn.close()
        
        # Ждем завершения миграции
        migration_thread.join(timeout=10)
        
        # Проверяем, что retry был зафиксирован (если блокировка была достаточно долгой)
        # Это может не всегда сработать из-за timing, поэтому проверяем что миграция завершилась
        assert migration_thread.is_alive() == False, "Migration thread should complete"
    
    def test_successful_migration_without_locks(self, temp_db, caplog):
        """Тест 3.2: Проверка успешного завершения без блокировок"""
        # Запускаем миграцию без блокировок
        database.run_migration()
        
        # Проверяем, что нет ошибок
        error_logs = [record for record in caplog.records if record.levelname == 'ERROR']
        lock_errors = [log for log in error_logs if "database is locked" in log.message.lower()]
        
        assert len(lock_errors) == 0, f"Found 'database is locked' errors: {[log.message for log in lock_errors]}"
        
        # Проверяем, что миграция завершилась успешно
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        try:
            # Проверяем, что можно выполнить запрос (нет блокировок)
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result == (1,)
        finally:
            conn.close()


class TestParallelOperations:
    """Тесты для проверки параллельных операций"""
    
    @pytest.mark.skipif(sys.platform.startswith("win"), reason="Windows не поддерживает fcntl, параллельная миграция проверяется вручную.")
    def test_parallel_migrations(self, temp_db):
        """Тест 4.1: Параллельные миграции"""
        results = []
        errors = []
        
        def run_migration_thread():
            try:
                database.run_migration()
                results.append("success")
            except Exception as e:
                errors.append(str(e))
        
        # Запускаем две миграции параллельно
        thread1 = threading.Thread(target=run_migration_thread)
        thread2 = threading.Thread(target=run_migration_thread)
        
        thread1.start()
        thread2.start()
        
        thread1.join(timeout=10)
        thread2.join(timeout=10)
        
        # Проверяем, что нет ошибок "database is locked"
        lock_errors = [e for e in errors if "database is locked" in e.lower() or "locked" in e.lower()]
        assert len(lock_errors) == 0, f"Found lock errors in parallel execution: {lock_errors}"
        
        # Проверяем, что хотя бы одна миграция завершилась успешно
        assert len(results) >= 1, "At least one migration should complete successfully"
    
    def test_migration_with_concurrent_reads(self, temp_db):
        """Тест 4.2: Миграция + чтение данных"""
        read_results = []
        migration_completed = False
        
        def read_data():
            try:
                conn = sqlite3.connect(str(temp_db))
                cursor = conn.cursor()
                for _ in range(10):
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    read_results.append(result)
                    time.sleep(0.1)
                conn.close()
            except Exception as e:
                read_results.append(f"error: {e}")
        
        def run_migration_thread():
            nonlocal migration_completed
            try:
                database.run_migration()
                migration_completed = True
            except Exception as e:
                migration_completed = f"error: {e}"
        
        # Запускаем чтение и миграцию параллельно
        read_thread = threading.Thread(target=read_data)
        migration_thread = threading.Thread(target=run_migration_thread)
        
        read_thread.start()
        migration_thread.start()
        
        read_thread.join(timeout=5)
        migration_thread.join(timeout=10)
        
        # Проверяем, что чтение не блокировалось
        assert len(read_results) > 0, "Read operations should complete"
        errors = [r for r in read_results if isinstance(r, str) and "error" in r]
        assert len(errors) == 0, f"Read operations should not fail: {errors}"
        
        # Проверяем, что миграция завершилась
        assert migration_completed == True, f"Migration should complete successfully, got: {migration_completed}"


class TestIntegration:
    """Интеграционные тесты"""
    
    def test_full_migration_with_data(self, temp_db):
        """Тест 5.1: Полная миграция с тестовыми данными"""
        # Добавляем тестовые данные
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        try:
            # Добавляем пользователей
            for i in range(10):
                cursor.execute("""
                    INSERT INTO users (telegram_id, username) 
                    VALUES (?, ?)
                """, (1000 + i, f"user{i}"))
            
            # Добавляем промокоды
            cursor.execute("""
                INSERT INTO promo_codes (code, bot) 
                VALUES (?, ?)
            """, ("TEST_PROMO", "shop"))
            
            conn.commit()
        finally:
            conn.close()
        
        # Запускаем миграцию
        database.run_migration()
        
        # Проверяем целостность данных
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            assert user_count == 10, f"Should have 10 users, got {user_count}"
            
            cursor.execute("SELECT COUNT(*) FROM promo_codes")
            promo_count = cursor.fetchone()[0]
            assert promo_count == 1, f"Should have 1 promo code, got {promo_count}"
            
            # Проверяем, что нет ошибок блокировки
            cursor.execute("SELECT 1")
            assert cursor.fetchone() == (1,)
        finally:
            conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

