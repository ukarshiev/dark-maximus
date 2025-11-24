# -*- coding: utf-8 -*-

"""

Модуль для работы с базой данных

"""



import sqlite3
import contextlib

from datetime import datetime, timezone, timedelta

import logging

from pathlib import Path

import json

import bcrypt

import time
from typing import Optional
import unicodedata
import re
import os
try:
    import fcntl  # type: ignore[attr-defined]
except ImportError:
    try:
        import msvcrt  # type: ignore[attr-defined]
    except ImportError:
        msvcrt = None  # type: ignore[assignment]

    class _FcntlStub:
        LOCK_EX = 0x01
        LOCK_NB = 0x02
        LOCK_UN = 0x04

        @staticmethod
        def flock(file_descriptor, operation):
            logger = logging.getLogger(__name__)
            if msvcrt is None:
                logger.debug(
                    "fcntl недоступен и msvcrt недоступен; операция блокировки пропущена."
                )
                return 0

            length = 1
            try:
                if operation & _FcntlStub.LOCK_UN:
                    msvcrt.locking(file_descriptor, msvcrt.LK_UNLCK, length)
                else:
                    mode = msvcrt.LK_LOCK
                    if operation & _FcntlStub.LOCK_NB:
                        mode = msvcrt.LK_NBLCK
                    msvcrt.locking(file_descriptor, mode, length)
            except OSError as exc:  # pragma: no cover - Windows specific
                logger.debug(f"msvcrt.locking raise OSError: {exc}")
                raise BlockingIOError(exc.errno, exc.strerror) from exc

            return 0

    fcntl = _FcntlStub()  # type: ignore[misc]
def _parse_db_datetime(value) -> Optional[datetime]:
    """Парсит datetime из БД, возвращая aware UTC значение."""
    if value in (None, ''):
        return None

    if isinstance(value, datetime):
        dt_value = value
    else:
        try:
            dt_value = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except (ValueError, TypeError):
            logger.warning("Не удалось распарсить дату из БД: %s", value)
            return None

    if dt_value.tzinfo is None:
        dt_value = dt_value.replace(tzinfo=timezone.utc)

    return dt_value



logger = logging.getLogger(__name__)


_HOST_TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
}


def _generate_group_code(group_name: str) -> str:
    """
    Генерирует код группы из названия группы.
    Транслитерация кириллицы в латиницу, приведение к lowercase,
    замена пробелов и спецсимволов на подчеркивания.
    """
    result = group_name.lower()

    for cyrillic, latin in _HOST_TRANSLIT_MAP.items():
        result = result.replace(cyrillic, latin)

    result = re.sub(r'[^a-z0-9_-]', '_', result)
    result = re.sub(r'_+', '_', result)
    result = result.strip('_')

    if not result:
        result = 'group'

    return result


# Определяем путь к базе данных в зависимости от окружения

import os

if os.path.exists("/app/project"):

    # Docker окружение

    PROJECT_ROOT = Path("/app/project")
    # В Docker база данных в корне проекта
    DB_FILE = PROJECT_ROOT / "users.db"

else:

    # Локальная разработка

    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
    DB_FILE = PROJECT_ROOT / "users.db"



# Универсальная нормализация идентификатора хоста.
# Применяется для поиска совпадений по имени и коду.
def _normalize_host_identifier(value: str | None) -> str:
    if value is None:
        return ""

    candidate = value.strip().lower()
    if not candidate:
        return ""

    for cyrillic, latin in _HOST_TRANSLIT_MAP.items():
        candidate = candidate.replace(cyrillic, latin)

    candidate = unicodedata.normalize("NFKD", candidate)
    candidate = "".join(ch for ch in candidate if unicodedata.category(ch)[0] != "M")
    candidate = re.sub(r'[^a-z0-9]+', '', candidate)

    return candidate


def _column_exists(cursor, table_name: str, column_name: str) -> bool:
    """Безопасная проверка существования колонки в таблице.
    
    Args:
        cursor: Курсор SQLite
        table_name: Имя таблицы
        column_name: Имя колонки
        
    Returns:
        True если колонка существует, False в противном случае или при ошибке
    """
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        return column_name in columns
    except Exception as e:
        logger.warning(f"Failed to check column existence for {table_name}.{column_name}: {e}")
        return False


