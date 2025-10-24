# -*- coding: utf-8 -*-

"""

Модуль для работы с базой данных

"""



import sqlite3

from datetime import datetime

import logging

from pathlib import Path

import json

import bcrypt



logger = logging.getLogger(__name__)



# Определяем путь к базе данных в зависимости от окружения

import os

if os.path.exists("/app/project"):

    # Docker окружение

    PROJECT_ROOT = Path("/app/project")
    # В Docker используем data директорию для базы данных
    DB_FILE = PROJECT_ROOT / "data" / "users.db"

else:

    # Локальная разработка

    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
    DB_FILE = PROJECT_ROOT / "users.db"



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

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

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

                    UNIQUE (promo_id, bot)

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
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Хешируем пароль по умолчанию

            default_password = "admin"

            hashed_password = bcrypt.hashpw(default_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            

            default_settings = {

                "panel_login": "admin",

                "panel_password": hashed_password,

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

                "ton_manifest_url": "https://panel.dark-maximus.com",

                "ton_manifest_icon_url": "https://panel.dark-maximus.com/static/logo.png",

                "ton_manifest_terms_url": "https://panel.dark-maximus.com/terms",

                "ton_manifest_privacy_url": "https://panel.dark-maximus.com/privacy",

            }

            run_migration()

            

            # Создание индексов для оптимизации производительности

            create_database_indexes(cursor)

            # Создание группы "Гость" по умолчанию
            cursor.execute("INSERT OR IGNORE INTO user_groups (group_name, group_description, is_default) VALUES (?, ?, ?)", 
                         ("Гость", "Группа по умолчанию для всех пользователей", 1))

            

            # Доп. защита: не сеем дефолтные panel_login/panel_password, если таблица уже не пустая
            try:
                cursor.execute("SELECT COUNT(*) FROM bot_settings")
                settings_count = cursor.fetchone()[0]
            except Exception as e:
                logger.debug(f"Failed to count settings during initialization: {e}")
                settings_count = 0

            seed_sensitive_defaults = (settings_count == 0)

            for key, value in default_settings.items():

                if key in ("panel_login", "panel_password") and not seed_sensitive_defaults:
                    logging.info(f"Skip seeding default '{key}': bot_settings already initialized")
                    continue

                cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)", (key, value))

            conn.commit()

            logging.info("Database initialized successfully.")

    except sqlite3.Error as e:

        logging.error(f"Database error on initialization: {e}", exc_info=True)



