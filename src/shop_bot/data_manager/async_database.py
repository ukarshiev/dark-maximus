# -*- coding: utf-8 -*-
"""
Асинхронный модуль для работы с базой данных с connection pooling
"""

import aiosqlite
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
import json
import bcrypt
from functools import lru_cache

logger = logging.getLogger(__name__)

# Определяем путь к базе данных в зависимости от окружения
import os
if os.path.exists("/app/project"):
    # Docker окружение
    PROJECT_ROOT = Path("/app/project")
else:
    # Локальная разработка
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

DB_FILE = PROJECT_ROOT / "users.db"

class AsyncDatabaseManager:
    """Асинхронный менеджер базы данных с connection pooling"""
    
    def __init__(self, db_path: str = None, max_connections: int = 10):
        self.db_path = db_path or str(DB_FILE)
        self.max_connections = max_connections
        self._connection_pool = asyncio.Queue(maxsize=max_connections)
        self._initialized = False
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """Инициализация connection pool"""
        if self._initialized:
            return
            
        async with self._lock:
            if self._initialized:
                return
                
            # Создаем соединения для пула
            for _ in range(self.max_connections):
                conn = await aiosqlite.connect(self.db_path)
                await conn.execute("PRAGMA journal_mode=WAL")
                await conn.execute("PRAGMA synchronous=NORMAL")
                await conn.execute("PRAGMA cache_size=10000")
                await conn.execute("PRAGMA temp_store=MEMORY")
                await self._connection_pool.put(conn)
            
            self._initialized = True
            logger.info(f"AsyncDatabaseManager initialized with {self.max_connections} connections")
    
    async def close(self):
        """Закрытие всех соединений"""
        while not self._connection_pool.empty():
            conn = await self._connection_pool.get()
            await conn.close()
        self._initialized = False
        logger.info("AsyncDatabaseManager closed")
    
    @asynccontextmanager
    async def get_connection(self):
        """Получение соединения из пула"""
        if not self._initialized:
            await self.initialize()
            
        conn = await self._connection_pool.get()
        try:
            yield conn
        finally:
            await self._connection_pool.put(conn)
    
    async def execute(self, query: str, params: tuple = ()) -> int:
        """Выполнение запроса с возвратом количества затронутых строк"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(query, params)
            await conn.commit()
            return cursor.rowcount
    
    async def fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Получение одной записи"""
        async with self.get_connection() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(query, params)
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Получение всех записей"""
        async with self.get_connection() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """Выполнение множественных запросов"""
        async with self.get_connection() as conn:
            cursor = await conn.executemany(query, params_list)
            await conn.commit()
            return cursor.rowcount

# Глобальный экземпляр менеджера
_db_manager: Optional[AsyncDatabaseManager] = None

async def get_db_manager() -> AsyncDatabaseManager:
    """Получение глобального экземпляра менеджера БД"""
    global _db_manager
    if _db_manager is None:
        _db_manager = AsyncDatabaseManager()
        await _db_manager.initialize()
    return _db_manager

# Кэшированные функции для часто используемых запросов
@lru_cache(maxsize=1000)
def _get_user_cache_key(user_id: int) -> str:
    """Ключ для кэша пользователя"""
    return f"user_{user_id}"

@lru_cache(maxsize=100)
def _get_setting_cache_key(setting_name: str) -> str:
    """Ключ для кэша настроек"""
    return f"setting_{setting_name}"

# Асинхронные версии основных функций
async def get_user_async(user_id: int) -> Optional[Dict[str, Any]]:
    """Асинхронное получение пользователя с кэшированием"""
    db = await get_db_manager()
    
    query = """
        SELECT telegram_id, username, total_spent, total_months, trial_used,
               agreed_to_terms, agreed_to_documents, registration_date,
               is_banned, referred_by, referral_balance, referral_balance_all,
               balance, subscription_status, key_id, connection_string,
               host_name, plan_name, price, email, created_date,
               trial_days_given, trial_reuses_count, user_id, fullname, fio
        FROM users 
        WHERE telegram_id = ?
    """
    
    return await db.fetchone(query, (user_id,))

async def get_setting_async(setting_name: str) -> Optional[str]:
    """Асинхронное получение настройки с кэшированием"""
    db = await get_db_manager()
    
    query = "SELECT value FROM bot_settings WHERE setting_name = ?"
    result = await db.fetchone(query, (setting_name,))
    return result['value'] if result else None

async def get_all_hosts_async() -> List[Dict[str, Any]]:
    """Асинхронное получение всех хостов"""
    db = await get_db_manager()
    
    query = """
        SELECT host_id, host_name, host_url, host_username, host_password,
               host_port, host_ssl, host_remark, host_status, host_order,
               host_created_date, host_updated_date
        FROM hosts 
        WHERE host_status = 'active'
        ORDER BY host_order ASC
    """
    
    return await db.fetchall(query)

async def get_plans_for_host_async(host_id: int) -> List[Dict[str, Any]]:
    """Асинхронное получение планов для хоста"""
    db = await get_db_manager()
    
    query = """
        SELECT plan_id, host_id, plan_name, price, days, hours, traffic_gb,
               plan_status, plan_order, plan_created_date, plan_updated_date,
               key_provision_mode
        FROM plans 
        WHERE host_id = ? AND plan_status = 'active'
        ORDER BY plan_order ASC
    """
    
    return await db.fetchall(query, (host_id,))

async def register_user_if_not_exists_async(
    user_id: int, 
    username: str, 
    referrer_id: Optional[int] = None,
    full_name: Optional[str] = None
) -> bool:
    """Асинхронная регистрация пользователя если не существует"""
    db = await get_db_manager()
    
    # Проверяем, существует ли пользователь
    existing_user = await get_user_async(user_id)
    if existing_user:
        return False
    
    # Создаем нового пользователя
    query = """
        INSERT INTO users (telegram_id, username, referred_by, fullname, fio, registration_date)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    
    now = datetime.now(timezone.utc)
    await db.execute(query, (user_id, username, referrer_id, full_name, full_name, now))
    return True