@contextlib.contextmanager
def _get_db_connection():
    """Контекстный менеджер для получения соединения с БД с гарантированным закрытием.
    
    Используется для исправления ResourceWarning в Python 3.13+.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        yield conn
    finally:
        if conn:
            conn.close()


# Локальная самодиагностика/восстановление БД при мягких повреждениях индексов
def _repair_database_indexes() -> bool:
    """Пытается восстановить индексы и провести обслуживание БД.

    Выполняет REINDEX, ANALYZE и VACUUM (вне транзакции). Возвращает True при
    успешном завершении без исключений, иначе False.
    """
    try:
        # REINDEX + ANALYZE внутри отдельного подключения/транзакции
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("PRAGMA busy_timeout=5000")
            except sqlite3.Error as e:
                logger.debug(f"Failed to set PRAGMA busy_timeout: {e}")
            cursor.execute("REINDEX")
            cursor.execute("ANALYZE")
            conn.commit()

        # VACUUM нужно выполнять вне транзакции
        conn2 = sqlite3.connect(DB_FILE)
        try:
            # Автокоммитный режим, чтобы VACUUM прошёл вне транзакции
            conn2.isolation_level = None
            cur2 = conn2.cursor()
            try:
                cur2.execute("PRAGMA busy_timeout=5000")
            except sqlite3.Error as e:
                logger.debug(f"Failed to set PRAGMA busy_timeout in VACUUM: {e}")
            cur2.execute("VACUUM")
        finally:
            conn2.close()
        return True
    except sqlite3.Error:
        # Подробности уже будут в вызывающем месте
        return False


def initialize_db():
    """
    Инициализация базы данных с защитой от параллельных запусков.
    
    Использует файловую блокировку через fcntl для предотвращения параллельной инициализации
    и retry логику для обработки временных блокировок БД.
    """
    # Детальное логирование для диагностики
    logger.info(f"[PID {os.getpid()}] Database initialization started. DB_FILE path: {DB_FILE}")
    logger.info(f"[PID {os.getpid()}] DB_FILE.parent: {DB_FILE.parent}, exists: {DB_FILE.parent.exists()}")
    logger.info(f"[PID {os.getpid()}] DB_FILE exists: {DB_FILE.exists()}")
    
    # Проверка и создание родительской директории если её нет
    if not DB_FILE.parent.exists():
        try:
            logger.info(f"[PID {os.getpid()}] Creating database directory: {DB_FILE.parent}")
            DB_FILE.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"[PID {os.getpid()}] Database directory created successfully: {DB_FILE.parent}")
        except Exception as dir_error:
            logger.error(f"[PID {os.getpid()}] Failed to create database directory {DB_FILE.parent}: {dir_error}", exc_info=True)
            raise
    
    # Проверка прав доступа к директории
    if DB_FILE.parent.exists():
        try:
            import stat
            dir_stat = os.stat(DB_FILE.parent)
            logger.debug(f"[PID {os.getpid()}] Directory permissions: {oct(dir_stat.st_mode)}")
            # Проверяем возможность записи
            test_file = DB_FILE.parent / ".test_write"
            try:
                test_file.touch()
                test_file.unlink()
                logger.debug(f"[PID {os.getpid()}] Directory is writable")
            except Exception as write_test_error:
                logger.error(f"[PID {os.getpid()}] Directory is NOT writable: {write_test_error}")
                raise PermissionError(f"Cannot write to directory {DB_FILE.parent}: {write_test_error}")
        except Exception as perm_error:
            logger.warning(f"[PID {os.getpid()}] Could not check directory permissions: {perm_error}")
    
    # Проверка существования БД и что это файл, а не директория
    if DB_FILE.exists():
        if DB_FILE.is_dir():
            logger.error(f"[PID {os.getpid()}] DB_FILE exists but is a DIRECTORY, not a file: {DB_FILE}")
            raise ValueError(f"Database path {DB_FILE} is a directory, not a file. Please remove the directory and create a file instead.")
        logger.info(f"[PID {os.getpid()}] Database file exists: {DB_FILE} (size: {DB_FILE.stat().st_size} bytes)")
    else:
        # Создаем пустой файл БД
        try:
            logger.info(f"[PID {os.getpid()}] Creating empty database file: {DB_FILE}")
            DB_FILE.touch()
            logger.info(f"[PID {os.getpid()}] Empty database file created successfully: {DB_FILE}")
        except Exception as file_error:
            logger.error(f"[PID {os.getpid()}] Failed to create database file {DB_FILE}: {file_error}", exc_info=True)
            raise
    
    # Путь к файлу блокировки
    lock_file_path = DB_FILE.parent / ".db_init.lock"
    lock_file = None
    lock_acquired = False
    
    # Retry логика с экспоненциальной задержкой
    max_retries = 5
    retry_delays = [0.5, 1.0, 2.0, 4.0, 8.0]
    process_id = os.getpid()
    
    for attempt in range(max_retries):
        try:
            # Попытка получить файловую блокировку
            try:
                lock_file = open(lock_file_path, 'w')
                # Неблокирующая попытка получить эксклюзивную блокировку
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                lock_acquired = True
                logger.info(f"[PID {process_id}] Database initialization lock acquired (attempt {attempt + 1})")
            except (IOError, OSError) as lock_error:
                # Блокировка занята другим процессом
                if attempt < max_retries - 1:
                    wait_time = retry_delays[attempt]
                    logger.warning(
                        f"[PID {process_id}] Database initialization lock is held by another process. "
                        f"Waiting {wait_time}s before retry {attempt + 2}/{max_retries}..."
                    )
                    time.sleep(wait_time)
                    if lock_file:
                        lock_file.close()
                        lock_file = None
                    continue
                else:
                    # Последняя попытка - используем fallback без блокировки
                    logger.warning(
                        f"[PID {process_id}] Could not acquire lock after {max_retries} attempts. "
                        f"Proceeding with retry logic only (fallback mode)."
                    )
                    if lock_file:
                        lock_file.close()
                        lock_file = None
            
            # Подключение к БД с retry логикой
            db_connected = False
            for db_attempt in range(max_retries):
                try:
                    # Дополнительная проверка перед подключением
                    if DB_FILE.exists() and DB_FILE.is_dir():
                        raise ValueError(f"Database path {DB_FILE} is a directory, not a file")
                    
                    # Проверка прав доступа к файлу
                    if DB_FILE.exists():
                        try:
                            test_access = os.access(DB_FILE, os.R_OK | os.W_OK)
                            if not test_access:
                                raise PermissionError(f"No read/write access to database file {DB_FILE}")
                        except Exception as access_error:
                            logger.warning(f"[PID {process_id}] Could not check file access: {access_error}")
                    
                    logger.debug(f"[PID {process_id}] Attempting to connect to database: {DB_FILE}")
                    conn = sqlite3.connect(str(DB_FILE), timeout=30)
                    cursor = conn.cursor()
                    
                    # Установка режима журналирования и оптимизационных PRAGMA
                    try:
                        cursor.execute("PRAGMA busy_timeout=30000")
                        # Проверяем текущий режим и переключаем на DELETE, если нужно
                        cursor.execute("PRAGMA journal_mode")
                        current_mode = cursor.fetchone()[0]
                        if current_mode.upper() != 'DELETE':
                            logger.info(f"[PID {process_id}] Переключение режима журналирования с {current_mode} на DELETE")
                            cursor.execute("PRAGMA journal_mode=DELETE")
                            cursor.execute("PRAGMA journal_mode")
                            new_mode = cursor.fetchone()[0]
                            logger.info(f"[PID {process_id}] Режим журналирования переключен на {new_mode}")
                        else:
                            cursor.execute("PRAGMA journal_mode=DELETE")
                        cursor.execute("PRAGMA synchronous=NORMAL")
                        cursor.execute("PRAGMA cache_size=10000")
                        cursor.execute("PRAGMA temp_store=MEMORY")
                        logger.debug(f"[PID {process_id}] Database PRAGMA settings configured (journal mode: DELETE)")
                    except sqlite3.Error as pragma_error:
                        logger.warning(f"[PID {process_id}] Failed to set some PRAGMA settings: {pragma_error}")
                        # Продолжаем работу даже если PRAGMA не установились
                    
                    db_connected = True
                    break
                    
                except sqlite3.OperationalError as db_error:
                    if "database is locked" in str(db_error).lower() and db_attempt < max_retries - 1:
                        wait_time = retry_delays[db_attempt]
                        logger.warning(
                            f"[PID {process_id}] Database is locked (attempt {db_attempt + 1}/{max_retries}). "
                            f"Retrying in {wait_time}s..."
                        )
                        time.sleep(wait_time)
                        if 'conn' in locals():
                            try:
                                conn.close()
                            except:
                                pass
                    else:
                        raise
            
            if not db_connected:
                raise sqlite3.OperationalError("Failed to connect to database after all retries")

            cursor.execute('''

                CREATE TABLE IF NOT EXISTS users (

                    telegram_id INTEGER PRIMARY KEY, username TEXT, total_spent REAL DEFAULT 0,

                    total_months INTEGER DEFAULT 0, trial_used INTEGER DEFAULT 0,

                    agreed_to_terms INTEGER DEFAULT 0,

                    agreed_to_documents INTEGER DEFAULT 0,

                    subscription_status TEXT DEFAULT 'not_checked',

                    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    is_banned INTEGER DEFAULT 0,

                    referred_by INTEGER,

                    referral_balance REAL DEFAULT 0,

                    referral_balance_all REAL DEFAULT 0,

                    balance REAL DEFAULT 0

                )

            ''')

            cursor.execute('''

                CREATE TABLE IF NOT EXISTS vpn_keys (

                    key_id INTEGER PRIMARY KEY AUTOINCREMENT,

                    user_id INTEGER NOT NULL,

                    host_name TEXT NOT NULL,

                    xui_client_uuid TEXT NOT NULL,

                    key_email TEXT NOT NULL UNIQUE,

                    expiry_date TIMESTAMP,

                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    protocol TEXT DEFAULT 'vless',

                    is_trial INTEGER DEFAULT 0,

                    subscription TEXT,

                    subscription_link TEXT,

                    telegram_chat_id INTEGER,

                    comment TEXT

                )

            ''')

            cursor.execute('''

                CREATE TABLE IF NOT EXISTS transactions (

                    username TEXT,

                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,

                    payment_id TEXT UNIQUE NOT NULL,

                    user_id INTEGER NOT NULL,

                    status TEXT NOT NULL,

                    amount_rub REAL NOT NULL,

                    amount_currency REAL,

                    currency_name TEXT,

                    payment_method TEXT,

                    metadata TEXT,

                    transaction_hash TEXT,

                    payment_link TEXT,

                    yookassa_payment_id TEXT,

                    rrn TEXT,

                    authorization_code TEXT,

                    payment_type TEXT,

                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                )

            ''')

            # Миграция: добавляем новые поля в таблицу vpn_keys если их нет
            # Проверяем существование колонок перед добавлением для оптимизации
            cursor.execute("PRAGMA table_info(vpn_keys)")
            existing_columns = [row[1] for row in cursor.fetchall()]
            
            new_columns = [
                ("subscription", "TEXT"),
                ("telegram_chat_id", "INTEGER"),
                ("comment", "TEXT")
            ]
            
            for column_name, column_type in new_columns:
                if column_name not in existing_columns:
                    try:
                        cursor.execute(f"ALTER TABLE vpn_keys ADD COLUMN {column_name} {column_type}")
                        logging.info(f" -> The column '{column_name}' is successfully added to vpn_keys table.")
                    except sqlite3.OperationalError as e:
                        logging.warning(f" -> Failed to add column '{column_name}': {e}")
                else:
                    logging.debug(f" -> The column '{column_name}' already exists in vpn_keys table.")

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

                CREATE TABLE IF NOT EXISTS notifications (

                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,

                    user_id INTEGER,

                    username TEXT,

                    type TEXT,

                    title TEXT,

                    message TEXT,

                    status TEXT,

                    meta TEXT,

                    key_id INTEGER,

                    marker_hours INTEGER,

                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                )

            ''')

            cursor.execute('''

                CREATE TABLE IF NOT EXISTS support_threads (

                    user_id INTEGER PRIMARY KEY,

                    thread_id INTEGER NOT NULL

                )

            ''')

            cursor.execute('''

                CREATE TABLE IF NOT EXISTS xui_hosts(

                    host_name TEXT NOT NULL,

                    host_url TEXT NOT NULL,

                    host_username TEXT NOT NULL,

                    host_pass TEXT NOT NULL,

                    host_inbound_id INTEGER NOT NULL,

                    host_code TEXT

                )

            ''')

            cursor.execute('''

                CREATE TABLE IF NOT EXISTS plans (

                    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,

                    host_name TEXT NOT NULL,

                    plan_name TEXT NOT NULL,

                    months INTEGER NOT NULL,

                    price REAL NOT NULL,

                    FOREIGN KEY (host_name) REFERENCES xui_hosts (host_name)

                )

            ''')

            cursor.execute('''

                CREATE TABLE IF NOT EXISTS promo_codes (

                    promo_id INTEGER PRIMARY KEY AUTOINCREMENT,

                    code TEXT NOT NULL UNIQUE,

                    bot TEXT NOT NULL,

                    vpn_plan_id TEXT,

                    tariff_code TEXT,

                    discount_amount REAL DEFAULT 0,

                    discount_percent REAL DEFAULT 0,

                    discount_bonus REAL DEFAULT 0,

                    usage_limit_per_bot INTEGER DEFAULT 1,

                    is_active INTEGER DEFAULT 1,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (vpn_plan_id) REFERENCES plans (plan_id)

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

                    status TEXT DEFAULT 'applied',

                    FOREIGN KEY (promo_id) REFERENCES promo_codes (promo_id),

                    FOREIGN KEY (plan_id) REFERENCES plans (plan_id),

                    FOREIGN KEY (user_id) REFERENCES users (telegram_id),

                    UNIQUE (promo_id, user_id, bot)

                )

            ''')
            
            # Миграция: добавляем колонку status если её нет
            try:
                cursor.execute("ALTER TABLE promo_code_usage ADD COLUMN status TEXT DEFAULT 'applied'")
                logging.info("Added status column to promo_code_usage table")
            except sqlite3.OperationalError:
                # Колонка уже существует
                pass
            
            # Миграция: обновляем существующие записи
            cursor.execute('''
                UPDATE promo_code_usage 
                SET status = 'used' 
                WHERE status IS NULL AND plan_id IS NOT NULL
            ''')
            
            cursor.execute('''
                UPDATE promo_code_usage 
                SET status = 'applied' 
                WHERE status IS NULL AND plan_id IS NULL
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS video_instructions (
                    video_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    filename TEXT NOT NULL UNIQUE,
                    poster_filename TEXT,
                    file_size_mb REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_groups (
                    group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_name TEXT NOT NULL UNIQUE,
                    group_description TEXT,
                    is_default BOOLEAN DEFAULT 0,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    group_code TEXT UNIQUE
                )
            ''')

            # Хешируем пароль по умолчанию (только для случая, когда оба поля отсутствуют)

            default_password = "admin"

            hashed_password = bcrypt.hashpw(default_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            

            # КРИТИЧНО: Доп. защита - проверяем наличие panel_password и panel_login перед вставкой дефолтных значений
            # НИКОГДА не вставляем дефолтные значения, если в базе УЖЕ ЕСТЬ любые записи в bot_settings
            try:
                # Проверяем общее количество записей в bot_settings
                cursor.execute("SELECT COUNT(*) FROM bot_settings")
                total_settings_count = cursor.fetchone()[0]
                
                # Проверяем текущий логин
                cursor.execute("SELECT value FROM bot_settings WHERE key = ?", ("panel_login",))
                login_result = cursor.fetchone()
                current_login = login_result[0] if login_result else None
            except Exception as e:
                logger.debug(f"Failed to check panel credentials during initialization: {e}")
                current_login = None

            # ПРАВИЛЬНАЯ логика: создаём учетные данные ТОЛЬКО если их НЕТ вообще
            # Если логин существует (ЛЮБОЙ, включая "admin") - НЕ ТРОГАЕМ!
            # Это защищает от сброса пользовательских паролей
            if current_login is not None and current_login != '':
                # Логин существует - НИКОГДА НЕ МЕНЯЕМ
                logging.info(f"Panel credentials exist (login: '{current_login}'), preserving user-configured credentials")
            else:
                # Логина НЕТ - создаём дефолтные ТОЛЬКО ОДИН РАЗ
                # Используем INSERT OR IGNORE для защиты от race conditions
                cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)", ("panel_login", "admin"))
                cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)", ("panel_password", hashed_password))
                logging.info("Created default panel_login and panel_password (credentials were missing)")

            # Проверяем, есть ли уже настройка global_domain в БД перед формированием дефолтных значений для TON manifest
            existing_global_domain = None
            try:
                cursor.execute("SELECT value FROM bot_settings WHERE key = ?", ("global_domain",))
                result = cursor.fetchone()
                if result and result[0]:
                    existing_global_domain = result[0].strip()
                # Если global_domain нет, проверяем старый параметр domain
                if not existing_global_domain:
                    cursor.execute("SELECT value FROM bot_settings WHERE key = ?", ("domain",))
                    result = cursor.fetchone()
                    if result and result[0]:
                        existing_global_domain = result[0].strip()
            except Exception:
                pass  # Если БД еще не создана или ошибка - используем дефолт

            # Формируем домен для TON manifest
            if existing_global_domain:
                # Нормализация домена (убираем протокол если есть, добавляем https)
                panel_domain = existing_global_domain.strip().rstrip('/')
                if not panel_domain.startswith(('http://', 'https://')):
                    panel_domain = f"https://{panel_domain}"
            else:
                # Если домен не настроен, используем None
                # Это безопаснее, чем жестко прописывать домен
                panel_domain = None
                logging.warning(
                    "global_domain не настроен в БД. TON manifest URL будут None. "
                    "Рекомендуется настроить global_domain в настройках панели."
                )

            default_settings = {

                "about_content": None,

                "terms_url": None,

                "privacy_url": None,

                "support_user": None,

                "support_text": None,

                "channel_url": None,

                "force_subscription": "true",

                "receipt_email": "example@example.com",

                "telegram_bot_token": None,

                "support_bot_token": None,

                "telegram_bot_username": None,

                "trial_enabled": "true",

                "trial_duration_days": "3",

                "enable_referrals": "true",

                "referral_percentage": "10",

                "referral_discount": "5",

                "minimum_withdrawal": "100",

                "support_group_id": None,

                "admin_telegram_id": None,

                "yookassa_shop_id": None,

                "yookassa_secret_key": None,

                "yookassa_test_mode": "true",

                "yookassa_test_shop_id": None,

                "yookassa_test_secret_key": None,

                "yookassa_api_url": "https://api.yookassa.ru/v3",

                "yookassa_test_api_url": "https://api.test.yookassa.ru/v3",

                "yookassa_verify_ssl": "true",

                "yookassa_test_verify_ssl": "false",

                "sbp_enabled": "false",

                "cryptobot_token": None,

                "heleket_merchant_id": None,

                "heleket_api_key": None,

                "domain": None,
                "global_domain": None,

                "ton_wallet_address": None,

                "tonapi_key": None,

                "auto_delete_orphans": "false",

                "hidden_mode": "0",

                "support_enabled": "true",

                "minimum_topup": "50",

                "ton_manifest_name": "Dark Maximus Shop Bot",

                "ton_manifest_url": f"{panel_domain}/.well-known/tonconnect-manifest.json" if panel_domain else None,

                "ton_manifest_icon_url": f"{panel_domain}/static/logo.png" if panel_domain else None,

                "ton_manifest_terms_url": f"{panel_domain}/terms" if panel_domain else None,

                "ton_manifest_privacy_url": f"{panel_domain}/privacy" if panel_domain else None,

                # Feature flags
                "feature_timezone_enabled": "0",  # Поддержка timezone (0 = выключена, 1 = включена)
                "admin_timezone": "Europe/Moscow",  # Часовой пояс администратора по умолчанию

            }

            run_migration(conn)

            

            # Создание индексов для оптимизации производительности

            create_database_indexes(cursor)

            # Создание группы "Пользователи" по умолчанию
            users_group_code = _generate_group_code("Пользователи")
            cursor.execute("INSERT OR IGNORE INTO user_groups (group_name, group_description, is_default, group_code) VALUES (?, ?, ?, ?)", 
                         ("Пользователи", "Группа по умолчанию для всех пользователей", 1, users_group_code))

            

            # Вставляем остальные настройки по умолчанию (panel_login и panel_password уже обработаны выше)
            # КРИТИЧНО: Никогда не вставляем panel_login и panel_password здесь, они обрабатываются отдельно выше
            sensitive_keys = {"panel_login", "panel_password"}
            for key, value in default_settings.items():
                if key in sensitive_keys:
                    # Пропускаем чувствительные ключи - они уже обработаны выше
                    logger.debug(f"Skipping sensitive key '{key}' in default_settings loop")
                    continue
                cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)", (key, value))

            # Коммитим все изменения
            conn.commit()
            
            # Закрываем соединение перед освобождением блокировки
            conn.close()
            
            logger.info(f"[PID {process_id}] Database initialized successfully.")
            
            # Освобождаем блокировку перед возвратом
            if lock_file and lock_acquired:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    lock_file.close()
                    logger.debug(f"[PID {process_id}] Database initialization lock released")
                except Exception as unlock_error:
                    logger.warning(f"[PID {process_id}] Failed to release lock: {unlock_error}")
            
            return  # Успешная инициализация
                    
        except sqlite3.OperationalError as db_error:
            if "database is locked" in str(db_error).lower():
                if attempt < max_retries - 1:
                    wait_time = retry_delays[attempt]
                    logger.warning(
                        f"[PID {process_id}] Database initialization failed due to lock "
                        f"(attempt {attempt + 1}/{max_retries}). Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                    # Закрываем соединение если было открыто
                    if 'conn' in locals():
                        try:
                            conn.close()
                        except:
                            pass
                    # Освобождаем блокировку перед следующей попыткой
                    if lock_file and lock_acquired:
                        try:
                            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                            lock_file.close()
                            lock_file = None
                            lock_acquired = False
                        except:
                            pass
                    continue
                else:
                    # Все попытки исчерпаны
                    logger.error(
                        f"[PID {process_id}] Database initialization failed after {max_retries} attempts. "
                        f"Database is locked and cannot be initialized."
                    )
                    if 'conn' in locals():
                        try:
                            conn.close()
                        except:
                            pass
                    raise
            else:
                # Другая ошибка БД - пробрасываем дальше
                if 'conn' in locals():
                    try:
                        conn.close()
                    except:
                        pass
                raise
        except Exception as e:
            # Любая другая ошибка
            logger.error(
                f"[PID {process_id}] Unexpected error during database initialization (attempt {attempt + 1}): {e}",
                exc_info=True
            )
            if 'conn' in locals():
                try:
                    conn.close()
                except:
                    pass
            if attempt < max_retries - 1:
                wait_time = retry_delays[attempt]
                logger.warning(f"[PID {process_id}] Retrying in {wait_time}s...")
                time.sleep(wait_time)
                # Освобождаем блокировку перед следующей попыткой
                if lock_file and lock_acquired:
                    try:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                        lock_file.close()
                        lock_file = None
                        lock_acquired = False
                    except:
                        pass
                continue
            else:
                raise
        finally:
            # Гарантированное освобождение блокировки при ошибке
            if lock_file and lock_acquired:
                try:
                    if not lock_file.closed:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                        lock_file.close()
                        logger.debug(f"[PID {process_id}] Database initialization lock released (finally block)")
                except Exception as unlock_error:
                    logger.warning(f"[PID {process_id}] Failed to release lock in finally: {unlock_error}")
            elif lock_file:
                try:
                    if not lock_file.closed:
                        lock_file.close()
                except:
                    pass
    
    # Если мы дошли сюда, все попытки исчерпаны
    logger.error(
        f"[PID {process_id}] Database initialization failed after {max_retries} attempts. "
        f"This may indicate concurrent initialization or database corruption."
    )
    raise sqlite3.OperationalError(
        f"Database locked after {max_retries} attempts. "
        f"This may indicate concurrent initialization."
    )



def create_database_indexes(cursor):

    """Создает индексы для оптимизации производительности базы данных"""

    try:
        def create_index_safe(sql: str, description: str) -> None:
            try:
                cursor.execute(sql)
            except sqlite3.Error as e:
                logging.debug(f"{description} may already exist: {e}")
            else:
                logging.debug(f"{description} ensure success")

        # Индексы для таблицы users

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_is_banned ON users(is_banned)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_registration_date ON users(registration_date)")
        
        # Проверяем существование колонки group_id перед созданием индекса
        cursor.execute("PRAGMA table_info(users)")
        users_columns = [row[1] for row in cursor.fetchall()]
        
        if 'group_id' in users_columns:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_group_id ON users(group_id)")

        

        # Индексы для таблицы vpn_keys

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vpn_keys_user_id ON vpn_keys(user_id)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vpn_keys_key_email ON vpn_keys(key_email)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vpn_keys_host_name ON vpn_keys(host_name)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vpn_keys_expiry_date ON vpn_keys(expiry_date)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vpn_keys_is_trial ON vpn_keys(is_trial)")

        # Проверяем существование колонок перед созданием индексов
        cursor.execute("PRAGMA table_info(vpn_keys)")
        vpn_keys_columns = [row[1] for row in cursor.fetchall()]
        
        if 'status' in vpn_keys_columns:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vpn_keys_status ON vpn_keys(status)")
        
        if 'enabled' in vpn_keys_columns:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vpn_keys_enabled ON vpn_keys(enabled)")

        if 'auto_renewal_enabled' in vpn_keys_columns:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vpn_keys_auto_renewal_enabled ON vpn_keys(auto_renewal_enabled)")

        

        # Индексы для таблицы transactions

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_payment_id ON transactions(payment_id)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_created_date ON transactions(created_date)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_payment_method ON transactions(payment_method)")

        

        # Индексы для таблицы notifications

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(type)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications(status)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_created_date ON notifications(created_date)")

        # Проверяем существование колонки key_id перед созданием индекса
        cursor.execute("PRAGMA table_info(notifications)")
        notifications_columns = [row[1] for row in cursor.fetchall()]
        
        if 'key_id' in notifications_columns:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_key_id ON notifications(key_id)")

        

        # Индексы для таблицы xui_hosts

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_xui_hosts_host_name ON xui_hosts(host_name)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_xui_hosts_host_code ON xui_hosts(host_code)")

        

        # Индексы для таблицы plans

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plans_host_name ON plans(host_name)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plans_plan_id ON plans(plan_id)")

        

        

        # Индексы для таблицы promo_codes

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_promo_codes_bot ON promo_codes(bot)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_promo_codes_active ON promo_codes(is_active)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_promo_codes_plan ON promo_codes(vpn_plan_id)")



        # Индексы для таблицы promo_code_usage

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_promo_code_usage_promo_id ON promo_code_usage(promo_id)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_promo_code_usage_user_id ON promo_code_usage(user_id)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_promo_code_usage_bot ON promo_code_usage(bot)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_promo_code_usage_used_at ON promo_code_usage(used_at)")

# Индексы для таблицы support_threads

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_threads_user_id ON support_threads(user_id)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_threads_thread_id ON support_threads(thread_id)")

        # Индексы для таблицы video_instructions

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_video_instructions_filename ON video_instructions(filename)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_video_instructions_created_at ON video_instructions(created_at)")

        # Индексы для таблицы user_groups
        create_index_safe(
            "CREATE INDEX IF NOT EXISTS idx_user_groups_group_name ON user_groups(group_name)",
            "Index idx_user_groups_group_name",
        )

        create_index_safe(
            "CREATE INDEX IF NOT EXISTS idx_user_groups_is_default ON user_groups(is_default)",
            "Index idx_user_groups_is_default",
        )

        create_index_safe(
            "CREATE INDEX IF NOT EXISTS idx_user_groups_group_code ON user_groups(group_code)",
            "Index idx_user_groups_group_code",
        )

        # Индекс для таблицы users по group_id (проверка существования колонки уже выполнена выше в create_database_indexes)
        # Индекс создается в функции create_database_indexes() с проверкой существования колонки

        

        logging.info("Database indexes created successfully.")

    except sqlite3.Error as e:

        logging.error(f"Error creating database indexes: {e}", exc_info=True)



def run_migration(conn: Optional[sqlite3.Connection] = None):

    if not DB_FILE.exists():

        logging.error("Users.db database file was not found. There is nothing to migrate.")

        return



    logging.info(f"Starting the migration of the database: {DB_FILE}")



    # Если соединение передано, используем его, иначе создаем новое
    should_close_conn = False
    if conn is None:
        conn = sqlite3.connect(DB_FILE)
        should_close_conn = True
        cursor = conn.cursor()
        # Устанавливаем PRAGMA для предотвращения блокировок только для нового соединения
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA journal_mode=DELETE")
    else:
        cursor = conn.cursor()
        # Проверяем, что PRAGMA уже установлены (они должны быть установлены в initialize_db)
        # Если нет - устанавливаем их
        try:
            cursor.execute("PRAGMA busy_timeout")
            timeout = cursor.fetchone()
            if timeout is None or timeout[0] < 30000:
                cursor.execute("PRAGMA busy_timeout=30000")
        except:
            cursor.execute("PRAGMA busy_timeout=30000")

    try:
        logging.info("The migration of the table 'users' ...")

        cursor.execute("PRAGMA table_info(users)")

        columns = [row[1] for row in cursor.fetchall()]

        if 'referred_by' not in columns:

            cursor.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")

            logging.info(" -> The column 'referred_by' is successfully added.")

        else:

            logging.info(" -> The column 'referred_by' already exists.")

        if 'referral_balance' not in columns:

            cursor.execute("ALTER TABLE users ADD COLUMN referral_balance REAL DEFAULT 0")

            logging.info(" -> The column 'referral_balance' is successfully added.")

        else:

            logging.info(" -> The column 'referral_balance' already exists.")

        if 'referral_balance_all' not in columns:

            cursor.execute("ALTER TABLE users ADD COLUMN referral_balance_all REAL DEFAULT 0")

            logging.info(" -> The column 'referral_balance_all' is successfully added.")

        else:

            logging.info(" -> The column 'referral_balance_all' already exists.")

        if 'balance' not in columns:

            cursor.execute("ALTER TABLE users ADD COLUMN balance REAL DEFAULT 0")

            logging.info(" -> The column 'balance' is successfully added.")

        else:

            logging.info(" -> The column 'balance' already exists.")

        if 'agreed_to_documents' not in columns:

            cursor.execute("ALTER TABLE users ADD COLUMN agreed_to_documents BOOLEAN DEFAULT 0")

            logging.info(" -> The column 'agreed_to_documents' is successfully added.")

        else:

            logging.info(" -> The column 'agreed_to_documents' already exists.")

        if 'subscription_status' not in columns:

            cursor.execute("ALTER TABLE users ADD COLUMN subscription_status TEXT DEFAULT 'not_checked'")

            logging.info(" -> The column 'subscription_status' is successfully added.")

        else:

            logging.info(" -> The column 'subscription_status' already exists.")

        # Добавляем колонки для ключей

        if 'key_id' not in columns:

            cursor.execute("ALTER TABLE users ADD COLUMN key_id INTEGER")

            logging.info(" -> The column 'key_id' is successfully added.")

        else:

            logging.info(" -> The column 'key_id' already exists.")

        if 'connection_string' not in columns:

            cursor.execute("ALTER TABLE users ADD COLUMN connection_string TEXT")

            logging.info(" -> The column 'connection_string' is successfully added.")

        else:

            logging.info(" -> The column 'connection_string' already exists.")

        if 'host_name' not in columns:

            cursor.execute("ALTER TABLE users ADD COLUMN host_name TEXT")

            logging.info(" -> The column 'host_name' is successfully added.")

        else:

            logging.info(" -> The column 'host_name' already exists.")

        if 'plan_name' not in columns:

            cursor.execute("ALTER TABLE users ADD COLUMN plan_name TEXT")

            logging.info(" -> The column 'plan_name' is successfully added.")

        else:

            logging.info(" -> The column 'plan_name' already exists.")

        if 'price' not in columns:

            cursor.execute("ALTER TABLE users ADD COLUMN price REAL")

            logging.info(" -> The column 'price' is successfully added.")

        else:

            logging.info(" -> The column 'price' already exists.")

        if 'email' not in columns:

            cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")

            logging.info(" -> The column 'email' is successfully added.")

        else:

            logging.info(" -> The column 'email' already exists.")

        if 'created_date' not in columns:

            cursor.execute("ALTER TABLE users ADD COLUMN created_date TIMESTAMP")

            logging.info(" -> The column 'created_date' is successfully added.")

        else:

            logging.info(" -> The column 'created_date' already exists.")

        if 'trial_days_given' not in columns:

            cursor.execute("ALTER TABLE users ADD COLUMN trial_days_given INTEGER DEFAULT 0")

            logging.info(" -> The column 'trial_days_given' is successfully added.")

        else:

            logging.info(" -> The column 'trial_days_given' already exists.")

        if 'trial_reuses_count' not in columns:

            cursor.execute("ALTER TABLE users ADD COLUMN trial_reuses_count INTEGER DEFAULT 0")

            logging.info(" -> The column 'trial_reuses_count' is successfully added.")

        else:

            logging.info(" -> The column 'trial_reuses_count' already exists.")

        if 'user_id' not in columns:

            # SQLite не позволяет добавить колонку с UNIQUE напрямую, добавляем без него

            cursor.execute("ALTER TABLE users ADD COLUMN user_id INTEGER")

            logging.info(" -> The column 'user_id' is successfully added.")

            

            # Заполняем существующие записи значениями, начиная с 1000

            cursor.execute("""

                SELECT telegram_id, ROW_NUMBER() OVER (ORDER BY registration_date ASC) as row_num

                FROM users

            """)

            users_to_update = cursor.fetchall()

            

            for telegram_id, row_num in users_to_update:

                new_user_id = 999 + row_num  # Начинаем с 1000

                cursor.execute("UPDATE users SET user_id = ? WHERE telegram_id = ?", (new_user_id, telegram_id))

                

            logging.info(f" -> Заполнено {len(users_to_update)} записей user_id, начиная с 1000.")

            

            # Создаем уникальный индекс на user_id

            try:

                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id)")

                logging.info(" -> Уникальный индекс на user_id успешно создан.")

            except sqlite3.Error as e:

                logging.warning(f" -> Не удалось создать уникальный индекс (возможно, уже существует): {e}")

        else:

            logging.info(" -> The column 'user_id' already exists.")

        if 'fullname' not in columns:

            cursor.execute("ALTER TABLE users ADD COLUMN fullname TEXT")

            logging.info(" -> The column 'fullname' is successfully added.")

        else:

            logging.info(" -> The column 'fullname' already exists.")

        
        
        if 'fio' not in columns:

            cursor.execute("ALTER TABLE users ADD COLUMN fio TEXT")

            logging.info(" -> The column 'fio' is successfully added.")

        else:

            logging.info(" -> The column 'fio' already exists.")

        
        if 'group_id' not in columns:

            cursor.execute("ALTER TABLE users ADD COLUMN group_id INTEGER")

            logging.info(" -> The column 'group_id' is successfully added.")

            # Находим ID группы по умолчанию и назначаем её всем существующим пользователям
            cursor.execute("SELECT group_id FROM user_groups WHERE is_default = 1 LIMIT 1")
            default_group = cursor.fetchone()
            
            if default_group:
                default_group_id = default_group[0]
                cursor.execute("UPDATE users SET group_id = ? WHERE group_id IS NULL", (default_group_id,))
                logging.info(f" -> Все существующие пользователи назначены в группу с ID {default_group_id}")

        else:

            logging.info(" -> The column 'group_id' already exists.")

        if 'auto_renewal_enabled' not in columns:

            cursor.execute("ALTER TABLE users ADD COLUMN auto_renewal_enabled INTEGER DEFAULT 1")

            logging.info(" -> The column 'auto_renewal_enabled' is successfully added.")

        else:

            logging.info(" -> The column 'auto_renewal_enabled' already exists.")

        # Миграция: добавляем поле keys_count для счетчика ключей пользователя
        if 'keys_count' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN keys_count INTEGER DEFAULT 0")
            logging.info(" -> The column 'keys_count' is successfully added to users table.")
            
            # Инициализируем счетчик для существующих пользователей
            # Вычисляем максимальный номер ключа для каждого пользователя на основе email
            logging.info(" -> Initializing keys_count for existing users...")
            try:
                # Получаем всех пользователей с ключами
                cursor.execute("SELECT DISTINCT user_id FROM vpn_keys")
                users_with_keys = cursor.fetchall()
                
                initialized_count = 0
                for (user_id,) in users_with_keys:
                    # Получаем все ключи пользователя
                    cursor.execute("SELECT key_email FROM vpn_keys WHERE user_id = ?", (user_id,))
                    user_keys = cursor.fetchall()
                    
                    max_key_number = 0
                    for (key_email,) in user_keys:
                        # Парсим номер ключа из email: user{user_id}-key{N}@...
                        try:
                            # Ищем паттерн -key{N}@ или -key{N}-trial@
                            match = re.search(r'-key(\d+)', key_email)
                            if match:
                                key_num = int(match.group(1))
                                if key_num > max_key_number:
                                    max_key_number = key_num
                        except (ValueError, AttributeError):
                            continue
                    
                    if max_key_number > 0:
                        cursor.execute(
                            "UPDATE users SET keys_count = ? WHERE telegram_id = ?",
                            (max_key_number, user_id)
                        )
                        initialized_count += 1
                        logging.debug(f" -> Initialized keys_count={max_key_number} for user_id={user_id}")
                
                conn.commit()
                logging.info(f" -> Initialized keys_count for {initialized_count} users.")
            except Exception as e:
                logging.warning(f" -> Failed to initialize keys_count for existing users: {e}", exc_info=True)
                # Не прерываем миграцию, продолжаем работу
        else:
            logging.info(" -> The column 'keys_count' already exists in users table.")

        # Миграция: добавляем поле timezone для поддержки временных зон пользователей
        if 'timezone' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN timezone TEXT")
            logging.info(" -> The column 'timezone' is successfully added to users table.")
        else:
            logging.info(" -> The column 'timezone' already exists in users table.")

        logging.info("The table 'users' has been successfully updated.")

        logging.info("The migration of the table 'vpn_keys' ...")

        cursor.execute("PRAGMA table_info(vpn_keys)")

        vpn_keys_columns = [row[1] for row in cursor.fetchall()]

        if 'connection_string' not in vpn_keys_columns:

            cursor.execute("ALTER TABLE vpn_keys ADD COLUMN connection_string TEXT")

            logging.info(" -> The column 'connection_string' is successfully added to vpn_keys table.")

        else:

            logging.info(" -> The column 'connection_string' already exists in vpn_keys table.")

            

        if 'plan_name' not in vpn_keys_columns:

            cursor.execute("ALTER TABLE vpn_keys ADD COLUMN plan_name TEXT")

            logging.info(" -> The column 'plan_name' is successfully added to vpn_keys table.")

        else:

            logging.info(" -> The column 'plan_name' already exists in vpn_keys table.")

            

        if 'price' not in vpn_keys_columns:

            cursor.execute("ALTER TABLE vpn_keys ADD COLUMN price REAL")

            logging.info(" -> The column 'price' is successfully added to vpn_keys table.")

        else:

            logging.info(" -> The column 'price' already exists in vpn_keys table.")



        if 'protocol' not in vpn_keys_columns:

            cursor.execute("ALTER TABLE vpn_keys ADD COLUMN protocol TEXT DEFAULT 'vless'")

            logging.info(" -> The column 'protocol' is successfully added to vpn_keys table.")

        else:

            logging.info(" -> The column 'protocol' already exists in vpn_keys table.")



        if 'is_trial' not in vpn_keys_columns:

            cursor.execute("ALTER TABLE vpn_keys ADD COLUMN is_trial INTEGER DEFAULT 0")

            logging.info(" -> The column 'is_trial' is successfully added to vpn_keys table.")

        else:

            logging.info(" -> The column 'is_trial' already exists in vpn_keys table.")



        if 'status' not in vpn_keys_columns:

            cursor.execute("ALTER TABLE vpn_keys ADD COLUMN status TEXT")

            logging.info(" -> The column 'status' is successfully added to vpn_keys table.")

        else:

            logging.info(" -> The column 'status' already exists in vpn_keys table.")



        if 'remaining_seconds' not in vpn_keys_columns:

            cursor.execute("ALTER TABLE vpn_keys ADD COLUMN remaining_seconds INTEGER")

            logging.info(" -> The column 'remaining_seconds' is successfully added to vpn_keys table.")

        else:

            logging.info(" -> The column 'remaining_seconds' already exists in vpn_keys table.")



        if 'start_date' not in vpn_keys_columns:

            cursor.execute("ALTER TABLE vpn_keys ADD COLUMN start_date TIMESTAMP")

            logging.info(" -> The column 'start_date' is successfully added to vpn_keys table.")

        else:

            logging.info(" -> The column 'start_date' already exists in vpn_keys table.")

            

        if 'enabled' not in vpn_keys_columns:

            cursor.execute("ALTER TABLE vpn_keys ADD COLUMN enabled INTEGER DEFAULT 1")

            logging.info(" -> The column 'enabled' is successfully added to vpn_keys table.")

        else:

            logging.info(" -> The column 'enabled' already exists in vpn_keys table.")

        

        if 'auto_renewal_enabled' not in vpn_keys_columns:

            cursor.execute("ALTER TABLE vpn_keys ADD COLUMN auto_renewal_enabled INTEGER DEFAULT 1")

            logging.info(" -> The column 'auto_renewal_enabled' is successfully added to vpn_keys table.")

        else:

            logging.info(" -> The column 'auto_renewal_enabled' already exists in vpn_keys table.")

        

        if 'subscription_link' not in vpn_keys_columns:

            cursor.execute("ALTER TABLE vpn_keys ADD COLUMN subscription_link TEXT")

            logging.info(" -> The column 'subscription_link' is successfully added to vpn_keys table.")

        else:

            logging.info(" -> The column 'subscription_link' already exists in vpn_keys table.")

        

        logging.info("The table 'vpn_keys' has been successfully updated.")



        logging.info("The migration of the table 'Transactions' ...")



        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'")

        table_exists = cursor.fetchone()



        if table_exists:

            cursor.execute("PRAGMA table_info(transactions)")

            trans_columns = [row[1] for row in cursor.fetchall()]

            

            # Проверяем и добавляем transaction_hash если нужно

            if 'transaction_hash' not in trans_columns:

                cursor.execute("ALTER TABLE transactions ADD COLUMN transaction_hash TEXT")

                logging.info(" -> The column 'transaction_hash' is successfully added to transactions table.")

            else:

                logging.info(" -> The column 'transaction_hash' already exists in transactions table.")

            

            # Проверяем и добавляем payment_link если нужно

            if 'payment_link' not in trans_columns:

                cursor.execute("ALTER TABLE transactions ADD COLUMN payment_link TEXT")

                logging.info(" -> The column 'payment_link' is successfully added to transactions table.")

            else:

                logging.info(" -> The column 'payment_link' already exists in transactions table.")

            
            # Проверяем и добавляем новые поля YooKassa если нужно

            if 'yookassa_payment_id' not in trans_columns:

                cursor.execute("ALTER TABLE transactions ADD COLUMN yookassa_payment_id TEXT")

                logging.info(" -> The column 'yookassa_payment_id' is successfully added to transactions table.")

            else:

                logging.info(" -> The column 'yookassa_payment_id' already exists in transactions table.")

            
            if 'rrn' not in trans_columns:

                cursor.execute("ALTER TABLE transactions ADD COLUMN rrn TEXT")

                logging.info(" -> The column 'rrn' is successfully added to transactions table.")

            else:

                logging.info(" -> The column 'rrn' already exists in transactions table.")

            
            if 'authorization_code' not in trans_columns:

                cursor.execute("ALTER TABLE transactions ADD COLUMN authorization_code TEXT")

                logging.info(" -> The column 'authorization_code' is successfully added to transactions table.")

            else:

                logging.info(" -> The column 'authorization_code' already exists in transactions table.")

            
            if 'payment_type' not in trans_columns:

                cursor.execute("ALTER TABLE transactions ADD COLUMN payment_type TEXT")

                logging.info(" -> The column 'payment_type' is successfully added to transactions table.")

            else:

                logging.info(" -> The column 'payment_type' already exists in transactions table.")

            
            # Проверяем и добавляем api_request если нужно
            if 'api_request' not in trans_columns:

                cursor.execute("ALTER TABLE transactions ADD COLUMN api_request TEXT")

                logging.info(" -> The column 'api_request' is successfully added to transactions table.")

            else:

                logging.info(" -> The column 'api_request' already exists in transactions table.")

            
            # Проверяем и добавляем api_response если нужно
            if 'api_response' not in trans_columns:

                cursor.execute("ALTER TABLE transactions ADD COLUMN api_response TEXT")

                logging.info(" -> The column 'api_response' is successfully added to transactions table.")

            else:

                logging.info(" -> The column 'api_response' already exists in transactions table.")

            

            if 'payment_id' in trans_columns and 'status' in trans_columns and 'username' in trans_columns:

                logging.info("The 'Transactions' table already has a new structure. Migration is not required.")

            else:

                backup_name = f"transactions_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}"

                logging.warning(f"The old structure of the TRANSACTIONS table was discovered. I rename in '{backup_name}' ...")

                # Валидация имени таблицы для безопасности (только буквы, цифры, подчеркивания)
                if not re.match(r'^[a-zA-Z0-9_]+$', backup_name):
                    raise ValueError(f"Invalid table name: {backup_name}. Only alphanumeric characters and underscores are allowed.")
                
                # SQLite не поддерживает параметризацию для имен таблиц в DDL операциях
                # Используем форматирование строки с валидированным именем
                cursor.execute(f"ALTER TABLE transactions RENAME TO {backup_name}")

                

                logging.info("I create a new table 'Transactions' with the correct structure ...")

                create_new_transactions_table(cursor)

                logging.info("The new table 'Transactions' has been successfully created. The old data is saved.")

        else:

            logging.info("TRANSACTIONS table was not found. I create a new one ...")

            create_new_transactions_table(cursor)

            logging.info("The new table 'Transactions' has been successfully created.")



        # Миграция таблицы webhooks для гибридного хранения webhook'ов
        logging.info("The migration of the table 'webhooks' ...")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='webhooks'")
        webhooks_table_exists = cursor.fetchone()
        
        if not webhooks_table_exists:
            # Создаем таблицу webhooks для гибридного хранения
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS webhooks (
                    webhook_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    webhook_type TEXT NOT NULL,
                    event_type TEXT,
                    payment_id TEXT,
                    transaction_id INTEGER,
                    request_payload TEXT,
                    response_payload TEXT,
                    status TEXT DEFAULT 'received',
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
                )
            ''')
            
            # Создаем индексы для быстрого поиска
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_webhooks_payment_id ON webhooks(payment_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_webhooks_transaction_id ON webhooks(transaction_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_webhooks_created_date ON webhooks(created_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_webhooks_webhook_type ON webhooks(webhook_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_webhooks_status ON webhooks(status)")
            
            logging.info(" -> The table 'webhooks' has been successfully created with indexes.")
        else:
            logging.info(" -> The table 'webhooks' already exists.")
            
            # Проверяем наличие индексов и создаем если их нет
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_webhooks_payment_id'")
            if not cursor.fetchone():
                cursor.execute("CREATE INDEX idx_webhooks_payment_id ON webhooks(payment_id)")
                logging.info(" -> Index 'idx_webhooks_payment_id' created.")
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_webhooks_transaction_id'")
            if not cursor.fetchone():
                cursor.execute("CREATE INDEX idx_webhooks_transaction_id ON webhooks(transaction_id)")
                logging.info(" -> Index 'idx_webhooks_transaction_id' created.")
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_webhooks_created_date'")
            if not cursor.fetchone():
                cursor.execute("CREATE INDEX idx_webhooks_created_date ON webhooks(created_date)")
                logging.info(" -> Index 'idx_webhooks_created_date' created.")
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_webhooks_webhook_type'")
            if not cursor.fetchone():
                cursor.execute("CREATE INDEX idx_webhooks_webhook_type ON webhooks(webhook_type)")
                logging.info(" -> Index 'idx_webhooks_webhook_type' created.")
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_webhooks_status'")
            if not cursor.fetchone():
                cursor.execute("CREATE INDEX idx_webhooks_status ON webhooks(status)")
                logging.info(" -> Index 'idx_webhooks_status' created.")

        logging.info("The migration of the table 'plans' ...")

        cursor.execute("PRAGMA table_info(plans)")

        plans_columns = [row[1] for row in cursor.fetchall()]

        if 'days' not in plans_columns:

            cursor.execute("ALTER TABLE plans ADD COLUMN days INTEGER DEFAULT 0")

            logging.info(" -> The column 'days' is successfully added to plans table.")

        else:

            logging.info(" -> The column 'days' already exists in plans table.")

        # New: support hours in plan duration

        if 'hours' not in plans_columns:

            cursor.execute("ALTER TABLE plans ADD COLUMN hours INTEGER DEFAULT 0")

            logging.info(" -> The column 'hours' is successfully added to plans table.")

        else:

            logging.info(" -> The column 'hours' already exists in plans table.")

        if 'traffic_gb' not in plans_columns:

            cursor.execute("ALTER TABLE plans ADD COLUMN traffic_gb REAL DEFAULT 0")

            logging.info(" -> The column 'traffic_gb' is successfully added to plans table.")

        else:

            logging.info(" -> The column 'traffic_gb' already exists in plans table.")

        # Добавляем поле key_provision_mode для выбора режима предоставления ключа
        if 'key_provision_mode' not in plans_columns:
            cursor.execute("ALTER TABLE plans ADD COLUMN key_provision_mode TEXT DEFAULT 'key'")
            logging.info(" -> The column 'key_provision_mode' is successfully added to plans table.")
        else:
            logging.info(" -> The column 'key_provision_mode' already exists in plans table.")

        # Добавляем поле display_mode для выбора режима отображения тарифа
        if 'display_mode' not in plans_columns:
            cursor.execute("ALTER TABLE plans ADD COLUMN display_mode TEXT DEFAULT 'all'")
            logging.info(" -> The column 'display_mode' is successfully added to plans table.")
        else:
            logging.info(" -> The column 'display_mode' already exists in plans table.")

        # Добавляем поле display_mode_groups для выбора групп пользователей
        if 'display_mode_groups' not in plans_columns:
            cursor.execute("ALTER TABLE plans ADD COLUMN display_mode_groups TEXT DEFAULT NULL")
            logging.info(" -> The column 'display_mode_groups' is successfully added to plans table.")
        else:
            logging.info(" -> The column 'display_mode_groups' already exists in plans table.")

        logging.info("The table 'plans' has been successfully updated.")



        # Ensure xui_hosts.host_code exists and is populated

        try:

            cursor.execute("PRAGMA table_info(xui_hosts)")

            hosts_columns = [row[1] for row in cursor.fetchall()]

            if 'host_code' not in hosts_columns:

                cursor.execute("ALTER TABLE xui_hosts ADD COLUMN host_code TEXT")

            # Backfill empty codes with slugified host_name (lowercase, no spaces)

            cursor.execute("UPDATE xui_hosts SET host_code = LOWER(REPLACE(host_name, ' ', '')) WHERE COALESCE(host_code, '') = ''")

        except Exception as e:
            logger.debug(f"Migration error (non-critical): {e}")



        # Notifications table

        logging.info("The migration of the table 'notifications' ...")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'")

        notif_exists = cursor.fetchone()

        if not notif_exists:

            cursor.execute('''

                CREATE TABLE IF NOT EXISTS notifications (

                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,

                    user_id INTEGER,

                    username TEXT,

                    type TEXT,

                    title TEXT,

                    message TEXT,

                    status TEXT,

                    meta TEXT,

                    key_id INTEGER,

                    marker_hours INTEGER,

                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                )

            ''')

            logging.info("The table 'notifications' has been successfully created.")

        else:

            logging.info("The table 'notifications' already exists. Migration is not required.")

            # Ensure new columns exist

            cursor.execute("PRAGMA table_info(notifications)")

            notif_columns = [row[1] for row in cursor.fetchall()]

            if 'key_id' not in notif_columns:

                try:

                    cursor.execute("ALTER TABLE notifications ADD COLUMN key_id INTEGER")
                    logging.info(" -> The column 'key_id' is successfully added to notifications table.")

                except Exception as e:
                    logger.warning(f"Migration error adding key_id column: {e}")

            if 'marker_hours' not in notif_columns:

                try:

                    cursor.execute("ALTER TABLE notifications ADD COLUMN marker_hours INTEGER")
                    logging.info(" -> The column 'marker_hours' is successfully added to notifications table.")

                except Exception as e:
                    logger.warning(f"Migration error adding marker_hours column: {e}")

        # Миграция для изменения типа поля vpn_plan_id в таблице promo_codes
        logging.info("The migration of the table 'promo_codes' ...")
        
        try:
            # Создаем таблицу для отслеживания выполненных миграций
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS migration_history (
                    migration_id TEXT PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Проверяем, была ли выполнена миграция promo_codes_vpn_plan_id
            cursor.execute("SELECT migration_id FROM migration_history WHERE migration_id = 'promo_codes_vpn_plan_id_to_text'")
            migration_done = cursor.fetchone()
            
            if not migration_done:
                # Проверяем, существует ли таблица promo_codes
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='promo_codes'")
                if cursor.fetchone():
                    # Получаем информацию о колонках
                    cursor.execute("PRAGMA table_info(promo_codes)")
                    promo_columns = [row[1] for row in cursor.fetchall()]
                    
                    if 'vpn_plan_id' in promo_columns:
                        # Проверяем текущий тип колонки
                        cursor.execute("PRAGMA table_info(promo_codes)")
                        for row in cursor.fetchall():
                            if row[1] == 'vpn_plan_id' and row[2] == 'INTEGER':
                                logging.info(" -> Converting vpn_plan_id column from INTEGER to TEXT for JSON support")
                                # SQLite не поддерживает изменение типа колонки напрямую
                                # Создаем новую таблицу с правильным типом
                                cursor.execute('''
                                    CREATE TABLE promo_codes_new (
                                        promo_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        code TEXT NOT NULL UNIQUE,
                                        bot TEXT NOT NULL,
                                        vpn_plan_id TEXT,
                                        tariff_code TEXT,
                                        discount_amount REAL DEFAULT 0,
                                        discount_percent REAL DEFAULT 0,
                                        discount_bonus REAL DEFAULT 0,
                                        usage_limit_per_bot INTEGER DEFAULT 1,
                                        is_active INTEGER DEFAULT 1,
                                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                    )
                                ''')
                                
                                # Копируем данные, преобразуя INTEGER в TEXT
                                cursor.execute('''
                                    INSERT INTO promo_codes_new 
                                    SELECT promo_id, code, bot, 
                                           CASE WHEN vpn_plan_id IS NULL THEN NULL ELSE CAST(vpn_plan_id AS TEXT) END,
                                           tariff_code, discount_amount, discount_percent, discount_bonus,
                                           usage_limit_per_bot, is_active, created_at, updated_at
                                    FROM promo_codes
                                ''')
                                
                                # Удаляем старую таблицу и переименовываем новую
                                cursor.execute('DROP TABLE promo_codes')
                                cursor.execute('ALTER TABLE promo_codes_new RENAME TO promo_codes')
                                
                                # Создаем индексы
                                cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_promo_codes_code ON promo_codes(code)')
                                cursor.execute('CREATE INDEX IF NOT EXISTS idx_promo_codes_bot ON promo_codes(bot)')
                                cursor.execute('CREATE INDEX IF NOT EXISTS idx_promo_codes_is_active ON promo_codes(is_active)')
                                
                                # Отмечаем миграцию как выполненную
                                cursor.execute("INSERT INTO migration_history (migration_id) VALUES ('promo_codes_vpn_plan_id_to_text')")
                                
                                logging.info(" -> The column 'vpn_plan_id' successfully converted to TEXT")
                                break
                    else:
                        logging.info(" -> The column 'vpn_plan_id' does not exist in promo_codes table")
                else:
                    logging.info(" -> The table 'promo_codes' does not exist")
            else:
                logging.info(" -> Migration 'promo_codes_vpn_plan_id_to_text' already applied, skipping")
        except Exception as e:
            logging.error(f" -> Error migrating promo_codes table: {e}")

        # Миграция настроек бота для логов
        logging.info("Migrating bot logging settings...")
        try:
            # Проверяем существующие настройки
            cursor.execute("SELECT key FROM bot_settings WHERE key IN ('logging_bot_token', 'logging_bot_username', 'logging_bot_admin_chat_id', 'logging_bot_level')")
            existing_keys = {row[0] for row in cursor.fetchall()}
            
            # Добавляем недостающие настройки
            new_settings = {
                'logging_bot_token': '',
                'logging_bot_username': '',
                'logging_bot_admin_chat_id': '',
                'logging_bot_level': 'error'
            }
            
            for key, default_value in new_settings.items():
                if key not in existing_keys:
                    cursor.execute("INSERT INTO bot_settings (key, value) VALUES (?, ?)", (key, default_value))
                    logging.info(f" -> Added setting '{key}' with default value '{default_value}'")
                else:
                    logging.info(f" -> Setting '{key}' already exists")
                    
        except Exception as e:
            logging.error(f" -> Error migrating bot logging settings: {e}")

        # Миграция новых колонок для promo_codes
        logging.info("Migrating promo_codes new columns...")
        try:
            # Проверяем существующие колонки (не полагаемся на migration_history)
            cursor.execute("PRAGMA table_info(promo_codes)")
            promo_columns = [row[1] for row in cursor.fetchall()]
            
            # Добавляем новые колонки
            new_columns = [
                ("burn_after_value", "INTEGER DEFAULT NULL"),
                ("burn_after_unit", "TEXT DEFAULT NULL"),
                ("valid_until", "TIMESTAMP DEFAULT NULL"),
                ("target_group_ids", "TEXT DEFAULT NULL"),
                ("bot_username", "TEXT DEFAULT NULL")
            ]
            
            all_columns_exist = True
            for column_name, column_definition in new_columns:
                if column_name not in promo_columns:
                    # Пытаемся добавить колонку с retry логикой для обработки блокировок БД
                    max_retries = 5
                    retry_delay = 0.5  # секунды
                    
                    for attempt in range(max_retries):
                        try:
                            cursor.execute(f"ALTER TABLE promo_codes ADD COLUMN {column_name} {column_definition}")
                            logging.info(f" -> Added column '{column_name}' to promo_codes table")
                            break  # Успех - выходим из retry цикла
                        except sqlite3.OperationalError as e:
                            if "database is locked" in str(e) and attempt < max_retries - 1:
                                logging.warning(f" -> Database locked while adding '{column_name}', retry {attempt + 1}/{max_retries} in {retry_delay}s...")
                                time.sleep(retry_delay)
                                retry_delay *= 2  # Экспоненциальная задержка
                            else:
                                logging.error(f" -> Failed to add column '{column_name}' after {attempt + 1} attempts: {e}")
                                all_columns_exist = False
                                break
                else:
                    logging.info(f" -> Column '{column_name}' already exists in promo_codes table")
            
            # Отмечаем миграцию как выполненную только если все колонки существуют
            if all_columns_exist:
                # Проверяем, не добавлена ли уже запись в migration_history
                try:
                    cursor.execute("SELECT migration_id FROM migration_history WHERE migration_id = 'promo_codes_new_columns'")
                    if not cursor.fetchone():
                        cursor.execute("INSERT INTO migration_history (migration_id) VALUES ('promo_codes_new_columns')")
                        logging.info(" -> Promo codes new columns migration completed and marked in history")
                    else:
                        logging.info(" -> Promo codes new columns migration completed (already marked in history)")
                except sqlite3.OperationalError as e:
                    # Игнорируем ошибку блокировки при записи в migration_history - колонки уже на месте
                    if "database is locked" in str(e):
                        logging.warning(f" -> Could not update migration_history due to lock, but all columns exist - migration successful")
                    else:
                        raise
            else:
                logging.warning(" -> Some columns failed to migrate, will retry on next start")
                
        except Exception as e:
            logging.error(f" -> Error migrating promo_codes new columns: {e}")

        # Миграция user_groups - добавление поля group_code
        logging.info("Migrating user_groups table...")
        try:
            # Проверяем наличие колонки group_code
            cursor.execute("PRAGMA table_info(user_groups)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'group_code' not in columns:
                # Добавляем колонку group_code без UNIQUE ограничения сначала
                cursor.execute("ALTER TABLE user_groups ADD COLUMN group_code TEXT")
                logging.info(" -> The column 'group_code' is successfully added to user_groups table.")
                
                # Генерируем коды для существующих групп
                cursor.execute("SELECT group_id, group_name FROM user_groups")
                existing_groups = cursor.fetchall()
                
                for group_id, group_name in existing_groups:
                    # Генерируем код из названия группы (транслитерация + lowercase)
                    group_code = _generate_group_code(group_name)
                    
                    # Проверяем уникальность кода
                    counter = 1
                    original_code = group_code
                    while True:
                        cursor.execute("SELECT COUNT(*) FROM user_groups WHERE group_code = ?", (group_code,))
                        if cursor.fetchone()[0] == 0:
                            break
                        group_code = f"{original_code}_{counter}"
                        counter += 1
                    
                    # Обновляем группу с сгенерированным кодом
                    cursor.execute("UPDATE user_groups SET group_code = ? WHERE group_id = ?", (group_code, group_id))
                    logging.info(f" -> Generated group_code '{group_code}' for group '{group_name}' (ID: {group_id})")
                
                # Теперь создаем UNIQUE индекс для group_code
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_user_groups_group_code_unique ON user_groups(group_code)")
                logging.info(" -> Unique index for group_code created successfully.")
                
                logging.info(" -> User groups migration completed successfully.")
            else:
                logging.info(" -> The column 'group_code' already exists in user_groups table.")
                
                # Проверяем, есть ли группы без group_code и генерируем для них коды
                cursor.execute("SELECT group_id, group_name FROM user_groups WHERE group_code IS NULL OR group_code = ''")
                groups_without_code = cursor.fetchall()
                
                if groups_without_code:
                    logging.info(f" -> Found {len(groups_without_code)} groups without group_code, generating codes...")
                    for group_id, group_name in groups_without_code:
                        # Генерируем код из названия группы (транслитерация + lowercase)
                        group_code = _generate_group_code(group_name)
                        
                        # Проверяем уникальность кода
                        counter = 1
                        original_code = group_code
                        while True:
                            cursor.execute("SELECT COUNT(*) FROM user_groups WHERE group_code = ?", (group_code,))
                            if cursor.fetchone()[0] == 0:
                                break
                            group_code = f"{original_code}_{counter}"
                            counter += 1
                        
                        # Обновляем группу с сгенерированным кодом
                        cursor.execute("UPDATE user_groups SET group_code = ? WHERE group_id = ?", (group_code, group_id))
                        logging.info(f" -> Generated group_code '{group_code}' for group '{group_name}' (ID: {group_id})")
                
        except Exception as e:
            logging.error(f" -> Error migrating user_groups: {e}")

        # Миграция promo_code_usage - исправление ограничения UNIQUE
        logging.info("Migrating promo_code_usage unique constraint...")
        try:
            # Проверяем, была ли выполнена миграция исправления ограничения UNIQUE
            cursor.execute("SELECT migration_id FROM migration_history WHERE migration_id = 'promo_code_usage_fix_unique_constraint'")
            migration_done = cursor.fetchone()
            
            if not migration_done:
                # Проверяем существующую структуру таблицы
                cursor.execute("PRAGMA table_info(promo_code_usage)")
                columns = [row[1] for row in cursor.fetchall()]
                
                if 'user_id' in columns:
                    # Используем retry логику для критичных операций миграции
                    max_retries = 5
                    retry_delay = 0.5  # секунды
                    migration_success = False
                    
                    for attempt in range(max_retries):
                        try:
                            # Создаем новую таблицу с правильным ограничением UNIQUE
                            cursor.execute('''
                                CREATE TABLE promo_code_usage_new (
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
                                    status TEXT DEFAULT 'applied',
                                    FOREIGN KEY (promo_id) REFERENCES promo_codes (promo_id),
                                    FOREIGN KEY (plan_id) REFERENCES plans (plan_id),
                                    FOREIGN KEY (user_id) REFERENCES users (telegram_id),
                                    UNIQUE (promo_id, user_id, bot)
                                )
                            ''')
                            
                            # Копируем данные из старой таблицы
                            cursor.execute('''
                                INSERT INTO promo_code_usage_new 
                                SELECT * FROM promo_code_usage
                            ''')
                            
                            # Удаляем старую таблицу и переименовываем новую
                            cursor.execute('DROP TABLE promo_code_usage')
                            cursor.execute('ALTER TABLE promo_code_usage_new RENAME TO promo_code_usage')
                            
                            # Создаем индексы
                            cursor.execute('CREATE INDEX IF NOT EXISTS idx_promo_code_usage_promo_id ON promo_code_usage(promo_id)')
                            cursor.execute('CREATE INDEX IF NOT EXISTS idx_promo_code_usage_user_id ON promo_code_usage(user_id)')
                            cursor.execute('CREATE INDEX IF NOT EXISTS idx_promo_code_usage_bot ON promo_code_usage(bot)')
                            cursor.execute('CREATE INDEX IF NOT EXISTS idx_promo_code_usage_status ON promo_code_usage(status)')
                            
                            # Отмечаем миграцию как выполненную
                            cursor.execute("INSERT INTO migration_history (migration_id) VALUES ('promo_code_usage_fix_unique_constraint')")
                            logging.info(" -> Promo code usage unique constraint migration completed")
                            migration_success = True
                            break  # Успех - выходим из retry цикла
                        except sqlite3.OperationalError as e:
                            if "database is locked" in str(e) and attempt < max_retries - 1:
                                logging.warning(f" -> Database locked during promo_code_usage migration, retry {attempt + 1}/{max_retries} in {retry_delay}s...")
                                time.sleep(retry_delay)
                                retry_delay *= 2  # Экспоненциальная задержка
                            else:
                                logging.error(f" -> Failed to migrate promo_code_usage after {attempt + 1} attempts: {e}")
                                raise
                    
                    if not migration_success:
                        logging.error(" -> Failed to complete promo_code_usage migration after all retries")
                else:
                    logging.warning(" -> Column 'user_id' not found in promo_code_usage table, skipping migration")
            else:
                logging.info(" -> Migration 'promo_code_usage_fix_unique_constraint' already applied, skipping")
                
        except Exception as e:
            logging.error(f" -> Error migrating promo_code_usage unique constraint: {e}")

        # Миграция настроек бекапов
        logging.info("Migrating backup settings...")
        migrate_backup_settings(conn)

        # Миграция таблицы user_tokens для личного кабинета
        logging.info("Migrating user_tokens table...")
        try:
            # Проверяем, была ли выполнена миграция создания таблицы user_tokens
            cursor.execute("SELECT migration_id FROM migration_history WHERE migration_id = 'user_tokens_create_table'")
            migration_done = cursor.fetchone()
            
            if not migration_done:
                # Проверяем, существует ли таблица user_tokens
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_tokens'")
                table_exists = cursor.fetchone()
                
                if not table_exists:
                    # Создаем таблицу user_tokens
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS user_tokens (
                            token TEXT PRIMARY KEY,
                            user_id INTEGER NOT NULL,
                            key_id INTEGER NOT NULL,
                            created_at TEXT NOT NULL,
                            last_used_at TEXT,
                            access_count INTEGER DEFAULT 0,
                            FOREIGN KEY (user_id) REFERENCES users (telegram_id),
                            FOREIGN KEY (key_id) REFERENCES vpn_keys (key_id)
                        )
                    ''')
                    
                    # Создаем индексы для оптимизации запросов
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_token ON user_tokens(token)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_key ON user_tokens(user_id, key_id)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_key_id ON user_tokens(key_id)')
                    
                    # Отмечаем миграцию как выполненную
                    cursor.execute("INSERT INTO migration_history (migration_id) VALUES ('user_tokens_create_table')")
                    logging.info(" -> Table 'user_tokens' created successfully with indexes")
                else:
                    logging.info(" -> Table 'user_tokens' already exists")
                    # Отмечаем миграцию как выполненную даже если таблица уже существует
                    cursor.execute("INSERT OR IGNORE INTO migration_history (migration_id) VALUES ('user_tokens_create_table')")
            else:
                logging.info(" -> Migration 'user_tokens_create_table' already applied, skipping")
                
        except Exception as e:
            logging.error(f" -> Error migrating user_tokens table: {e}")

        # Миграция для создания таблицы шаблонов сообщений
        try:
            logging.info("Creating message_templates table...")
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='message_templates'")
            table_exists = cursor.fetchone()
            
            if not table_exists:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS message_templates (
                        template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        template_key TEXT UNIQUE NOT NULL,
                        category TEXT NOT NULL,
                        provision_mode TEXT,
                        template_text TEXT NOT NULL,
                        description TEXT,
                        variables TEXT,
                        is_active INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Создаем индексы для оптимизации запросов
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_template_key ON message_templates(template_key)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON message_templates(category)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_provision_mode ON message_templates(provision_mode)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_is_active ON message_templates(is_active)')
                
                logging.info(" -> message_templates table created")
                
                # Инициализация дефолтных шаблонов только если таблица пустая
                cursor.execute('SELECT COUNT(*) FROM message_templates')
                count = cursor.fetchone()[0]
                if count == 0:
                    logging.info(" -> Initializing default message templates...")
                    default_templates = [
                        ('purchase_success_key', 'purchase', 'key', 
                         '🎉 <b>Ваш ключ #{key_number}{trial_suffix} {action_text}!</b>\n\n⏳ <b>Он будет действовать до:</b> {expiry_formatted}\n\n⬇️ <b>НИЖЕ ВАШ КЛЮЧ</b> ⬇️\n------------------------------------------------------------------------\n<code>{connection_string}</code>\n------------------------------------------------------------------------\n<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>\n{cabinet_text}{fallback_text}',
                         'Сообщение о покупке для режима "Ключ"', '["key_number", "trial_suffix", "action_text", "expiry_formatted", "connection_string", "cabinet_text", "fallback_text", "status_icon", "host_flag", "tariff_name", "price_formatted", "tariff_info"]'),
                        
                        ('purchase_success_subscription', 'purchase', 'subscription',
                         '🎉 <b>Ваш ключ #{key_number}{trial_suffix} {action_text}!</b>\n\n⏳ <b>Он будет действовать до:</b> {expiry_formatted}\n\n⬇️ <b>ВАША ПОДПИСКА</b> ⬇️\n------------------------------------------------------------------------\n{subscription_link}\n------------------------------------------------------------------------\n<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>\n{cabinet_text}{fallback_text}',
                         'Сообщение о покупке для режима "Подписка"', '["key_number", "trial_suffix", "action_text", "expiry_formatted", "subscription_link", "cabinet_text", "fallback_text", "status_icon", "host_flag", "tariff_name", "price_formatted", "tariff_info"]'),
                        
                        ('purchase_success_both', 'purchase', 'both',
                         '🎉 <b>Ваш ключ #{key_number}{trial_suffix} {action_text}!</b>\n\n⏳ <b>Он будет действовать до:</b> {expiry_formatted}\n\n⬇️ <b>НИЖЕ ВАШ КЛЮЧ</b> ⬇️\n------------------------------------------------------------------------\n<code>{connection_string}</code>\n------------------------------------------------------------------------\n\n⬇️ <b>ВАША ПОДПИСКА</b> ⬇️\n------------------------------------------------------------------------\n{subscription_link}\n------------------------------------------------------------------------\n<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>\n{cabinet_text}{fallback_text}',
                         'Сообщение о покупке для режима "Ключ + Подписка"', '["key_number", "trial_suffix", "action_text", "expiry_formatted", "connection_string", "subscription_link", "cabinet_text", "fallback_text", "status_icon", "host_flag", "tariff_name", "price_formatted", "tariff_info"]'),
                        
                        ('purchase_success_cabinet', 'purchase', 'cabinet',
                         '🎉 <b>Ваш ключ #{key_number}{trial_suffix} {action_text}!</b>\n\n⏳ <b>Он будет действовать до:</b> {expiry_formatted}\n\n⬇️ <b>ВАШ ЛИЧНЫЙ КАБИНЕТ</b> ⬇️\n------------------------------------------------------------------------\n<a href="{cabinet_url}">{cabinet_url}</a>\n------------------------------------------------------------------------\n<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>\n',
                         'Сообщение о покупке для режима "Личный кабинет"', '["key_number", "trial_suffix", "action_text", "expiry_formatted", "cabinet_url", "status_icon", "host_flag", "tariff_name", "price_formatted", "tariff_info"]'),
                        
                        ('purchase_success_cabinet_subscription', 'purchase', 'cabinet_subscription',
                         '🎉 <b>Ваш ключ #{key_number}{trial_suffix} {action_text}!</b>\n\n⏳ <b>Он будет действовать до:</b> {expiry_formatted}\n\n⬇️ <b>ВАШ ЛИЧНЫЙ КАБИНЕТ</b> ⬇️\n------------------------------------------------------------------------\n<a href="{cabinet_url}">{cabinet_url}</a>\n------------------------------------------------------------------------\n<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>\n',
                         'Сообщение о покупке для режима "Личный кабинет + Подписка"', '["key_number", "trial_suffix", "action_text", "expiry_formatted", "cabinet_url", "subscription_link", "status_icon", "host_flag", "tariff_name", "price_formatted", "tariff_info"]'),
                        
                        # Шаблоны информации о ключе
                        ('key_info_key', 'key_info', 'key',
                         '<b>🔑 Информация о ключе #{key_number}{trial_suffix}</b><br><br><b>➕ Приобретён:</b> {created_formatted}<br><b>⏳ Действителен до:</b> {expiry_formatted}<br><b>{status_icon} Статус:</b> {status_text}<br><br>⬇️ <b>НИЖЕ ВАШ КЛЮЧ</b> ⬇️<br>------------------------------------------------------------------------<br><code>{connection_string}</code><br>------------------------------------------------------------------------<br><blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>',
                         'Информация о ключе для режима "Ключ"', '["key_number", "trial_suffix", "created_formatted", "expiry_formatted", "status_icon", "status_text", "connection_string", "host_flag", "tariff_name", "price_formatted", "tariff_info", "auto_renewal_status"]'),
                        
                        ('key_info_subscription', 'key_info', 'subscription',
                         '<b>🔑 Информация о ключе #{key_number}{trial_suffix}</b><br><br><b>➕ Приобретён:</b> {created_formatted}<br><b>⏳ Действителен до:</b> {expiry_formatted}<br><b>{status_icon} Статус:</b> {status_text}<br><br>⬇️ <b>ВАША ПОДПИСКА</b> ⬇️<br>------------------------------------------------------------------------<br>{subscription_link}<br>------------------------------------------------------------------------<br><blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>',
                         'Информация о ключе для режима "Подписка"', '["key_number", "trial_suffix", "created_formatted", "expiry_formatted", "status_icon", "status_text", "subscription_link", "host_flag", "tariff_name", "price_formatted", "tariff_info", "auto_renewal_status"]'),
                        
                        ('key_info_both', 'key_info', 'both',
                         '<b>🔑 Информация о ключе #{key_number}{trial_suffix}</b><br><br><b>➕ Приобретён:</b> {created_formatted}<br><b>⏳ Действителен до:</b> {expiry_formatted}<br><b>{status_icon} Статус:</b> {status_text}<br><br>⬇️ <b>НИЖЕ ВАШ КЛЮЧ</b> ⬇️<br>------------------------------------------------------------------------<br><code>{connection_string}</code><br>------------------------------------------------------------------------<br>💡<i>Просто нажмите на ключ один раз, чтобы скопировать</i><br><br>⬇️ <b>ВАША ПОДПИСКА</b> ⬇️<br>------------------------------------------------------------------------<br>{subscription_link}<br>------------------------------------------------------------------------<br><blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>',
                         'Информация о ключе для режима "Ключ + Подписка"', '["key_number", "trial_suffix", "created_formatted", "expiry_formatted", "status_icon", "status_text", "connection_string", "subscription_link", "host_flag", "tariff_name", "price_formatted", "tariff_info", "auto_renewal_status"]'),
                        
                        ('key_info_cabinet', 'key_info', 'cabinet',
                         '<b>🔑 Информация о ключе #{key_number}{trial_suffix}</b><br><br><b>➕ Приобретён:</b> {created_formatted}<br><b>⏳ Действителен до:</b> {expiry_formatted}<br><b>{status_icon} Статус:</b> {status_text}<br><br>⬇️ <b>ВАШ ЛИЧНЫЙ КАБИНЕТ</b> ⬇️<br>------------------------------------------------------------------------<br><a href="{cabinet_url}">{cabinet_url}</a><br>------------------------------------------------------------------------<br><br><blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>',
                         'Информация о ключе для режима "Личный кабинет"', '["key_number", "trial_suffix", "created_formatted", "expiry_formatted", "status_icon", "status_text", "cabinet_url", "host_flag", "tariff_name", "price_formatted", "tariff_info", "auto_renewal_status"]'),
                        
                        ('key_info_cabinet_subscription', 'key_info', 'cabinet_subscription',
                         '<b>🔑 Информация о ключе #{key_number}{trial_suffix}</b><br><br><b>➕ Приобретён:</b> {created_formatted}<br><b>⏳ Действителен до:</b> {expiry_formatted}<br><b>{status_icon} Статус:</b> {status_text}<br><br>⬇️ <b>ВАШ ЛИЧНЫЙ КАБИНЕТ</b> ⬇️<br>------------------------------------------------------------------------<br><a href="{cabinet_url}">{cabinet_url}</a><br>------------------------------------------------------------------------<br><br><blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>',
                         'Информация о ключе для режима "Личный кабинет + Подписка"', '["key_number", "trial_suffix", "created_formatted", "expiry_formatted", "status_icon", "status_text", "cabinet_url", "subscription_link", "host_flag", "tariff_name", "price_formatted", "tariff_info", "auto_renewal_status"]'),
                    ]
                    
                    for template_key, category, provision_mode, template_text, description, variables in default_templates:
                        try:
                            cursor.execute('''
                                INSERT INTO message_templates 
                                (template_key, category, provision_mode, template_text, description, variables, is_active)
                                VALUES (?, ?, ?, ?, ?, ?, 0)
                            ''', (template_key, category, provision_mode, template_text, description, variables))
                        except Exception as e:
                            logging.warning(f"Failed to insert default template {template_key}: {e}")
                    
                    logging.info(" -> Default message templates initialized (inactive by default)")
            else:
                logging.info(" -> message_templates table already exists")
        except Exception as e:
            logging.error(f" -> Failed to create message_templates table: {e}")

        # Миграция: добавляем настройку server_environment
        logging.info("The migration of the setting 'server_environment' ...")
        try:
            # Проверяем существование настройки через прямой SQL запрос
            cursor.execute("SELECT value FROM bot_settings WHERE key = ?", ("server_environment",))
            existing_env = cursor.fetchone()
            if existing_env is None:
                # Создаем настройку со значением по умолчанию "production"
                cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)", ("server_environment", "production"))
                logging.info(" -> The setting 'server_environment' is successfully added with default value 'production'.")
            else:
                logging.debug(" -> The setting 'server_environment' already exists.")
        except Exception as e:
            logging.warning(f" -> Failed to add setting 'server_environment': {e}")

        logging.info("--- The database is successfully completed! ---")
        
        # Коммитим изменения только если мы создали соединение сами
        if should_close_conn:
            conn.commit()

    except sqlite3.Error as e:

        logging.error(f"An error occurred during migration: {e}")
        # Откатываем транзакцию только если мы создали соединение сами
        if should_close_conn:
            try:
                conn.rollback()
            except:
                pass
        raise
    finally:
        # Закрываем соединение только если мы его создали
        if should_close_conn and conn:
            try:
                conn.close()
            except:
                pass



def create_new_transactions_table(cursor: sqlite3.Cursor):

            cursor.execute('''

                CREATE TABLE IF NOT EXISTS transactions (

                    username TEXT,

                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,

                    payment_id TEXT UNIQUE NOT NULL,

                    user_id INTEGER NOT NULL,

                    status TEXT NOT NULL,

                    amount_rub REAL NOT NULL,

                    amount_currency REAL,

                    currency_name TEXT,

                    payment_method TEXT,

                    metadata TEXT,

                    transaction_hash TEXT,

                    payment_link TEXT,

                    yookassa_payment_id TEXT,

                    rrn TEXT,

                    authorization_code TEXT,

                    payment_type TEXT,

                    api_request TEXT,

                    api_response TEXT,

                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                )

            ''')

            

            # Добавляем поле transaction_hash если его нет

            try:

                cursor.execute("ALTER TABLE transactions ADD COLUMN transaction_hash TEXT")

            except sqlite3.OperationalError:

                # Поле уже существует

                pass



def create_host(name: str, url: str, user: str, passwd: str, inbound: int, host_code: str | None = None):

    try:

        with _get_db_connection() as conn:

            cursor = conn.cursor()

            # host_code по умолчанию – slug от host_name (если не передан явно)

            if not host_code or not host_code.strip():
                host_code = (name or '').replace(' ', '').lower()

            cursor.execute(

                "INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",

                (name, url, user, passwd, inbound, host_code)

            )

            conn.commit()

            logging.info(f"Successfully created a new host: {name} with host_code: {host_code}")

    except sqlite3.Error as e:

        logging.error(f"Error creating host '{name}': {e}")



def delete_host(host_name: str):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("DELETE FROM plans WHERE host_name = ?", (host_name,))

            cursor.execute("DELETE FROM xui_hosts WHERE host_name = ?", (host_name,))

            conn.commit()

            logging.info(f"Successfully deleted host '{host_name}' and its plans.")

    except sqlite3.Error as e:

        logging.error(f"Error deleting host '{host_name}': {e}")



def update_host(old_host_name: str, new_host_name: str, url: str, user: str, passwd: str, inbound: int, host_code: str | None = None) -> bool:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            if not host_code or host_code.strip() == '':

                host_code = (new_host_name or '').replace(' ', '').lower()

            cursor.execute(

                "UPDATE xui_hosts SET host_name = ?, host_url = ?, host_username = ?, host_pass = ?, host_inbound_id = ?, host_code = ? WHERE host_name = ?",

                (new_host_name, url, user, passwd, inbound, host_code, old_host_name)

            )

            if old_host_name != new_host_name:

                # Обновляем связанные сущности, ссылающиеся на имя хоста строкой

                cursor.execute(

                    "UPDATE plans SET host_name = ? WHERE host_name = ?",

                    (new_host_name, old_host_name)

                )

                cursor.execute(

                    "UPDATE vpn_keys SET host_name = ? WHERE host_name = ?",

                    (new_host_name, old_host_name)

                )

            conn.commit()

            logging.info(f"Successfully updated host '{old_host_name}' -> '{new_host_name}'.")

            return True

    except sqlite3.Error as e:

        logging.error(f"Error updating host '{old_host_name}': {e}")

        return False



def get_host(host_name: str) -> dict | None:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            sanitized_name = host_name.strip() if isinstance(host_name, str) else ""

            if not sanitized_name:
                return None

            cursor.execute("SELECT * FROM xui_hosts WHERE host_name = ?", (sanitized_name,))

            result = cursor.fetchone()

            if result:
                return dict(result)

            normalized_target = _normalize_host_identifier(sanitized_name)
            if not normalized_target:
                return None

            cursor.execute("SELECT * FROM xui_hosts")
            for row in cursor.fetchall():
                row_dict = dict(row)
                normalized_host_name = _normalize_host_identifier(row_dict.get("host_name"))
                normalized_host_code = _normalize_host_identifier(row_dict.get("host_code"))

                if normalized_target and (
                    normalized_target == normalized_host_name or
                    (normalized_host_code and normalized_target == normalized_host_code)
                ):
                    logging.warning(
                        "Fallback match for host '%s' resolved to '%s' (code: %s).",
                        host_name,
                        row_dict.get("host_name"),
                        row_dict.get("host_code")
                    )
                    return row_dict

            return None

    except sqlite3.Error as e:

        logging.error(f"Error getting host '{host_name}': {e}")

        return None



def get_host_by_code(host_code: str) -> dict | None:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute("SELECT * FROM xui_hosts WHERE host_code = ?", (host_code,))

            result = cursor.fetchone()

            return dict(result) if result else None

    except sqlite3.Error as e:

        logging.error(f"Error getting host by code '{host_code}': {e}")

        return None



def get_all_hosts() -> list[dict]:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute("SELECT * FROM xui_hosts")

            hosts = cursor.fetchall()

            return [dict(row) for row in hosts]

    except sqlite3.Error as e:

        logging.error(f"Error getting list of all hosts: {e}")

        return []



def get_all_keys() -> list[dict]:

    try:
        with _get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vpn_keys")
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to get all keys: {e}")
        return []



def get_setting(key: str) -> str | None:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))

            result = cursor.fetchone()

            return result[0] if result else None

    except sqlite3.Error as e:

        logging.error(f"Failed to get setting '{key}': {e}")

        return None

def get_server_environment() -> str:
    """
    Получает текущее окружение сервера из настроек.
    
    Returns:
        "development" или "production" (по умолчанию "production")
    """
    env = get_setting("server_environment")
    if env in ("development", "production"):
        return env
    # По умолчанию production для безопасности
    return "production"

def is_production_server() -> bool:
    """
    Проверяет, запущен ли сервер в production окружении.
    
    Returns:
        True если окружение "production", False если "development"
    """
    return get_server_environment() == "production"

def is_development_server() -> bool:
    """
    Проверяет, запущен ли сервер в development окружении.
    
    Returns:
        True если окружение "development", False если "production"
    """
    return get_server_environment() == "development"

def get_global_domain() -> str | None:
    """Получить глобальный домен с fallback на старый параметр domain"""
    global_domain = get_setting("global_domain")
    # Проверяем, что значение не None и не пустая строка
    if global_domain and global_domain.strip():
        return global_domain
    
    # Fallback на старый параметр domain
    domain = get_setting("domain")
    # Проверяем, что значение не None и не пустая строка
    if domain and domain.strip():
        if not domain.startswith(('http://', 'https://')):
            domain = f"https://{domain}"
        return domain
    
    # Fallback зависит от окружения
    if is_development_server():
        return "https://localhost:8443"
    else:
        # В production возвращаем None если домен не настроен
        return None

def get_all_settings() -> dict:

    settings = {}

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute("SELECT key, value FROM bot_settings")

            rows = cursor.fetchall()

            for row in rows:

                settings[row['key']] = row['value']

    except sqlite3.Error as e:

        logging.error(f"Failed to get all settings: {e}")

    return settings



def update_setting(key: str, value: str):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()
            
            # Логируем что именно сохраняем
            logging.info(f"[DATABASE] update_setting called: key='{key}', value='{value}' (type: {type(value).__name__})")

            cursor.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)", (key, value))

            conn.commit()
            
            # Проверяем что действительно сохранилось
            cursor.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
            result = cursor.fetchone()
            saved_value = result[0] if result else None
            logging.info(f"[DATABASE] Setting '{key}' updated. Saved value in DB: '{saved_value}'")

    except sqlite3.Error as e:

        logging.error(f"Failed to update setting '{key}': {e}")


# ============================================================================
# Timezone Support Functions
# ============================================================================

def is_timezone_feature_enabled() -> bool:
    """
    Проверяет, включена ли функциональность timezone.
    
    Returns:
        True если feature_timezone_enabled = '1', иначе False
    """
    try:
        value = get_setting('feature_timezone_enabled')
        return value == '1' if value is not None else False
    except Exception as e:
        logger.error(f"Error checking timezone feature flag: {e}")
        return False


def get_admin_timezone() -> str:
    """
    Получает timezone администратора из настроек.
    
    Returns:
        Название timezone (например, 'Europe/Moscow').
        По умолчанию 'Europe/Moscow' при ошибке.
    """
    try:
        timezone = get_setting('admin_timezone')
        if timezone:
            return timezone
        logger.warning("admin_timezone not found in settings, using default 'Europe/Moscow'")
        return 'Europe/Moscow'
    except Exception as e:
        logger.error(f"Error getting admin timezone: {e}")
        return 'Europe/Moscow'


def set_admin_timezone(timezone: str) -> bool:
    """
    Устанавливает timezone администратора.
    
    Args:
        timezone: Название timezone (например, 'Europe/Moscow')
        
    Returns:
        True если успешно, иначе False
    """
    try:
        # Валидация timezone (опциональная в Windows)
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(timezone)
        except Exception as e:
            # В Windows может не быть timezone данных, это нормально для разработки
            logger.warning(f"Could not validate timezone '{timezone}': {e} (this is OK in Windows dev environment)")
        
        update_setting('admin_timezone', timezone)
        logger.info(f"Admin timezone updated to: {timezone}")
        return True
    except Exception as e:
        logger.error(f"Error setting admin timezone: {e}")
        return False


def get_user_timezone(user_id: int) -> str:
    """
    Получает timezone пользователя из таблицы users.
    
    Args:
        user_id: Telegram ID пользователя
        
    Returns:
        Название timezone пользователя.
        Fallback на admin_timezone при отсутствии/ошибке.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timezone FROM users WHERE telegram_id = ?", (user_id,))
            result = cursor.fetchone()
            
            if result and result[0]:
                return result[0]
            
            # Fallback на admin timezone
            return get_admin_timezone()
    except Exception as e:
        logger.error(f"Error getting user timezone for {user_id}: {e}")
        return get_admin_timezone()


