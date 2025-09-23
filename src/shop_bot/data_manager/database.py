import sqlite3
from datetime import datetime
import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path("/app/project")
DB_FILE = PROJECT_ROOT / "users.db"

def initialize_db():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY, username TEXT, total_spent REAL DEFAULT 0,
                    total_months INTEGER DEFAULT 0, trial_used BOOLEAN DEFAULT 0,
                    agreed_to_terms BOOLEAN DEFAULT 0,
                    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_banned BOOLEAN DEFAULT 0,
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
                    is_trial INTEGER DEFAULT 0
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
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
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
            default_settings = {
                "panel_login": "admin",
                "panel_password": "admin",
                "about_text": None,
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
                "sbp_enabled": "false",
                "cryptobot_token": None,
                "heleket_merchant_id": None,
                "heleket_api_key": None,
                "domain": None,
                "ton_wallet_address": None,
                "tonapi_key": None,
                "auto_delete_orphans": "false",
                "hidden_mode": "0",
                "support_enabled": "true",
                "minimum_topup": "50",
            }
            run_migration()
            for key, value in default_settings.items():
                cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)", (key, value))
            conn.commit()
            logging.info("Database initialized successfully.")
    except sqlite3.Error as e:
        logging.error(f"Database error on initialization: {e}")

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
            
            if 'payment_id' in trans_columns and 'status' in trans_columns and 'username' in trans_columns:
                logging.info("The 'Transactions' table already has a new structure. Migration is not required.")
            else:
                backup_name = f"transactions_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                logging.warning(f"The old structure of the TRANSACTIONS table was discovered. I rename in '{backup_name}' ...")
                cursor.execute(f"ALTER TABLE transactions RENAME TO {backup_name}")
                
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
        logging.info("The table 'plans' has been successfully updated.")

        # Ensure xui_hosts.host_code exists and is populated
        try:
            cursor.execute("PRAGMA table_info(xui_hosts)")
            hosts_columns = [row[1] for row in cursor.fetchall()]
            if 'host_code' not in hosts_columns:
                cursor.execute("ALTER TABLE xui_hosts ADD COLUMN host_code TEXT")
            # Backfill empty codes with slugified host_name (lowercase, no spaces)
            cursor.execute("UPDATE xui_hosts SET host_code = LOWER(REPLACE(host_name, ' ', '')) WHERE COALESCE(host_code, '') = ''")
        except Exception:
            pass

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
                except Exception:
                    pass
            if 'marker_hours' not in notif_columns:
                try:
                    cursor.execute("ALTER TABLE notifications ADD COLUMN marker_hours INTEGER")
                except Exception:
                    pass

        conn.commit()
        conn.close()
        
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
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Добавляем поле transaction_hash если его нет
            try:
                cursor.execute("ALTER TABLE transactions ADD COLUMN transaction_hash TEXT")
            except sqlite3.OperationalError:
                # Поле уже существует
                pass

def create_host(name: str, url: str, user: str, passwd: str, inbound: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # host_code по умолчанию – slug от host_name
            default_code = (name or '').replace(' ', '').lower()
            cursor.execute(
                "INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",
                (name, url, user, passwd, inbound, default_code)
            )
            conn.commit()
            logging.info(f"Successfully created a new host: {name}")
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

def create_plan(host_name: str, plan_name: str, months: int, price: float, days: int = 0, traffic_gb: float = 0.0, hours: int = 0):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Ensure 'hours' column exists
            try:
                cursor.execute("ALTER TABLE plans ADD COLUMN hours INTEGER DEFAULT 0")
            except Exception:
                pass
            cursor.execute(
                "INSERT INTO plans (host_name, plan_name, months, price, days, traffic_gb, hours) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (host_name, plan_name, months, price, days, traffic_gb, hours)
            )
            conn.commit()
            logging.info(f"Created new plan '{plan_name}' for host '{host_name}'.")
    except sqlite3.Error as e:
        logging.error(f"Failed to create plan for host '{host_name}': {e}")

def get_plans_for_host(host_name: str) -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Ensure hours column exists
            try:
                cursor.execute("ALTER TABLE plans ADD COLUMN hours INTEGER DEFAULT 0")
            except Exception:
                pass
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

def update_plan(plan_id: int, plan_name: str, months: int, days: int, price: float, traffic_gb: float, hours: int = 0) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Ensure 'hours' column exists
            try:
                cursor.execute("ALTER TABLE plans ADD COLUMN hours INTEGER DEFAULT 0")
            except Exception:
                pass
            cursor.execute(
                "UPDATE plans SET plan_name = ?, months = ?, days = ?, hours = ?, price = ?, traffic_gb = ? WHERE plan_id = ?",
                (plan_name, months, days, hours, price, traffic_gb, plan_id)
            )
            conn.commit()
            logging.info(f"Updated plan id={plan_id}.")
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to update plan id {plan_id}: {e}")
        return False

def register_user_if_not_exists(telegram_id: int, username: str, referrer_id):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT telegram_id FROM users WHERE telegram_id = ?", (telegram_id,))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO users (telegram_id, username, registration_date, referred_by) VALUES (?, ?, ?, ?)",
                    (telegram_id, username, datetime.now(), referrer_id)
                )
            else:
                cursor.execute("UPDATE users SET username = ? WHERE telegram_id = ?", (username, telegram_id))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to register user {telegram_id}: {e}")