def create_database_indexes(cursor):

    """Создает индексы для оптимизации производительности базы данных"""

    try:

        # Индексы для таблицы users

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_is_banned ON users(is_banned)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_registration_date ON users(registration_date)")

        

        # Индексы для таблицы vpn_keys

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vpn_keys_user_id ON vpn_keys(user_id)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vpn_keys_key_email ON vpn_keys(key_email)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vpn_keys_host_name ON vpn_keys(host_name)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vpn_keys_expiry_date ON vpn_keys(expiry_date)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vpn_keys_is_trial ON vpn_keys(is_trial)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vpn_keys_status ON vpn_keys(status)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vpn_keys_enabled ON vpn_keys(enabled)")

        

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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_groups_group_name ON user_groups(group_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_groups_is_default ON user_groups(is_default)")

        # Индекс для таблицы users по group_id
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_group_id ON users(group_id)")

        

        logging.info("Database indexes created successfully.")

    except sqlite3.Error as e:

        logging.error(f"Error creating database indexes: {e}", exc_info=True)



def run_migration():

    if not DB_FILE.exists():

        logging.error("Users.db database file was not found. There is nothing to migrate.")

        return



    logging.info(f"Starting the migration of the database: {DB_FILE}")



    try:

        conn = sqlite3.connect(DB_FILE)

        cursor = conn.cursor()



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

            # Находим ID группы "Гость" и назначаем её всем существующим пользователям
            cursor.execute("SELECT group_id FROM user_groups WHERE is_default = 1 LIMIT 1")
            default_group = cursor.fetchone()
            
            if default_group:
                default_group_id = default_group[0]
                cursor.execute("UPDATE users SET group_id = ? WHERE group_id IS NULL", (default_group_id,))
                logging.info(f" -> Все существующие пользователи назначены в группу с ID {default_group_id}")

        else:

            logging.info(" -> The column 'group_id' already exists.")

        

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

            

            if 'payment_id' in trans_columns and 'status' in trans_columns and 'username' in trans_columns:

                logging.info("The 'Transactions' table already has a new structure. Migration is not required.")

            else:

                backup_name = f"transactions_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}"

                logging.warning(f"The old structure of the TRANSACTIONS table was discovered. I rename in '{backup_name}' ...")

                # Используем параметризованный запрос для безопасности

                cursor.execute("ALTER TABLE transactions RENAME TO ?", (backup_name,))

                

                logging.info("I create a new table 'Transactions' with the correct structure ...")

                create_new_transactions_table(cursor)

                logging.info("The new table 'Transactions' has been successfully created. The old data is saved.")

        else:

            logging.info("TRANSACTIONS table was not found. I create a new one ...")

            create_new_transactions_table(cursor)

            logging.info("The new table 'Transactions' has been successfully created.")



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

                except Exception as e:
                    logger.debug(f"Migration error adding key_id column: {e}")

            if 'marker_hours' not in notif_columns:

                try:

                    cursor.execute("ALTER TABLE notifications ADD COLUMN marker_hours INTEGER")

                except Exception as e:
                    logger.debug(f"Migration error adding marker_hours column: {e}")

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
            # Проверяем, была ли выполнена миграция новых колонок promo_codes
            cursor.execute("SELECT migration_id FROM migration_history WHERE migration_id = 'promo_codes_new_columns'")
            migration_done = cursor.fetchone()
            
            if not migration_done:
                # Проверяем существующие колонки
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
                
                for column_name, column_definition in new_columns:
                    if column_name not in promo_columns:
                        try:
                            cursor.execute(f"ALTER TABLE promo_codes ADD COLUMN {column_name} {column_definition}")
                            logging.info(f" -> Added column '{column_name}' to promo_codes table")
                        except sqlite3.OperationalError as e:
                            logging.warning(f" -> Failed to add column '{column_name}': {e}")
                    else:
                        logging.info(f" -> Column '{column_name}' already exists in promo_codes table")
                
                # Отмечаем миграцию как выполненную
                cursor.execute("INSERT INTO migration_history (migration_id) VALUES ('promo_codes_new_columns')")
                logging.info(" -> Promo codes new columns migration completed")
            else:
                logging.info(" -> Migration 'promo_codes_new_columns' already applied, skipping")
                
        except Exception as e:
            logging.error(f" -> Error migrating promo_codes new columns: {e}")

        conn.commit()

        conn.close()

        

        # Миграция настроек бекапов
        logging.info("Migrating backup settings...")
        migrate_backup_settings()

        logging.info("--- The database is successfully completed! ---")



    except sqlite3.Error as e:

        logging.error(f"An error occurred during migration: {e}")



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

        with sqlite3.connect(DB_FILE) as conn:

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

            cursor.execute("SELECT * FROM xui_hosts WHERE host_name = ?", (host_name,))

            result = cursor.fetchone()

            return dict(result) if result else None

    except sqlite3.Error as e:

        logging.error(f"Error getting host '{host_name}': {e}")

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

        with sqlite3.connect(DB_FILE) as conn:

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

def get_global_domain() -> str:
    """Получить глобальный домен с fallback на старый параметр domain"""
    global_domain = get_setting("global_domain")
    if global_domain:
        return global_domain
    
    # Fallback на старый параметр domain
    domain = get_setting("domain")
    if domain:
        if not domain.startswith(('http://', 'https://')):
            domain = f"https://{domain}"
        return domain
    
    # Fallback на localhost для разработки
    return "https://localhost:8443"

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

            cursor.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)", (key, value))

            conn.commit()

            logging.info(f"Setting '{key}' updated.")

    except sqlite3.Error as e:

        logging.error(f"Failed to update setting '{key}': {e}")


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