def set_user_timezone(user_id: int, timezone: str) -> bool:
    """
    Устанавливает timezone для пользователя.
    
    Args:
        user_id: Telegram ID пользователя
        timezone: Название timezone (например, 'Europe/Moscow')
        
    Returns:
        True если успешно, иначе False
    """
    try:
        # Валидация timezone (опциональная в Windows)
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(timezone)
        except Exception as e:
            # В Windows может не быть timezone данных, это нормально для разработки
            logger.warning(f"Could not validate timezone '{timezone}': {e} (this is OK in Windows dev environment)")
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET timezone = ? WHERE telegram_id = ?",
                (timezone, user_id)
            )
            conn.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"User {user_id} timezone updated to: {timezone}")
                return True
            else:
                logger.warning(f"User {user_id} not found when setting timezone")
                return False
    except Exception as e:
        logger.error(f"Error setting user timezone for {user_id}: {e}")
        return False


# ============================================================================
# End Timezone Support Functions
# ============================================================================

def get_backup_setting(key: str) -> str | None:
    """Получить настройку бекапа"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM backup_settings WHERE key = ?", (key,))
            result = cursor.fetchone()
            return result[0] if result else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get backup setting '{key}': {e}")
        return None


def update_backup_setting(key: str, value: str):
    """Обновить настройку бекапа"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO backup_settings (key, value, updated_at) 
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, value))
            conn.commit()
            logging.info(f"Backup setting '{key}' updated.")
    except sqlite3.Error as e:
        logging.error(f"Failed to update backup setting '{key}': {e}")


