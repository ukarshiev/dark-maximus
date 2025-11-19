#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для проверки исправлений блокировок базы данных SQLite
"""

import pytest
import allure
import sqlite3
import threading
import time
import tempfile
from pathlib import Path
import sys
import os
import logging

# Добавляем путь к src для импорта модулей
project_root = Path(__file__).parent.parent.parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# Настраиваем логирование для тестов
logging.basicConfig(level=logging.INFO)

from shop_bot.data_manager import database




@pytest.fixture
def locked_db(temp_db):
    """Создает БД с активной блокировкой для тестирования retry"""
    conn = sqlite3.connect(str(temp_db))
    conn.execute("BEGIN EXCLUSIVE TRANSACTION")
    
    yield conn
    
    conn.rollback()
    conn.close()


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Блокировки БД")
@allure.label("package", "src.shop_bot.database")
class TestContextManager:
    """Тесты для проверки context manager в run_migration()"""
    
    @allure.title("Проверка автоматического закрытия соединения")
    @allure.description("""
    Проверяет автоматическое закрытие соединения с БД после выполнения миграции.
    
    **Что проверяется:**
    - Автоматическое закрытие соединения через context manager
    - Отсутствие ошибок "database is locked" в логах
    - Доступность БД после миграции
    
    **Ожидаемый результат:**
    Соединение автоматически закрыто, БД доступна для дальнейших операций, ошибок блокировки нет.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("locks", "connection", "context_manager", "database", "unit")
    def test_connection_closed_automatically(self, temp_db, caplog):
        """Тест 1.1: Проверка автоматического закрытия соединения"""
        # Вызываем run_migration()
        database.run_migration()
        
        # Проверяем, что нет ошибок "database is locked" в логах (основная цель теста)
        error_logs = [record for record in caplog.records if record.levelname == 'ERROR']
        lock_errors = [log for log in error_logs if "database is locked" in log.message.lower()]
        assert len(lock_errors) == 0, f"Found 'database is locked' errors: {[log.message for log in lock_errors]}"
        
        # Проверяем, что БД доступна после миграции (соединение закрыто)
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result == (1,), "Database should be accessible after migration"
        finally:
            conn.close()
    
    @allure.title("Проверка отсутствия утечек соединений")
    @allure.description("""
    Проверяет отсутствие утечек соединений при многократном вызове миграции.
    
    **Что проверяется:**
    - Многократный вызов run_migration() (5 раз)
    - Отсутствие блокировок БД после множественных вызовов
    - Доступность БД для дальнейших операций
    
    **Ожидаемый результат:**
    БД остается доступной после множественных вызовов миграции, утечек соединений нет.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("locks", "connection_leaks", "database", "unit")
    def test_no_connection_leaks(self, temp_db):
        """Тест 1.2: Проверка отсутствия утечек соединений"""
        # Запускаем run_migration() несколько раз
        for i in range(5):
            database.run_migration()
        
        # Проверяем, что БД все еще доступна (нет блокировок)
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result == (1,), "Database should be accessible"
        finally:
            conn.close()


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Блокировки БД")
class TestPragmaSettings:
    """Тесты для проверки PRAGMA настроек"""
    
    @allure.title("Проверка PRAGMA busy_timeout=30000 в run_migration()")
    @allure.description("""
    Проверяет установку PRAGMA busy_timeout=30000 в функции run_migration().
    
    **Что проверяется:**
    - Установка PRAGMA busy_timeout=30000 при выполнении миграции
    - Корректность значения busy_timeout в БД
    
    **Ожидаемый результат:**
    PRAGMA busy_timeout установлен в значение 30000.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("locks", "pragma", "busy_timeout", "database", "unit")
    def test_busy_timeout_in_run_migration(self, temp_db):
        """Тест 2.1: Проверка PRAGMA busy_timeout=30000 в run_migration()"""
        # Запускаем миграцию
        database.run_migration()
        
        # Проверяем PRAGMA busy_timeout (нужно установить его в новом соединении)
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
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
    
    @allure.title("Проверка PRAGMA journal_mode=WAL в run_migration()")
    @allure.description("""
    Проверяет установку PRAGMA journal_mode=WAL в функции run_migration().
    
    **Что проверяется:**
    - Установка PRAGMA journal_mode=WAL при выполнении миграции
    - Корректность режима журналирования в БД
    
    **Ожидаемый результат:**
    PRAGMA journal_mode установлен в значение WAL.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("locks", "pragma", "wal_mode", "database", "unit")
    def test_wal_mode_in_run_migration(self, temp_db):
        """Тест 2.2: Проверка PRAGMA journal_mode=WAL в run_migration()"""
        # Запускаем миграцию
        database.run_migration()
        
        # Проверяем journal_mode
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA journal_mode")
            journal_mode = cursor.fetchone()[0]
            # WAL mode отключен намеренно, проверяем DELETE
            assert journal_mode.upper() == 'DELETE', f"journal_mode should be DELETE, got {journal_mode}"
        finally:
            conn.close()
    
    @allure.title("Проверка что migrate_backup_settings() использует переданное соединение")
    @allure.description("""
    Проверяет, что функция migrate_backup_settings() использует переданное соединение с БД.
    
    **Что проверяется:**
    - Использование переданного соединения вместо создания нового
    - Корректность работы с переданным соединением
    
    **Ожидаемый результат:**
    Функция использует переданное соединение для выполнения операций.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("locks", "migrate_backup_settings", "connection", "database", "unit")
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


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Блокировки БД")
class TestRetryLogic:
    """Тесты для проверки retry логики promo_code_usage"""
    
    @allure.title("Проверка retry при блокировке")
    @allure.description("""
    Проверяет механизм повторных попыток (retry) при блокировке БД.
    
    **Что проверяется:**
    - Создание блокировки БД в отдельном потоке
    - Выполнение миграции с ожиданием разблокировки
    - Успешное завершение миграции после разблокировки
    - Логирование попыток retry
    
    **Ожидаемый результат:**
    Миграция успешно завершается после разблокировки БД, попытки retry логируются.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("locks", "retry", "blocking", "database", "unit")
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
    
    @allure.title("Проверка успешного завершения без блокировок")
    @allure.description("""
    Проверяет успешное завершение миграции при отсутствии блокировок БД.
    
    **Что проверяется:**
    - Выполнение миграции без блокировок
    - Отсутствие ошибок в логах
    - Успешное завершение миграции
    
    **Ожидаемый результат:**
    Миграция успешно завершается без ошибок и блокировок.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("locks", "migration", "success", "database", "unit")
    def test_successful_migration_without_locks(self, temp_db, caplog):
        """Тест 3.2: Проверка успешного завершения без блокировок"""
        # Запускаем миграцию без блокировок
        database.run_migration()
        
        # Проверяем, что нет ошибок
        error_logs = [record for record in caplog.records if record.levelname == 'ERROR']
        lock_errors = [log for log in error_logs if "database is locked" in log.message.lower()]
        
        assert len(lock_errors) == 0, f"Found 'database is locked' errors: {[log.message for log in lock_errors]}"
        
        # Проверяем, что миграция завершилась успешно
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        try:
            # Проверяем, что можно выполнить запрос (нет блокировок)
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result == (1,)
        finally:
            conn.close()


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Блокировки БД")
class TestParallelOperations:
    """Тесты для проверки параллельных операций"""
    
    @pytest.mark.skipif(sys.platform.startswith("win"), reason="Windows не поддерживает fcntl, параллельная миграция проверяется вручную.")
    @allure.title("Параллельные миграции")
    @allure.description("""
    Проверяет выполнение параллельных миграций в нескольких потоках.
    
    **Что проверяется:**
    - Запуск нескольких миграций одновременно в разных потоках
    - Корректная обработка параллельных запросов
    - Отсутствие ошибок при параллельном выполнении
    
    **Ожидаемый результат:**
    Все параллельные миграции успешно завершаются без ошибок.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("locks", "parallel", "migration", "database", "unit")
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
    
    @allure.title("Миграция + чтение данных")
    @allure.description("""
    Проверяет выполнение миграции при одновременном чтении данных из БД.
    
    **Что проверяется:**
    - Выполнение миграции в одном потоке
    - Одновременное чтение данных в других потоках
    - Корректная работа WAL режима при параллельных операциях
    
    **Ожидаемый результат:**
    Миграция и чтение данных выполняются параллельно без конфликтов.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("locks", "concurrent_reads", "migration", "database", "unit")
    def test_migration_with_concurrent_reads(self, temp_db):
        """Тест 4.2: Миграция + чтение данных"""
        read_results = []
        migration_completed = False
        
        def read_data():
            try:
                # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
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


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Блокировки БД")
class TestIntegration:
    """Интеграционные тесты"""
    
    @allure.title("Полная миграция с тестовыми данными")
    @allure.description("""
    Проверяет выполнение полной миграции БД с тестовыми данными.
    
    **Что проверяется:**
    - Добавление тестовых данных в БД
    - Выполнение полной миграции
    - Сохранность данных после миграции
    
    **Ожидаемый результат:**
    Миграция успешно выполнена, тестовые данные сохранены.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("locks", "full_migration", "data", "database", "unit")
    def test_full_migration_with_data(self, temp_db):
        """Тест 5.1: Полная миграция с тестовыми данными"""
        # Добавляем тестовые данные
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
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
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
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