def migrate_backup_settings():
    """Миграция настроек бекапов из bot_settings в backup_settings"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
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
            
            conn.commit()
            logging.info("Backup settings migration completed successfully")
            
    except sqlite3.Error as e:
        logging.error(f"Failed to migrate backup settings: {e}")



def create_plan(host_name: str, plan_name: str, months: int, price: float, days: int = 0, traffic_gb: float = 0.0, hours: int = 0, key_provision_mode: str = 'key', display_mode: str = 'all'):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            # Ensure 'hours' column exists
            try:
                cursor.execute("ALTER TABLE plans ADD COLUMN hours INTEGER DEFAULT 0")
            except Exception as e:
                logger.debug(f"Failed to add hours column to plans table: {e}")

            # Ensure 'key_provision_mode' column exists
            try:
                cursor.execute("ALTER TABLE plans ADD COLUMN key_provision_mode TEXT DEFAULT 'key'")
            except Exception as e:
                logger.debug(f"Failed to add key_provision_mode column to plans table: {e}")

            # Ensure 'display_mode' column exists
            try:
                cursor.execute("ALTER TABLE plans ADD COLUMN display_mode TEXT DEFAULT 'all'")
            except Exception as e:
                logger.debug(f"Failed to add display_mode column to plans table: {e}")

            cursor.execute(
                "INSERT INTO plans (host_name, plan_name, months, price, days, traffic_gb, hours, key_provision_mode, display_mode) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (host_name, plan_name, months, price, days, traffic_gb, hours, key_provision_mode, display_mode)
            )

            conn.commit()
            
            logging.info(f"Created new plan '{plan_name}' for host '{host_name}' with provision mode '{key_provision_mode}' and display mode '{display_mode}'.")

    except sqlite3.Error as e:
        logging.error(f"Failed to create plan for host '{host_name}': {e}")
        raise



def get_plans_for_host(host_name: str) -> list[dict]:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            # Ensure hours column exists

            try:

                cursor.execute("ALTER TABLE plans ADD COLUMN hours INTEGER DEFAULT 0")

            except Exception as e:
                logger.debug(f"Failed to add hours column to plans table in get_plans_for_host: {e}")

            # Ensure key_provision_mode column exists

            try:

                cursor.execute("ALTER TABLE plans ADD COLUMN key_provision_mode TEXT DEFAULT 'key'")

            except Exception as e:
                logger.debug(f"Failed to add key_provision_mode column to plans table in get_plans_for_host: {e}")

            # Ensure display_mode column exists

            try:

                cursor.execute("ALTER TABLE plans ADD COLUMN display_mode TEXT DEFAULT 'all'")

            except Exception as e:
                logger.debug(f"Failed to add display_mode column to plans table in get_plans_for_host: {e}")

            cursor.execute("SELECT * FROM plans WHERE host_name = ? ORDER BY months, days, hours", (host_name,))

            plans = cursor.fetchall()

            return [dict(plan) for plan in plans]

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

            return dict(plan) if plan else None

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



def update_plan(plan_id: int, plan_name: str, months: int, days: int, price: float, traffic_gb: float, hours: int = 0, key_provision_mode: str = 'key', display_mode: str = 'all') -> bool:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            # Ensure 'hours' column exists

            try:

                cursor.execute("ALTER TABLE plans ADD COLUMN hours INTEGER DEFAULT 0")

            except Exception:

                pass

            # Ensure 'key_provision_mode' column exists

            try:

                cursor.execute("ALTER TABLE plans ADD COLUMN key_provision_mode TEXT DEFAULT 'key'")

            except Exception as e:
                logger.debug(f"Failed to add key_provision_mode column to plans table in update_plan: {e}")

            # Ensure 'display_mode' column exists

            try:

                cursor.execute("ALTER TABLE plans ADD COLUMN display_mode TEXT DEFAULT 'all'")

            except Exception as e:
                logger.debug(f"Failed to add display_mode column to plans table in update_plan: {e}")

            cursor.execute(

                "UPDATE plans SET plan_name = ?, months = ?, days = ?, hours = ?, price = ?, traffic_gb = ?, key_provision_mode = ?, display_mode = ? WHERE plan_id = ?",

                (plan_name, months, days, hours, price, traffic_gb, key_provision_mode, display_mode, plan_id)

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


def filter_plans_by_display_mode(plans: list[dict], user_id: int) -> list[dict]:
    """
    Фильтрует список тарифов по режиму отображения для конкретного пользователя.
    
    Режимы отображения:
    - 'all': отображать всем (по умолчанию)
    - 'hidden_all': скрыть у всех пользователей
    - 'hidden_new': скрыть у новых пользователей (кто ни разу не использовал этот тариф)
    - 'hidden_old': скрыть у старых пользователей (кто уже использовал этот тариф ранее)
    """
    if not plans:
        return []
    
    filtered_plans = []
    
    for plan in plans:
        display_mode = plan.get('display_mode', 'all')
        plan_id = plan.get('plan_id')
        
        # Если режим 'all' - показываем всем
        if display_mode == 'all':
            filtered_plans.append(plan)
            continue
        
        # Если режим 'hidden_all' - скрываем от всех
        if display_mode == 'hidden_all':
            continue
        
        # Для режимов 'hidden_new' и 'hidden_old' проверяем историю использования
        if plan_id:
            has_used = has_user_used_plan(user_id, plan_id)
            
            # Если 'hidden_new' - скрываем от тех, кто НЕ использовал (новые)
            if display_mode == 'hidden_new' and not has_used:
                continue
            
            # Если 'hidden_old' - скрываем от тех, кто использовал (старые)
            if display_mode == 'hidden_old' and has_used:
                continue
        
        filtered_plans.append(plan)
    
    return filtered_plans


def _normalize_bot_value(bot: str) -> str:
    """Нормализует и валидирует значение бота.
    
    Args:
        bot: Название бота (должно быть 'shop')
        
    Returns:
        Нормализованное значение бота в нижнем регистре
        
    Raises:
        ValueError: Если бот не 'shop'
    """
    normalized = (bot or "").strip().lower()
    
    # Валидация: поддерживаем только 'shop' бота
    if normalized and normalized != 'shop':
        raise ValueError(f"Неподдерживаемый тип бота: '{bot}'. Допустимые значения: 'shop'")
    
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
            
            # Включаем WAL режим для лучшей производительности при конкурентном доступе
            cursor.execute("PRAGMA journal_mode=WAL")
            
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
            
            # Включаем WAL режим для лучшей производительности при конкурентном доступе
            cursor.execute("PRAGMA journal_mode=WAL")
            
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
                
                # Проверяем, не использовал ли уже пользователь этот промокод со статусом 'used'
                cursor.execute('''
                    SELECT COUNT(*) as usage_count
                    FROM promo_code_usage 
                    WHERE promo_id = ? AND user_id = ? AND bot = ? AND status = 'used'
                ''', (promo_id, user_id, bot_value))
                
                usage_result = cursor.fetchone()
                if usage_result and usage_result[0] > 0:
                    cursor.execute("ROLLBACK")
                    logging.warning(f"User {user_id} already used promo code {promo_id}")
                    return False
                
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

        logging.warning(f"Promo code usage already exists for promo_id={promo_id}, bot={bot_value}: {e}")

        return False

    except sqlite3.Error as e:

        logging.error(f"Failed to record promo code usage for promo_id={promo_id}: {e}")

        return False



def remove_promo_code_usage(promo_id: int, bot: str) -> bool:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()
            
            # Включаем WAL режим для лучшей производительности при конкурентном доступе
            cursor.execute("PRAGMA journal_mode=WAL")
            
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
            
            # Включаем WAL режим для лучшей производительности при конкурентном доступе
            cursor.execute("PRAGMA journal_mode=WAL")
            
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

        with sqlite3.connect(DB_FILE) as conn:

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

    except sqlite3.Error as e:

        logging.error(f"Failed to register user {telegram_id}: {e}")



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

        with sqlite3.connect(DB_FILE) as conn:

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

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (user_id,))

            row = cursor.fetchone()

            return float(row[0]) if row and row[0] is not None else 0.0

    except sqlite3.Error as e:

        logging.error(f"Failed to get balance for user {user_id}: {e}")

        return 0.0



def add_to_user_balance(user_id: int, amount: float) -> bool:

    try:

        if amount == 0:

            return True

        with sqlite3.connect(DB_FILE) as conn:

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



def create_pending_transaction(payment_id: str, user_id: int, amount_rub: float, metadata: dict) -> int:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            # Используем локальное время (UTC+3)

            from datetime import timezone, timedelta

            local_tz = timezone(timedelta(hours=3))  # UTC+3 для России

            local_now = datetime.now(local_tz)

            cursor.execute(

                "INSERT INTO transactions (payment_id, user_id, status, amount_rub, metadata, created_date) VALUES (?, ?, ?, ?, ?, ?)",

                (payment_id, user_id, 'pending', amount_rub, json.dumps(metadata), local_now)

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


def update_yookassa_transaction(payment_id: str, status: str, amount_rub: float, 
                              yookassa_payment_id: str | None = None, rrn: str | None = None, 
                              authorization_code: str | None = None, payment_type: str | None = None,
                              metadata: dict | None = None) -> bool:

    """Обновляет транзакцию YooKassa с дополнительными данными"""

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            

            # Обновляем основную информацию и дополнительные поля YooKassa

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



def find_and_complete_ton_transaction(payment_id: str, amount_ton: float, tx_hash: str = None) -> dict | None:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            

            # Ищем транзакцию по payment_id

            cursor.execute("SELECT * FROM transactions WHERE payment_id = ? AND status = 'pending'", (payment_id,))

            transaction = cursor.fetchone()

            

            # Если не найдено, попробуем найти по сумме (fallback)

            if not transaction:

                cursor.execute("SELECT * FROM transactions WHERE status = 'pending' AND payment_method = 'TON Connect' AND ABS(amount_currency - ?) < 0.01", (amount_ton,))

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

            cursor = conn.cursor()

            # Используем локальное время (UTC+3)

            from datetime import timezone, timedelta

            local_tz = timezone(timedelta(hours=3))  # UTC+3 для России

            local_now = datetime.now(local_tz)

            cursor.execute(

                """INSERT INTO transactions

                   (username, transaction_id, payment_id, user_id, status, amount_rub, amount_currency, currency_name, payment_method, metadata, created_date)

                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",

                (username, transaction_id, payment_id, user_id, status, amount_rub, amount_currency, currency_name, payment_method, metadata, local_now)

            )

            conn.commit()

    except sqlite3.Error as e:

        logging.error(f"Failed to log transaction for user {user_id}: {e}")



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

                

                # Преобразуем created_date в datetime объект

                if transaction_dict.get('created_date'):

                    try:

                        from datetime import datetime

                        if isinstance(transaction_dict['created_date'], str):

                            transaction_dict['created_date'] = datetime.fromisoformat(transaction_dict['created_date'].replace('Z', '+00:00'))

                    except (ValueError, TypeError):

                        transaction_dict['created_date'] = None

                

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