def get_all_backup_settings() -> dict:
    """Получить все настройки бекапов"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM backup_settings")
            rows = cursor.fetchall()
            return {row[0]: row[1] for row in rows}
    except sqlite3.Error as e:
        logging.error(f"Failed to get backup settings: {e}")
        return {}


def migrate_backup_settings(conn: sqlite3.Connection):
    """Миграция настроек бекапов из bot_settings в backup_settings
    
    Args:
        conn: Существующее соединение с базой данных из run_migration()
    """
    try:
        cursor = conn.cursor()
        
        # PRAGMA busy_timeout уже установлен в run_migration()
        
        # Список настроек бекапов для миграции
        backup_keys = [
            'backup_enabled', 'backup_interval_hours', 'backup_retention_days',
            'backup_compression', 'backup_verify'
        ]
        
        # Получаем существующие настройки из bot_settings
        for key in backup_keys:
            cursor.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
            result = cursor.fetchone()
            
            if result:
                # Переносим в backup_settings
                cursor.execute("""
                    INSERT OR IGNORE INTO backup_settings (key, value, created_at, updated_at) 
                    VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (key, result[0]))
                logging.info(f"Migrated backup setting '{key}' from bot_settings to backup_settings")
        
        # Устанавливаем значения по умолчанию для отсутствующих настроек
        default_backup_settings = {
            'backup_enabled': 'true',
            'backup_interval_hours': '24',
            'backup_retention_days': '30',
            'backup_compression': 'true',
            'backup_verify': 'true'
        }
        
        for key, default_value in default_backup_settings.items():
            cursor.execute("""
                INSERT OR IGNORE INTO backup_settings (key, value, created_at, updated_at) 
                VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (key, default_value))
        
        # conn.commit() будет выполнен в run_migration() для атомарности всех миграций
        logging.info("Backup settings migration completed successfully")
        
    except sqlite3.Error as e:
        logging.error(f"Failed to migrate backup settings: {e}")
        raise  # Пробрасываем исключение для отката транзакции в run_migration()



def create_plan(host_name: str, plan_name: str, months: int, price: float, days: int = 0, traffic_gb: float = 0.0, hours: int = 0, key_provision_mode: str = 'key', display_mode: str = 'all', display_mode_groups: list[int] | None = None):
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()

            # Проверяем существование колонок через PRAGMA table_info (безопасный метод, только чтение)
            # Если колонки отсутствуют - это означает проблему с миграцией, логируем предупреждение
            cursor.execute("PRAGMA table_info(plans)")
            plans_columns = [row[1] for row in cursor.fetchall()]

            missing_columns = []
            if 'hours' not in plans_columns:
                missing_columns.append('hours')
            if 'key_provision_mode' not in plans_columns:
                missing_columns.append('key_provision_mode')
            if 'display_mode' not in plans_columns:
                missing_columns.append('display_mode')
            if 'display_mode_groups' not in plans_columns:
                missing_columns.append('display_mode_groups')

            if missing_columns:
                logger.warning(
                    f"Missing columns in plans table: {', '.join(missing_columns)}. "
                    f"Database migration may not have been executed. Please run migration."
                )

            # Сериализуем display_mode_groups в JSON
            serialized_display_mode_groups = None
            if display_mode_groups is not None:
                if isinstance(display_mode_groups, list):
                    if len(display_mode_groups) > 0:
                        serialized_display_mode_groups = json.dumps(display_mode_groups, ensure_ascii=False)
                elif display_mode_groups:  # если не None и не список, пробуем преобразовать
                    serialized_display_mode_groups = json.dumps([display_mode_groups], ensure_ascii=False)

            cursor.execute(
                "INSERT INTO plans (host_name, plan_name, months, price, days, traffic_gb, hours, key_provision_mode, display_mode, display_mode_groups) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (host_name, plan_name, months, price, days, traffic_gb, hours, key_provision_mode, display_mode, serialized_display_mode_groups)
            )

            conn.commit()
            
            plan_id = cursor.lastrowid
            logging.info(f"Created new plan '{plan_name}' for host '{host_name}' with provision mode '{key_provision_mode}' and display mode '{display_mode}' (plan_id: {plan_id}).")
            
            return plan_id

    except sqlite3.Error as e:
        logging.error(f"Failed to create plan for host '{host_name}': {e}")
        raise



def get_plans_for_host(host_name: str) -> list[dict]:

    try:

        with _get_db_connection() as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            # Проверяем существование колонок через PRAGMA table_info (безопасный метод, только чтение)
            # Если колонки отсутствуют - это означает проблему с миграцией, логируем предупреждение
            cursor.execute("PRAGMA table_info(plans)")
            plans_columns = [row[1] for row in cursor.fetchall()]

            missing_columns = []
            if 'hours' not in plans_columns:
                missing_columns.append('hours')
            if 'key_provision_mode' not in plans_columns:
                missing_columns.append('key_provision_mode')
            if 'display_mode' not in plans_columns:
                missing_columns.append('display_mode')
            if 'display_mode_groups' not in plans_columns:
                missing_columns.append('display_mode_groups')

            if missing_columns:
                logger.warning(
                    f"Missing columns in plans table: {', '.join(missing_columns)}. "
                    f"Database migration may not have been executed. Please run migration."
                )

            cursor.execute("SELECT * FROM plans WHERE host_name = ? ORDER BY months, days, hours", (host_name,))

            plans = cursor.fetchall()
            
            result = []
            for plan in plans:
                plan_dict = dict(plan)
                # Десериализуем display_mode_groups из JSON
                if plan_dict.get('display_mode_groups'):
                    try:
                        plan_dict['display_mode_groups'] = json.loads(plan_dict['display_mode_groups'])
                    except (json.JSONDecodeError, TypeError):
                        plan_dict['display_mode_groups'] = None
                else:
                    plan_dict['display_mode_groups'] = None
                result.append(plan_dict)
            
            return result

    except sqlite3.Error as e:

        logging.error(f"Failed to get plans for host '{host_name}': {e}")

        return []



def get_plan_by_id(plan_id: int) -> dict | None:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,))

            plan = cursor.fetchone()
            
            if not plan:
                return None

            plan_dict = dict(plan)
            
            # Десериализуем display_mode_groups из JSON
            if plan_dict.get('display_mode_groups'):
                try:
                    plan_dict['display_mode_groups'] = json.loads(plan_dict['display_mode_groups'])
                except (json.JSONDecodeError, TypeError):
                    plan_dict['display_mode_groups'] = None
            else:
                plan_dict['display_mode_groups'] = None

            return plan_dict

    except sqlite3.Error as e:

        logging.error(f"Failed to get plan by id '{plan_id}': {e}")

        return None



def delete_plan(plan_id: int):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("DELETE FROM plans WHERE plan_id = ?", (plan_id,))

            conn.commit()

            logging.info(f"Deleted plan with id {plan_id}.")

    except sqlite3.Error as e:

        logging.error(f"Failed to delete plan with id {plan_id}: {e}")



def update_plan(plan_id: int, plan_name: str, months: int, days: int, price: float, traffic_gb: float, hours: int = 0, key_provision_mode: str = 'key', display_mode: str = 'all', display_mode_groups: list[int] | None = None) -> bool:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            # Проверяем существование колонок через PRAGMA table_info (безопасный метод, только чтение)
            # Если колонки отсутствуют - это означает проблему с миграцией, логируем предупреждение
            cursor.execute("PRAGMA table_info(plans)")
            plans_columns = [row[1] for row in cursor.fetchall()]

            missing_columns = []
            if 'hours' not in plans_columns:
                missing_columns.append('hours')
            if 'key_provision_mode' not in plans_columns:
                missing_columns.append('key_provision_mode')
            if 'display_mode' not in plans_columns:
                missing_columns.append('display_mode')
            if 'display_mode_groups' not in plans_columns:
                missing_columns.append('display_mode_groups')

            if missing_columns:
                logger.warning(
                    f"Missing columns in plans table: {', '.join(missing_columns)}. "
                    f"Database migration may not have been executed. Please run migration."
                )

            # Сериализуем display_mode_groups в JSON
            serialized_display_mode_groups = None
            if display_mode_groups is not None:
                if isinstance(display_mode_groups, list):
                    if len(display_mode_groups) > 0:
                        serialized_display_mode_groups = json.dumps(display_mode_groups, ensure_ascii=False)
                elif display_mode_groups:  # если не None и не список, пробуем преобразовать
                    serialized_display_mode_groups = json.dumps([display_mode_groups], ensure_ascii=False)

            cursor.execute(

                "UPDATE plans SET plan_name = ?, months = ?, days = ?, hours = ?, price = ?, traffic_gb = ?, key_provision_mode = ?, display_mode = ?, display_mode_groups = ? WHERE plan_id = ?",

                (plan_name, months, days, hours, price, traffic_gb, key_provision_mode, display_mode, serialized_display_mode_groups, plan_id)

            )

            conn.commit()

            logging.info(f"Updated plan id={plan_id} with provision mode '{key_provision_mode}' and display mode '{display_mode}'.")

            return True

    except sqlite3.Error as e:

        logging.error(f"Failed to update plan id {plan_id}: {e}")

        return False





def has_user_used_plan(user_id: int, plan_id: int) -> bool:
    """
    Проверяет, использовал ли пользователь данный тариф ранее.
    Проверяет наличие оплаченных транзакций (status='paid') с данным plan_id в metadata.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Проверяем транзакции с status='paid' и plan_id в metadata
            # Ищем как число с пробелом: "plan_id": 43 (может быть в конце или в середине JSON)
            cursor.execute(
                "SELECT COUNT(*) FROM transactions WHERE user_id = ? AND status = 'paid' AND (metadata LIKE ? OR metadata LIKE ?)",
                (user_id, f'%"plan_id": {plan_id},%', f'%"plan_id": {plan_id}}}%')
            )
            
            count = cursor.fetchone()[0]
            return count > 0
            
    except sqlite3.Error as e:
        logging.error(f"Failed to check if user {user_id} used plan {plan_id}: {e}")
        return False


def get_user_used_plans_batch(user_id: int) -> set[int]:
    """
    Получает все plan_id из оплаченных транзакций пользователя одним запросом.
    Оптимизированная версия для устранения N+1 проблемы.
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Множество plan_id, которые пользователь использовал ранее
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Получаем все metadata из оплаченных транзакций пользователя
            cursor.execute(
                "SELECT metadata FROM transactions WHERE user_id = ? AND status = 'paid' AND metadata IS NOT NULL",
                (user_id,)
            )
            
            rows = cursor.fetchall()
            used_plan_ids = set()
            
            # Парсим JSON из metadata и извлекаем plan_id
            for (metadata_str,) in rows:
                if not metadata_str:
                    continue
                    
                try:
                    metadata = json.loads(metadata_str)
                    plan_id = metadata.get('plan_id')
                    if plan_id is not None:
                        # Преобразуем в int для консистентности
                        try:
                            used_plan_ids.add(int(plan_id))
                        except (ValueError, TypeError):
                            # Если plan_id не число, пропускаем
                            continue
                except (json.JSONDecodeError, TypeError):
                    # Если metadata не валидный JSON, пропускаем
                    continue
            
            return used_plan_ids
            
    except sqlite3.Error as e:
        logging.error(f"Failed to get user used plans batch for user {user_id}: {e}")
        # Возвращаем пустое множество в случае ошибки (безопасный fallback)
        return set()


def filter_plans_by_display_mode(plans: list[dict], user_id: int) -> list[dict]:
    """
    Фильтрует список тарифов по режиму отображения для конкретного пользователя.
    
    Режимы отображения:
    - 'all': отображать всем (по умолчанию)
    - 'hidden_all': скрыть у всех пользователей
    - 'hidden_new': скрыть у новых пользователей (кто ни разу не использовал этот тариф)
    - 'hidden_old': скрыть у старых пользователей (кто уже использовал этот тариф ранее)
    
    Режим отображения (группы):
    - Если не указан или пуст - показывать всем группам
    - Если указан список group_id - показывать только пользователям из этих групп
    
    Приоритет: display_mode имеет приоритет над display_mode_groups.
    Если display_mode = 'hidden_all', тариф скрыт независимо от display_mode_groups.
    """
    if not plans:
        return []
    
    # Получаем информацию о группе пользователя
    user_group_info = get_user_group_info(user_id)
    user_group_id = user_group_info.get('group_id') if user_group_info else None
    
    # Оптимизация: получаем все использованные планы пользователя одним запросом
    # Это устраняет N+1 проблему при проверке display_mode 'hidden_new' и 'hidden_old'
    used_plan_ids = get_user_used_plans_batch(user_id)
    
    filtered_plans = []
    
    for plan in plans:
        display_mode = plan.get('display_mode', 'all')
        plan_id = plan.get('plan_id')
        display_mode_groups = plan.get('display_mode_groups')
        
        # ПРИОРИТЕТ 1: Если режим 'hidden_all' - скрываем от всех независимо от групп
        if display_mode == 'hidden_all':
            continue
        
        # ПРИОРИТЕТ 2: Проверяем display_mode (но не hidden_all, так как уже обработали выше)
        if display_mode == 'all':
            # Режим 'all' - переходим к проверке групп
            pass
        else:
            # Для режимов 'hidden_new' и 'hidden_old' проверяем историю использования
            if plan_id:
                # Используем оптимизированную проверку через set (O(1) вместо запроса к БД)
                has_used = plan_id in used_plan_ids
                
                # Если 'hidden_new' - скрываем от тех, кто НЕ использовал (новые)
                if display_mode == 'hidden_new' and not has_used:
                    continue
                
                # Если 'hidden_old' - скрываем от тех, кто использовал (старые)
                if display_mode == 'hidden_old' and has_used:
                    continue
        
        # ПРИОРИТЕТ 3: Проверяем display_mode_groups
        # Если display_mode_groups не указан или пуст - показывать всем
        if display_mode_groups:
            # Если указан список групп, проверяем принадлежность пользователя
            if isinstance(display_mode_groups, list) and len(display_mode_groups) > 0:
                # Конвертируем все в int для сравнения
                group_ids = [int(gid) for gid in display_mode_groups if gid is not None]
                # Если пользователь не в одной из указанных групп - скрываем тариф
                if user_group_id is None or user_group_id not in group_ids:
                    continue
        
        filtered_plans.append(plan)
    
    return filtered_plans


def _normalize_bot_value(bot: str) -> str:
    """Нормализует и валидирует значение бота.
    
    Args:
        bot: Название бота (должно быть 'shop' или 'test_bot' для тестов)
        
    Returns:
        Нормализованное значение бота в нижнем регистре
        
    Raises:
        ValueError: Если бот не 'shop' или 'test_bot'
    """
    normalized = (bot or "").strip().lower()
    
    # Валидация: поддерживаем 'shop' бота и 'test_bot' для тестов
    if normalized and normalized not in ('shop', 'test_bot'):
        raise ValueError(f"Неподдерживаемый тип бота: '{bot}'. Допустимые значения: 'shop', 'test_bot'")
    
    return normalized



def _serialize_vpn_plan_id(vpn_plan_id) -> str | None:
    """Сериализует vpn_plan_id в JSON строку для хранения в БД"""
    if vpn_plan_id is None:
        return None
    
    if isinstance(vpn_plan_id, (int, str)):
        return str(vpn_plan_id)
    
    if isinstance(vpn_plan_id, (list, tuple)):
        return json.dumps(vpn_plan_id, ensure_ascii=False)
    
    return str(vpn_plan_id)


def _deserialize_vpn_plan_id(vpn_plan_id_str: str | None) -> int | list[int] | None:
    """Десериализует vpn_plan_id из JSON строки"""
    if not vpn_plan_id_str:
        return None
    
    try:
        # Пытаемся распарсить как JSON массив
        parsed = json.loads(vpn_plan_id_str)
        if isinstance(parsed, list):
            return [int(x) for x in parsed if str(x).isdigit()]
        elif isinstance(parsed, (int, str)) and str(parsed).isdigit():
            return int(parsed)
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    
    # Если не JSON, пытаемся как одиночное число
    try:
        if str(vpn_plan_id_str).isdigit():
            return int(vpn_plan_id_str)
    except (ValueError, TypeError):
        pass
    
    return None


def create_promo_code(
    code: str,
    bot: str,
    vpn_plan_id: int | str | list[int] | None,
    tariff_code: str | list[str] | None,
    discount_amount: float,
    discount_percent: float,
    discount_bonus: float,
    usage_limit_per_bot: int = 1,
    is_active: bool = True,
    burn_after_value: int | None = None,
    burn_after_unit: str | None = None,
    valid_until: str | None = None,
    target_group_ids: list[int] | None = None,
    bot_username: str | None = None,
) -> int:

    code_value = (code or "").strip().upper()

    if not code_value:

        raise ValueError("Promo code value cannot be empty")

    bot_value = _normalize_bot_value(bot)

    if not bot_value:

        raise ValueError("Bot value cannot be empty")

    # Валидация vpn_plan_id
    if vpn_plan_id is not None:
        if isinstance(vpn_plan_id, list):
            if len(vpn_plan_id) == 0:
                # Пустой список - это нормально, означает что промокод не привязан к планам
                vpn_plan_id = None
            elif not all(isinstance(x, (int, str)) and str(x).isdigit() for x in vpn_plan_id):
                raise ValueError("Все элементы vpn_plan_id должны быть числами")
        elif isinstance(vpn_plan_id, str):
            # Проверяем, является ли это JSON строкой
            try:
                import json
                parsed = json.loads(vpn_plan_id)
                if isinstance(parsed, list):
                    if len(parsed) == 0:
                        # Пустой JSON массив - это нормально
                        vpn_plan_id = None
                    elif not all(isinstance(x, (int, str)) and str(x).isdigit() for x in parsed):
                        raise ValueError("Все элементы vpn_plan_id в JSON должны быть числами")
                    else:
                        # Валидный JSON массив - оставляем как есть
                        pass
                else:
                    raise ValueError("JSON vpn_plan_id должен быть массивом")
            except (json.JSONDecodeError, ValueError):
                # Если это не JSON, проверяем как обычное число
                if not str(vpn_plan_id).isdigit():
                    raise ValueError("vpn_plan_id должен быть числом, списком чисел или JSON массивом чисел")
        elif not (isinstance(vpn_plan_id, (int, str)) and str(vpn_plan_id).isdigit()):
            raise ValueError("vpn_plan_id должен быть числом, списком чисел или JSON массивом чисел")

    # Валидация tariff_code
    if tariff_code is not None:
        if isinstance(tariff_code, list):
            if not all(isinstance(x, str) and x.strip() for x in tariff_code):
                raise ValueError("Все элементы tariff_code должны быть непустыми строками")
        elif not (isinstance(tariff_code, str) and tariff_code.strip()):
            raise ValueError("tariff_code должен быть строкой или списком строк")

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            # Сериализуем данные для хранения
            serialized_vpn_plan_id = _serialize_vpn_plan_id(vpn_plan_id)
            serialized_tariff_code = None
            if tariff_code is not None:
                if isinstance(tariff_code, list):
                    serialized_tariff_code = json.dumps(tariff_code, ensure_ascii=False)
                else:
                    serialized_tariff_code = tariff_code.strip()

            # Сериализуем target_group_ids
            serialized_target_group_ids = None
            if target_group_ids is not None:
                serialized_target_group_ids = json.dumps(target_group_ids, ensure_ascii=False)

            cursor.execute(

                '''
                INSERT INTO promo_codes (
                    code, bot, vpn_plan_id, tariff_code,
                    discount_amount, discount_percent, discount_bonus,
                    usage_limit_per_bot, is_active, created_at, updated_at,
                    burn_after_value, burn_after_unit, valid_until, target_group_ids, bot_username
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?)
                ''',

                (
                    code_value,
                    bot_value,
                    serialized_vpn_plan_id,
                    serialized_tariff_code,
                    float(discount_amount or 0),
                    float(discount_percent or 0),
                    float(discount_bonus or 0),
                    max(int(usage_limit_per_bot or 1), 1),
                    1 if is_active else 0,
                    burn_after_value,
                    burn_after_unit,
                    valid_until,
                    serialized_target_group_ids,
                    bot_username,
                ),

            )

            conn.commit()

            logging.info(f"Created promo code '{code_value}' with vpn_plan_id={vpn_plan_id}, tariff_code={tariff_code}")
            logging.info(f"Promo code creation details: code='{code_value}', bot='{bot_value}', discount_amount={discount_amount}, discount_percent={discount_percent}, discount_bonus={discount_bonus}, usage_limit={usage_limit_per_bot}, active={is_active}")

            return cursor.lastrowid

    except sqlite3.IntegrityError as e:

        logging.warning(f"Failed to create promo code '{code_value}': {e}")

        raise ValueError("Промокод с таким кодом уже существует") from e

    except sqlite3.Error as e:

        logging.error(f"Database error while creating promo code '{code_value}': {e}")

        raise RuntimeError("Ошибка базы данных при создании промокода") from e



def update_promo_code(
    promo_id: int,
    code: str,
    bot: str,
    vpn_plan_id: int | str | list[int] | None,
    tariff_code: str | list[str] | None,
    discount_amount: float,
    discount_percent: float,
    discount_bonus: float,
    usage_limit_per_bot: int = 1,
    is_active: bool = True,
    burn_after_value: int | None = None,
    burn_after_unit: str | None = None,
    valid_until: str | None = None,
    target_group_ids: list[int] | None = None,
    bot_username: str | None = None,
) -> bool:

    code_value = (code or "").strip().upper()

    if not code_value:

        raise ValueError("Promo code value cannot be empty")

    bot_value = _normalize_bot_value(bot)

    if not bot_value:

        raise ValueError("Bot value cannot be empty")

    # Валидация vpn_plan_id
    if vpn_plan_id is not None:
        if isinstance(vpn_plan_id, list):
            if len(vpn_plan_id) == 0:
                # Пустой список - это нормально, означает что промокод не привязан к планам
                vpn_plan_id = None
            elif not all(isinstance(x, (int, str)) and str(x).isdigit() for x in vpn_plan_id):
                raise ValueError("Все элементы vpn_plan_id должны быть числами")
        elif isinstance(vpn_plan_id, str):
            # Проверяем, является ли это JSON строкой
            try:
                import json
                parsed = json.loads(vpn_plan_id)
                if isinstance(parsed, list):
                    if len(parsed) == 0:
                        # Пустой JSON массив - это нормально
                        vpn_plan_id = None
                    elif not all(isinstance(x, (int, str)) and str(x).isdigit() for x in parsed):
                        raise ValueError("Все элементы vpn_plan_id в JSON должны быть числами")
                    else:
                        # Валидный JSON массив - оставляем как есть
                        pass
                else:
                    raise ValueError("JSON vpn_plan_id должен быть массивом")
            except (json.JSONDecodeError, ValueError):
                # Если это не JSON, проверяем как обычное число
                if not str(vpn_plan_id).isdigit():
                    raise ValueError("vpn_plan_id должен быть числом, списком чисел или JSON массивом чисел")
        elif not (isinstance(vpn_plan_id, (int, str)) and str(vpn_plan_id).isdigit()):
            raise ValueError("vpn_plan_id должен быть числом, списком чисел или JSON массивом чисел")

    # Валидация tariff_code
    if tariff_code is not None:
        if isinstance(tariff_code, list):
            if len(tariff_code) == 0:
                # Пустой список - это нормально
                tariff_code = None
            elif not all(isinstance(x, str) and x.strip() for x in tariff_code):
                raise ValueError("Все элементы tariff_code должны быть непустыми строками")
        elif not (isinstance(tariff_code, str) and tariff_code.strip()):
            raise ValueError("tariff_code должен быть строкой или списком строк")

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            # Сериализуем данные для хранения
            serialized_vpn_plan_id = _serialize_vpn_plan_id(vpn_plan_id)
            serialized_tariff_code = None
            if tariff_code is not None:
                if isinstance(tariff_code, list):
                    serialized_tariff_code = json.dumps(tariff_code, ensure_ascii=False)
                else:
                    serialized_tariff_code = tariff_code.strip()

            # Сериализуем target_group_ids
            serialized_target_group_ids = None
            if target_group_ids is not None:
                serialized_target_group_ids = json.dumps(target_group_ids, ensure_ascii=False)

            cursor.execute(

                '''
                UPDATE promo_codes
                SET code = ?, bot = ?, vpn_plan_id = ?, tariff_code = ?,
                    discount_amount = ?, discount_percent = ?, discount_bonus = ?,
                    usage_limit_per_bot = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP,
                    burn_after_value = ?, burn_after_unit = ?, valid_until = ?, target_group_ids = ?, bot_username = ?
                WHERE promo_id = ?
                ''',

                (
                    code_value,
                    bot_value,
                    serialized_vpn_plan_id,
                    serialized_tariff_code,
                    float(discount_amount or 0),
                    float(discount_percent or 0),
                    float(discount_bonus or 0),
                    max(int(usage_limit_per_bot or 1), 1),
                    1 if is_active else 0,
                    burn_after_value,
                    burn_after_unit,
                    valid_until,
                    serialized_target_group_ids,
                    bot_username,
                    promo_id,
                ),

            )

            conn.commit()

            if cursor.rowcount > 0:
                logging.info(f"Updated promo code id={promo_id} with vpn_plan_id={vpn_plan_id}, tariff_code={tariff_code}")
                logging.info(f"Promo code update details: id={promo_id}, code='{code_value}', bot='{bot_value}', discount_amount={discount_amount}, discount_percent={discount_percent}, discount_bonus={discount_bonus}, usage_limit={usage_limit_per_bot}, active={is_active}")

            return cursor.rowcount > 0

    except sqlite3.IntegrityError as e:

        logging.warning(f"Failed to update promo code {promo_id}: {e}")

        raise ValueError("Промокод с таким кодом уже существует") from e

    except sqlite3.Error as e:

        logging.error(f"Database error while updating promo code {promo_id}: {e}")

        raise RuntimeError("Ошибка базы данных при обновлении промокода") from e


def get_promo_usage_id(promo_id: int, user_id: int, bot: str) -> int | None:
    """Получить usage_id для последней записи использования промокода со статусом 'applied'"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT usage_id FROM promo_code_usage 
                WHERE promo_id = ? AND user_id = ? AND bot = ? AND status = 'applied'
                ORDER BY used_at DESC LIMIT 1
            ''', (promo_id, user_id, bot))
            result = cursor.fetchone()
            return result[0] if result else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get promo usage id: {e}")
        return None


def update_promo_usage_status(usage_id: int, plan_id: int | None = None) -> bool:
    """Обновить статус использования промокода с 'applied' на 'used'"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Устанавливаем режим журналирования
            cursor.execute("PRAGMA journal_mode=DELETE")
            
            # Начинаем транзакцию с блокировкой
            cursor.execute("BEGIN IMMEDIATE")
            
            try:
                # Обновляем статус и plan_id
                cursor.execute('''
                    UPDATE promo_code_usage 
                    SET status = 'used', plan_id = ?, used_at = CURRENT_TIMESTAMP
                    WHERE usage_id = ? AND status = 'applied'
                ''', (plan_id, usage_id))
                
                if cursor.rowcount == 0:
                    cursor.execute("ROLLBACK")
                    logging.warning(f"Failed to update promo usage status for usage_id {usage_id}")
                    return False
                
                cursor.execute("COMMIT")
                logging.info(f"Updated promo usage {usage_id} to 'used' status with plan_id {plan_id}")
                return True
                
            except sqlite3.Error as e:
                cursor.execute("ROLLBACK")
                logging.error(f"Database error updating promo usage status: {e}")
                return False
                
    except sqlite3.Error as e:
        logging.error(f"Failed to update promo usage status: {e}")
        return False


def can_delete_promo_code(promo_id: int) -> tuple[bool, int]:
    """
    Проверяет, можно ли удалить промокод.
    Возвращает (можно_удалить, количество_использований)
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM promo_code_usage WHERE promo_id = ?', (promo_id,))
            usage_count = cursor.fetchone()[0]
            return usage_count == 0, usage_count
    except sqlite3.Error as e:
        logging.error(f"Failed to check promo code usage for {promo_id}: {e}")
        # Если повреждение структуры, попробуем мягкое восстановление и одну повторную попытку
        if isinstance(e, sqlite3.DatabaseError) and 'malformed' in str(e).lower():
            logging.warning("Detected SQLite corruption symptoms on can_delete_promo_code; attempting REINDEX/ANALYZE/VACUUM and retry once")
            if _repair_database_indexes():
                try:
                    with sqlite3.connect(DB_FILE) as conn:
                        cursor = conn.cursor()
                        cursor.execute('SELECT COUNT(*) FROM promo_code_usage WHERE promo_id = ?', (promo_id,))
                        usage_count = cursor.fetchone()[0]
                        return usage_count == 0, usage_count
                except sqlite3.Error as e2:
                    logging.error(f"Retry failed for can_delete_promo_code after repair: {e2}")
        return False, 0


def delete_promo_code(promo_id: int) -> bool:

    def _delete_once() -> bool:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Проверяем, использовался ли промокод
            cursor.execute('SELECT COUNT(*) FROM promo_code_usage WHERE promo_id = ?', (promo_id,))
            usage_count = cursor.fetchone()[0]
            if usage_count > 0:
                logging.warning(f"Cannot delete promo code {promo_id}: it has been used {usage_count} times")
                return False
            # Получаем информацию о промокоде перед удалением для логирования
            cursor.execute('SELECT code, bot FROM promo_codes WHERE promo_id = ?', (promo_id,))
            promo_info = cursor.fetchone()
            cursor.execute('DELETE FROM promo_codes WHERE promo_id = ?', (promo_id,))
            deleted = cursor.rowcount
            conn.commit()
            if deleted > 0 and promo_info:
                logging.info(f"Deleted promo code: id={promo_id}, code='{promo_info[0]}', bot='{promo_info[1]}'")
            return deleted > 0

    try:
        return _delete_once()
    except sqlite3.Error as e:
        logging.error(f"Failed to delete promo code {promo_id}: {e}")
        # Попробуем восстановить индексы/страницы и повторить один раз при типичном повреждении
        if isinstance(e, sqlite3.DatabaseError) and 'malformed' in str(e).lower():
            logging.warning("Detected SQLite corruption symptoms on delete_promo_code; attempting REINDEX/ANALYZE/VACUUM and retry once")
            if _repair_database_indexes():
                try:
                    return _delete_once()
                except sqlite3.Error as e2:
                    logging.error(f"Retry failed for delete_promo_code after repair: {e2}")
        return False



def get_promo_code(promo_id: int) -> dict | None:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute(

                '''
                SELECT pc.*, pl.plan_name, pl.host_name
                FROM promo_codes pc
                LEFT JOIN plans pl ON pl.plan_id = pc.vpn_plan_id
                WHERE pc.promo_id = ?
                ''',

                (promo_id,),

            )

            record = cursor.fetchone()

            if not record:

                return None

            data = dict(record)

            data['bot'] = _normalize_bot_value(data.get('bot'))
            
            # Десериализуем vpn_plan_id и tariff_code
            data['vpn_plan_id'] = _deserialize_vpn_plan_id(data.get('vpn_plan_id'))
            if data.get('tariff_code'):
                try:
                    data['tariff_code'] = json.loads(data['tariff_code'])
                except (json.JSONDecodeError, TypeError):
                    # Если не JSON, оставляем как есть
                    pass

            # Десериализуем target_group_ids
            if data.get('target_group_ids'):
                try:
                    data['target_group_ids'] = json.loads(data['target_group_ids'])
                except (json.JSONDecodeError, TypeError):
                    data['target_group_ids'] = []

            # Генерируем ссылку на промокод
            bot_username = data.get('bot_username')
            if bot_username:
                data['promo_link'] = f"https://t.me/{bot_username}?start=promo_{data['code']}"
            else:
                data['promo_link'] = None

            return data

    except sqlite3.Error as e:

        logging.error(f"Failed to fetch promo code {promo_id}: {e}")

        return None



def get_promo_code_by_code(code: str, bot: str | None = None, include_inactive: bool = False) -> dict | None:

    code_value = (code or "").strip().upper()

    if not code_value:

        return None

    bot_value = _normalize_bot_value(bot) if bot else None

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            query = (
                'SELECT pc.*, pl.plan_name, pl.host_name '
                'FROM promo_codes pc '
                'LEFT JOIN plans pl ON pl.plan_id = pc.vpn_plan_id '
                'WHERE pc.code = ?'
            )

            params: list = [code_value]

            if bot_value:

                query += ' AND pc.bot = ?'

                params.append(bot_value)

            if not include_inactive:

                query += ' AND pc.is_active = 1'

            query += ' LIMIT 1'

            cursor.execute(query, tuple(params))

            record = cursor.fetchone()

            if not record:

                return None

            data = dict(record)

            data['bot'] = _normalize_bot_value(data.get('bot'))
            
            # Десериализуем vpn_plan_id и tariff_code
            data['vpn_plan_id'] = _deserialize_vpn_plan_id(data.get('vpn_plan_id'))
            if data.get('tariff_code'):
                try:
                    data['tariff_code'] = json.loads(data['tariff_code'])
                except (json.JSONDecodeError, TypeError):
                    # Если не JSON, оставляем как есть
                    pass

            return data

    except sqlite3.Error as e:

        logging.error(f"Failed to fetch promo code '{code_value}': {e}")

        return None



def get_all_promo_codes() -> list[dict]:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute(

                '''
                SELECT pc.*, pl.plan_name, pl.host_name
                FROM promo_codes pc
                LEFT JOIN plans pl ON pl.plan_id = pc.vpn_plan_id
                ORDER BY pc.created_at DESC
                '''

            )

            promo_rows = [dict(row) for row in cursor.fetchall()]

            usage_map: dict[int, dict[str, dict]] = {}

            cursor.execute(

                '''
                SELECT promo_id, bot, COUNT(*) AS usage_count,
                       MIN(used_at) AS first_used_at, MAX(used_at) AS last_used_at
                FROM promo_code_usage
                GROUP BY promo_id, bot
                '''

            )

            for row in cursor.fetchall():

                pid = row['promo_id']

                bot_value = _normalize_bot_value(row['bot'])

                usage_map.setdefault(pid, {})[bot_value] = {
                    'count': row['usage_count'],
                    'first_used_at': row['first_used_at'],
                    'last_used_at': row['last_used_at'],
                }

            for promo in promo_rows:

                promo['bot'] = _normalize_bot_value(promo.get('bot'))
                
                # Десериализуем vpn_plan_id и tariff_code
                promo['vpn_plan_id'] = _deserialize_vpn_plan_id(promo.get('vpn_plan_id'))
                if promo.get('tariff_code'):
                    try:
                        promo['tariff_code'] = json.loads(promo['tariff_code'])
                    except (json.JSONDecodeError, TypeError):
                        # Если не JSON, оставляем как есть
                        pass

                # Десериализуем target_group_ids
                if promo.get('target_group_ids'):
                    try:
                        promo['target_group_ids'] = json.loads(promo['target_group_ids'])
                    except (json.JSONDecodeError, TypeError):
                        promo['target_group_ids'] = []

                # Генерируем ссылку на промокод
                bot_username = promo.get('bot_username')
                if bot_username:
                    promo['promo_link'] = f"https://t.me/{bot_username}?start=promo_{promo['code']}"
                else:
                    promo['promo_link'] = None

                promo['usage_by_bot'] = usage_map.get(promo['promo_id'], {})

                promo['usage_total'] = sum(item['count'] for item in promo['usage_by_bot'].values())

            return promo_rows

    except sqlite3.Error as e:

        logging.error(f"Failed to fetch promo codes: {e}")

        return []



def has_promo_code_usage(promo_id: int, bot: str) -> bool:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute(

                'SELECT 1 FROM promo_code_usage WHERE promo_id = ? AND bot = ? LIMIT 1',

                (promo_id, _normalize_bot_value(bot)),

            )

            return cursor.fetchone() is not None

    except sqlite3.Error as e:

        logging.error(f"Failed to check promo code usage for {promo_id}: {e}")

        return False



def record_promo_code_usage(
    promo_id: int,
    user_id: int | None,
    bot: str,
    plan_id: int | None,
    discount_amount: float = 0.0,
    discount_percent: float = 0.0,
    discount_bonus: float = 0.0,
    metadata: dict | None = None,
    status: str = 'applied',
    existing_usage_id: int | None = None,
) -> bool:

    bot_value = _normalize_bot_value(bot)

    metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()
            
            # Устанавливаем режим журналирования
            cursor.execute("PRAGMA journal_mode=DELETE")
            
            # Начинаем транзакцию с блокировкой
            cursor.execute("BEGIN IMMEDIATE")
            
            try:
                # Если передан existing_usage_id, обновляем существующую запись
                if existing_usage_id:
                    cursor.execute('''
                        UPDATE promo_code_usage 
                        SET used_at = CURRENT_TIMESTAMP, status = ?
                        WHERE usage_id = ? AND promo_id = ? AND user_id = ? AND bot = ?
                    ''', (status, existing_usage_id, promo_id, user_id, bot_value))
                    
                    if cursor.rowcount == 0:
                        cursor.execute("ROLLBACK")
                        logging.warning(f"Failed to update existing promo usage {existing_usage_id}")
                        return False
                    
                    cursor.execute("COMMIT")
                    return True
                
                # Проверяем существующую запись для этого промокода
                cursor.execute('''
                    SELECT usage_id, status
                    FROM promo_code_usage 
                    WHERE promo_id = ? AND user_id = ? AND bot = ?
                ''', (promo_id, user_id, bot_value))
                
                existing_record = cursor.fetchone()
                if existing_record:
                    existing_id, existing_status = existing_record
                    
                    # Если промокод уже использован (status='used'), запрещаем повторное применение
                    if existing_status == 'used':
                        cursor.execute("ROLLBACK")
                        logging.warning(f"User {user_id} already used promo code {promo_id} with status 'used'")
                        return False
                    
                    # Если промокод уже применён (status='applied'), разрешаем повторное применение
                    # Обновляем существующую запись
                    if existing_status == 'applied':
                        cursor.execute('''
                            UPDATE promo_code_usage 
                            SET used_at = CURRENT_TIMESTAMP, status = ?
                            WHERE usage_id = ? AND promo_id = ? AND user_id = ? AND bot = ?
                        ''', (status, existing_id, promo_id, user_id, bot_value))
                        
                        cursor.execute("COMMIT")
                        logging.info(f"Updated existing promo code usage (id={existing_id}) for user {user_id}, promo {promo_id}")
                        return True
                
                # Проверяем общий лимит использований
                cursor.execute('''
                    SELECT usage_limit_per_bot FROM promo_codes WHERE promo_id = ?
                ''', (promo_id,))
                
                limit_result = cursor.fetchone()
                if limit_result:
                    limit = limit_result[0]
                    cursor.execute('''
                        SELECT COUNT(*) as total_usage
                        FROM promo_code_usage 
                        WHERE promo_id = ? AND bot = ?
                    ''', (promo_id, bot_value))
                    
                    total_result = cursor.fetchone()
                    if total_result and total_result[0] >= limit:
                        cursor.execute("ROLLBACK")
                        logging.warning(f"Promo code {promo_id} usage limit exceeded")
                        return False

                cursor.execute(

                    '''
                    INSERT INTO promo_code_usage (
                        promo_id, user_id, bot, plan_id,
                        discount_amount, discount_percent, discount_bonus, metadata, used_at, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                    ''',

                    (
                        promo_id,
                        user_id,
                        bot_value,
                        plan_id,
                        float(discount_amount or 0),
                        float(discount_percent or 0),
                        float(discount_bonus or 0),
                        metadata_json,
                        status,
                    ),

                )

                cursor.execute("COMMIT")
                
                # Проверяем, что запись действительно добавилась
                cursor.execute('SELECT COUNT(*) FROM promo_code_usage WHERE promo_id = ? AND user_id = ?', (promo_id, user_id))
                count = cursor.fetchone()[0]
                
                logging.info(f"Recorded promo code usage: promo_id={promo_id}, user_id={user_id}, bot={bot_value}, records_count={count}")
                return True
                
            except Exception as e:
                cursor.execute("ROLLBACK")
                raise e

    except sqlite3.IntegrityError as e:
        # Этот блок теперь не должен срабатывать, так как мы проверяем существующие записи заранее
        logging.error(f"Unexpected IntegrityError for promo_id={promo_id}, bot={bot_value}: {e}")
        return False

    except sqlite3.Error as e:

        logging.error(f"Failed to record promo code usage for promo_id={promo_id}: {e}")

        return False



def remove_promo_code_usage(promo_id: int, bot: str) -> bool:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()
            
            # Устанавливаем режим журналирования
            cursor.execute("PRAGMA journal_mode=DELETE")
            
            # Начинаем транзакцию
            cursor.execute("BEGIN IMMEDIATE")
            
            try:
                # Получаем информацию для логирования
                cursor.execute('SELECT COUNT(*) FROM promo_code_usage WHERE promo_id = ? AND bot = ?', 
                             (promo_id, _normalize_bot_value(bot)))
                count_before = cursor.fetchone()[0]
                
                cursor.execute(
                    'DELETE FROM promo_code_usage WHERE promo_id = ? AND bot = ?',
                    (promo_id, _normalize_bot_value(bot)),
                )

                deleted = cursor.rowcount
                cursor.execute("COMMIT")
                
                if deleted > 0:
                    logging.info(f"Removed {deleted} promo code usage records for promo_id={promo_id}, bot={bot}")

                return deleted > 0
                
            except Exception as e:
                cursor.execute("ROLLBACK")
                raise e

    except sqlite3.Error as e:

        logging.error(f"Failed to remove promo code usage for promo_id={promo_id}: {e}")

        return False



def get_promo_code_usage_by_user(promo_id: int, user_id: int, bot: str) -> dict | None:
    """Получить информацию об использовании промокода конкретным пользователем"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT usage_id, status, used_at, discount_amount, discount_percent, discount_bonus
                FROM promo_code_usage 
                WHERE promo_id = ? AND user_id = ? AND bot = ?
            ''', (promo_id, user_id, _normalize_bot_value(bot)))
            
            result = cursor.fetchone()
            return dict(result) if result else None
            
    except sqlite3.Error as e:
        logging.error(f"Failed to get promo code usage for promo_id={promo_id}, user_id={user_id}: {e}")
        return None


def get_promo_code_usage(promo_id: int) -> list[dict]:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute(

                '''
                SELECT u.*, us.username, us.registration_date, us.total_spent, us.balance,
                       pl.plan_name, pl.host_name
                FROM promo_code_usage u
                LEFT JOIN users us ON us.telegram_id = u.user_id
                LEFT JOIN plans pl ON pl.plan_id = u.plan_id
                WHERE u.promo_id = ?
                ORDER BY u.used_at DESC
                ''',

                (promo_id,),

            )

            usage_rows: list[dict] = []

            for row in cursor.fetchall():

                data = dict(row)

                data['bot'] = _normalize_bot_value(data.get('bot'))

                metadata = data.get('metadata')

                if isinstance(metadata, str) and metadata:

                    try:

                        data['metadata'] = json.loads(metadata)

                    except json.JSONDecodeError:

                        pass

                usage_rows.append(data)

            return usage_rows

    except sqlite3.Error as e:

        logging.error(f"Failed to fetch promo code usage for promo_id={promo_id}: {e}")

        return []


def get_promo_code_usage_history(promo_id: int) -> list[dict]:
    """Получить историю использования промокода"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT pcu.*, u.username, pl.plan_name
                FROM promo_code_usage pcu
                LEFT JOIN users u ON u.telegram_id = pcu.user_id
                LEFT JOIN plans pl ON pl.plan_id = pcu.plan_id
                WHERE pcu.promo_id = ?
                ORDER BY pcu.used_at DESC
            ''', (promo_id,))
            
            return [dict(row) for row in cursor.fetchall()]
            
    except sqlite3.Error as e:
        logging.error(f"Failed to get promo code usage history for promo_id={promo_id}: {e}")
        return []


def get_all_promo_code_usage_history() -> list[dict]:
    """Получить всю историю использования промокодов"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT pcu.*, pc.code, u.username, pl.plan_name, pl.host_name
                FROM promo_code_usage pcu
                JOIN promo_codes pc ON pc.promo_id = pcu.promo_id
                LEFT JOIN users u ON u.telegram_id = pcu.user_id
                LEFT JOIN plans pl ON pl.plan_id = pcu.plan_id
                ORDER BY pcu.used_at DESC
            ''')
            
            return [dict(row) for row in cursor.fetchall()]
            
    except sqlite3.Error as e:
        logging.error(f"Failed to get all promo code usage history: {e}")
        return []


def get_user_promo_codes(user_id: int, bot: str) -> list[dict]:
    """Получить список использованных промокодов пользователя"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT pcu.*, pc.code, pc.discount_amount, pc.discount_percent, 
                       pc.discount_bonus, pc.tariff_code, pl.plan_name, pl.host_name
                FROM promo_code_usage pcu
                JOIN promo_codes pc ON pc.promo_id = pcu.promo_id
                LEFT JOIN plans pl ON pl.plan_id = pc.vpn_plan_id
                WHERE pcu.user_id = ? AND pcu.bot = ?
                ORDER BY pcu.used_at DESC
            ''', (user_id, bot))
            
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Error getting user promo codes: {e}")
        return []