def add_to_referral_balance(user_id: int, amount: float):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET referral_balance = referral_balance + ? WHERE telegram_id = ?", (amount, user_id))
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

def set_terms_agreed(telegram_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET agreed_to_terms = 1 WHERE telegram_id = ?", (telegram_id,))
            conn.commit()
            logging.info(f"User {telegram_id} has agreed to terms.")
    except sqlite3.Error as e:
        logging.error(f"Failed to set terms agreed for user {telegram_id}: {e}")

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
            return cursor.fetchone()[0] or 0
    except sqlite3.Error as e:
        logging.error(f"Failed to get user count: {e}")
        return 0

def get_total_keys_count() -> int:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM vpn_keys")
            return cursor.fetchone()[0] or 0
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
            return cursor.fetchone()[0] or 0
    except sqlite3.Error as e:
        logging.error(f"Failed to get total notifications count: {e}")
        return 0

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

def create_pending_ton_transaction(payment_id: str, user_id: int, amount_rub: float, amount_ton: float, metadata: dict, payment_link: str = None) -> int:
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

def update_transaction_on_payment(payment_id: str, status: str, amount_rub: float, tx_hash: str = None, metadata: dict = None) -> bool:
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

def add_new_key(user_id: int, host_name: str, xui_client_uuid: str, key_email: str, expiry_timestamp_ms: int, connection_string: str = None, plan_name: str = None, price: float = None, protocol: str = 'vless', is_trial: int = 0):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            expiry_date = datetime.fromtimestamp(expiry_timestamp_ms / 1000)
            from datetime import timezone, timedelta
            local_tz = timezone(timedelta(hours=3))
            local_now = datetime.now(local_tz)
            # Сразу посчитаем remaining_seconds
            from datetime import timezone as _tz
            now_ms = int(datetime.now(_tz.utc).timestamp() * 1000)
            remaining_seconds = max(0, int((expiry_timestamp_ms - now_ms) / 1000))
            try:
                cursor.execute(
                    "INSERT INTO vpn_keys (user_id, host_name, xui_client_uuid, key_email, expiry_date, connection_string, plan_name, price, created_date, protocol, is_trial, remaining_seconds) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, host_name, xui_client_uuid, key_email, expiry_date, connection_string, plan_name, price, local_now, protocol, is_trial, remaining_seconds)
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
                    cursor.execute(
                        "UPDATE vpn_keys SET xui_client_uuid = ?, expiry_date = ?, remaining_seconds = ?, plan_name = COALESCE(?, plan_name), price = COALESCE(?, price), protocol = ?, is_trial = ? WHERE key_id = ?",
                        (xui_client_uuid, expiry_date, remaining_seconds, plan_name, price, protocol, is_trial, key_id)
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

def update_key_info(key_id: int, new_xui_uuid: str, new_expiry_ms: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            expiry_date = datetime.fromtimestamp(new_expiry_ms / 1000)
            # Пересчёт remaining_seconds
            from datetime import timezone as _tz
            now_ms = int(datetime.now(_tz.utc).timestamp() * 1000)
            remaining_seconds = max(0, int((new_expiry_ms - now_ms) / 1000))
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
                cursor.execute("UPDATE vpn_keys SET xui_client_uuid = ?, expiry_date = ? WHERE key_email = ?", (xui_client_data.id, expiry_date, key_email))
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

def get_all_users() -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Получаем пользователей с подсчетом уведомлений
            cursor.execute("""
                SELECT u.*, 
                       COALESCE(COUNT(n.notification_id), 0) as notifications_count
                FROM users u
                LEFT JOIN notifications n ON u.telegram_id = n.user_id
                GROUP BY u.telegram_id
                ORDER BY u.registration_date DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
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