def add_new_key(user_id: int, host_name: str, xui_client_uuid: str, key_email: str, expiry_timestamp_ms: int, connection_string: str = None, plan_name: str = None, price: float = None, protocol: str = 'vless', is_trial: int = 0, subscription: str = None, subscription_link: str = None, telegram_chat_id: int = None, comment: str = None):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            from datetime import timezone, timedelta

            local_tz = timezone(timedelta(hours=3))
            
            # Используем UTC для совместимости с 3x-ui
            from datetime import timezone as _tz
            utc_tz = _tz.utc
            
            # Преобразуем expiry_timestamp_ms в UTC datetime
            expiry_date = datetime.fromtimestamp(expiry_timestamp_ms / 1000, tz=utc_tz)
            
            # Убираем timezone для совместимости с БД
            expiry_date = expiry_date.replace(tzinfo=None)

            local_now = datetime.now(local_tz)

            # Рассчитываем remaining_seconds используя UTC
            now_ms = int(datetime.now(utc_tz).timestamp() * 1000)
            remaining_seconds = max(0, int((expiry_timestamp_ms - now_ms) / 1000))

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

                cursor.execute(

                    "INSERT INTO vpn_keys (user_id, host_name, xui_client_uuid, key_email, expiry_date, connection_string, plan_name, price, created_date, protocol, is_trial, remaining_seconds, status, enabled, start_date, subscription, subscription_link, telegram_chat_id, comment) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",

                    (user_id, host_name, xui_client_uuid, key_email, expiry_date, connection_string, plan_name, price, local_now, protocol, is_trial, remaining_seconds, status, enabled, start_date, subscription, subscription_link, telegram_chat_id, comment)

                )

                new_key_id = cursor.lastrowid

                conn.commit()

                return new_key_id

            except sqlite3.IntegrityError:

                # Ключ с таким email уже есть — считаем это продлением и обновляем данные

                cursor.execute("SELECT key_id FROM vpn_keys WHERE key_email = ? LIMIT 1", (key_email,))

                row = cursor.fetchone()

                if row:

                    key_id = row[0]

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

                    return key_id

                else:

                    raise

    except sqlite3.Error as e:

        logging.error(f"Failed to add new key for user {user_id}: {e}")

        return None