def remove_user_promo_code_usage(user_id: int, usage_id: int, bot: str) -> bool:
    """Удалить использование промокода конкретным пользователем по usage_id"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Устанавливаем режим журналирования
            cursor.execute("PRAGMA journal_mode=DELETE")
            
            # Начинаем транзакцию
            cursor.execute("BEGIN IMMEDIATE")
            
            try:
                # Получаем информацию для логирования
                cursor.execute('''
                    SELECT pcu.promo_id, pc.code FROM promo_code_usage pcu
                    JOIN promo_codes pc ON pc.promo_id = pcu.promo_id
                    WHERE pcu.user_id = ? AND pcu.usage_id = ? AND pcu.bot = ?
                ''', (user_id, usage_id, _normalize_bot_value(bot)))
                
                promo_info = cursor.fetchone()
                
                # Основное удаление с учетом бота
                cursor.execute('''
                    DELETE FROM promo_code_usage 
                    WHERE user_id = ? AND usage_id = ? AND bot = ?
                ''', (user_id, usage_id, _normalize_bot_value(bot)))
                
                deleted = cursor.rowcount

                # Фолбэк: если ничего не удалили, пробуем без фильтра по bot (защита от рассинхронизации регистров)
                if deleted == 0:
                    cursor.execute('''
                        DELETE FROM promo_code_usage
                        WHERE user_id = ? AND usage_id = ?
                    ''', (user_id, usage_id))
                    deleted = cursor.rowcount
                cursor.execute("COMMIT")
                
                if deleted > 0 and promo_info:
                    logging.info(f"Removed user promo code usage: user_id={user_id}, usage_id={usage_id}, promo_id={promo_info[0]}, code='{promo_info[1]}'")
                
                return deleted > 0
                
            except Exception as e:
                cursor.execute("ROLLBACK")
                raise e
                
    except sqlite3.Error as e:
        logging.error(f"Error removing user promo code usage: {e}")
        return False


def validate_promo_code(code: str, bot: str) -> dict:
    """Валидировать промокод и вернуть информацию о нем"""
    try:
        code_value = (code or "").strip().upper()
        if not code_value:
            return {'valid': False, 'message': 'Промокод не может быть пустым'}
        
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Ищем промокод
            cursor.execute('''
                SELECT pc.*, pl.plan_name, pl.host_name
                FROM promo_codes pc
                LEFT JOIN plans pl ON pl.plan_id = pc.vpn_plan_id
                WHERE pc.code = ? AND pc.bot = ? AND pc.is_active = 1
            ''', (code_value, bot))
            
            promo = cursor.fetchone()
            if not promo:
                return {'valid': False, 'message': 'Промокод не найден или неактивен'}
            
            promo_dict = dict(promo)
            
            # Формируем описание промокода
            description_parts = []
            
            if promo_dict['discount_amount'] > 0:
                description_parts.append(f"💰 Скидка: {promo_dict['discount_amount']} руб.")
            
            if promo_dict['discount_percent'] > 0:
                description_parts.append(f"📊 Скидка: {promo_dict['discount_percent']}%")
            
            if promo_dict['discount_bonus'] > 0:
                description_parts.append(f"🎁 Бонус: {promo_dict['discount_bonus']} руб.")
            
            if promo_dict['plan_name']:
                description_parts.append(f"🔗 Тариф: {promo_dict['plan_name']}")
            
            if promo_dict['tariff_code']:
                description_parts.append(f"🏷️ Код тарифа: {promo_dict['tariff_code']}")
            
            description = '\n'.join(description_parts) if description_parts else "Промокод активен"
            
            return {
                'valid': True,
                'message': f'✅ Промокод "{code_value}" найден!',
                'description': description,
                'promo_data': promo_dict
            }
            
    except sqlite3.Error as e:
        logging.error(f"Error validating promo code: {e}")
        return {'valid': False, 'message': 'Ошибка при проверке промокода'}


def register_user_if_not_exists(telegram_id: int, username: str, referrer_id, fullname: str = None):

    try:

        with _get_db_connection() as conn:

            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT telegram_id FROM users WHERE telegram_id = ?", (telegram_id,))

            if not cursor.fetchone():

                # Получаем максимальный user_id и увеличиваем на 1

                cursor.execute("SELECT COALESCE(MAX(user_id), 999) FROM users")

                max_user_id = cursor.fetchone()[0]

                new_user_id = max_user_id + 1

                # Получаем ID группы по умолчанию
                cursor.execute("SELECT group_id FROM user_groups WHERE is_default = 1 LIMIT 1")
                default_group = cursor.fetchone()
                default_group_id = default_group[0] if default_group else None

                cursor.execute(

                    "INSERT INTO users (telegram_id, username, fullname, registration_date, referred_by, user_id, group_id) VALUES (?, ?, ?, ?, ?, ?, ?)",

                    (telegram_id, username, fullname, datetime.now(), referrer_id, new_user_id, default_group_id)

                )

            else:

                cursor.execute("UPDATE users SET username = ?, fullname = ? WHERE telegram_id = ?", (username, fullname, telegram_id))

            conn.commit()
            
            # Получаем и возвращаем созданного/обновлённого пользователя
            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            user_data = cursor.fetchone()
            
            if user_data:
                # Явное преобразование sqlite3.Row в словарь для совместимости
                return {key: user_data[key] for key in user_data.keys()}
            return None

    except sqlite3.Error as e:

        logging.error(f"Failed to register user {telegram_id}: {e}")
        return None



def add_to_referral_balance(user_id: int, amount: float):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            # Увеличиваем доступный баланс для вывода
            cursor.execute("UPDATE users SET referral_balance = referral_balance + ? WHERE telegram_id = ?", (amount, user_id))
            
            # Увеличиваем общую сумму всех заработков (история)
            cursor.execute("UPDATE users SET referral_balance_all = referral_balance_all + ? WHERE telegram_id = ?", (amount, user_id))

            conn.commit()

    except sqlite3.Error as e:

        logging.error(f"Failed to add to referral balance for user {user_id}: {e}")



def set_referral_balance(user_id: int, value: float):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("UPDATE users SET referral_balance = ? WHERE telegram_id = ?", (value, user_id))

            conn.commit()

    except sqlite3.Error as e:

        logging.error(f"Failed to set referral balance for user {user_id}: {e}")



def set_referral_balance_all(user_id: int, value: float):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("UPDATE users SET referral_balance_all = ? WHERE telegram_id = ?", (value, user_id))

            conn.commit()

    except sqlite3.Error as e:

        logging.error(f"Failed to set total referral balance for user {user_id}: {e}")



def get_referral_balance(user_id: int) -> float:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("SELECT referral_balance FROM users WHERE telegram_id = ?", (user_id,))

            result = cursor.fetchone()

            return result[0] if result else 0.0

    except sqlite3.Error as e:

        logging.error(f"Failed to get referral balance for user {user_id}: {e}")

        return 0.0



def get_referral_count(user_id: int) -> int:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))

            return cursor.fetchone()[0] or 0

    except sqlite3.Error as e:

        logging.error(f"Failed to get referral count for user {user_id}: {e}")

        return 0



def get_user(telegram_id: int):

    try:

        with _get_db_connection() as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))

            user_data = cursor.fetchone()

            return dict(user_data) if user_data else None

    except sqlite3.Error as e:

        logging.error(f"Failed to get user {telegram_id}: {e}")

        return None



def get_user_balance(user_id: int) -> float:

    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (user_id,))
            row = cursor.fetchone()
            return float(row[0]) if row and row[0] is not None else 0.0
    except sqlite3.Error as e:
        logging.error(f"Failed to get balance for user {user_id}: {e}")
        return 0.0



def get_auto_renewal_enabled(user_id: int) -> bool:

    """Получает статус автопродления для пользователя. По умолчанию True (включено)."""

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("SELECT auto_renewal_enabled FROM users WHERE telegram_id = ?", (user_id,))

            row = cursor.fetchone()

            # По умолчанию автопродление включено (1), если поле NULL или отсутствует - возвращаем True

            if row and row[0] is not None:

                return bool(row[0])

            return True  # По умолчанию включено

    except sqlite3.OperationalError as e:

        # Если колонка еще не существует (миграция не выполнилась), возвращаем True по умолчанию

        if "no such column" in str(e).lower():

            logging.debug(f"Column auto_renewal_enabled does not exist yet for user {user_id}, returning default True")

            return True  # По умолчанию включено

        logging.error(f"Failed to get auto_renewal_enabled for user {user_id}: {e}")

        return True  # По умолчанию включено при ошибке

    except sqlite3.Error as e:

        logging.error(f"Failed to get auto_renewal_enabled for user {user_id}: {e}")

        return True  # По умолчанию включено при ошибке



def set_auto_renewal_enabled(user_id: int, enabled: bool) -> bool:

    """Устанавливает статус автопродления для пользователя."""

    try:

        with _get_db_connection() as conn:

            cursor = conn.cursor()

            cursor.execute("UPDATE users SET auto_renewal_enabled = ? WHERE telegram_id = ?", (1 if enabled else 0, user_id))

            conn.commit()

            return True

    except sqlite3.OperationalError as e:

        # Если колонка еще не существует (миграция не выполнилась), пытаемся выполнить миграцию

        if "no such column" in str(e).lower():

            logging.warning(f"Column auto_renewal_enabled does not exist yet. Attempting to add it...")

            try:

                # Пытаемся добавить колонку напрямую

                with _get_db_connection() as conn2:

                    cursor2 = conn2.cursor()

                    cursor2.execute("ALTER TABLE users ADD COLUMN auto_renewal_enabled INTEGER DEFAULT 1")

                    conn2.commit()

                    # Теперь устанавливаем значение

                    cursor2.execute("UPDATE users SET auto_renewal_enabled = ? WHERE telegram_id = ?", (1 if enabled else 0, user_id))

                    conn2.commit()

                    logging.info(f"Column auto_renewal_enabled added and value set for user {user_id}")

                    return True

            except Exception as e2:

                logging.error(f"Failed to add column auto_renewal_enabled: {e2}")

                return False

        logging.error(f"Failed to set auto_renewal_enabled for user {user_id}: {e}")

        return False

    except sqlite3.Error as e:

        logging.error(f"Failed to set auto_renewal_enabled for user {user_id}: {e}")

        return False



def get_key_auto_renewal_enabled(key_id: int) -> bool:

    """Получает статус автопродления для конкретного ключа. По умолчанию True (включено)."""

    try:

        with _get_db_connection() as conn:

            cursor = conn.cursor()

            cursor.execute("SELECT auto_renewal_enabled FROM vpn_keys WHERE key_id = ?", (key_id,))

            row = cursor.fetchone()

            # По умолчанию автопродление включено (1), если поле NULL или отсутствует - возвращаем True

            if row and row[0] is not None:

                return bool(row[0])

            return True  # По умолчанию включено

    except sqlite3.OperationalError as e:

        # Если колонка еще не существует (миграция не выполнилась), возвращаем True по умолчанию

        if "no such column" in str(e).lower():

            logging.debug(f"Column auto_renewal_enabled does not exist yet for key {key_id}, returning default True")

            return True  # По умолчанию включено

        logging.error(f"Failed to get auto_renewal_enabled for key {key_id}: {e}")

        return True  # По умолчанию включено при ошибке

    except sqlite3.Error as e:

        logging.error(f"Failed to get auto_renewal_enabled for key {key_id}: {e}")

        return True  # По умолчанию включено при ошибке



def set_key_auto_renewal_enabled(key_id: int, enabled: bool) -> bool:

    """Устанавливает статус автопродления для ключа."""

    try:

        with _get_db_connection() as conn:

            cursor = conn.cursor()

            cursor.execute("UPDATE vpn_keys SET auto_renewal_enabled = ? WHERE key_id = ?", (1 if enabled else 0, key_id))

            conn.commit()

            return True

    except sqlite3.OperationalError as e:

        # Если колонка еще не существует (миграция не выполнилась), пытаемся выполнить миграцию

        if "no such column" in str(e).lower():

            logging.warning(f"Column auto_renewal_enabled does not exist yet in vpn_keys. Attempting to add it...")

            try:

                # Пытаемся добавить колонку напрямую

                with _get_db_connection() as conn2:

                    cursor2 = conn2.cursor()

                    cursor2.execute("ALTER TABLE vpn_keys ADD COLUMN auto_renewal_enabled INTEGER DEFAULT 1")

                    conn2.commit()

                    # Теперь устанавливаем значение

                    cursor2.execute("UPDATE vpn_keys SET auto_renewal_enabled = ? WHERE key_id = ?", (1 if enabled else 0, key_id))

                    conn2.commit()

                    logging.info(f"Column auto_renewal_enabled added and value set for key {key_id}")

                    return True

            except Exception as e2:

                logging.error(f"Failed to add column auto_renewal_enabled to vpn_keys: {e2}")

                return False

        logging.error(f"Failed to set auto_renewal_enabled for key {key_id}: {e}")

        return False

    except sqlite3.Error as e:

        logging.error(f"Failed to set auto_renewal_enabled for key {key_id}: {e}")

        return False



def add_to_user_balance(user_id: int, amount: float) -> bool:

    try:

        if amount == 0:

            return True

        with _get_db_connection() as conn:

            cursor = conn.cursor()

            cursor.execute("UPDATE users SET balance = COALESCE(balance, 0) + ? WHERE telegram_id = ?", (amount, user_id))

            conn.commit()

            return cursor.rowcount > 0

    except sqlite3.Error as e:

        logging.error(f"Failed to add {amount} to balance for user {user_id}: {e}")

        return False



def set_terms_agreed(telegram_id: int, agreed: bool = True):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("UPDATE users SET agreed_to_terms = ? WHERE telegram_id = ?", (1 if agreed else 0, telegram_id))

            conn.commit()

            action = "agreed to" if agreed else "revoked agreement to"

            logging.info(f"User {telegram_id} has {action} terms.")

    except sqlite3.Error as e:

        logging.error(f"Failed to set terms agreed for user {telegram_id}: {e}")



def set_documents_agreed(telegram_id: int):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("UPDATE users SET agreed_to_documents = 1 WHERE telegram_id = ?", (telegram_id,))

            conn.commit()

            logging.info(f"User {telegram_id} has agreed to documents.")

    except sqlite3.Error as e:

        logging.error(f"Failed to set documents agreed for user {telegram_id}: {e}")



def set_terms_agreed(telegram_id: int):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("UPDATE users SET agreed_to_terms = 1 WHERE telegram_id = ?", (telegram_id,))

            conn.commit()

            logging.info(f"User {telegram_id} has agreed to terms.")

    except sqlite3.Error as e:

        logging.error(f"Failed to set terms agreed for user {telegram_id}: {e}")



def set_subscription_status(telegram_id: int, status: str):

    """Устанавливает статус подписки пользователя: 'subscribed', 'not_subscribed', 'not_checked'"""

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("UPDATE users SET subscription_status = ? WHERE telegram_id = ?", (status, telegram_id))

            conn.commit()

            logging.info(f"User {telegram_id} subscription status set to {status}.")

    except sqlite3.Error as e:

        logging.error(f"Failed to set subscription status for user {telegram_id}: {e}")



def revoke_user_consent(telegram_id: int):

    """Отзывает согласие пользователя с документами"""

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("UPDATE users SET agreed_to_documents = 0 WHERE telegram_id = ?", (telegram_id,))

            conn.commit()

            logging.info(f"User {telegram_id} consent has been revoked.")

    except sqlite3.Error as e:

        logging.error(f"Failed to revoke consent for user {telegram_id}: {e}")



def update_user_stats(telegram_id: int, amount_spent: float, months_purchased: int):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("UPDATE users SET total_spent = total_spent + ?, total_months = total_months + ? WHERE telegram_id = ?", (amount_spent, months_purchased, telegram_id))

            conn.commit()

    except sqlite3.Error as e:

        logging.error(f"Failed to update user stats for {telegram_id}: {e}")



def get_user_count() -> int:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM users")

            result = cursor.fetchone()[0]

            logging.info(f"User count retrieved: {result}")

            return result or 0

    except sqlite3.Error as e:

        logging.error(f"Failed to get user count: {e}")

        return 0



def get_total_keys_count() -> int:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM vpn_keys")

            result = cursor.fetchone()[0]

            logging.info(f"Total keys count retrieved: {result}")

            return result or 0

    except sqlite3.Error as e:

        logging.error(f"Failed to get total keys count: {e}")

        return 0



def get_total_spent_sum() -> float:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("SELECT SUM(total_spent) FROM users")

            return cursor.fetchone()[0] or 0.0

    except sqlite3.Error as e:

        logging.error(f"Failed to get total spent sum: {e}")

        return 0.0



def get_total_notifications_count() -> int:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM notifications")

            result = cursor.fetchone()[0]

            logging.info(f"Total notifications count retrieved: {result}")

            return result or 0

    except sqlite3.Error as e:

        logging.error(f"Failed to get total notifications count: {e}")

        return 0



def get_total_earned_sum() -> float:

    """Возвращает общую сумму заработанных средств из успешных транзакций"""

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("SELECT SUM(amount_rub) FROM transactions WHERE status = 'completed'")

            result = cursor.fetchone()[0]

            logging.info(f"Total earned sum retrieved: {result}")

            return result or 0.0

    except sqlite3.Error as e:

        logging.error(f"Failed to get total earned sum: {e}")

        return 0.0



def create_pending_transaction(payment_id: str, user_id: int, amount_rub: float, metadata: dict, payment_link: str | None = None, api_request: str | None = None) -> int:

    """Создает pending транзакцию с поддержкой payment_link и api_request"""
    
    try:

        with sqlite3.connect(DB_FILE, timeout=30) as conn:

            cursor = conn.cursor()
            
            # Устанавливаем PRAGMA для предотвращения блокировок
            try:
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.execute("PRAGMA journal_mode=DELETE")
            except sqlite3.Error as e:
                logging.debug(f"Failed to set PRAGMA in create_pending_transaction: {e}")

            # Используем локальное время (UTC+3)

            from datetime import timezone, timedelta

            local_tz = timezone(timedelta(hours=3))  # UTC+3 для России

            local_now = datetime.now(local_tz)

            # Извлекаем payment_method из metadata если есть
            payment_method = metadata.get('payment_method', None)

            cursor.execute(

                "INSERT INTO transactions (payment_id, user_id, status, amount_rub, payment_method, metadata, payment_link, api_request, created_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",

                (payment_id, user_id, 'pending', amount_rub, payment_method, json.dumps(metadata), payment_link, api_request, local_now)

            )

            conn.commit()

            return cursor.lastrowid

    except sqlite3.Error as e:

        logging.error(f"Failed to create pending transaction: {e}")

        return 0



def create_pending_ton_transaction(payment_id: str, user_id: int, amount_rub: float, amount_ton: float, metadata: dict, payment_link: str | None = None) -> int:

    """Создает pending транзакцию для TON платежей"""

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            # Используем локальное время (UTC+3)

            from datetime import timezone, timedelta

            local_tz = timezone(timedelta(hours=3))  # UTC+3 для России

            local_now = datetime.now(local_tz)

            cursor.execute(

                "INSERT INTO transactions (payment_id, user_id, status, amount_rub, amount_currency, currency_name, payment_method, metadata, payment_link, created_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",

                (payment_id, user_id, 'pending', amount_rub, amount_ton, 'TON', 'TON Connect', json.dumps(metadata), payment_link, local_now)

            )

            conn.commit()

            return cursor.lastrowid

    except sqlite3.Error as e:

        logging.error(f"Failed to create pending TON transaction: {e}")

        return 0



def create_pending_stars_transaction(payment_id: str, user_id: int, amount_rub: float, amount_stars: int, metadata: dict) -> int:

    """Создает pending транзакцию для Stars платежей"""

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            # Используем локальное время (UTC+3)

            from datetime import timezone, timedelta

            local_tz = timezone(timedelta(hours=3))  # UTC+3 для России

            local_now = datetime.now(local_tz)

            cursor.execute(

                "INSERT INTO transactions (payment_id, user_id, status, amount_rub, amount_currency, currency_name, payment_method, metadata, created_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",

                (payment_id, user_id, 'pending', amount_rub, amount_stars, 'XTR', 'Stars', json.dumps(metadata), local_now)

            )

            conn.commit()

            return cursor.lastrowid

    except sqlite3.Error as e:

        logging.error(f"Failed to create pending Stars transaction: {e}")

        return 0



def update_transaction_status(payment_id: str, status: str, tx_hash: str = None) -> bool:

    """Обновляет статус транзакции и хеш"""

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            if tx_hash:

                cursor.execute(

                    "UPDATE transactions SET status = ?, transaction_hash = ? WHERE payment_id = ?",

                    (status, tx_hash, payment_id)

                )

            else:

                cursor.execute(

                    "UPDATE transactions SET status = ? WHERE payment_id = ?",

                    (status, payment_id)

                )

            conn.commit()

            return cursor.rowcount > 0

    except sqlite3.Error as e:

        logging.error(f"Failed to update transaction status: {e}")

        return False



def update_transaction_on_payment(payment_id: str, status: str, amount_rub: float, tx_hash: str | None = None, metadata: dict | None = None) -> bool:

    """Обновляет транзакцию при успешной оплате"""

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            

            # Обновляем основную информацию

            if tx_hash and metadata:

                cursor.execute("""

                    UPDATE transactions 

                    SET status = ?, amount_rub = ?, transaction_hash = ?, metadata = ?

                    WHERE payment_id = ?

                """, (status, amount_rub, tx_hash, json.dumps(metadata), payment_id))

            elif tx_hash:

                cursor.execute("""

                    UPDATE transactions 

                    SET status = ?, amount_rub = ?, transaction_hash = ?

                    WHERE payment_id = ?

                """, (status, amount_rub, tx_hash, payment_id))

            elif metadata:

                cursor.execute("""

                    UPDATE transactions 

                    SET status = ?, amount_rub = ?, metadata = ?

                    WHERE payment_id = ?

                """, (status, amount_rub, json.dumps(metadata), payment_id))

            else:

                cursor.execute("""

                    UPDATE transactions 

                    SET status = ?, amount_rub = ?

                    WHERE payment_id = ?

                """, (status, amount_rub, payment_id))

            

            conn.commit()

            return cursor.rowcount > 0

    except sqlite3.Error as e:

        logging.error(f"Failed to update transaction on payment: {e}")

        return False


def update_yookassa_transaction_atomic(payment_id: str, old_status: str, new_status: str, amount_rub: float, 
                                      yookassa_payment_id: str | None = None, rrn: str | None = None, 
                                      authorization_code: str | None = None, payment_type: str | None = None,
                                      metadata: dict | None = None, api_response: str | None = None) -> bool:
    """
    Атомарно обновляет транзакцию YooKassa только если текущий статус соответствует old_status.
    Это предотвращает race conditions при одновременной обработке webhook'ов.
    """
    try:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            cursor = conn.cursor()
            
            # Устанавливаем PRAGMA для предотвращения блокировок
            try:
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.execute("PRAGMA journal_mode=DELETE")
            except sqlite3.Error as e:
                logging.debug(f"Failed to set PRAGMA in update_yookassa_transaction_atomic: {e}")
            
            # Начинаем транзакцию с блокировкой
            cursor.execute("BEGIN IMMEDIATE")
            
            try:
                # Проверяем текущий статус и обновляем только если он соответствует ожидаемому
                if api_response is not None:
                    cursor.execute("""
                        UPDATE transactions 
                        SET status = ?, amount_rub = ?, yookassa_payment_id = ?, rrn = ?, 
                            authorization_code = ?, payment_type = ?, metadata = ?, api_response = ?
                        WHERE payment_id = ? AND status = ?
                    """, (new_status, amount_rub, yookassa_payment_id, rrn, authorization_code, 
                          payment_type, json.dumps(metadata) if metadata else None, api_response, 
                          payment_id, old_status))
                else:
                    cursor.execute("""
                        UPDATE transactions 
                        SET status = ?, amount_rub = ?, yookassa_payment_id = ?, rrn = ?, 
                            authorization_code = ?, payment_type = ?, metadata = ?
                        WHERE payment_id = ? AND status = ?
                    """, (new_status, amount_rub, yookassa_payment_id, rrn, authorization_code, 
                          payment_type, json.dumps(metadata) if metadata else None, 
                          payment_id, old_status))
                
                updated = cursor.rowcount > 0
                
                if updated:
                    cursor.execute("COMMIT")
                    logging.info(f"Atomically updated YooKassa transaction {payment_id} from {old_status} to {new_status}")
                else:
                    cursor.execute("ROLLBACK")
                    logging.warning(f"Failed to atomically update YooKassa transaction {payment_id}: status mismatch (expected {old_status})")
                
                return updated
                
            except sqlite3.Error as e:
                cursor.execute("ROLLBACK")
                logging.error(f"Database error in update_yookassa_transaction_atomic: {e}")
                raise

    except sqlite3.Error as e:
        logging.error(f"Failed to atomically update YooKassa transaction: {e}")
        return False


def update_yookassa_transaction(payment_id: str, status: str, amount_rub: float, 
                              yookassa_payment_id: str | None = None, rrn: str | None = None, 
                              authorization_code: str | None = None, payment_type: str | None = None,
                              metadata: dict | None = None, api_response: str | None = None) -> bool:

    """Обновляет транзакцию YooKassa с дополнительными данными, включая api_response"""

    try:

        with sqlite3.connect(DB_FILE, timeout=30) as conn:

            cursor = conn.cursor()
            
            # Устанавливаем PRAGMA для предотвращения блокировок
            try:
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.execute("PRAGMA journal_mode=DELETE")
            except sqlite3.Error as e:
                logging.debug(f"Failed to set PRAGMA in update_yookassa_transaction: {e}")

            # Обновляем основную информацию и дополнительные поля YooKassa
            # Если api_response передан, обновляем его
            if api_response is not None:
                cursor.execute("""

                    UPDATE transactions 

                    SET status = ?, amount_rub = ?, yookassa_payment_id = ?, rrn = ?, 

                        authorization_code = ?, payment_type = ?, metadata = ?, api_response = ?

                    WHERE payment_id = ?

                """, (status, amount_rub, yookassa_payment_id, rrn, authorization_code, 

                      payment_type, json.dumps(metadata) if metadata else None, api_response, payment_id))
            else:
                cursor.execute("""

                    UPDATE transactions 

                    SET status = ?, amount_rub = ?, yookassa_payment_id = ?, rrn = ?, 

                        authorization_code = ?, payment_type = ?, metadata = ?

                    WHERE payment_id = ?

                """, (status, amount_rub, yookassa_payment_id, rrn, authorization_code, 

                      payment_type, json.dumps(metadata) if metadata else None, payment_id))

            conn.commit()

            return cursor.rowcount > 0

    except sqlite3.Error as e:

        logging.error(f"Failed to update YooKassa transaction: {e}")

        return False



def save_webhook_to_db(webhook_type: str, event_type: str, payment_id: str | None = None, 
                       transaction_id: int | None = None, request_payload: dict | None = None,
                       response_payload: dict | None = None, status: str = 'received') -> int:
    """Сохраняет webhook в таблицу webhooks для гибридного хранения
    
    Args:
        webhook_type: Тип webhook (yookassa, heleket, ton)
        event_type: Тип события (payment.succeeded, payment.waiting_for_capture и т.д.)
        payment_id: ID платежа
        transaction_id: ID транзакции в БД (опционально)
        request_payload: JSON payload запроса (будет сериализован)
        response_payload: JSON payload ответа (будет сериализован)
        status: Статус обработки (received, processed, error)
    
    Returns:
        ID созданной записи webhook или 0 при ошибке
    """
    try:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            cursor = conn.cursor()
            
            # Устанавливаем PRAGMA для предотвращения блокировок
            try:
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.execute("PRAGMA journal_mode=DELETE")
            except sqlite3.Error as e:
                logging.debug(f"Failed to set PRAGMA in save_webhook_to_db: {e}")
            
            # Используем локальное время (UTC+3)
            from datetime import timezone, timedelta
            local_tz = timezone(timedelta(hours=3))  # UTC+3 для России
            local_now = datetime.now(local_tz)
            
            # Сериализуем payload если это dict
            request_payload_str = None
            if request_payload is not None:
                if isinstance(request_payload, dict):
                    request_payload_str = json.dumps(request_payload, ensure_ascii=False)
                elif isinstance(request_payload, str):
                    request_payload_str = request_payload
                else:
                    request_payload_str = str(request_payload)
            
            response_payload_str = None
            if response_payload is not None:
                if isinstance(response_payload, dict):
                    response_payload_str = json.dumps(response_payload, ensure_ascii=False)
                elif isinstance(response_payload, str):
                    response_payload_str = response_payload
                else:
                    response_payload_str = str(response_payload)
            
            cursor.execute("""
                INSERT INTO webhooks 
                (webhook_type, event_type, payment_id, transaction_id, request_payload, response_payload, status, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (webhook_type, event_type, payment_id, transaction_id, request_payload_str, 
                  response_payload_str, status, local_now))
            
            conn.commit()
            return cursor.lastrowid
            
    except sqlite3.Error as e:
        logging.error(f"Failed to save webhook to DB: {e}", exc_info=True)
        return 0


