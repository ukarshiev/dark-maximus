# -*- coding: utf-8 -*-
"""
Система бэкапов базы данных для Dark Maximus
"""

import os
import shutil
import sqlite3
import logging
import asyncio
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
import gzip
import json

from shop_bot.data_manager.database import DB_FILE
from shop_bot.utils import app_logger, database_logger

logger = logging.getLogger(__name__)

def _parse_bool(value: Any, default: bool = True) -> bool:
    """Нормализует булево значение из строки/числа/булева.
    Принимает True/False, 'true'/'false', 'True'/'False', '1'/'0', 1/0, 'yes'/'no', 'on'/'off'.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(int(value))
    s = str(value).strip().lower()
    if s in ('true', '1', 'yes', 'on'):  # положительные значения
        return True
    if s in ('false', '0', 'no', 'off'):
        return False
    return default

class DatabaseBackupManager:
    """Менеджер бэкапов базы данных"""
    
    def __init__(self, backup_dir: str = "backups", retention_days: int = 30):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.retention_days = retention_days
        self.is_running = False
        self.backup_thread = None
        
        # Настройки бэкапов
        self.backup_interval_hours = 24  # По умолчанию каждые 24 часа
        self.compression_enabled = True
        self.verify_backups = True
        
        # Статистика
        self.last_backup_time = None
        self.backup_count = 0
        self.failed_backups = 0
    
    def create_backup(self, backup_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Создает бэкап базы данных
        
        Args:
            backup_name: Имя файла бэкапа (если не указано, генерируется автоматически)
            
        Returns:
            Dict с информацией о бэкапе
        """
        try:
            if not DB_FILE.exists():
                raise FileNotFoundError(f"Database file not found: {DB_FILE}")
            
            # Генерируем имя файла бэкапа
            if not backup_name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"users_backup_{timestamp}.db"
            
            backup_path = self.backup_dir / backup_name

            # Создаем бэкап через SQLite backup API (атомарный снимок без гонок записи)
            # Всегда создаем сначала несжатый .db, проверяем целостность, затем по необходимости сжимаем
            uncompressed_backup_path = backup_path.with_suffix('.db') if backup_path.suffix != '.db' else backup_path

            # Убедимся, что директория существует
            uncompressed_backup_path.parent.mkdir(parents=True, exist_ok=True)

            # Выполняем резервное копирование через API с retry логикой при блокировке
            max_retries = 3
            retry_delays = [1.0, 2.0, 3.0]
            backup_success = False
            
            for attempt in range(max_retries):
                try:
                    with sqlite3.connect(DB_FILE, timeout=30) as src_conn:
                        try:
                            # На случай WAL — сделаем чекпойнт; игнорируем ошибку, если режим не WAL
                            try:
                                src_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                            except sqlite3.Error as e:
                                logger.debug(f"Failed to checkpoint WAL in backup: {e}")

                            src_conn.execute("PRAGMA busy_timeout=5000")
                            with sqlite3.connect(uncompressed_backup_path) as dst_conn:
                                dst_conn.execute("PRAGMA busy_timeout=5000")
                                src_conn.backup(dst_conn)
                        finally:
                            src_conn.commit()
                    
                    backup_success = True
                    break
                    
                except sqlite3.OperationalError as db_error:
                    if "database is locked" in str(db_error).lower() and attempt < max_retries - 1:
                        wait_time = retry_delays[attempt]
                        logger.warning(
                            f"Database is locked during backup (attempt {attempt + 1}/{max_retries}). "
                            f"Retrying in {wait_time}s..."
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        raise

            # Глубокая проверка целостности бэкапа и авто-восстановление индексов при необходимости
            if self.verify_backups:
                try:
                    self._verify_backup(uncompressed_backup_path)
                except Exception as integrity_err:
                    # Попробуем переиндексировать копию и проверить ещё раз
                    try:
                        with sqlite3.connect(uncompressed_backup_path) as fix_conn:
                            cur = fix_conn.cursor()
                            cur.execute("REINDEX")
                            cur.execute("ANALYZE")
                            fix_conn.commit()
                        # Повторная проверка
                        self._verify_backup(uncompressed_backup_path)
                    except Exception as e:
                        logger.debug(f"Failed to reindex backup copy: {e}")
                        # Если переиндексация не помогла — пробрасываем исходную ошибку
                        raise integrity_err

            # Сжимаем бэкап, если включено сжатие (после успешной проверки)
            if self.compression_enabled:
                compressed_path = uncompressed_backup_path.with_suffix('.db.gz')
                with open(uncompressed_backup_path, 'rb') as f_in:
                    with gzip.open(compressed_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                # Удаляем несжатый файл после успешного сжатия
                if uncompressed_backup_path.exists():
                    uncompressed_backup_path.unlink()
                backup_path = compressed_path
            else:
                backup_path = uncompressed_backup_path
            
            # Обновляем статистику
            self.last_backup_time = datetime.now()
            self.backup_count += 1
            
            backup_info = {
                'success': True,
                'backup_name': backup_name,
                'backup_path': str(backup_path),
                'backup_size': backup_path.stat().st_size,
                'created_at': self.last_backup_time.isoformat(),
                'compressed': self.compression_enabled
            }
            
            database_logger.log_database_operation(
                "backup_created",
                "users",
                backup_info
            )
            
            logger.info(f"Database backup created successfully: {backup_path}")
            return backup_info
            
        except Exception as e:
            self.failed_backups += 1
            error_info = {
                'success': False,
                'error': str(e),
                'created_at': datetime.now().isoformat()
            }
            
            database_logger.log_database_operation(
                "backup_failed",
                "users",
                error_info
            )
            
            logger.error(f"Failed to create database backup: {e}")
            return error_info
    
    def _verify_backup(self, backup_path: Path) -> bool:
        """Проверяет целостность бэкапа"""
        try:
            # Если файл сжат — выполняем проверку на декомпрессированной копии в памяти файла
            if backup_path.suffix == '.gz':
                # Декомпрессируем во временный соседний файл и проверим
                tmp_path = backup_path.with_suffix('')  # убрать .gz
                with gzip.open(backup_path, 'rb') as f_in:
                    with open(tmp_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                try:
                    conn = sqlite3.connect(tmp_path)
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA integrity_check")
                    result = cursor.fetchone()
                    conn.close()
                    if result[0] != 'ok':
                        raise Exception(f"Database integrity check failed: {result[0]}")
                finally:
                    # Удаляем временный файл
                    if tmp_path.exists():
                        tmp_path.unlink()
            else:
                # Проверяем SQLite файл
                conn = sqlite3.connect(backup_path)
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()
                conn.close()
                if result[0] != 'ok':
                    raise Exception(f"Database integrity check failed: {result[0]}")
            
            return True
            
        except Exception as e:
            logger.error(f"Backup verification failed for {backup_path}: {e}")
            raise
    
    def restore_backup(self, backup_path: str, create_backup_before_restore: bool = True) -> Dict[str, Any]:
        """
        Восстанавливает базу данных из бэкапа
        
        Args:
            backup_path: Путь к файлу бэкапа
            create_backup_before_restore: Создать бэкап перед восстановлением
            
        Returns:
            Dict с результатом восстановления
        """
        try:
            backup_file = Path(backup_path)
            if not backup_file.exists():
                raise FileNotFoundError(f"Backup file not found: {backup_path}")
            
            # Создаем бэкап текущей БД перед восстановлением
            if create_backup_before_restore:
                current_backup = self.create_backup("pre_restore_backup.db")
                if not current_backup['success']:
                    raise Exception("Failed to create backup before restore")
            
            # Восстанавливаем из бэкапа
            if backup_file.suffix == '.gz':
                # Распаковываем сжатый файл
                with gzip.open(backup_file, 'rb') as f_in:
                    with open(DB_FILE, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                # Копируем обычный файл
                shutil.copy2(backup_file, DB_FILE)
            
            # Проверяем целостность восстановленной БД
            if self.verify_backups:
                self._verify_backup(DB_FILE)
            
            restore_info = {
                'success': True,
                'restored_from': str(backup_file),
                'restored_at': datetime.now().isoformat()
            }
            
            database_logger.log_database_operation(
                "database_restored",
                "users",
                restore_info
            )
            
            logger.info(f"Database restored successfully from: {backup_file}")
            return restore_info
            
        except Exception as e:
            error_info = {
                'success': False,
                'error': str(e),
                'restored_at': datetime.now().isoformat()
            }
            
            database_logger.log_database_operation(
                "restore_failed",
                "users",
                error_info
            )
            
            logger.error(f"Failed to restore database from {backup_path}: {e}")
            return error_info
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """Возвращает список доступных бэкапов"""
        backups = []
        
        try:
            # Таймзоны для корректного представления времени
            try:
                from zoneinfo import ZoneInfo  # Python 3.9+
                tz_utc = ZoneInfo('UTC')
                tz_msk = ZoneInfo('Europe/Moscow')
            except Exception as e:
                logger.debug(f"Failed to get timezone info: {e}")
                tz_utc = None
                tz_msk = None

            for backup_file in self.backup_dir.glob("users_backup_*.db*"):
                stat = backup_file.stat()
                ts = stat.st_ctime
                # Время создания в UTC и МСК
                if tz_utc is not None:
                    dt_utc = datetime.fromtimestamp(ts, tz_utc)
                else:
                    dt_utc = datetime.utcfromtimestamp(ts)
                dt_msk = dt_utc.astimezone(tz_msk) if tz_msk is not None else dt_utc

                compressed = backup_file.suffix == '.gz'
                # Отображаемое имя файла по МСК (не переименовываем фактический файл)
                display_base = f"users_backup_{dt_msk.strftime('%Y%m%d_%H%M%S')}.db"
                display_name = display_base + ('.gz' if compressed else '')

                backups.append({
                    'name': backup_file.name,
                    'display_name': display_name,
                    'path': str(backup_file),
                    'size': stat.st_size,
                    'created_at': dt_utc.isoformat(),
                    'created_at_msk': dt_msk.isoformat(),
                    'compressed': compressed
                })
            
            # Сортируем по дате создания (новые первыми)
            backups.sort(key=lambda x: x['created_at'], reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
        
        return backups
    
    def cleanup_old_backups(self) -> int:
        """Удаляет старые бэкапы согласно политике хранения"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            deleted_count = 0
            
            for backup_file in self.backup_dir.glob("users_backup_*.db*"):
                if datetime.fromtimestamp(backup_file.stat().st_ctime) < cutoff_date:
                    backup_file.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted old backup: {backup_file}")
            
            if deleted_count > 0:
                database_logger.log_database_operation(
                    "backups_cleaned",
                    "users",
                    {'deleted_count': deleted_count, 'retention_days': self.retention_days}
                )
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")
            return 0
    
    def start_automatic_backups(self, interval_hours: int = 24):
        """Запускает автоматические бэкапы"""
        if self.is_running:
            logger.warning("Automatic backups already running")
            return
        
        self.backup_interval_hours = interval_hours
        self.is_running = True
        
        def backup_worker():
            while self.is_running:
                try:
                    # Создаем бэкап
                    backup_info = self.create_backup()
                    
                    if backup_info['success']:
                        logger.info("Automatic backup completed successfully")
                    else:
                        logger.error(f"Automatic backup failed: {backup_info.get('error')}")
                    
                    # Очищаем старые бэкапы
                    deleted_count = self.cleanup_old_backups()
                    if deleted_count > 0:
                        logger.info(f"Cleaned up {deleted_count} old backups")
                    
                except Exception as e:
                    logger.error(f"Error in automatic backup worker: {e}")
                
                # Ждем до следующего бэкапа
                time.sleep(self.backup_interval_hours * 3600)
        
        self.backup_thread = threading.Thread(target=backup_worker, daemon=True)
        self.backup_thread.start()
        
        logger.info(f"Automatic backups started with interval: {interval_hours} hours")
    
    def stop_automatic_backups(self):
        """Останавливает автоматические бэкапы"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.backup_thread and self.backup_thread.is_alive():
            self.backup_thread.join(timeout=5)
        
        logger.info("Automatic backups stopped")
    
    def update_settings(self, interval_hours: int = None, retention_days: int = None, 
                       compression_enabled: bool = None, verify_backups: bool = None):
        """
        Обновляет настройки бекапов без перезапуска системы
        
        Args:
            interval_hours: Новый интервал в часах
            retention_days: Новое количество дней хранения
            compression_enabled: Включить/выключить сжатие
            verify_backups: Включить/выключить проверку целостности
        """
        if interval_hours is not None:
            self.backup_interval_hours = interval_hours
            logger.info(f"Backup interval updated to {interval_hours} hours")
        
        if retention_days is not None:
            self.retention_days = retention_days
            logger.info(f"Backup retention updated to {retention_days} days")
        
        if compression_enabled is not None:
            self.compression_enabled = compression_enabled
            logger.info(f"Backup compression {'enabled' if compression_enabled else 'disabled'}")
        
        if verify_backups is not None:
            self.verify_backups = verify_backups
            logger.info(f"Backup verification {'enabled' if verify_backups else 'disabled'}")

    def get_backup_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику бэкапов"""
        backups = self.list_backups()
        
        return {
            'total_backups': len(backups),
            'backup_count': self.backup_count,
            'failed_backups': self.failed_backups,
            'last_backup_time': self.last_backup_time.isoformat() if self.last_backup_time else None,
            'is_running': self.is_running,
            'backup_interval_hours': self.backup_interval_hours,
            'retention_days': self.retention_days,
            'backup_dir': str(self.backup_dir),
            'compression_enabled': self.compression_enabled,
            'verify_backups': self.verify_backups,
            'total_size': sum(backup['size'] for backup in backups),
            'backups': backups  # Добавляем список бекапов
        }

# Глобальный экземпляр менеджера бэкапов
backup_manager = DatabaseBackupManager()

def initialize_backup_system():
    """Инициализация системы бэкапов"""
    try:
        from shop_bot.data_manager.database import get_backup_setting
        
        # Получаем настройки из backup_settings
        backup_enabled_raw = get_backup_setting('backup_enabled')
        interval_hours_raw = get_backup_setting('backup_interval_hours')
        retention_days_raw = get_backup_setting('backup_retention_days')
        compression_raw = get_backup_setting('backup_compression')
        verify_raw = get_backup_setting('backup_verify')

        # Нормализация типов
        backup_enabled = _parse_bool(backup_enabled_raw, default=True)
        try:
            interval_hours = int(interval_hours_raw) if interval_hours_raw else 24
        except (TypeError, ValueError):
            interval_hours = 24
        try:
            retention_days = int(retention_days_raw) if retention_days_raw else 30
        except (TypeError, ValueError):
            retention_days = 30
        compression = _parse_bool(compression_raw, default=True)
        verify = _parse_bool(verify_raw, default=True)
        
        # Обновляем настройки менеджера
        backup_manager.retention_days = retention_days
        backup_manager.compression_enabled = compression
        backup_manager.verify_backups = verify
        
        if backup_enabled:
            # Создаем первый бэкап при запуске (опционально, не прерываем инициализацию при ошибке)
            try:
                backup_info = backup_manager.create_backup("initial_backup.db")
                
                if backup_info['success']:
                    logger.info("Initial database backup created successfully")
                else:
                    error_msg = backup_info.get('error', 'Unknown error')
                    if "database is locked" in str(error_msg).lower():
                        logger.warning(
                            f"Initial backup skipped due to database lock: {error_msg}. "
                            "Backup will be created automatically later."
                        )
                    else:
                        logger.warning(f"Failed to create initial backup: {error_msg}")
            except Exception as e:
                error_msg = str(e)
                if "database is locked" in error_msg.lower():
                    logger.warning(
                        f"Initial backup skipped due to database lock: {error_msg}. "
                        "Backup will be created automatically later."
                    )
                else:
                    logger.warning(f"Failed to create initial backup: {e}")
            
            # Запускаем автоматические бэкапы (даже если initial backup не удался)
            backup_manager.start_automatic_backups(interval_hours)
            logger.info(f"Backup system initialized with {interval_hours}h interval")
        else:
            logger.info("Backup system disabled by settings")
        
    except Exception as e:
        logger.error(f"Failed to initialize backup system: {e}")

def shutdown_backup_system():
    """Остановка системы бэкапов"""
    try:
        backup_manager.stop_automatic_backups()
        logger.info("Backup system shutdown completed")
    except Exception as e:
        logger.error(f"Error during backup system shutdown: {e}")