def delete_key_by_email(email: str):

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

            cursor.execute("DELETE FROM vpn_keys WHERE key_email = ?", (email,))

            conn.commit()

    except sqlite3.Error as e:

        logging.error(f"Failed to delete key '{email}': {e}")



def get_user_keys(user_id: int):

    try:

        with sqlite3.connect(DB_FILE) as conn:

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

        with sqlite3.connect(DB_FILE) as conn:

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute("SELECT * FROM vpn_keys WHERE key_id = ?", (key_id,))

            key_data = cursor.fetchone()

            return dict(key_data) if key_data else None

    except sqlite3.Error as e:

        logging.error(f"Failed to get key by ID {key_id}: {e}")

        return None



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

            expiry_date = datetime.fromtimestamp(new_expiry_ms / 1000)

            # Пересчёт remaining_seconds

            from datetime import timezone as _tz

            now_ms = int(datetime.now(_tz.utc).timestamp() * 1000)

            remaining_seconds = max(0, int((new_expiry_ms - now_ms) / 1000))

            if subscription_link:
                cursor.execute("UPDATE vpn_keys SET xui_client_uuid = ?, expiry_date = ?, remaining_seconds = ?, subscription_link = ? WHERE key_id = ?", (new_xui_uuid, expiry_date, remaining_seconds, subscription_link, key_id))
            else:
                cursor.execute("UPDATE vpn_keys SET xui_client_uuid = ?, expiry_date = ?, remaining_seconds = ? WHERE key_id = ?", (new_xui_uuid, expiry_date, remaining_seconds, key_id))

            conn.commit()

    except sqlite3.Error as e:

        logging.error(f"Failed to update key {key_id}: {e}")