def cleanup_old_webhooks(days_to_keep: int = 90) -> int:
    """Удаляет старые записи webhook'ов из БД
    
    Args:
        days_to_keep: Количество дней для хранения (по умолчанию 90)
    
    Returns:
        Количество удаленных записей
    """
    try:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            cursor = conn.cursor()
            
            # Устанавливаем PRAGMA для предотвращения блокировок
            try:
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.execute("PRAGMA journal_mode=DELETE")
            except sqlite3.Error as e:
                logging.debug(f"Failed to set PRAGMA in cleanup_old_webhooks: {e}")
            
            # Используем локальное время (UTC+3)
            from datetime import timezone, timedelta
            local_tz = timezone(timedelta(hours=3))  # UTC+3 для России
            cutoff_date = datetime.now(local_tz) - timedelta(days=days_to_keep)
            
            cursor.execute("""
                DELETE FROM webhooks 
                WHERE created_date < ?
            """, (cutoff_date,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            if deleted_count > 0:
                logging.info(f"Cleaned up {deleted_count} old webhook records (older than {days_to_keep} days)")
            
            return deleted_count
            
    except sqlite3.Error as e:
        logging.error(f"Failed to cleanup old webhooks: {e}", exc_info=True)
        return 0


def get_transaction_by_payment_id(payment_id: str) -> dict | None:

    """Возвращает транзакцию по payment_id как dict со всеми полями. metadata парсится в dict."""

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute("SELECT * FROM transactions WHERE payment_id = ? LIMIT 1", (payment_id,))

            row = cursor.fetchone()

            if not row:

                return None

            result = {key: row[key] for key in row.keys()}

            try:

                result['metadata'] = json.loads(result.get('metadata') or '{}')

            except Exception:

                result['metadata'] = {}

            return result

    except sqlite3.Error as e:

        logging.error(f"Failed to fetch transaction by payment_id {payment_id}: {e}")

        return None



def find_ton_transaction_by_amount(amount_ton: float) -> dict | None:

    """Ищет pending TON транзакцию по сумме"""

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            

            # Ищем pending транзакции с похожей суммой в TON (с погрешностью 0.01 TON)

            cursor.execute("""

                SELECT * FROM transactions 

                WHERE status = 'pending' 

                AND payment_method = 'TON Connect'

                AND ABS(amount_currency - ?) < 0.01

                ORDER BY created_date DESC 

                LIMIT 1

            """, (amount_ton,))

            

            transaction = cursor.fetchone()

            if transaction:

                # Только находим транзакцию, НЕ обновляем статус

                logger.info(f"Found pending TON transaction by amount: {amount_ton} TON")

                return json.loads(transaction['metadata'])

            

            return None

    except sqlite3.Error as e:

        logging.error(f"Failed to find TON transaction by amount {amount_ton}: {e}")

        return None



def find_and_complete_ton_transaction(payment_id: str, amount_ton: float, tx_hash: str = None, user_id: int | None = None) -> dict | None:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            

            # Ищем транзакцию по payment_id

            cursor.execute("SELECT * FROM transactions WHERE payment_id = ? AND status = 'pending'", (payment_id,))

            transaction = cursor.fetchone()

            

            # Если не найдено, попробуем найти по сумме (fallback) - ТОЛЬКО если передан user_id для безопасности
            if not transaction and user_id is not None:

                cursor.execute("""
                    SELECT * FROM transactions 
                    WHERE status = 'pending' 
                    AND payment_method = 'TON Connect' 
                    AND user_id = ?
                    AND ABS(amount_currency - ?) < 0.01
                    ORDER BY created_date DESC
                    LIMIT 1
                """, (user_id, amount_ton))

                transaction = cursor.fetchone()

            

            if not transaction:

                logger.warning(f"TON Webhook: Received payment for unknown or completed payment_id: {payment_id}")

                return None

            

            if tx_hash:

                cursor.execute(

                    "UPDATE transactions SET status = 'paid', amount_currency = ?, currency_name = 'TON', payment_method = 'TON Connect', transaction_hash = ? WHERE payment_id = ?",

                    (amount_ton, tx_hash, transaction['payment_id'])

                )

            else:

                cursor.execute(

                    "UPDATE transactions SET status = 'paid', amount_currency = ?, currency_name = 'TON', payment_method = 'TON Connect' WHERE payment_id = ?",

                    (amount_ton, transaction['payment_id'])

                )

            conn.commit()

            

            return json.loads(transaction['metadata'])

    except sqlite3.Error as e:

        logging.error(f"Failed to complete TON transaction {payment_id}: {e}")

        return None



def log_transaction(username: str, transaction_id: str | None, payment_id: str | None, user_id: int, status: str, amount_rub: float, amount_currency: float | None, currency_name: str | None, payment_method: str, metadata: str):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Используем локальное время (UTC+3)

            from datetime import timezone, timedelta

            local_tz = timezone(timedelta(hours=3))  # UTC+3 для России

            local_now = datetime.now(local_tz)

            cursor.execute(

                """INSERT INTO transactions

                   (username, payment_id, user_id, status, amount_rub, amount_currency, currency_name, payment_method, metadata, created_date)

                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",

                (username, payment_id, user_id, status, amount_rub, amount_currency, currency_name, payment_method, metadata, local_now)

            )

            conn.commit()
            
            # Получаем и возвращаем созданную транзакцию
            if payment_id:
                cursor.execute("SELECT * FROM transactions WHERE payment_id = ? LIMIT 1", (payment_id,))
                row = cursor.fetchone()
                if row:
                    result = {key: row[key] for key in row.keys()}
                    try:
                        result['metadata'] = json.loads(result.get('metadata') or '{}')
                    except Exception:
                        result['metadata'] = {}
                    return result
            
            return None

    except sqlite3.Error as e:

        logging.error(f"Failed to log transaction for user {user_id}: {e}")
        return None



def get_paginated_transactions(page: int = 1, per_page: int = 15) -> tuple[list[dict], int]:

    offset = (page - 1) * per_page

    transactions = []

    total = 0

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            

            cursor.execute("SELECT COUNT(*) FROM transactions")

            total = cursor.fetchone()[0]



            query = """

                SELECT 

                    t.*, 

                    u.username AS joined_username,

                    u.telegram_id AS joined_user_id

                FROM transactions t 

                LEFT JOIN users u ON t.user_id = u.telegram_id 

                ORDER BY t.created_date DESC 

                LIMIT ? OFFSET ?

            """

            cursor.execute(query, (per_page, offset))

            

            for row in cursor.fetchall():

                transaction_dict = dict(row)

                

                # Преобразуем created_date в datetime объект (UTC aware)
                if transaction_dict.get('created_date'):
                    transaction_dict['created_date'] = _parse_db_datetime(transaction_dict['created_date'])

                

                metadata_str = transaction_dict.get('metadata')

                if metadata_str:

                    try:

                        metadata = json.loads(metadata_str)

                        transaction_dict['metadata'] = metadata

                        transaction_dict['host_name'] = metadata.get('host_name', 'N/A')

                        transaction_dict['plan_name'] = metadata.get('plan_name', 'N/A')

                    except json.JSONDecodeError:

                        transaction_dict['host_name'] = 'Error'

                        transaction_dict['plan_name'] = 'Error'

                        pass

                else:

                    transaction_dict['host_name'] = 'N/A'

                    transaction_dict['plan_name'] = 'N/A'

                

                # Username привносим из таблицы users (joined_username), если есть

                if transaction_dict.get('joined_username'):

                    transaction_dict['username'] = transaction_dict.get('joined_username')

                

                transactions.append(transaction_dict)

            

    except sqlite3.Error as e:

        logging.error(f"Failed to get paginated transactions: {e}")

    

    return transactions, total



def set_trial_used(telegram_id: int):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("UPDATE users SET trial_used = 1 WHERE telegram_id = ?", (telegram_id,))

            conn.commit()

            logging.info(f"Trial period marked as used for user {telegram_id}.")

    except sqlite3.Error as e:

        logging.error(f"Failed to set trial used for user {telegram_id}: {e}")



def set_trial_days_given(telegram_id: int, days: int):

    """Устанавливает количество дней, выданных по пробному ключу"""

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("UPDATE users SET trial_days_given = ? WHERE telegram_id = ?", (days, telegram_id))

            conn.commit()

            logging.info(f"Trial days set to {days} for user {telegram_id}.")

    except sqlite3.Error as e:

        logging.error(f"Failed to set trial days for user {telegram_id}: {e}")



def increment_trial_reuses(telegram_id: int):

    """Увеличивает счетчик повторных использований триала"""

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("UPDATE users SET trial_reuses_count = trial_reuses_count + 1 WHERE telegram_id = ?", (telegram_id,))

            conn.commit()

            logging.info(f"Trial reuses count incremented for user {telegram_id}.")

    except sqlite3.Error as e:

        logging.error(f"Failed to increment trial reuses for user {telegram_id}: {e}")



def reset_trial_used(telegram_id: int):

    """Сбрасывает флаг использования триала (для повторного использования)"""

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("UPDATE users SET trial_used = 0 WHERE telegram_id = ?", (telegram_id,))

            conn.commit()

            logging.info(f"Trial used flag reset for user {telegram_id}.")

    except sqlite3.Error as e:

        logging.error(f"Failed to reset trial used for user {telegram_id}: {e}")



def admin_reset_trial_completely(telegram_id: int):

    """Полностью сбрасывает всю информацию о триале пользователя (админская функция)"""

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            

            # Проверяем текущее состояние перед сбросом

            cursor.execute("SELECT trial_used, trial_days_given, trial_reuses_count FROM users WHERE telegram_id = ?", (telegram_id,))

            before_reset = cursor.fetchone()

            logging.info(f"Before reset for user {telegram_id}: trial_used={before_reset[0] if before_reset else 'None'}, trial_days_given={before_reset[1] if before_reset else 'None'}, trial_reuses_count={before_reset[2] if before_reset else 'None'}")

            

            # Сбрасываем все поля связанные с триалом

            cursor.execute("""

                UPDATE users 

                SET trial_used = 0, 

                    trial_days_given = 0, 

                    trial_reuses_count = 0 

                WHERE telegram_id = ?

            """, (telegram_id,))

            

            # Проверяем количество затронутых строк

            rows_affected = cursor.rowcount

            logging.info(f"Users table update affected {rows_affected} rows for user {telegram_id}")

            

            # Удаляем все триальные ключи пользователя
            # Сначала получаем key_id всех триальных ключей для удаления токенов
            cursor.execute("SELECT key_id FROM vpn_keys WHERE user_id = ? AND is_trial = 1", (telegram_id,))
            trial_key_ids = [row[0] for row in cursor.fetchall()]
            
            # Удаляем токены для всех триальных ключей
            if trial_key_ids:
                placeholders = ','.join(['?'] * len(trial_key_ids))
                cursor.execute(f"DELETE FROM user_tokens WHERE key_id IN ({placeholders})", trial_key_ids)
                deleted_tokens = cursor.rowcount
                logging.info(f"Deleted {deleted_tokens} tokens for {len(trial_key_ids)} trial keys before deleting keys")

            cursor.execute("""

                DELETE FROM vpn_keys 

                WHERE user_id = ? AND is_trial = 1

            """, (telegram_id,))

            

            trial_keys_deleted = cursor.rowcount

            logging.info(f"Deleted {trial_keys_deleted} trial keys for user {telegram_id}")

            

            conn.commit()

            

            # Проверяем состояние после сброса

            cursor.execute("SELECT trial_used, trial_days_given, trial_reuses_count FROM users WHERE telegram_id = ?", (telegram_id,))

            after_reset = cursor.fetchone()

            logging.info(f"After reset for user {telegram_id}: trial_used={after_reset[0] if after_reset else 'None'}, trial_days_given={after_reset[1] if after_reset else 'None'}, trial_reuses_count={after_reset[2] if after_reset else 'None'}")

            

            logging.info(f"Trial completely reset for user {telegram_id} by admin.")

            return True

    except sqlite3.Error as e:

        logging.error(f"Failed to completely reset trial for user {telegram_id}: {e}")

        return False



def get_trial_info(telegram_id: int) -> dict:

    """Получает информацию о триале пользователя"""

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute("SELECT trial_used, trial_days_given, trial_reuses_count FROM users WHERE telegram_id = ?", (telegram_id,))

            result = cursor.fetchone()

            if result:

                return {

                    'trial_used': bool(result['trial_used']),

                    'trial_days_given': result['trial_days_given'] or 0,

                    'trial_reuses_count': result['trial_reuses_count'] or 0

                }

            return {'trial_used': False, 'trial_days_given': 0, 'trial_reuses_count': 0}

    except sqlite3.Error as e:

        logging.error(f"Failed to get trial info for user {telegram_id}: {e}")

        return {'trial_used': False, 'trial_days_given': 0, 'trial_reuses_count': 0}



def create_key_with_stats_atomic(user_id: int, host_name: str, xui_client_uuid: str, key_email: str, 
                                  expiry_timestamp_ms: int, amount_spent: float, months_purchased: int,
                                  payment_id: str | None = None, promo_usage_id: int | None = None, 
                                  plan_id: int | None = None, connection_string: str = None, 
                                  plan_name: str = None, price: float = None, protocol: str = 'vless', 
                                  is_trial: int = 0, subscription: str = None, subscription_link: str = None, 
                                  telegram_chat_id: int = None, comment: str = None) -> int | None:
    """
    Атомарно создает ключ и обновляет статистику пользователя, транзакцию и промокод в одной транзакции БД.
    Возвращает key_id при успехе, None при ошибке.
    """
    try:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            cursor = conn.cursor()
            
            # Устанавливаем PRAGMA для предотвращения блокировок
            try:
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.execute("PRAGMA journal_mode=DELETE")
            except sqlite3.Error as e:
                logging.debug(f"Failed to set PRAGMA in create_key_with_stats_atomic: {e}")
            
            # Начинаем транзакцию с блокировкой
            cursor.execute("BEGIN IMMEDIATE")
            
            try:
                from datetime import timezone, timedelta
                from shop_bot.utils.datetime_utils import timestamp_to_utc_datetime, calculate_remaining_seconds, get_moscow_now
                
                local_tz = timezone(timedelta(hours=3))
                expiry_date = timestamp_to_utc_datetime(expiry_timestamp_ms)
                local_now = get_moscow_now()
                remaining_seconds = calculate_remaining_seconds(expiry_timestamp_ms)
                
                # Определяем статус ключа
                if is_trial and remaining_seconds > 0:
                    status = 'trial-active'
                elif is_trial and remaining_seconds <= 0:
                    status = 'trial-ended'
                elif not is_trial and remaining_seconds > 0:
                    status = 'pay-active'
                else:
                    status = 'pay-ended'
                
                enabled = 1
                start_date = local_now
                
                # 1. Создаем ключ
                cursor.execute(
                    """INSERT INTO vpn_keys 
                    (user_id, host_name, xui_client_uuid, key_email, expiry_date, connection_string, 
                     plan_name, price, created_date, protocol, is_trial, remaining_seconds, status, 
                     enabled, start_date, subscription, subscription_link, telegram_chat_id, comment) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, host_name, xui_client_uuid, key_email, expiry_date, connection_string, 
                     plan_name, price, local_now, protocol, is_trial, remaining_seconds, status, 
                     enabled, start_date, subscription, subscription_link, telegram_chat_id, comment)
                )
                
                new_key_id = cursor.lastrowid
                
                # 2. Обновляем статистику пользователя
                # Примечание: keys_count обновляется через get_next_key_number() перед созданием ключа,
                # поэтому здесь не нужно инкрементировать счетчик
                cursor.execute(
                    "UPDATE users SET total_spent = total_spent + ?, total_months = total_months + ? WHERE telegram_id = ?",
                    (amount_spent, months_purchased, user_id)
                )
                
                # 3. Обновляем транзакцию (если передан payment_id)
                if payment_id:
                    cursor.execute(
                        "UPDATE transactions SET status = 'paid', amount_rub = ? WHERE payment_id = ? AND status = 'pending'",
                        (price or amount_spent, payment_id)
                    )
                
                # 4. Обновляем статус промокода (если передан promo_usage_id)
                if promo_usage_id and plan_id:
                    cursor.execute(
                        """UPDATE promo_code_usage 
                        SET status = 'used', plan_id = ?, used_at = CURRENT_TIMESTAMP 
                        WHERE usage_id = ? AND status = 'applied'""",
                        (plan_id, promo_usage_id)
                    )
                
                # Коммитим все изменения
                cursor.execute("COMMIT")
                
                logging.info(
                    f"Atomically created key_id={new_key_id} for user_id={user_id} with stats update, "
                    f"amount_spent={amount_spent}, months={months_purchased}"
                )
                
                # Создаем токен для личного кабинета после успешного создания ключа
                try:
                    from shop_bot.data_manager.database import get_or_create_permanent_token
                    get_or_create_permanent_token(user_id, new_key_id)
                    logging.info(f"Created permanent token for new key_id={new_key_id}, user_id={user_id}")
                except Exception as token_error:
                    logging.error(f"Failed to create permanent token for key_id={new_key_id}, user_id={user_id}: {token_error}", exc_info=True)
                
                return new_key_id
                
            except sqlite3.IntegrityError as integrity_err:
                cursor.execute("ROLLBACK")
                logging.warning(f"IntegrityError in create_key_with_stats_atomic for user_id={user_id}, email={key_email}: {integrity_err}")
                # Ключ с таким email уже существует - возвращаем None, вызывающий код должен обработать это
                return None
            except sqlite3.Error as e:
                cursor.execute("ROLLBACK")
                logging.error(f"Database error in create_key_with_stats_atomic: {e}", exc_info=True)
                raise
                
    except sqlite3.Error as e:
        logging.error(f"Failed to atomically create key with stats: {e}", exc_info=True)
        return None


def add_new_key(user_id: int, host_name: str, xui_client_uuid: str, key_email: str, expiry_timestamp_ms: int, connection_string: str = None, plan_name: str = None, price: float = None, protocol: str = 'vless', is_trial: int = 0, subscription: str = None, subscription_link: str = None, telegram_chat_id: int = None, comment: str = None):

    conn = None
    try:
        conn = sqlite3.connect(DB_FILE, timeout=30)
        cursor = conn.cursor()
        
        # Устанавливаем PRAGMA для предотвращения блокировок
        try:
            cursor.execute("PRAGMA busy_timeout=30000")
        except sqlite3.Error as e:
            logging.debug(f"Failed to set PRAGMA busy_timeout in add_new_key: {e}")

        # Импортируем необходимые модули
        from datetime import timezone, timedelta
        # Импортируем новые утилиты для работы с timezone
        from shop_bot.utils.datetime_utils import timestamp_to_utc_datetime, calculate_remaining_seconds, get_moscow_now

        local_tz = timezone(timedelta(hours=3))
        
        # Используем новую утилиту для корректной конвертации timestamp в UTC
        expiry_date = timestamp_to_utc_datetime(expiry_timestamp_ms)

        local_now = get_moscow_now()

        # Рассчитываем remaining_seconds с помощью утилиты
        remaining_seconds = calculate_remaining_seconds(expiry_timestamp_ms)

        try:

            # Определяем статус ключа на основе активности и типа
            if is_trial and remaining_seconds > 0:
                status = 'trial-active'
            elif is_trial and remaining_seconds <= 0:
                status = 'trial-ended'
            elif not is_trial and remaining_seconds > 0:
                status = 'pay-active'
            else:
                status = 'pay-ended'

            enabled = 1
            
            # Устанавливаем start_date как created_date
            start_date = local_now

            logging.info(
                f"add_new_key: Inserting new key: user_id={user_id}, email={key_email}, "
                f"host_name={host_name}, expiry_date={expiry_date}, is_trial={is_trial}, "
                f"status={status}, remaining_seconds={remaining_seconds}"
            )

            cursor.execute(

                "INSERT INTO vpn_keys (user_id, host_name, xui_client_uuid, key_email, expiry_date, connection_string, plan_name, price, created_date, protocol, is_trial, remaining_seconds, status, enabled, start_date, subscription, subscription_link, telegram_chat_id, comment) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",

                (user_id, host_name, xui_client_uuid, key_email, expiry_date, connection_string, plan_name, price, local_now, protocol, is_trial, remaining_seconds, status, enabled, start_date, subscription, subscription_link, telegram_chat_id, comment)

            )

            new_key_id = cursor.lastrowid

            conn.commit()
            
            logging.info(
                f"add_new_key: Successfully created new key: key_id={new_key_id}, user_id={user_id}, "
                f"email={key_email}"
            )
            
            # Создаем токен для личного кабинета после успешного создания ключа
            try:
                get_or_create_permanent_token(user_id, new_key_id)
                logging.info(f"Created permanent token for new key_id={new_key_id}, user_id={user_id}")
            except Exception as token_error:
                # Логируем ошибку, но не прерываем создание ключа
                logging.error(f"Failed to create permanent token for key_id={new_key_id}, user_id={user_id}: {token_error}", exc_info=True)

            return new_key_id

        except sqlite3.IntegrityError as integrity_err:

            # Ключ с таким email уже есть — считаем это продлением и обновляем данные
            logging.warning(
                f"add_new_key: IntegrityError for user_id={user_id}, email={key_email}. "
                f"This means a key with this email already exists. Error: {integrity_err}"
            )

            cursor.execute("SELECT key_id, user_id, created_date FROM vpn_keys WHERE key_email = ? LIMIT 1", (key_email,))

            row = cursor.fetchone()

            if row:

                key_id = row[0]
                existing_user_id = row[1]
                existing_created_date = row[2] if len(row) > 2 else None
                
                logging.warning(
                    f"add_new_key: Found existing key_id={key_id} with email={key_email}, "
                    f"existing_user_id={existing_user_id}, existing_created_date={existing_created_date}, "
                    f"new_user_id={user_id}. This will update the existing key instead of creating a new one!"
                )

                # Определяем статус ключа на основе активности и типа
                if is_trial and remaining_seconds > 0:
                    status = 'trial-active'
                elif is_trial and remaining_seconds <= 0:
                    status = 'trial-ended'
                elif not is_trial and remaining_seconds > 0:
                    status = 'pay-active'
                else:
                    status = 'pay-ended'

                enabled = 1
                
                # Устанавливаем start_date если его нет
                cursor.execute("SELECT start_date FROM vpn_keys WHERE key_id = ?", (key_id,))
                existing_start_date = cursor.fetchone()
                start_date_to_set = None
                if not existing_start_date or not existing_start_date[0]:
                    start_date_to_set = datetime.now(timezone(timedelta(hours=3)))

                cursor.execute(

                    "UPDATE vpn_keys SET xui_client_uuid = ?, expiry_date = ?, remaining_seconds = ?, plan_name = COALESCE(?, plan_name), price = COALESCE(?, price), protocol = ?, is_trial = ?, status = COALESCE(?, status), enabled = COALESCE(?, enabled), subscription = COALESCE(?, subscription), telegram_chat_id = COALESCE(?, telegram_chat_id), comment = COALESCE(?, comment), start_date = COALESCE(?, start_date) WHERE key_id = ?",

                    (xui_client_uuid, expiry_date, remaining_seconds, plan_name, price, protocol, is_trial, status, enabled, subscription, telegram_chat_id, comment, start_date_to_set, key_id)

                )

                # connection_string обновляем, если пришёл

                if connection_string:

                    cursor.execute(

                        "UPDATE vpn_keys SET connection_string = ? WHERE key_id = ?",

                        (connection_string, key_id)

                    )

                conn.commit()
                
                # Создаем токен для личного кабинета после успешного обновления ключа (продление)
                try:
                    get_or_create_permanent_token(user_id, key_id)
                    logging.debug(f"Ensured permanent token exists for extended key_id={key_id}, user_id={user_id}")
                except Exception as token_error:
                    # Логируем ошибку, но не прерываем обновление ключа
                    logging.error(f"Failed to create/ensure permanent token for key_id={key_id}, user_id={user_id}: {token_error}", exc_info=True)

                return key_id

            else:

                raise

    except sqlite3.Error as e:

        logging.error(f"Failed to add new key for user {user_id}: {e}")

        return None
    finally:
        if conn:
            conn.close()



def delete_key_by_email(email: str):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()
            
            # Получаем key_id для логирования
            cursor.execute("SELECT key_id FROM vpn_keys WHERE key_email = ? LIMIT 1", (email,))
            row = cursor.fetchone()
            
            key_id = row[0] if row else None
            
            # НЕ удаляем токен при удалении ключа - это позволяет validate_permanent_token
            # корректно определить удаленный ключ через LEFT JOIN и вернуть key_deleted=True,
            # что обеспечивает правильную обработку в приложении user-cabinet
            # (возврат 404 "Ключ удален" вместо 403 "Ссылка недействительна")
            
            # Удаляем ключ
            cursor.execute("DELETE FROM vpn_keys WHERE key_email = ?", (email,))
            deleted_keys = cursor.rowcount

            conn.commit()
            if deleted_keys > 0:
                if key_id:
                    logging.info(f"Deleted key with email '{email}' (key_id={key_id}). Token preserved for proper error handling.")
                else:
                    logging.info(f"Deleted key with email '{email}'")

    except sqlite3.Error as e:

        logging.error(f"Failed to delete key '{email}': {e}")



def get_user_keys(user_id: int):

    try:

        with _get_db_connection() as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute("SELECT * FROM vpn_keys WHERE user_id = ? ORDER BY key_id", (user_id,))

            keys = cursor.fetchall()

            return [dict(key) for key in keys]

    except sqlite3.Error as e:

        logging.error(f"Failed to get keys for user {user_id}: {e}")

        return []



def get_key_by_id(key_id: int):

    try:

        with _get_db_connection() as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute("SELECT * FROM vpn_keys WHERE key_id = ?", (key_id,))

            key_data = cursor.fetchone()

            if not key_data:
                return None
            
            # Конвертируем Row в dict
            key_dict = dict(key_data)
            
            # Добавляем expiry_timestamp_ms для совместимости с тестами и API
            # expiry_date хранится как naive UTC datetime в БД
            if key_dict.get('expiry_date'):
                from datetime import datetime, timezone
                expiry_date = key_dict['expiry_date']
                
                # SQLite возвращает datetime как строку или datetime объект
                if isinstance(expiry_date, str):
                    # Парсим строку в формате 'YYYY-MM-DD HH:MM:SS' или ISO format
                    try:
                        # Пробуем ISO format
                        expiry_date = datetime.fromisoformat(expiry_date.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        # Пробуем стандартный формат SQLite
                        try:
                            expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            # Пробуем формат с микросекундами
                            expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d %H:%M:%S.%f')
                
                # Если naive datetime, считаем что это UTC (как хранится в БД)
                if expiry_date.tzinfo is None:
                    expiry_date = expiry_date.replace(tzinfo=timezone.utc)
                
                # Конвертируем в timestamp в миллисекундах
                key_dict['expiry_timestamp_ms'] = int(expiry_date.timestamp() * 1000)
            else:
                key_dict['expiry_timestamp_ms'] = None

            return key_dict

    except sqlite3.Error as e:

        logging.error(f"Failed to get key by ID {key_id}: {e}")

        return None


def create_user_token(user_id: int, key_id: int) -> str:
    """
    Создает токен для доступа к личному кабинету
    
    Args:
        user_id: ID пользователя
        key_id: ID ключа
        
    Returns:
        Токен доступа (URL-safe строка)
    """
    import secrets
    from datetime import datetime, timezone
    
    try:
        # Генерируем безопасный токен
        token = secrets.token_urlsafe(32)
        
        # Получаем текущее время в UTC
        now = datetime.now(timezone.utc).isoformat()
        
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            cursor = conn.cursor()
            
            # Устанавливаем PRAGMA для предотвращения блокировок
            try:
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.execute("PRAGMA journal_mode=DELETE")
            except sqlite3.Error as e:
                logging.debug(f"Failed to set PRAGMA in create_user_token: {e}")
            
            # Вставляем токен в БД
            cursor.execute('''
                INSERT INTO user_tokens (token, user_id, key_id, created_at, last_used_at, access_count)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (token, user_id, key_id, now, None, 0))
            
            conn.commit()
            logging.info(f"Created token for user {user_id}, key {key_id}")
            
            return token
            
    except sqlite3.Error as e:
        logging.error(f"Failed to create user token for user {user_id}, key {key_id}: {e}")
        raise


def validate_user_token(token: str) -> dict | None:
    """
    Проверяет токен и возвращает информацию о пользователе и ключе
    Также проверяет активность подписки
    
    Args:
        token: Токен доступа
        
    Returns:
        Словарь с данными пользователя и ключа или None если токен недействителен
    """
    try:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Устанавливаем PRAGMA для предотвращения блокировок
            try:
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.execute("PRAGMA journal_mode=DELETE")
            except sqlite3.Error as e:
                logging.debug(f"Failed to set PRAGMA in validate_user_token: {e}")
            
            # Получаем информацию о токене
            cursor.execute('''
                SELECT ut.token, ut.user_id, ut.key_id, ut.created_at, ut.last_used_at, ut.access_count,
                       k.expiry_date, k.status, k.enabled, k.subscription_link
                FROM user_tokens ut
                JOIN vpn_keys k ON ut.key_id = k.key_id
                WHERE ut.token = ?
            ''', (token,))
            
            result = cursor.fetchone()
            
            if not result:
                return None
            
            token_data = dict(result)
            
            # Проверяем активность подписки
            expiry_date_str = token_data.get('expiry_date')
            if expiry_date_str:
                try:
                    expiry_date = datetime.fromisoformat(expiry_date_str.replace('Z', '+00:00'))
                    if expiry_date.tzinfo is None:
                        expiry_date = expiry_date.replace(tzinfo=timezone.utc)
                    
                    current_time = datetime.now(timezone.utc)
                    if expiry_date <= current_time:
                        # Подписка истекла
                        logging.info(f"Token {token[:10]}... expired (key {token_data['key_id']})")
                        return None
                except Exception as e:
                    logging.warning(f"Failed to parse expiry_date for token validation: {e}")
            
            # Проверяем статус ключа
            key_status = token_data.get('status')
            key_enabled = token_data.get('enabled', 1)
            
            if key_status in ['deactivate'] or not key_enabled:
                logging.info(f"Token {token[:10]}... invalid (key {token_data['key_id']} is deactivated)")
                return None
            
            # Обновляем статистику использования токена
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute('''
                UPDATE user_tokens 
                SET last_used_at = ?, access_count = access_count + 1
                WHERE token = ?
            ''', (now, token))
            conn.commit()
            
            return token_data
            
    except sqlite3.Error as e:
        logging.error(f"Failed to validate user token: {e}")
        return None


def update_token_usage(token: str) -> bool:
    """
    Обновляет статистику использования токена
    
    Args:
        token: Токен доступа
        
    Returns:
        True если обновление успешно, False в противном случае
    """
    try:
        from datetime import datetime, timezone
        
        now = datetime.now(timezone.utc).isoformat()
        
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE user_tokens 
                SET last_used_at = ?, access_count = access_count + 1
                WHERE token = ?
            ''', (now, token))
            
            conn.commit()
            return cursor.rowcount > 0
            
    except sqlite3.Error as e:
        logging.error(f"Failed to update token usage: {e}")
        return False


def cleanup_expired_tokens() -> int:
    """
    Историческая функция очистки токенов.
    После перехода на постоянные ссылки личного кабинета не удаляет записи.
    
    Returns:
        Количество удаленных токенов
    """
    logging.debug("cleanup_expired_tokens() called but skipped (persistent cabinet links enabled)")
    return 0


def get_user_tokens(user_id: int) -> list:
    """
    Получает все токены пользователя
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Список словарей с информацией о токенах
    """
    try:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT ut.token, ut.key_id, ut.created_at, ut.last_used_at, ut.access_count,
                       k.expiry_date, k.status, k.host_name
                FROM user_tokens ut
                JOIN vpn_keys k ON ut.key_id = k.key_id
                WHERE ut.user_id = ?
                ORDER BY ut.created_at DESC
            ''', (user_id,))
            
            tokens = cursor.fetchall()
            return [dict(token) for token in tokens]
            
    except sqlite3.Error as e:
        logging.error(f"Failed to get user tokens for user {user_id}: {e}")
        return []


def get_or_create_permanent_token(user_id: int, key_id: int) -> str:
    """
    Получает или создает постоянный токен для пары (user_id, key_id).
    Токен хранится в БД и не меняется при перезагрузках.
    
    Args:
        user_id: ID пользователя
        key_id: ID ключа
    
    Returns:
        Постоянный токен доступа (URL-safe строка)
    """
    import secrets
    from datetime import datetime, timezone
    
    try:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Устанавливаем PRAGMA для предотвращения блокировок
            try:
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.execute("PRAGMA journal_mode=DELETE")
            except sqlite3.Error as e:
                logging.debug(f"Failed to set PRAGMA in get_or_create_permanent_token: {e}")
            
            # Проверяем наличие токена в БД
            cursor.execute('''
                SELECT token FROM user_tokens 
                WHERE user_id = ? AND key_id = ?
                LIMIT 1
            ''', (user_id, key_id))
            
            result = cursor.fetchone()
            
            if result:
                # Токен уже существует - возвращаем его
                token = result['token']
                logging.debug(f"Found existing token for user {user_id}, key {key_id}")
                return token
            
            # Токена нет - создаем новый
            token = secrets.token_urlsafe(32)
            now = datetime.now(timezone.utc).isoformat()
            
            try:
                cursor.execute('''
                    INSERT INTO user_tokens (token, user_id, key_id, created_at, last_used_at, access_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (token, user_id, key_id, now, None, 0))
                
                conn.commit()
                logging.info(f"Created permanent token for user {user_id}, key {key_id}")
                return token
                
            except sqlite3.IntegrityError:
                # Возможна гонка - токен был создан другим процессом
                # Пробуем получить его снова
                cursor.execute('''
                    SELECT token FROM user_tokens 
                    WHERE user_id = ? AND key_id = ?
                    LIMIT 1
                ''', (user_id, key_id))
                
                result = cursor.fetchone()
                if result:
                    logging.debug(f"Token was created by another process for user {user_id}, key {key_id}")
                    return result['token']
                else:
                    # Если все еще нет - генерируем новый токен
                    token = secrets.token_urlsafe(32)
                    cursor.execute('''
                        INSERT INTO user_tokens (token, user_id, key_id, created_at, last_used_at, access_count)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (token, user_id, key_id, now, None, 0))
                    conn.commit()
                    logging.info(f"Created permanent token (retry) for user {user_id}, key {key_id}")
                    return token
            
    except sqlite3.Error as e:
        logging.error(f"Failed to get or create permanent token for user {user_id}, key {key_id}: {e}")
        raise


def get_permanent_token_by_key_id(key_id: int) -> str | None:
    """
    Получает постоянный токен по key_id
    
    Args:
        key_id: ID ключа
    
    Returns:
        Токен доступа или None если не найден
    """
    try:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT token FROM user_tokens 
                WHERE key_id = ?
                LIMIT 1
            ''', (key_id,))
            
            result = cursor.fetchone()
            
            if result:
                return result['token']
            
            return None
            
    except sqlite3.Error as e:
        logging.error(f"Failed to get permanent token by key_id {key_id}: {e}")
        return None


def get_tokens_for_key(key_id: int) -> list[dict]:
    """
    Возвращает список токенов личного кабинета, связанных с ключом.

    Args:
        key_id: идентификатор ключа

    Returns:
        Список словарей с токенами и метаданными
    """
    try:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                '''
                SELECT token, user_id, key_id, created_at, last_used_at, access_count
                FROM user_tokens
                WHERE key_id = ?
                ORDER BY created_at DESC
                ''',
                (key_id,),
            )

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    except sqlite3.Error as e:
        logging.error(f"Failed to get tokens for key_id {key_id}: {e}")
        return []


def validate_permanent_token(token: str) -> dict | None:
    """
    Валидирует постоянный токен и возвращает информацию о пользователе и ключе.
    Проверяет активность подписки и обновляет статистику использования.
    
    Args:
        token: Токен доступа
    
    Returns:
        Словарь с данными пользователя и ключа или None если токен недействителен
    """
    token_preview = token[:10] + "..." if len(token) > 10 else token
    
    try:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Устанавливаем PRAGMA для предотвращения блокировок
            try:
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.execute("PRAGMA journal_mode=DELETE")
            except sqlite3.Error as e:
                logging.debug(f"Failed to set PRAGMA in validate_permanent_token: {e}")
            
            # Получаем информацию о токене
            logging.debug(f"Validating permanent token: {token_preview}")
            
            # Сначала проверяем наличие токена в user_tokens
            cursor.execute('''
                SELECT token, user_id, key_id, created_at, last_used_at, access_count
                FROM user_tokens
                WHERE token = ?
            ''', (token,))
            
            token_row = cursor.fetchone()
            
            if not token_row:
                logging.info(f"Permanent token {token_preview} not found in user_tokens table")
                return None
            
            token_data = dict(token_row)
            user_id = token_data['user_id']
            key_id = token_data['key_id']
            
            # Теперь проверяем наличие ключа через LEFT JOIN
            cursor.execute('''
                SELECT ut.token, ut.user_id, ut.key_id, ut.created_at, ut.last_used_at, ut.access_count,
                       k.expiry_date, k.status, k.enabled, k.subscription_link
                FROM user_tokens ut
                LEFT JOIN vpn_keys k ON ut.key_id = k.key_id
                WHERE ut.token = ?
            ''', (token,))
            
            result = cursor.fetchone()
            
            if not result:
                logging.error(f"Permanent token {token_preview} found in user_tokens but JOIN failed (user_id={user_id}, key_id={key_id})")
                return None
            
            token_data = dict(result)
            
            # Проверяем наличие ключа
            if token_data.get('expiry_date') is None:
                # Ключ не найден - токен есть, но ключ удален
                logging.warning(f"Permanent token {token_preview} found but key_id={key_id} does not exist in vpn_keys (key was deleted)")
                # Возвращаем данные токена без данных ключа для отображения соответствующего сообщения
                token_data['key_deleted'] = True
            else:
                logging.debug(f"Permanent token {token_preview} found with valid key (user_id={user_id}, key_id={key_id})")
            
            # Обновляем статистику использования токена
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute('''
                UPDATE user_tokens 
                SET last_used_at = ?, access_count = access_count + 1
                WHERE token = ?
            ''', (now, token))
            conn.commit()
            
            logging.debug(f"Permanent token {token_preview} validated successfully (user_id={user_id}, key_id={key_id})")
            return token_data
            
    except sqlite3.Error as e:
        logging.error(f"Database error while validating permanent token {token_preview}: {e}", exc_info=True)
        return None
    except Exception as e:
        logging.error(f"Unexpected error while validating permanent token {token_preview}: {e}", exc_info=True)
        return None


# Кэш для шаблонов сообщений (TTL 10 минут)
_template_cache = {}
_template_cache_time = {}
CACHE_TTL_TEMPLATES = 600  # 10 минут


def get_message_template(template_key: str, provision_mode: str = None) -> dict | None:
    """
    Получить шаблон сообщения из БД с кэшированием
    
    Args:
        template_key: ключ шаблона (например: 'purchase_success_key')
        provision_mode: режим предоставления для фильтрации (опционально)
    
    Returns:
        Словарь с данными шаблона или None если не найден
    """
    cache_key = f"{template_key}_{provision_mode or 'all'}"
    current_time = time.time()
    
    # Проверяем кэш
    if cache_key in _template_cache:
        cached_data, cached_time = _template_cache[cache_key]
        if current_time - cached_time < CACHE_TTL_TEMPLATES:
            return cached_data
    
    try:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if provision_mode:
                cursor.execute('''
                    SELECT * FROM message_templates 
                    WHERE template_key = ? AND (provision_mode = ? OR provision_mode IS NULL) AND is_active = 1
                    ORDER BY provision_mode DESC
                    LIMIT 1
                ''', (template_key, provision_mode))
            else:
                cursor.execute('''
                    SELECT * FROM message_templates 
                    WHERE template_key = ? AND (provision_mode IS NULL) AND is_active = 1
                    LIMIT 1
                ''', (template_key,))
            
            result = cursor.fetchone()
            
            if result:
                template = dict(result)
                # Сохраняем в кэш
                _template_cache[cache_key] = (template, current_time)
                return template
            
            return None
            
    except sqlite3.Error as e:
        logging.error(f"Failed to get message template {template_key}: {e}")
        return None


def get_all_message_templates(category: str = None) -> list[dict]:
    """
    Получить все шаблоны сообщений
    
    Args:
        category: категория для фильтрации (опционально)
    
    Returns:
        Список словарей с данными шаблонов
    """
    try:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if category:
                cursor.execute('''
                    SELECT * FROM message_templates 
                    WHERE category = ?
                    ORDER BY template_key, provision_mode
                ''', (category,))
            else:
                cursor.execute('''
                    SELECT * FROM message_templates 
                    ORDER BY category, template_key, provision_mode
                ''')
            
            templates = cursor.fetchall()
            return [dict(template) for template in templates]
            
    except sqlite3.Error as e:
        logging.error(f"Failed to get all message templates: {e}")
        return []


def create_message_template(
    template_key: str,
    category: str,
    template_text: str,
    provision_mode: str = None,
    description: str = None,
    variables: str = None
) -> int | None:
    """
    Создать новый шаблон сообщения
    
    Args:
        template_key: уникальный ключ шаблона
        category: категория шаблона
        template_text: текст шаблона
        provision_mode: режим предоставления (опционально)
        description: описание шаблона (опционально)
        variables: JSON список переменных (опционально)
    
    Returns:
        ID созданного шаблона или None при ошибке
    """
    try:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO message_templates 
                (template_key, category, provision_mode, template_text, description, variables, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            ''', (template_key, category, provision_mode, template_text, description, variables))
            
            conn.commit()
            template_id = cursor.lastrowid
            
            # Очищаем кэш
            _template_cache.clear()
            
            logging.info(f"Created message template {template_key} with ID {template_id}")
            return template_id
            
    except sqlite3.IntegrityError as e:
        logging.error(f"Template {template_key} already exists: {e}")
        return None
    except sqlite3.Error as e:
        logging.error(f"Failed to create message template {template_key}: {e}")
        return None


def update_message_template(
    template_id: int,
    template_text: str = None,
    description: str = None,
    is_active: int = None
) -> bool:
    """
    Обновить шаблон сообщения
    
    Args:
        template_id: ID шаблона
        template_text: новый текст шаблона (опционально)
        description: новое описание (опционально)
        is_active: активен ли шаблон (опционально)
    
    Returns:
        True если успешно, False при ошибке
    """
    try:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            cursor = conn.cursor()
            
            updates = []
            params = []
            
            if template_text is not None:
                updates.append("template_text = ?")
                params.append(template_text)
            
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            
            if is_active is not None:
                updates.append("is_active = ?")
                params.append(is_active)
            
            if not updates:
                return False
            
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(template_id)
            
            cursor.execute(f'''
                UPDATE message_templates 
                SET {', '.join(updates)}
                WHERE template_id = ?
            ''', params)
            
            conn.commit()
            
            # Очищаем кэш
            _template_cache.clear()
            
            logging.info(f"Updated message template {template_id}")
            return cursor.rowcount > 0
            
    except sqlite3.Error as e:
        logging.error(f"Failed to update message template {template_id}: {e}")
        return False


def delete_message_template(template_id: int) -> bool:
    """
    Удалить шаблон сообщения
    
    Args:
        template_id: ID шаблона
    
    Returns:
        True если успешно, False при ошибке
    """
    try:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM message_templates WHERE template_id = ?', (template_id,))
            conn.commit()
            
            # Очищаем кэш
            _template_cache.clear()
            
            logging.info(f"Deleted message template {template_id}")
            return cursor.rowcount > 0
            
    except sqlite3.Error as e:
        logging.error(f"Failed to delete message template {template_id}: {e}")
        return False


def get_message_template_statistics() -> dict:
    """
    Получить статистику шаблонов сообщений
    
    Returns:
        Словарь со статистикой
    """
    try:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM message_templates')
            total = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM message_templates WHERE is_active = 1')
            active = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(DISTINCT category) FROM message_templates')
            categories = cursor.fetchone()[0]
            
            return {
                'total_templates': total,
                'active_templates': active,
                'inactive_templates': total - active,
                'categories_count': categories
            }
            
    except sqlite3.Error as e:
        logging.error(f"Failed to get message template statistics: {e}")
        return {
            'total_templates': 0,
            'active_templates': 0,
            'inactive_templates': 0,
            'categories_count': 0
        }


def get_key_by_email(key_email: str):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute("SELECT * FROM vpn_keys WHERE key_email = ?", (key_email,))

            key_data = cursor.fetchone()

            return dict(key_data) if key_data else None

    except sqlite3.Error as e:

        logging.error(f"Failed to get key by email {key_email}: {e}")

        return None



def update_key_info(key_id: int, new_xui_uuid: str, new_expiry_ms: int, subscription_link: str = None):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            # Используем новую утилиту для корректной конвертации timestamp в UTC
            from shop_bot.utils.datetime_utils import timestamp_to_utc_datetime, calculate_remaining_seconds
            
            expiry_date = timestamp_to_utc_datetime(new_expiry_ms)

            # Пересчёт remaining_seconds с помощью утилиты

            remaining_seconds = calculate_remaining_seconds(new_expiry_ms)

            if subscription_link:
                cursor.execute("UPDATE vpn_keys SET xui_client_uuid = ?, expiry_date = ?, remaining_seconds = ?, subscription_link = ? WHERE key_id = ?", (new_xui_uuid, expiry_date, remaining_seconds, subscription_link, key_id))
            else:
                cursor.execute("UPDATE vpn_keys SET xui_client_uuid = ?, expiry_date = ?, remaining_seconds = ? WHERE key_id = ?", (new_xui_uuid, expiry_date, remaining_seconds, key_id))

            conn.commit()

    except sqlite3.Error as e:

        logging.error(f"Failed to update key {key_id}: {e}")


def update_key_trial_status(key_id: int, is_trial: int):
    """
    Обновляет is_trial и пересчитывает status ключа на основе is_trial и remaining_seconds.
    
    Args:
        key_id: ID ключа для обновления
        is_trial: Новое значение is_trial (0 или 1)
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Получаем текущий ключ для получения remaining_seconds
            cursor.execute("SELECT remaining_seconds FROM vpn_keys WHERE key_id = ?", (key_id,))
            row = cursor.fetchone()
            
            if not row:
                logging.warning(f"Key {key_id} not found for trial status update")
                return False
            
            remaining_seconds = row[0] if row[0] is not None else 0
            
            # Определяем статус ключа на основе is_trial и remaining_seconds
            if is_trial and remaining_seconds > 0:
                status = 'trial-active'
            elif is_trial and remaining_seconds <= 0:
                status = 'trial-ended'
            elif not is_trial and remaining_seconds > 0:
                status = 'pay-active'
            else:
                status = 'pay-ended'
            
            # Обновляем is_trial и status
            cursor.execute(
                "UPDATE vpn_keys SET is_trial = ?, status = ? WHERE key_id = ?",
                (is_trial, status, key_id)
            )
            
            conn.commit()
            logging.info(f"Updated key {key_id}: is_trial={is_trial}, status={status}")
            return True
            
    except sqlite3.Error as e:
        logging.error(f"Failed to update key trial status {key_id}: {e}")
        return False



def get_next_key_number(user_id: int) -> int:
    """
    Получает следующий номер ключа для пользователя с атомарным инкрементом счетчика.
    
    Использует счетчик keys_count из таблицы users для гарантии уникальности номера,
    даже если старые ключи были удалены.
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Следующий номер ключа
    """
    try:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            cursor = conn.cursor()
            
            # Устанавливаем PRAGMA для предотвращения блокировок
            try:
                cursor.execute("PRAGMA busy_timeout=30000")
            except sqlite3.Error as e:
                logging.debug(f"Failed to set PRAGMA busy_timeout in get_next_key_number: {e}")
            
            # Атомарно получаем текущий счетчик и инкрементируем его
            cursor.execute("SELECT keys_count FROM users WHERE telegram_id = ?", (user_id,))
            row = cursor.fetchone()
            
            if row:
                current_count = row[0] or 0
                next_number = current_count + 1
                
                # Атомарно обновляем счетчик
                cursor.execute("UPDATE users SET keys_count = ? WHERE telegram_id = ?", (next_number, user_id))
                conn.commit()
                
                logging.info(f"get_next_key_number: user_id={user_id}, current_count={current_count}, next_number={next_number}")
                return next_number
            else:
                # Пользователь не найден - создаем пользователя с keys_count=0, затем возвращаем 1
                logging.warning(f"get_next_key_number: user {user_id} not found, creating user with keys_count=0")
                try:
                    # Создаем пользователя с keys_count=0
                    cursor.execute("INSERT OR IGNORE INTO users (telegram_id, keys_count) VALUES (?, 0)", (user_id,))
                    conn.commit()
                    # После создания пользователя возвращаем 1 и обновляем счетчик до 1
                    cursor.execute("UPDATE users SET keys_count = 1 WHERE telegram_id = ?", (user_id,))
                    conn.commit()
                    logging.info(f"get_next_key_number: Created user {user_id} with keys_count=1")
                    return 1
                except Exception as e:
                    logging.error(f"get_next_key_number: Failed to create user {user_id}: {e}")
                    # Fallback на старую логику
                    keys = get_user_keys(user_id)
                    return len(keys) + 1
                
    except sqlite3.Error as e:
        logging.error(f"Failed to get next key number for user {user_id}: {e}")
        # Fallback на старую логику
        keys = get_user_keys(user_id)
        return len(keys) + 1



def get_keys_for_host(host_name: str) -> list[dict]:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute("SELECT * FROM vpn_keys WHERE host_name = ?", (host_name,))

            keys = cursor.fetchall()

            return [dict(key) for key in keys]

    except sqlite3.Error as e:

        logging.error(f"Failed to get keys for host '{host_name}': {e}")

        return []



def get_all_vpn_users():

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute("SELECT DISTINCT user_id FROM vpn_keys")

            users = cursor.fetchall()

            return [dict(user) for user in users]

    except sqlite3.Error as e:

        logging.error(f"Failed to get all vpn users: {e}")

        return []



def update_key_status_from_server(key_email: str, xui_client_data):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            if xui_client_data:

                # Используем новую утилиту для корректной конвертации timestamp в UTC
                from shop_bot.utils.datetime_utils import timestamp_to_utc_datetime, calculate_remaining_seconds
                
                expiry_date = timestamp_to_utc_datetime(xui_client_data.expiry_time)

                

                # Определяем статус ключа

                from datetime import timezone

                now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

                is_trial = int(xui_client_data.is_trial) if hasattr(xui_client_data, 'is_trial') else 0

                active = xui_client_data.expiry_time > now_ms

                

                if is_trial and active:

                    status = 'trial-active'

                elif is_trial and not active:

                    status = 'trial-ended'

                elif not is_trial and active:

                    status = 'pay-active'

                else:

                    status = 'pay-ended'

                

                # Вычисляем remaining_seconds с помощью утилиты
                remaining_seconds = calculate_remaining_seconds(xui_client_data.expiry_time)
                
                # Получаем квоту трафика из клиента
                quota_total_gb = None
                quota_remaining_bytes = None
                traffic_down_bytes = None
                
                try:
                    # Пытаемся получить данные о трафике из атрибутов клиента
                    total_bytes = getattr(xui_client_data, 'total', None)
                    if total_bytes and total_bytes > 0:
                        quota_total_gb = round(total_bytes / (1024*1024*1024), 2)
                    
                    down_bytes = getattr(xui_client_data, 'down', None)
                    if down_bytes:
                        traffic_down_bytes = int(down_bytes)
                    
                    up_bytes = getattr(xui_client_data, 'up', None)
                    if total_bytes and up_bytes is not None and down_bytes is not None:
                        quota_remaining_bytes = max(0, int(total_bytes) - (int(up_bytes) + int(down_bytes)))
                except Exception:
                    pass
                
                cursor.execute("UPDATE vpn_keys SET xui_client_uuid = ?, expiry_date = ?, status = ?, remaining_seconds = ?, quota_total_gb = ?, quota_remaining_bytes = ?, traffic_down_bytes = ? WHERE key_email = ?", 

                             (xui_client_data.id, expiry_date, status, remaining_seconds, quota_total_gb, quota_remaining_bytes, traffic_down_bytes, key_email))

            else:

                cursor.execute("DELETE FROM vpn_keys WHERE key_email = ?", (key_email,))

            conn.commit()

    except sqlite3.Error as e:

        logging.error(f"Failed to update key status for {key_email}: {e}")



def get_daily_stats_for_charts(days: int = 30) -> dict:

    stats = {'users': {}, 'keys': {}, 'earned': {}, 'notifications': {}}

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            query_users = """

                SELECT date(registration_date) as day, COUNT(*)

                FROM users

                WHERE registration_date >= date('now', ?)

                GROUP BY day

                ORDER BY day;

            """

            cursor.execute(query_users, (f'-{days} days',))

            for row in cursor.fetchall():

                stats['users'][row[0]] = row[1]



            query_keys = """

                SELECT date(created_date) as day, COUNT(*)

                FROM vpn_keys

                WHERE created_date >= date('now', ?)

                GROUP BY day

                ORDER BY day;

            """

            cursor.execute(query_keys, (f'-{days} days',))

            for row in cursor.fetchall():

                stats['keys'][row[0]] = row[1]



            # Заработано в RUB по дням (только оплаченные)

            query_earned = """

                SELECT date(created_date) as day, COALESCE(SUM(amount_rub), 0)

                FROM transactions

                WHERE created_date >= date('now', ?) AND status = 'paid'

                GROUP BY day

                ORDER BY day;

            """

            cursor.execute(query_earned, (f'-{days} days',))

            for row in cursor.fetchall():

                stats['earned'][row[0]] = row[1] or 0



            # Новые уведомления по дням

            query_notifications = """

                SELECT date(created_date) as day, COUNT(*)

                FROM notifications

                WHERE created_date >= date('now', ?)

                GROUP BY day

                ORDER BY day;

            """

            cursor.execute(query_notifications, (f'-{days} days',))

            for row in cursor.fetchall():

                stats['notifications'][row[0]] = row[1]

    except sqlite3.Error as e:

        logging.error(f"Failed to get daily stats for charts: {e}")



    # Преобразуем в формат для графиков

    from datetime import datetime, timedelta



    # Создаем список всех дат за последние N дней

    dates = []

    for i in range(days):

        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')

        dates.append(date)

    dates.reverse()  # От старых к новым



    # Создаем массивы данных для графиков

    new_users = []

    new_keys = []

    earned_sum = []

    new_notifications = []



    for date in dates:

        new_users.append(stats['users'].get(date, 0))

        new_keys.append(stats['keys'].get(date, 0))

        earned_sum.append(round(stats['earned'].get(date, 0) or 0, 2))

        new_notifications.append(stats['notifications'].get(date, 0))



    return {

        'dates': dates,

        'new_users': new_users,

        'new_keys': new_keys,

        'earned_sum': earned_sum,

        'new_notifications': new_notifications

    }





def get_recent_transactions(limit: int = 15) -> list[dict]:

    transactions = []

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            query = """

                SELECT

                    k.key_id,

                    k.host_name,

                    k.created_date,

                    u.telegram_id,

                    u.username

                FROM vpn_keys k

                JOIN users u ON k.user_id = u.telegram_id

                ORDER BY k.created_date DESC

                LIMIT ?;

            """

            cursor.execute(query, (limit,))

            for row in cursor.fetchall():
                tx = dict(row)
                tx['created_date'] = _parse_db_datetime(tx.get('created_date'))
                transactions.append(tx)

    except sqlite3.Error as e:

        logging.error(f"Failed to get recent transactions: {e}")

    return transactions



def log_notification(user_id: int, username: str | None, notif_type: str, title: str, message: str, status: str = 'sent', meta: dict | None = None, key_id: int | None = None, marker_hours: int | None = None) -> int:

    try:

        with _get_db_connection() as conn:

            cursor = conn.cursor()
            
            # Устанавливаем PRAGMA настройки для предотвращения блокировок
            try:
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.execute("PRAGMA journal_mode=DELETE")
            except sqlite3.Error as e:
                logging.debug(f"Failed to set PRAGMA settings in log_notification: {e}")

            from datetime import timezone, timedelta

            local_tz = timezone(timedelta(hours=3))

            local_now = datetime.now(local_tz)

            cursor.execute(

                """

                INSERT INTO notifications (user_id, username, type, title, message, status, meta, key_id, marker_hours, created_date)

                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

                """,

                (user_id, username, notif_type, title, message, status, json.dumps(meta or {}), key_id, marker_hours, local_now)

            )

            conn.commit()

            return cursor.lastrowid

    except sqlite3.Error as e:

        logging.error(f"Failed to log notification for user {user_id}: {e}")

        return 0



def get_paginated_notifications(page: int = 1, per_page: int = 15) -> tuple[list[dict], int]:

    offset = (page - 1) * per_page

    notifications: list[dict] = []

    total = 0

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM notifications")

            total = cursor.fetchone()[0] or 0

            cursor.execute(

                """

                SELECT n.*, u.username AS joined_username

                FROM notifications n

                LEFT JOIN users u ON n.user_id = u.telegram_id

                ORDER BY n.created_date DESC

                LIMIT ? OFFSET ?

                """,

                (per_page, offset)

            )

            for row in cursor.fetchall():

                item = dict(row)

                # Try parse meta

                meta_str = item.get('meta')

                if meta_str:

                    try:

                        item['meta'] = json.loads(meta_str)

                    except Exception:

                        item['meta'] = {}

                # Prefer joined username

                if item.get('joined_username'):

                    item['username'] = item['joined_username']

                # Normalize created_date
                item['created_date'] = _parse_db_datetime(item.get('created_date'))

                notifications.append(item)

    except sqlite3.Error as e:

        logging.error(f"Failed to get paginated notifications: {e}")

    return notifications, total



def get_notification_by_id(notification_id: int) -> dict | None:

    """Получить уведомление по ID"""

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute(

                """

                SELECT n.*, u.username AS joined_username

                FROM notifications n

                LEFT JOIN users u ON n.user_id = u.telegram_id

                WHERE n.notification_id = ?

                """,

                (notification_id,)

            )

            row = cursor.fetchone()

            if not row:

                return None

            

            item = dict(row)

            # Try parse meta

            meta_str = item.get('meta')

            if meta_str:

                try:

                    item['meta'] = json.loads(meta_str)

                except Exception:

                    item['meta'] = {}

            # Prefer joined username

            if item.get('joined_username'):

                item['username'] = item['joined_username']

            # Normalize created_date
            item['created_date'] = _parse_db_datetime(item.get('created_date'))

            return item

    except sqlite3.Error as e:

        logging.error(f"Failed to get notification by ID {notification_id}: {e}")

        return None



def add_support_thread(user_id: int, thread_id: int):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("INSERT OR REPLACE INTO support_threads (user_id, thread_id) VALUES (?, ?)", (user_id, thread_id))

            conn.commit()

    except sqlite3.Error as e:

        logging.error(f"Failed to add support thread for user {user_id}: {e}")



def get_support_thread_id(user_id: int) -> int | None:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("SELECT thread_id FROM support_threads WHERE user_id = ?", (user_id,))

            result = cursor.fetchone()

            return result[0] if result else None

    except sqlite3.Error as e:

        logging.error(f"Failed to get support thread_id for user {user_id}: {e}")

        return None



def get_user_id_by_thread(thread_id: int) -> int | None:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("SELECT user_id FROM support_threads WHERE thread_id = ?", (thread_id,))

            result = cursor.fetchone()

            return result[0] if result else None

    except sqlite3.Error as e:

        logging.error(f"Failed to get user_id for thread {thread_id}: {e}")

        return None



def get_latest_transaction(user_id: int) -> dict | None:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY created_date DESC LIMIT 1", (user_id,))

            transaction = cursor.fetchone()

            return dict(transaction) if transaction else None

    except sqlite3.Error as e:

        logging.error(f"Failed to get latest transaction for user {user_id}: {e}")

        return None





def search_users(query: str, limit: int = 10) -> list[dict]:

    query = (query or '').strip()

    if not query:

        return []

    try:

        try:

            limit_value = int(limit)

        except (TypeError, ValueError):

            limit_value = 10

        limit_value = max(1, min(limit_value, 50))

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            like_id = f"%{query}%"

            like_username = f"%{query.lower()}%"

            cursor.execute(

                """

                SELECT u.telegram_id,

                       u.username,

                       u.is_banned,

                       u.agreed_to_documents,

                       u.subscription_status,

                       COALESCE(u.balance, 0) AS balance

                FROM users u

                WHERE CAST(u.telegram_id AS TEXT) LIKE ?

                   OR (u.username IS NOT NULL AND LOWER(u.username) LIKE ?)

                ORDER BY u.registration_date DESC

                LIMIT ?

                """,

                (like_id, like_username, limit_value)

            )

            return [dict(row) for row in cursor.fetchall()]

    except sqlite3.Error as e:

        logger.error(f"Failed to search users with query '{query}': {e}")

        return []



def get_all_users() -> list[dict]:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            # Получаем пользователей с подсчетом уведомлений и ключей

            cursor.execute("""

                SELECT u.*, 

                       COALESCE(COUNT(DISTINCT n.notification_id), 0) as notifications_count,

                       COALESCE(COUNT(DISTINCT vk.key_id), 0) as user_keys_count,

                       GROUP_CONCAT(DISTINCT vk.key_id) as user_keys,

                       ug.group_name,

                       ug.group_description

                FROM users u

                LEFT JOIN notifications n ON u.telegram_id = n.user_id

                LEFT JOIN vpn_keys vk ON u.telegram_id = vk.user_id

                LEFT JOIN user_groups ug ON u.group_id = ug.group_id

                GROUP BY u.telegram_id, u.trial_days_given, u.trial_reuses_count, ug.group_name, ug.group_description

                ORDER BY u.registration_date DESC

            """)

            users = []

            for row in cursor.fetchall():

                user_dict = dict(row)

                # Преобразуем user_keys в список

                if user_dict.get('user_keys'):

                    user_dict['user_keys'] = [int(kid) for kid in user_dict['user_keys'].split(',') if kid]

                else:

                    user_dict['user_keys'] = []

                if user_dict.get('registration_date'):
                    user_dict['registration_date'] = _parse_db_datetime(user_dict['registration_date'])

                users.append(user_dict)

            return users

    except sqlite3.Error as e:

        logging.error(f"Failed to get all users: {e}")

        return []



def ban_user(telegram_id: int):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("UPDATE users SET is_banned = 1 WHERE telegram_id = ?", (telegram_id,))

            conn.commit()

    except sqlite3.Error as e:

        logging.error(f"Failed to ban user {telegram_id}: {e}")



def unban_user(telegram_id: int):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("UPDATE users SET is_banned = 0 WHERE telegram_id = ?", (telegram_id,))

            conn.commit()

    except sqlite3.Error as e:

        logging.error(f"Failed to unban user {telegram_id}: {e}")



def delete_user_keys(user_id: int):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()
            
            # Сначала получаем key_id всех ключей пользователя для удаления токенов
            cursor.execute("SELECT key_id FROM vpn_keys WHERE user_id = ?", (user_id,))
            key_ids = [row[0] for row in cursor.fetchall()]
            
            # Удаляем токены для всех ключей пользователя
            if key_ids:
                placeholders = ','.join(['?'] * len(key_ids))
                cursor.execute(f"DELETE FROM user_tokens WHERE key_id IN ({placeholders})", key_ids)
                deleted_tokens = cursor.rowcount
                logging.info(f"Deleted {deleted_tokens} tokens for user {user_id} before deleting keys")

            # Удаляем ключи
            cursor.execute("DELETE FROM vpn_keys WHERE user_id = ?", (user_id,))
            deleted_keys = cursor.rowcount

            conn.commit()
            logging.info(f"Deleted {deleted_keys} keys for user {user_id}")

    except sqlite3.Error as e:

        logging.error(f"Failed to delete keys for user {user_id}: {e}")



def get_paginated_keys(page: int = 1, per_page: int = 15) -> tuple[list[dict], int]:

    """Получает ключи с пагинацией"""

    offset = (page - 1) * per_page

    keys = []

    total = 0

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            

            cursor.execute("SELECT COUNT(*) FROM vpn_keys")

            total = cursor.fetchone()[0]



            # Ensure quota column exists

            try:

                cursor.execute("ALTER TABLE vpn_keys ADD COLUMN quota_remaining_bytes INTEGER")

            except Exception:

                pass



            query = """

                SELECT 

                    vk.key_id,

                    vk.user_id,

                    u.username,

                    vk.key_email,

                    vk.host_name,

                    vk.plan_name,

                    vk.price,

                    vk.connection_string,

                    vk.created_date,

                    vk.expiry_date,

                    vk.remaining_seconds,

                    vk.quota_remaining_bytes,

                    vk.quota_total_gb,

                    vk.traffic_down_bytes,

                    vk.is_trial,

                    vk.protocol,

                    vk.status,

                    vk.enabled,

                    vk.subscription,

                    vk.subscription_link,

                    (SELECT COUNT(*) FROM vpn_keys vk2 WHERE vk2.user_id = vk.user_id) as user_keys_count

                FROM vpn_keys vk

                LEFT JOIN users u ON vk.user_id = u.telegram_id

                ORDER BY vk.created_date DESC 

                LIMIT ? OFFSET ?

            """

            cursor.execute(query, (per_page, offset))

            

            for row in cursor.fetchall():

                key_dict = dict(row)

                

                # Преобразуем даты в datetime объекты
                if key_dict.get('created_date'):
                    key_dict['created_date'] = _parse_db_datetime(key_dict['created_date'])

                if key_dict.get('expiry_date'):
                    parsed_expiry = _parse_db_datetime(key_dict['expiry_date'])
                    if parsed_expiry is not None:
                        key_dict['expiry_date'] = parsed_expiry

                

                keys.append(key_dict)

            

            return keys, total

            

    except sqlite3.Error as e:

        logging.error(f"Failed to get paginated keys: {e}")

        return [], 0



def update_key_remaining_seconds(key_id: int, remaining_seconds: int, expiry_dt: datetime | None = None) -> None:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            if expiry_dt is not None:

                cursor.execute(

                    "UPDATE vpn_keys SET remaining_seconds = ?, expiry_date = ? WHERE key_id = ?",

                    (remaining_seconds, expiry_dt, key_id)

                )

            else:

                cursor.execute(

                    "UPDATE vpn_keys SET remaining_seconds = ? WHERE key_id = ?",

                    (remaining_seconds, key_id)

                )

            conn.commit()

    except sqlite3.Error as e:

        logging.error(f"Failed to update remaining_seconds for key_id={key_id}: {e}")



def update_key_quota(key_id: int, quota_total_gb: float | None, traffic_down_bytes: int | None, quota_remaining_bytes: int | None) -> None:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            try:

                cursor.execute("ALTER TABLE vpn_keys ADD COLUMN quota_total_gb REAL")

            except Exception:

                pass

            try:

                cursor.execute("ALTER TABLE vpn_keys ADD COLUMN traffic_down_bytes INTEGER")

            except Exception:

                pass

            try:

                cursor.execute("ALTER TABLE vpn_keys ADD COLUMN quota_remaining_bytes INTEGER")

            except Exception:

                pass

            cursor.execute(

                "UPDATE vpn_keys SET quota_total_gb = ?, traffic_down_bytes = ?, quota_remaining_bytes = ? WHERE key_id = ?",

                (quota_total_gb, traffic_down_bytes, quota_remaining_bytes, key_id)

            )

            conn.commit()

    except sqlite3.Error as e:

        logging.error(f"Failed to update quota for key_id={key_id}: {e}")



def update_key_enabled_status(key_id: int, enabled: bool) -> None:

    """Обновляет статус включения/отключения ключа в базе данных"""

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            try:

                cursor.execute("ALTER TABLE vpn_keys ADD COLUMN enabled INTEGER DEFAULT 1")

            except Exception:

                pass

            

            if not enabled:

                # При отключении ключа устанавливаем remaining_seconds на 0 (текущее время)

                from datetime import timezone as _tz

                now_ms = int(datetime.now(_tz.utc).timestamp() * 1000)

                remaining_seconds = 0

                expiry_date = datetime.fromtimestamp(now_ms / 1000)

                

                cursor.execute(

                    "UPDATE vpn_keys SET enabled = ?, remaining_seconds = ?, expiry_date = ? WHERE key_id = ?",

                    (0, remaining_seconds, expiry_date, key_id)

                )

            else:

                # При включении ключа обновляем только статус

                cursor.execute(

                    "UPDATE vpn_keys SET enabled = ? WHERE key_id = ?",

                    (1, key_id)

                )

            conn.commit()

    except sqlite3.Error as e:

        logging.error(f"Failed to update enabled status for key_id={key_id}: {e}")



def update_key_status(key_id: int, status: str) -> None:

    """Обновляет статус ключа в базе данных"""

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            try:

                cursor.execute("ALTER TABLE vpn_keys ADD COLUMN status TEXT")

            except Exception:

                pass

            cursor.execute(

                "UPDATE vpn_keys SET status = ? WHERE key_id = ?",

                (status, key_id)

            )

            conn.commit()

    except sqlite3.Error as e:

        logging.error(f"Failed to update status for key_id={key_id}: {e}")


def fix_key_fields(key_id: int) -> bool:
    """Исправляет поля status, remaining_seconds, start_date для существующего ключа"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Получаем данные ключа
            cursor.execute("SELECT * FROM vpn_keys WHERE key_id = ?", (key_id,))
            key_data = cursor.fetchone()
            
            if not key_data:
                logging.error(f"Key {key_id} not found")
                return False
            
            # Получаем названия колонок
            cursor.execute("PRAGMA table_info(vpn_keys)")
            columns_info = cursor.fetchall()
            columns = [col[1] for col in columns_info]
            
            # Создаем словарь с данными ключа
            key_dict = dict(zip(columns, key_data))
            
            # Вычисляем remaining_seconds
            expiry_date_str = key_dict.get('expiry_date')
            if expiry_date_str:
                try:
                    expiry_date = _parse_db_datetime(expiry_date_str)
                    if expiry_date is None:
                        raise ValueError("expiry_date parsing returned None")
                    now = datetime.now(timezone.utc)
                    remaining_seconds = max(0, int((expiry_date - now).total_seconds()))
                except Exception as e:
                    logging.error(f"Error calculating remaining_seconds for key {key_id}: {e}")
                    remaining_seconds = 0
            else:
                remaining_seconds = 0
            
            # Определяем статус
            is_trial = key_dict.get('is_trial', 0)
            if is_trial and remaining_seconds > 0:
                status = 'trial-active'
            elif is_trial and remaining_seconds <= 0:
                status = 'trial-ended'
            elif not is_trial and remaining_seconds > 0:
                status = 'pay-active'
            else:
                status = 'pay-ended'
            
            # Устанавливаем start_date если его нет
            start_date = key_dict.get('start_date')
            if not start_date:
                created_date = key_dict.get('created_date')
                if created_date:
                    start_date = created_date
                else:
                    from datetime import timezone, timedelta
                    local_tz = timezone(timedelta(hours=3))
                    start_date = datetime.now(local_tz)
            
            # Обновляем поля
            cursor.execute("""
                UPDATE vpn_keys 
                SET status = ?, remaining_seconds = ?, start_date = ?
                WHERE key_id = ?
            """, (status, remaining_seconds, start_date, key_id))
            
            conn.commit()
            logging.info(f"Fixed key {key_id}: status={status}, remaining_seconds={remaining_seconds}, start_date={start_date}")
            return True
            
    except Exception as e:
        logging.error(f"Error fixing key {key_id}: {e}")
        return False


def get_key_enabled_status(key_id: int) -> bool:

    """Получает статус включения/отключения ключа из базы данных"""

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute("SELECT enabled FROM vpn_keys WHERE key_id = ?", (key_id,))

            row = cursor.fetchone()

            if row:

                return bool(row['enabled'])

            return True  # По умолчанию включен

    except sqlite3.Error as e:

        logging.error(f"Failed to get enabled status for key_id={key_id}: {e}")

        return True



def hash_password(password: str) -> str:

    """Хеширует пароль с использованием bcrypt"""

    try:

        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    except Exception as e:

        logging.error(f"Failed to hash password: {e}")

        return password  # Fallback для совместимости



def verify_password(password: str, hashed_password: str) -> bool:

    """Проверяет пароль против хеша"""

    try:

        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

    except Exception as e:

        logging.error(f"Failed to verify password: {e}")

        return False



def verify_admin_credentials(username: str, password: str) -> bool:

    """Проверяет учетные данные администратора"""

    try:

        stored_username = get_setting("panel_login")

        stored_password = get_setting("panel_password")

        

        if not stored_username or not stored_password:

            return False

            

        # Проверяем имя пользователя

        if username != stored_username:

            return False

            

        # Проверяем пароль (поддерживаем как старые, так и новые хеши)

        if stored_password.startswith('$2b$'):

            # Новый формат с bcrypt

            return verify_password(password, stored_password)

        else:

            # Старый формат - обновляем на лету

            if password == stored_password:

                # Обновляем пароль на хешированный

                update_setting("panel_password", hash_password(password))

                return True

            return False

            

    except Exception as e:

        logging.error(f"Failed to verify admin credentials: {e}")

        return False



def get_ton_manifest() -> dict:

    """Получить настройки Ton manifest из базы данных"""

    try:

        settings = get_all_settings()

        domain = get_global_domain()
        if not domain:
            logging.warning(
                "global_domain не настроен. TON manifest будет использовать значения по умолчанию или из настроек app_url."
            )
        
        return {

            "url": settings.get("app_url", domain or ""),

            "name": settings.get("ton_manifest_name", "Dark Maximus Shop Bot"),

            "iconUrl": settings.get("ton_manifest_icon_url", f"{domain}/static/logo.png" if domain else ""),

            "termsOfUseUrl": settings.get("ton_manifest_terms_url", f"{domain}/terms" if domain else ""),

            "privacyPolicyUrl": settings.get("ton_manifest_privacy_url", f"{domain}/privacy" if domain else "")

        }

    except Exception as e:

        logging.error(f"Failed to get Ton manifest settings: {e}")

        domain = get_global_domain()
        if not domain:
            logging.warning(
                "global_domain не настроен. TON manifest будет использовать значения по умолчанию."
            )
        
        return {

            "url": domain or "",

            "name": "Dark Maximus Shop Bot",

            "iconUrl": f"{domain}/static/logo.png" if domain else "",

            "termsOfUseUrl": f"{domain}/terms" if domain else "",

            "privacyPolicyUrl": f"{domain}/privacy" if domain else ""

        }


def get_all_plans() -> list[dict]:
    """Получить все планы для выпадающих списков"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT plan_id, host_name, plan_name, months, price, days, traffic_gb, hours
                FROM plans
                ORDER BY host_name, plan_name
            ''')
            
            return [dict(row) for row in cursor.fetchall()]
            
    except sqlite3.Error as e:
        logging.error(f"Failed to get all plans: {e}")
        return []


def can_user_use_promo_code(user_id: int, promo_code: str, bot: str) -> dict:
    """Проверить, может ли пользователь использовать промокод"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Устанавливаем режим журналирования
            cursor.execute("PRAGMA journal_mode=DELETE")
            
            # Начинаем транзакцию с блокировкой
            cursor.execute("BEGIN IMMEDIATE")
            
            try:
                # Получаем промокод
                cursor.execute('''
                    SELECT * FROM promo_codes 
                    WHERE code = ? AND is_active = 1
                ''', (promo_code,))
                
                promo = cursor.fetchone()
                if not promo:
                    cursor.execute("ROLLBACK")
                    return {'can_use': False, 'message': 'Промокод не найден или неактивен'}
                
                promo_dict = dict(promo)
                
                # Проверяем, использовал ли пользователь этот промокод в этом боте
                cursor.execute('''
                    SELECT usage_id, status, plan_id, discount_amount, discount_percent, discount_bonus
                    FROM promo_code_usage 
                    WHERE promo_id = ? AND user_id = ? AND bot = ?
                ''', (promo_dict['promo_id'], user_id, bot))
                
                usage_result = cursor.fetchone()
                if usage_result:
                    # Если есть запись со статусом 'used' - промокод уже использован
                    if usage_result['status'] == 'used':
                        cursor.execute("ROLLBACK")
                        return {'can_use': False, 'message': 'Вы уже использовали этот промокод'}
                    # Если есть запись со статусом 'applied' - возвращаем данные для обновления
                    elif usage_result['status'] == 'applied':
                        cursor.execute("ROLLBACK")
                        return {
                            'can_use': True, 
                            'message': 'Промокод уже применен, обновляем запись',
                            'existing_usage_id': usage_result['usage_id'],
                            'promo_data': {
                                'promo_id': promo_dict['promo_id'],
                                'discount_amount': usage_result['discount_amount'],
                                'discount_percent': usage_result['discount_percent'],
                                'discount_bonus': usage_result['discount_bonus']
                            }
                        }
                
                # Проверяем общий лимит использований для этого бота
                cursor.execute('''
                    SELECT COUNT(*) as total_usage
                    FROM promo_code_usage 
                    WHERE promo_id = ? AND bot = ?
                ''', (promo_dict['promo_id'], bot))
                
                total_usage_result = cursor.fetchone()
                if total_usage_result and total_usage_result['total_usage'] >= promo_dict['usage_limit_per_bot']:
                    cursor.execute("ROLLBACK")
                    return {'can_use': False, 'message': 'Лимит использований промокода исчерпан'}
                
                # Проверяем срок действия промокода (valid_until)
                if promo_dict.get('valid_until'):
                    try:
                        valid_until = _parse_db_datetime(promo_dict['valid_until'])
                        if valid_until and datetime.now(timezone.utc) > valid_until:
                            cursor.execute("ROLLBACK")
                            return {'can_use': False, 'message': 'Срок действия промокода истек'}
                    except (ValueError, TypeError):
                        pass  # Если не удалось распарсить дату, пропускаем проверку
                
                # Проверяем срок сгорания промокода (burn_after)
                if promo_dict.get('burn_after_value') and promo_dict.get('burn_after_unit'):
                    try:
                        burn_value = int(promo_dict['burn_after_value'])
                        burn_unit = promo_dict['burn_after_unit']
                        
                        # Получаем дату создания промокода
                        created_at = _parse_db_datetime(promo_dict['created_at'])
                        if created_at is None:
                            raise ValueError('invalid created_at')
                        
                        # Вычисляем дату сгорания
                        if burn_unit == 'min':
                            burn_until = created_at + timedelta(minutes=burn_value)
                        elif burn_unit == 'hour':
                            burn_until = created_at + timedelta(hours=burn_value)
                        elif burn_unit == 'day':
                            burn_until = created_at + timedelta(days=burn_value)
                        else:
                            burn_until = None
                        
                        if burn_until and datetime.now(timezone.utc) > burn_until:
                            cursor.execute("ROLLBACK")
                            return {'can_use': False, 'message': 'Время использования промокода истекло'}
                    except (ValueError, TypeError):
                        pass  # Если не удалось распарсить, пропускаем проверку
                
                # Проверяем группу пользователя
                if promo_dict.get('target_group_ids'):
                    try:
                        target_groups = json.loads(promo_dict['target_group_ids'])
                        if target_groups:  # Если указаны группы
                            # Получаем группу пользователя
                            cursor.execute('''
                                SELECT group_id FROM users WHERE telegram_id = ?
                            ''', (user_id,))
                            user_group_result = cursor.fetchone()
                            
                            if not user_group_result or user_group_result[0] not in target_groups:
                                cursor.execute("ROLLBACK")
                                return {'can_use': False, 'message': 'Промокод недоступен для вашей группы пользователей'}
                    except (json.JSONDecodeError, TypeError):
                        pass  # Если не удалось распарсить группы, пропускаем проверку
                
                # Десериализуем данные
                promo_dict['vpn_plan_id'] = _deserialize_vpn_plan_id(promo_dict.get('vpn_plan_id'))
                if promo_dict.get('tariff_code'):
                    try:
                        promo_dict['tariff_code'] = json.loads(promo_dict['tariff_code'])
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                # Десериализуем target_group_ids
                if promo_dict.get('target_group_ids'):
                    try:
                        promo_dict['target_group_ids'] = json.loads(promo_dict['target_group_ids'])
                    except (json.JSONDecodeError, TypeError):
                        promo_dict['target_group_ids'] = []
                
                cursor.execute("COMMIT")
                return {
                    'can_use': True, 
                    'message': 'Промокод можно использовать',
                    'promo_data': promo_dict
                }
                
            except Exception as e:
                cursor.execute("ROLLBACK")
                raise e
            
    except sqlite3.Error as e:
        logging.error(f"Failed to check promo code usage: {e}")
        return {'can_use': False, 'message': 'Ошибка проверки промокода'}


def update_keys_status_by_expiry():
    """
    Обновляет статус всех ключей на основе реального времени истечения.
    Вызывается для синхронизации статуса в БД с реальным временем.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # БЕЗОПАСНАЯ ПРОВЕРКА: существует ли колонка status
            if not _column_exists(cursor, 'vpn_keys', 'status'):
                logger.warning("Column 'status' does not exist in vpn_keys table. Skipping status update.")
                return 0
            
            # Получаем все ключи с их временем истечения
            cursor.execute("""
                SELECT key_id, expiry_date, is_trial, status 
                FROM vpn_keys 
                WHERE status IS NOT NULL
            """)
            
            keys = cursor.fetchall()
            current_time = datetime.now()
            updated_count = 0
            
            for key_id, expiry_date_str, is_trial, current_status in keys:
                try:
                    expiry_date = _parse_db_datetime(expiry_date_str)
                    # Убираем timezone info для корректного сравнения
                    if expiry_date.tzinfo is not None:
                        expiry_date = expiry_date.replace(tzinfo=None)
                    
                    # Определяем новый статус на основе времени истечения
                    is_expired = expiry_date <= current_time
                    
                    if is_trial:
                        new_status = 'trial-ended' if is_expired else 'trial-active'
                    else:
                        new_status = 'pay-ended' if is_expired else 'pay-active'
                    
                    # Обновляем только если статус изменился
                    if new_status != current_status:
                        cursor.execute(
                            "UPDATE vpn_keys SET status = ? WHERE key_id = ?",
                            (new_status, key_id)
                        )
                        updated_count += 1
                        logging.debug(f"Updated key {key_id} status from {current_status} to {new_status}")
                        
                except Exception as e:
                    logging.error(f"Error processing key {key_id}: {e}")
                    continue
            
            conn.commit()
            if updated_count > 0:
                logging.info(f"Updated status for {updated_count} keys based on expiry time")
            
            return updated_count
            
    except sqlite3.Error as e:
        logging.error(f"Database error while updating keys status: {e}")
        return 0


# ============================================
# Функции для работы с видеоинструкциями
# ============================================

def get_all_video_instructions():
    """Получает список всех видеоинструкций"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT video_id, title, filename, poster_filename, file_size_mb, 
                       created_at, updated_at 
                FROM video_instructions 
                ORDER BY created_at DESC
            """)
            videos = [dict(row) for row in cursor.fetchall()]
            return videos
    except sqlite3.Error as e:
        logging.error(f"Failed to get video instructions: {e}")
        return []