async def add_new_key_async(
    user_id: int,
    host_name: str,
    xui_client_uuid: str,
    key_email: str,
    expiry_date: datetime,
    protocol: str = 'vless',
    is_trial: bool = False,
    subscription: Optional[str] = None,
    subscription_link: Optional[str] = None,
    comment: Optional[str] = None
) -> int:
    """Асинхронное добавление нового ключа"""
    db = await get_db_manager()
    
    query = """
        INSERT INTO vpn_keys (
            user_id, host_name, xui_client_uuid, key_email, expiry_date,
            protocol, is_trial, subscription, subscription_link, comment
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    await db.execute(query, (
        user_id, host_name, xui_client_uuid, key_email, expiry_date,
        protocol, is_trial, subscription, subscription_link, comment
    ))
    
    # Получаем ID созданного ключа
    result = await db.fetchone("SELECT last_insert_rowid() as key_id")
    return result['key_id'] if result else 0

async def get_user_keys_async(user_id: int) -> List[Dict[str, Any]]:
    """Асинхронное получение ключей пользователя"""
    db = await get_db_manager()
    
    query = """
        SELECT key_id, user_id, host_name, xui_client_uuid, key_email,
               expiry_date, created_date, protocol, is_trial, subscription,
               subscription_link, comment, status, enabled, remaining_seconds,
               start_date, quota_remaining_bytes, quota_total_gb, traffic_down_bytes
        FROM vpn_keys 
        WHERE user_id = ?
        ORDER BY created_date DESC
    """
    
    return await db.fetchall(query, (user_id,))

async def update_user_stats_async(user_id: int, total_spent: float, total_months: int) -> bool:
    """Асинхронное обновление статистики пользователя"""
    db = await get_db_manager()
    
    query = """
        UPDATE users 
        SET total_spent = ?, total_months = ?
        WHERE telegram_id = ?
    """
    
    await db.execute(query, (total_spent, total_months, user_id))
    return True

async def log_transaction_async(
    username: str,
    transaction_id: Optional[str],
    payment_id: Optional[str],
    user_id: int,
    status: str,
    amount_rub: float,
    amount_currency: Optional[float],
    currency_name: Optional[str],
    payment_method: str,
    metadata: str
) -> bool:
    """Асинхронное логирование транзакции"""
    db = await get_db_manager()
    
    # Используем локальное время (UTC+3)
    local_tz = timezone(timedelta(hours=3))
    local_now = datetime.now(local_tz)
    
    query = """
        INSERT INTO transactions (
            username, transaction_id, payment_id, user_id, status,
            amount_rub, amount_currency, currency_name, payment_method,
            metadata, created_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    await db.execute(query, (
        username, transaction_id, payment_id, user_id, status,
        amount_rub, amount_currency, currency_name, payment_method,
        metadata, local_now
    ))
    return True

# Функция для инициализации асинхронной БД
async def initialize_async_db():
    """Инициализация асинхронной базы данных"""
    db = await get_db_manager()
    
    # Создаем таблицы если их нет
    async with db.get_connection() as conn:
        # Таблица пользователей
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                total_spent REAL DEFAULT 0,
                total_months INTEGER DEFAULT 0,
                trial_used INTEGER DEFAULT 0,
                agreed_to_terms INTEGER DEFAULT 0,
                agreed_to_documents INTEGER DEFAULT 0,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_banned INTEGER DEFAULT 0,
                referred_by INTEGER,
                referral_balance REAL DEFAULT 0,
                referral_balance_all REAL DEFAULT 0,
                balance REAL DEFAULT 0,
                subscription_status TEXT DEFAULT 'none',
                key_id INTEGER,
                connection_string TEXT,
                host_name TEXT,
                plan_name TEXT,
                price REAL,
                email TEXT,
                created_date TIMESTAMP,
                trial_days_given INTEGER DEFAULT 0,
                trial_reuses_count INTEGER DEFAULT 0,
                user_id INTEGER,
                fullname TEXT,
                fio TEXT
            )
        ''')
        
        # Таблица ключей VPN
        await conn.execute('''
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
                comment TEXT,
                status TEXT DEFAULT 'active',
                enabled INTEGER DEFAULT 1,
                remaining_seconds INTEGER,
                start_date TIMESTAMP,
                quota_remaining_bytes INTEGER,
                quota_total_gb REAL,
                traffic_down_bytes INTEGER
            )
        ''')
        
        # Таблица транзакций
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                payment_id TEXT,
                user_id INTEGER,
                status TEXT,
                amount_rub REAL,
                amount_currency REAL,
                currency_name TEXT,
                payment_method TEXT,
                metadata TEXT,
                created_date TIMESTAMP,
                transaction_hash TEXT,
                payment_link TEXT,
                yookassa_payment_id TEXT,
                rrn TEXT,
                authorization_code TEXT,
                payment_type TEXT
            )
        ''')
        
        # Таблица настроек
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS bot_settings (
                setting_name TEXT PRIMARY KEY,
                value TEXT,
                description TEXT,
                updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица хостов
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS hosts (
                host_id INTEGER PRIMARY KEY AUTOINCREMENT,
                host_name TEXT NOT NULL,
                host_url TEXT NOT NULL,
                host_username TEXT NOT NULL,
                host_password TEXT NOT NULL,
                host_port INTEGER DEFAULT 443,
                host_ssl INTEGER DEFAULT 1,
                host_remark TEXT,
                host_status TEXT DEFAULT 'active',
                host_order INTEGER DEFAULT 0,
                host_created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                host_updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица планов
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS plans (
                plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                host_id INTEGER NOT NULL,
                plan_name TEXT NOT NULL,
                price REAL NOT NULL,
                days INTEGER NOT NULL,
                hours INTEGER DEFAULT 0,
                traffic_gb REAL DEFAULT 0,
                plan_status TEXT DEFAULT 'active',
                plan_order INTEGER DEFAULT 0,
                plan_created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                plan_updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                key_provision_mode TEXT DEFAULT 'key',
                FOREIGN KEY (host_id) REFERENCES hosts (host_id)
            )
        ''')
        
        await conn.commit()
    
    logger.info("Async database initialized successfully")

# Функция для закрытия асинхронной БД
async def close_async_db():
    """Закрытие асинхронной базы данных"""
    global _db_manager
    if _db_manager:
        await _db_manager.close()
        _db_manager = None
    logger.info("Async database closed")