def get_next_key_number(user_id: int) -> int:

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

                expiry_date = datetime.fromtimestamp(xui_client_data.expiry_time / 1000)

                

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

                

                # Вычисляем remaining_seconds
                from datetime import timezone as _tz
                now_ms = int(datetime.now(_tz.utc).timestamp() * 1000)
                remaining_seconds = max(0, int((xui_client_data.expiry_time - now_ms) / 1000))
                
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

            transactions = [dict(row) for row in cursor.fetchall()]

    except sqlite3.Error as e:

        logging.error(f"Failed to get recent transactions: {e}")

    return transactions



def log_notification(user_id: int, username: str | None, notif_type: str, title: str, message: str, status: str = 'sent', meta: dict | None = None, key_id: int | None = None, marker_hours: int | None = None) -> int:

    try:

        with sqlite3.connect(DB_FILE) as conn:

            cursor = conn.cursor()

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

                try:

                    if isinstance(item.get('created_date'), str):

                        from datetime import datetime

                        item['created_date'] = datetime.fromisoformat(item['created_date'].replace('Z', '+00:00'))

                except Exception:

                    pass

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

            try:

                if isinstance(item.get('created_date'), str):

                    from datetime import datetime

                    item['created_date'] = datetime.fromisoformat(item['created_date'].replace('Z', '+00:00'))

            except Exception:

                pass

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

            cursor.execute("DELETE FROM vpn_keys WHERE user_id = ?", (user_id,))

            conn.commit()

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

                

                # Преобразуем created_date в datetime объект

                if key_dict.get('created_date'):

                    try:

                        from datetime import datetime

                        if isinstance(key_dict['created_date'], str):

                            key_dict['created_date'] = datetime.fromisoformat(key_dict['created_date'].replace('Z', '+00:00'))

                    except (ValueError, TypeError):

                        key_dict['created_date'] = None



                # Преобразуем expiry_date в datetime объект (если строка)

                if key_dict.get('expiry_date'):

                    try:

                        from datetime import datetime

                        if isinstance(key_dict['expiry_date'], str):

                            key_dict['expiry_date'] = datetime.fromisoformat(key_dict['expiry_date'].replace('Z', '+00:00'))

                    except (ValueError, TypeError):

                        # оставляем строку как есть, чтобы не падал шаблон

                        pass

                

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
                    from datetime import timezone as _tz
                    if isinstance(expiry_date_str, str):
                        expiry_date = datetime.fromisoformat(expiry_date_str)
                    else:
                        expiry_date = expiry_date_str
                    
                    # Убираем timezone info для совместимости
                    if expiry_date.tzinfo is not None:
                        expiry_date = expiry_date.replace(tzinfo=None)
                    
                    now = datetime.now()
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

        return {

            "url": settings.get("app_url", get_global_domain()),

            "name": settings.get("ton_manifest_name", "Dark Maximus Shop Bot"),

            "iconUrl": settings.get("ton_manifest_icon_url", f"{get_global_domain()}/static/logo.png"),

            "termsOfUseUrl": settings.get("ton_manifest_terms_url", f"{get_global_domain()}/terms"),

            "privacyPolicyUrl": settings.get("ton_manifest_privacy_url", f"{get_global_domain()}/privacy")

        }

    except Exception as e:

        logging.error(f"Failed to get Ton manifest settings: {e}")

        return {

            "url": get_global_domain(),

            "name": "Dark Maximus Shop Bot",

            "iconUrl": f"{get_global_domain()}/static/logo.png",

            "termsOfUseUrl": f"{get_global_domain()}/terms",

            "privacyPolicyUrl": f"{get_global_domain()}/privacy"

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
            
            # Включаем WAL режим для лучшей производительности при конкурентном доступе
            cursor.execute("PRAGMA journal_mode=WAL")
            
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
                    from datetime import datetime
                    try:
                        valid_until = datetime.fromisoformat(promo_dict['valid_until'])
                        if datetime.now() > valid_until:
                            cursor.execute("ROLLBACK")
                            return {'can_use': False, 'message': 'Срок действия промокода истек'}
                    except (ValueError, TypeError):
                        pass  # Если не удалось распарсить дату, пропускаем проверку
                
                # Проверяем срок сгорания промокода (burn_after)
                if promo_dict.get('burn_after_value') and promo_dict.get('burn_after_unit'):
                    from datetime import datetime, timedelta
                    try:
                        burn_value = int(promo_dict['burn_after_value'])
                        burn_unit = promo_dict['burn_after_unit']
                        
                        # Получаем дату создания промокода
                        created_at = datetime.fromisoformat(promo_dict['created_at'])
                        
                        # Вычисляем дату сгорания
                        if burn_unit == 'min':
                            burn_until = created_at + timedelta(minutes=burn_value)
                        elif burn_unit == 'hour':
                            burn_until = created_at + timedelta(hours=burn_value)
                        elif burn_unit == 'day':
                            burn_until = created_at + timedelta(days=burn_value)
                        else:
                            burn_until = None
                        
                        if burn_until and datetime.now() > burn_until:
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
                    expiry_date = datetime.fromisoformat(expiry_date_str)
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
                    COUNT(u.telegram_id) as user_count
                FROM user_groups ug
                LEFT JOIN users u ON ug.group_id = u.group_id
                GROUP BY ug.group_id, ug.group_name, ug.group_description, ug.is_default, ug.created_date
                ORDER BY ug.group_id
            ''')
            
            groups = cursor.fetchall()
            return [dict(row) for row in groups]
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
            return dict(result) if result else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get user group {group_id}: {e}")
        return None


def create_user_group(group_name: str, group_description: str = None) -> int | None:
    """Создать новую группу пользователей"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO user_groups (group_name, group_description)
                VALUES (?, ?)
            ''', (group_name, group_description))
            
            group_id = cursor.lastrowid
            conn.commit()
            
            logging.info(f"Created new user group: {group_name} (ID: {group_id})")
            return group_id
    except sqlite3.IntegrityError:
        logging.warning(f"Group with name '{group_name}' already exists")
        return None
    except sqlite3.Error as e:
        logging.error(f"Failed to create user group '{group_name}': {e}")
        return None


def update_user_group(group_id: int, group_name: str, group_description: str = None) -> bool:
    """Обновить группу пользователей"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE user_groups 
                SET group_name = ?, group_description = ?
                WHERE group_id = ?
            ''', (group_name, group_description, group_id))
            
            if cursor.rowcount > 0:
                conn.commit()
                logging.info(f"Updated user group {group_id}: {group_name}")
                return True
            else:
                logging.warning(f"User group {group_id} not found")
                return False
    except sqlite3.IntegrityError:
        logging.warning(f"Group with name '{group_name}' already exists")
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
                SELECT ug.group_id, ug.group_name, ug.group_description, ug.is_default
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