def get_video_instruction_by_id(video_id: int):
    """Получает видеоинструкцию по ID"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT video_id, title, filename, poster_filename, file_size_mb, 
                       created_at, updated_at 
                FROM video_instructions 
                WHERE video_id = ?
            """, (video_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get video instruction by id {video_id}: {e}")
        return None


def create_video_instruction(title: str, filename: str, poster_filename: str = None, file_size_mb: float = None):
    """Создает новую видеоинструкцию"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO video_instructions (title, filename, poster_filename, file_size_mb) 
                VALUES (?, ?, ?, ?)
            """, (title, filename, poster_filename, file_size_mb))
            conn.commit()
            video_id = cursor.lastrowid
            logging.info(f"Created video instruction: {video_id}")
            return video_id
    except sqlite3.Error as e:
        logging.error(f"Failed to create video instruction: {e}")
        return None


def update_video_instruction(video_id: int, title: str = None, filename: str = None, 
                             poster_filename: str = None, file_size_mb: float = None):
    """Обновляет видеоинструкцию"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Строим запрос динамически, обновляя только переданные поля
            updates = []
            params = []
            
            if title is not None:
                updates.append("title = ?")
                params.append(title)
            if filename is not None:
                updates.append("filename = ?")
                params.append(filename)
            if poster_filename is not None:
                updates.append("poster_filename = ?")
                params.append(poster_filename)
            if file_size_mb is not None:
                updates.append("file_size_mb = ?")
                params.append(file_size_mb)
            
            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(video_id)
                
                query = f"UPDATE video_instructions SET {', '.join(updates)} WHERE video_id = ?"
                cursor.execute(query, params)
                conn.commit()
                logging.info(f"Updated video instruction: {video_id}")
                return True
            return False
    except sqlite3.Error as e:
        logging.error(f"Failed to update video instruction {video_id}: {e}")
        return False


def delete_video_instruction(video_id: int):
    """Удаляет видеоинструкцию"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM video_instructions WHERE video_id = ?", (video_id,))
            conn.commit()
            logging.info(f"Deleted video instruction: {video_id}")
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to delete video instruction {video_id}: {e}")
        return False


def video_instruction_exists(filename: str):
    """Проверяет, существует ли видеоинструкция с таким filename"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM video_instructions WHERE filename = ?", (filename,))
            count = cursor.fetchone()[0]
            return count > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to check video instruction existence: {e}")
        return False


# ============================================
# Функции для работы с настройками отображения инструкций
# ============================================

def get_instruction_display_setting(platform: str) -> bool:
    """Получает настройку отображения инструкции для платформы в боте"""
    try:
        key = f"instruction_{platform}_show_in_bot"
        value = get_setting(key)
        return value == "true" if value else True  # По умолчанию включено
    except Exception as e:
        logging.error(f"Failed to get instruction display setting for {platform}: {e}")
        return True

def set_instruction_display_setting(platform: str, show_in_bot: bool):
    """Устанавливает настройку отображения инструкции для платформы в боте"""
    try:
        key = f"instruction_{platform}_show_in_bot"
        value = "true" if show_in_bot else "false"
        update_setting(key, value)
        logging.info(f"Updated instruction display setting for {platform}: {show_in_bot}")
    except Exception as e:
        logging.error(f"Failed to set instruction display setting for {platform}: {e}")

def get_video_instructions_display_setting() -> bool:
    """Получает настройку отображения кнопки 'Видеоинструкции' в боте"""
    try:
        value = get_setting("video_instructions_show_in_bot")
        return value == "true" if value else True  # По умолчанию включено
    except Exception as e:
        logging.error(f"Failed to get video instructions display setting: {e}")
        return True

def set_video_instructions_display_setting(show_in_bot: bool):
    """Устанавливает настройку отображения кнопки 'Видеоинструкции' в боте"""
    try:
        value = "true" if show_in_bot else "false"
        update_setting("video_instructions_show_in_bot", value)
        logging.info(f"Updated video instructions display setting: {show_in_bot}")
    except Exception as e:
        logging.error(f"Failed to set video instructions display setting: {e}")

def has_any_instructions_enabled() -> bool:
    """Проверяет, есть ли хотя бы одна включенная инструкция (текстовая или видео)"""
    try:
        # Проверяем текстовые инструкции для всех платформ
        platforms = ['android', 'ios', 'windows', 'macos', 'linux']
        for platform in platforms:
            if get_instruction_display_setting(platform):
                return True
        
        # Проверяем видеоинструкции
        if get_video_instructions_display_setting():
            return True
        
        # Если ни одна инструкция не включена
        return False
    except Exception as e:
        logging.error(f"Failed to check if any instructions are enabled: {e}")
        # В случае ошибки возвращаем True, чтобы не скрывать кнопку
        return True


# ==================== ФУНКЦИИ ДЛЯ РАБОТЫ С ГРУППАМИ ПОЛЬЗОВАТЕЛЕЙ ====================

def get_all_user_groups() -> list[dict]:
    """Получить все группы пользователей с количеством пользователей в каждой группе"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    ug.group_id,
                    ug.group_name,
                    ug.group_description,
                    ug.is_default,
                    ug.created_date,
                    ug.group_code,
                    COUNT(u.telegram_id) as user_count
                FROM user_groups ug
                LEFT JOIN users u ON ug.group_id = u.group_id
                GROUP BY ug.group_id, ug.group_name, ug.group_description, ug.is_default, ug.created_date, ug.group_code
                ORDER BY ug.group_id
            ''')
            
            groups = []
            for row in cursor.fetchall():
                group = dict(row)
                group['created_date'] = _parse_db_datetime(group.get('created_date'))
                groups.append(group)
            return groups
    except sqlite3.Error as e:
        logging.error(f"Failed to get all user groups: {e}")
        return []


def get_user_group(group_id: int) -> dict | None:
    """Получить группу пользователей по ID"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM user_groups WHERE group_id = ?", (group_id,))
            result = cursor.fetchone()
            if not result:
                return None
            group = dict(result)
            group['created_date'] = _parse_db_datetime(group.get('created_date'))
            return group
    except sqlite3.Error as e:
        logging.error(f"Failed to get user group {group_id}: {e}")
        return None


def create_user_group(group_name: str, group_description: str = None, group_code: str = None) -> int | None:
    """Создать новую группу пользователей"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Если group_code не указан, генерируем его из group_name
            if not group_code:
                group_code = _generate_group_code(group_name)
                
                # Проверяем уникальность кода
                counter = 1
                original_code = group_code
                while True:
                    cursor.execute("SELECT COUNT(*) FROM user_groups WHERE group_code = ?", (group_code,))
                    if cursor.fetchone()[0] == 0:
                        break
                    group_code = f"{original_code}_{counter}"
                    counter += 1
            
            cursor.execute('''
                INSERT INTO user_groups (group_name, group_description, group_code)
                VALUES (?, ?, ?)
            ''', (group_name, group_description, group_code))
            
            group_id = cursor.lastrowid
            conn.commit()
            
            logging.info(f"Created new user group: {group_name} (ID: {group_id}, code: {group_code})")
            return group_id
    except sqlite3.IntegrityError:
        logging.warning(f"Group with name '{group_name}' or code '{group_code}' already exists")
        return None
    except sqlite3.Error as e:
        logging.error(f"Failed to create user group '{group_name}': {e}")
        return None


def update_user_group(group_id: int, group_name: str, group_description: str = None, group_code: str = None) -> bool:
    """Обновить группу пользователей"""
    try:
        logging.info(f"DEBUG: update_user_group called: group_id={group_id}, group_name={group_name}, group_code={group_code}")
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Если group_code не указан (None) или пустая строка, генерируем его из group_name
            logging.info(f"DEBUG: Checking group_code: '{group_code}', is None: {group_code is None}, strip: '{group_code.strip() if group_code else 'N/A'}'")
            if group_code is None or group_code.strip() == "":
                group_code = _generate_group_code(group_name)
                
                # Проверяем уникальность кода (исключая текущую группу)
                counter = 1
                original_code = group_code
                while True:
                    cursor.execute("SELECT COUNT(*) FROM user_groups WHERE group_code = ? AND group_id != ?", (group_code, group_id))
                    if cursor.fetchone()[0] == 0:
                        break
                    group_code = f"{original_code}_{counter}"
                    counter += 1
            else:
                # Если group_code указан, проверяем его уникальность
                group_code = group_code.strip()
                cursor.execute("SELECT COUNT(*) FROM user_groups WHERE group_code = ? AND group_id != ?", (group_code, group_id))
                if cursor.fetchone()[0] > 0:
                    logging.warning(f"Group code '{group_code}' already exists")
                    return False
            
            logging.info(f"DEBUG: Executing UPDATE with group_name={group_name}, group_description={group_description}, group_code={group_code}, group_id={group_id}")
            cursor.execute('''
                UPDATE user_groups 
                SET group_name = ?, group_description = ?, group_code = ?
                WHERE group_id = ?
            ''', (group_name, group_description, group_code, group_id))
            
            logging.info(f"DEBUG: UPDATE executed, rowcount={cursor.rowcount}")
            if cursor.rowcount > 0:
                conn.commit()
                logging.info(f"DEBUG: COMMIT executed successfully")
                # Проверяем, что изменения действительно сохранились
                cursor.execute("SELECT group_code FROM user_groups WHERE group_id = ?", (group_id,))
                actual_code = cursor.fetchone()[0]
                logging.info(f"DEBUG: After commit, actual code in DB: {actual_code}")
                logging.info(f"Updated user group {group_id}: {group_name} (code: {group_code})")
                return True
            else:
                logging.warning(f"User group {group_id} not found")
                return False
    except sqlite3.IntegrityError:
        logging.warning(f"Group with name '{group_name}' or code '{group_code}' already exists")
        return False
    except sqlite3.Error as e:
        logging.error(f"Failed to update user group {group_id}: {e}")
        return False


def delete_user_group(group_id: int) -> tuple[bool, int]:
    """Удалить группу пользователей. Возвращает (успех, количество_пользователей_переназначенных)"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Проверяем, что группа не является группой по умолчанию
            cursor.execute("SELECT is_default FROM user_groups WHERE group_id = ?", (group_id,))
            result = cursor.fetchone()
            
            if not result:
                logging.warning(f"User group {group_id} not found")
                return False, 0
                
            if result[0]:
                logging.warning(f"Cannot delete default group {group_id}")
                return False, 0
            
            # Считаем количество пользователей в группе
            cursor.execute("SELECT COUNT(*) FROM users WHERE group_id = ?", (group_id,))
            user_count = cursor.fetchone()[0]
            
            # Находим группу по умолчанию
            cursor.execute("SELECT group_id FROM user_groups WHERE is_default = 1 LIMIT 1")
            default_group = cursor.fetchone()
            
            if default_group:
                default_group_id = default_group[0]
                # Переназначаем всех пользователей на группу по умолчанию
                cursor.execute("UPDATE users SET group_id = ? WHERE group_id = ?", 
                             (default_group_id, group_id))
                logging.info(f"Reassigned {user_count} users to default group {default_group_id}")
            
            # Удаляем группу
            cursor.execute("DELETE FROM user_groups WHERE group_id = ?", (group_id,))
            conn.commit()
            
            logging.info(f"Deleted user group {group_id}, reassigned {user_count} users")
            return True, user_count
            
    except sqlite3.Error as e:
        logging.error(f"Failed to delete user group {group_id}: {e}")
        return False, 0


def get_user_group_by_name(group_name: str) -> dict | None:
    """Получить группу пользователей по названию"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM user_groups WHERE group_name = ?", (group_name,))
            result = cursor.fetchone()
            return dict(result) if result else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get user group by name '{group_name}': {e}")
        return None


def get_user_group_by_code(group_code: str) -> dict | None:
    """Получить группу пользователей по коду"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM user_groups WHERE group_code = ?", (group_code,))
            result = cursor.fetchone()
            return dict(result) if result else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get user group by code '{group_code}': {e}")
        return None


def get_default_user_group() -> dict | None:
    """Получить группу пользователей по умолчанию"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM user_groups WHERE is_default = 1 LIMIT 1")
            result = cursor.fetchone()
            return dict(result) if result else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get default user group: {e}")
        return None


def update_user_group_assignment(telegram_id: int, group_id: int) -> bool:
    """Назначить пользователя в группу"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Проверяем, что группа существует
            cursor.execute("SELECT group_id FROM user_groups WHERE group_id = ?", (group_id,))
            if not cursor.fetchone():
                logging.warning(f"Group {group_id} not found")
                return False
            
            cursor.execute("UPDATE users SET group_id = ? WHERE telegram_id = ?", 
                         (group_id, telegram_id))
            
            if cursor.rowcount > 0:
                conn.commit()
                logging.info(f"Assigned user {telegram_id} to group {group_id}")
                return True
            else:
                logging.warning(f"User {telegram_id} not found")
                return False
                
    except sqlite3.Error as e:
        logging.error(f"Failed to assign user {telegram_id} to group {group_id}: {e}")
        return False


def get_user_group_info(telegram_id: int) -> dict | None:
    """Получить информацию о группе пользователя"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT ug.group_id, ug.group_name, ug.group_description, ug.is_default, ug.group_code
                FROM users u
                JOIN user_groups ug ON u.group_id = ug.group_id
                WHERE u.telegram_id = ?
            ''', (telegram_id,))
            
            result = cursor.fetchone()
            return dict(result) if result else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get user group info for {telegram_id}: {e}")
        return None


def get_users_in_group(group_id: int) -> list[dict]:
    """Получить всех пользователей в группе"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT u.telegram_id, u.username, u.fullname, u.fio, u.email
                FROM users u
                WHERE u.group_id = ?
                ORDER BY u.registration_date
            ''', (group_id,))
            
            users = cursor.fetchall()
            return [dict(row) for row in users]
    except sqlite3.Error as e:
        logging.error(f"Failed to get users in group {group_id}: {e}")
        return []


def get_groups_statistics() -> dict:
    """Получить статистику по группам пользователей"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Общее количество групп
            cursor.execute("SELECT COUNT(*) FROM user_groups")
            total_groups = cursor.fetchone()[0]
            
            # Общее количество пользователей
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            # Количество пользователей в каждой группе
            cursor.execute('''
                SELECT ug.group_name, COUNT(u.telegram_id) as user_count
                FROM user_groups ug
                LEFT JOIN users u ON ug.group_id = u.group_id
                GROUP BY ug.group_id, ug.group_name
                ORDER BY user_count DESC
            ''')
            
            groups_stats = cursor.fetchall()
            
            return {
                'total_groups': total_groups,
                'total_users': total_users,
                'groups_stats': [{'group_name': row[0], 'user_count': row[1]} for row in groups_stats]
            }
    except sqlite3.Error as e:
        logging.error(f"Failed to get groups statistics: {e}")
        return {'total_groups': 0, 'total_users': 0, 'groups_stats': []}


def assign_user_to_group_by_code(telegram_id: int, group_code: str) -> bool:
    """Назначить пользователя в группу по коду группы"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Находим группу по коду
            cursor.execute("SELECT group_id FROM user_groups WHERE group_code = ?", (group_code,))
            group_result = cursor.fetchone()
            
            if not group_result:
                logging.warning(f"Group with code '{group_code}' not found")
                return False
            
            group_id = group_result[0]
            
            # Назначаем пользователя в группу
            cursor.execute("UPDATE users SET group_id = ? WHERE telegram_id = ?", 
                         (group_id, telegram_id))
            
            if cursor.rowcount > 0:
                conn.commit()
                logging.info(f"Assigned user {telegram_id} to group {group_id} (code: {group_code})")
                return True
            else:
                logging.warning(f"User {telegram_id} not found")
                return False
                
    except sqlite3.Error as e:
        logging.error(f"Failed to assign user {telegram_id} to group by code '{group_code}': {e}")
        return False


